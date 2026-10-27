"""Read-only Citi refresh. Publish only a complete, validated snapshot."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import subprocess
import pandas as pd
from portal_link import add_portal_link

ROOT = Path(__file__).resolve().parent
KST = ZoneInfo('Asia/Seoul')
ORDER = ['GLB','G10','EM','APAC','BRIC','US','EA','GB','JP','CN','CA','AU','NZ']
EXCLUDED = {'LATAM','CEEMEA','SE','NO','CH'}
REGIONS = {'EA','GLB','G10','EM','APAC','BRIC','LATAM','CEEMEA'}
GEO = {'United States':('US','미국'),'Euro Area':('EA','유로존'),'United Kingdom':('GB','영국'),
       'Japan':('JP','일본'),'Canada':('CA','캐나다'),'Australia':('AU','호주'),'New Zealand':('NZ','뉴질랜드'),
       'Switzerland':('CH','스위스'),'Sweden':('SE','스웨덴'),'Norway':('NO','노르웨이'),
       'Global':('GLB','전세계'),'Developed Markets':('G10','G10'),'Emerging Markets':('EM','신흥국'),
       'Latin America':('LATAM','남미'),'CEEMEA':('CEEMEA','CEEMEA')}

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def atomic_text(path, text):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)

def fetch(config, now):
    if config.get('source') != 'snowflake':
        raise ValueError('Only Snowflake is permitted; legacy snapshots are not accepted')
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT) as temp:
        output=Path(temp)/'snowflake_snapshot.json'
        subprocess.run([config['snowflake_python'], '-X', 'utf8', str(ROOT/'fetch_snowflake.py'),
                        '--config', str(ROOT/'config.json'), '--output', str(output),
                        '--retrieved-at', now.isoformat(timespec='seconds')],check=True)
        return json.loads(output.read_text(encoding='utf-8'))

def prepare(raw, now):
    if raw.get('source')!='snowflake':
        raise ValueError('Legacy PostgreSQL snapshots cannot be published; fetch Snowflake first')
    result={'source':'snowflake','sourceTable':raw['source_table'],'retrievedAt':raw['retrieved_at'],'builtAt':now.isoformat(timespec='seconds'),
            'startDate':raw['start_date'],'cutoff':raw['cutoff'],'economic':[],'inflation':[]}
    for kind in ('economic','inflation'):
        seen=set()
        for source in raw[kind]:
            m=source['meta']; f=pd.DataFrame(source['rows'])
            f['date']=pd.to_datetime(f.date,errors='raise').dt.normalize()
            f['value']=pd.to_numeric(f.value,errors='raise')
            if f.value.isna().any() or not f.value.map(math.isfinite).all(): raise ValueError('Missing/nonfinite source value')
            if f.date.max().date()>pd.Timestamp(raw['cutoff']).date(): raise ValueError('Future observation')
            duplicates=int(f.duplicated('date').sum())
            if kind=='economic':
                f['update_dt']=pd.to_datetime(f.update_dt,errors='raise',utc=True,format='mixed')
                if f.duplicated(['date','update_dt']).any(): raise ValueError('Ambiguous duplicate versions')
                f=f.sort_values(['date','update_dt']).drop_duplicates('date',keep='last')
                weekends=int(f.date.dt.dayofweek.ge(5).sum())
                f=f[f.date.dt.dayofweek.lt(5)].copy().sort_values('date')
                f['display']=f.value.rolling(5,min_periods=5).mean()
                code,name=m['country_ISO'],m['country_KOR']; ticker=m['ticker']
            else:
                if duplicates: raise ValueError('Duplicate monthly observations')
                f=f.sort_values('date'); f['display']=f.value
                if f.date.dt.to_period('M').duplicated().any(): raise ValueError('More than one observation per month')
                code,name=m['country_ISO'],m['country_KOR']
                ticker=m['ticker_pk']; weekends=0
            if code in seen or len(f)<5: raise ValueError('Duplicate country or insufficient observations')
            seen.add(code)
            points=[[r.date.strftime('%Y-%m-%d'),float(r.value),None if pd.isna(r.display) else round(float(r.display),6)] for r in f.itertuples()]
            result[kind].append({'id':code,'name':name,'region':code in REGIONS,'ticker':ticker,'points':points,
                'source':'snowflake','seriesId':m['series_id'],'provider':m['provider'],
                'last':points[-1][0],'first':points[0][0],'rows':len(f),'weekendsExcluded':weekends,'duplicatesResolved':duplicates,
                'lagDays':(now.date()-f.date.max().date()).days})
        result[kind] = [s for s in result[kind] if s['id'] not in EXCLUDED]
        result[kind].sort(key=lambda s:(ORDER.index(s['id']) if s['id'] in ORDER else 999,s['name']))
    return result

def render(data):
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    return (ROOT/'template.html').read_text(encoding='utf-8').replace('__SURPRISE_DATA__',payload)

def run(args):
    now=datetime.now(KST)
    run_dir=ROOT/'runs'/now.strftime('%Y%m%d_%H%M%S_%f')
    run_dir.mkdir(parents=True)
    if args.from_cache:
        latest=json.loads((ROOT/'latest.json').read_text(encoding='utf-8'))
        raw=json.loads((ROOT/latest['snapshot']).read_text(encoding='utf-8'))
    else:
        raw=fetch(json.loads((ROOT/'config.json').read_text(encoding='utf-8')),now)
    data=prepare(raw,now)
    page=render(data)
    assert '__SURPRISE_DATA__' not in page and 'id="economic"' in page and 'id="inflation"' in page
    write_json(run_dir/'snapshot.json',raw); write_json(run_dir/'data.json',data)
    (run_dir/'index.html').write_text(page,encoding='utf-8')
    manifest={'source':'snowflake','source_table':raw['source_table'],'retrieved_at':raw['retrieved_at'],'built_at':data['builtAt'],'mode':'cached-render' if args.from_cache else 'snowflake-refresh',
              'snapshot':str((run_dir/'snapshot.json').relative_to(ROOT)).replace(os.sep,'/'),
              'report':str((run_dir/'index.html').relative_to(ROOT)).replace(os.sep,'/'),
              'sha256':hashlib.sha256(page.encode()).hexdigest(),
              'series':{k:len(data[k]) for k in ('economic','inflation')},
              'latest_observation':{k:max(s['last'] for s in data[k]) for k in ('economic','inflation')}}
    write_json(run_dir/'manifest.json',manifest)
    # Atomic page publication keeps the previous usable page on any retrieval/validation failure.
    if (ROOT/'index.html').exists(): (run_dir/'previous_index.html').write_bytes((ROOT/'index.html').read_bytes())
    atomic_text(ROOT/'index.html',page)
    atomic_text(ROOT/'latest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    portal=ROOT.parent/'index.html'
    if portal.exists():
        old=portal.read_text(encoding='utf-8')
        new=add_portal_link(old,portal)
        if new!=old:
            (run_dir/'portal_before.html').write_text(old,encoding='utf-8')
            if portal.read_text(encoding='utf-8')!=old: raise RuntimeError('Portal changed concurrently; report saved, menu not edited')
            atomic_text(portal,new)
    web_sync=ROOT.parents[2]/'macro_hub/scripts/sync_surprise.mjs'
    if web_sync.exists():
        subprocess.run(['node',str(web_sync)],check=True)
    write_json(ROOT/'last_attempt.json',{'status':'success',**manifest})
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    if args.open:
        import webbrowser
        webbrowser.open((ROOT/'index.html').as_uri())

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-cache',action='store_true',help='Rebuild saved snapshot without calling the API; original retrieval time retained')
    p.add_argument('--open',action='store_true')
    args=p.parse_args()
    lock=ROOT/'update.lock'
    try:
        handle=lock.open('x')
    except FileExistsError:
        print('Another refresh is running. If interrupted, inspect and remove update.lock.',file=sys.stderr); sys.exit(1)
    try:
        handle.write(str(os.getpid())); handle.flush()
        run(args)
    except Exception as exc:
        # Avoid printing request details or credentials in exception strings.
        message=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__
        write_json(ROOT/'last_attempt.json',{'status':'failed','at':datetime.now(KST).isoformat(),'error':message})
        print('Refresh failed: '+message,file=sys.stderr)
        sys.exit(1)
    finally:
        handle.close(); lock.unlink()
