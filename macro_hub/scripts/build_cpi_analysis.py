"""CPI analysis: audited Haver mappings, monthly rates and weight-based estimates.

Run --fetch after DLX login; without it, rebuild from the saved raw observations.
No missing observations are filled for price indices. Weights use last known values.
"""
import argparse
import csv
import json
import re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'macro_hub/public/data/cpi_analysis.json'
CACHE = ROOT / 'haver/haver-api_CPI/cpi_analysis_raw.json'
CONFIG = HERE / 'cpi_analysis_manifest.json'
META = ROOT / 'haver/haver-api_CPI/cpi_analysis_metadata.json'
GROUPS = {
 'US': ('USECON', 'iufbm iuhm iuapm iutrm iumm iuem iudcm iuom'),
 'Japan': ('JAPAN', 'jpcwf jpcwh jpcwfl jpcwfh jpcwcl jpcwmc jpcwtr jpcwed jpcwre jpcwmi'),
 'UK': ('UK', 'chzr chzs chzt chzu chzv chzw chzx chzy chzz cjuu cjuv cjuw'),
 'Germany': ('GERMANY', 'denpw001 denpw015 denpw021 denpw030 denpw047 denpw064 denpw074 denpw091 denpw096 denpw122 denpw126 denpw131'),
 'Australia': ('ANZ', 'aunmwff aunmwb aunmwa aunmww aunmwg aunmwm aunmwtc aunmwc aunmwr aunmwe aunmwfs'),
 'Canada': ('CANADA', 'cwf cww cwg cwa cwt cwhp cwrer cwba cwtb cwcb'),
}
OVERRIDES = {'denpw030':'denpc030','denpw047':'denpc047','chzv':'d7by','chzw':'d7bz','cwg':'v4c91067','cwba':'v4c91207','cwtb':'v4c91216','cwcb':'v1p24072','aunmwg':'aumpco'}

def core_manifest():
    rows=catalog('G10')
    chosen=[r for r in rows if re.fullmatch(r'h\d{3}pcx',r['code']) and r['frequency']=='M'
            and '(SA,' in r['descriptor'] and r['code'] not in ['h025pcx','h156pcx','h158pcx']]
    chosen += [r for r in rows if r['code'] in ['s111pcx','s156pcx','s158pcx','h196pcx']]
    out=[{'ticker':r['code']+'@G10','name':r['descriptor'].split(':')[0], 'descriptor':r['descriptor'],'frequency':r['frequency']} for r in chosen]
    au=next(r for r in catalog('ANZ') if r['code']=='auwpctmr')
    out.append({'ticker':'auwpctmr@ANZ','name':'Australia','descriptor':au['descriptor'],'frequency':'M'})
    return out

def label(s):
    return re.split(r'\s*\(', s.split(':')[-1])[0].strip()

def norm(s):
    return re.sub(r'[^a-z0-9]', '', label(s).lower().replace('&','and').replace('non-alcoholic','nonalcoholic'))

def catalog(db):
    folder = 'canada_catalog' if db == 'CANADA' else 'db_catalog'
    with (ROOT / 'haver/haver-api_PCA' / folder / f'catalog_{db}.csv').open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def make_manifest():
    result = {}
    for country, (db, weights) in GROUPS.items():
        rows = catalog(db)
        bycode = {r['code']:r for r in rows}
        indices = [r for r in rows if r['frequency']=='M' and re.search(r'CPI|Consumer Price',r['descriptor'],re.I)
                   and 'NSA' in r['descriptor'] and '=100' in r['descriptor']
                   and not re.search(r'DISC|CPIH|HICP|Y/Y|M/M|Contribution|Tokyo',r['descriptor'],re.I)]
        groups=[]
        for code in weights.split():
            w=bycode[code]
            candidates=[r for r in indices if norm(r['descriptor'])==norm(w['descriptor'])]
            candidates.sort(key=lambda r:(r['enddate'],r['startdate']),reverse=True)
            if code in OVERRIDES:candidates=[bycode[OVERRIDES[code]]]
            if country=='Japan':candidates=[bycode['jpcij'+code[4:]]]
            if not candidates:
                print('UNMATCHED',country,code,label(w['descriptor']),flush=True)
                continue
            p=candidates[0]
            groups.append({'name':label(w['descriptor']),'weight':code+'@'+db,'index':p['code']+'@'+db,
                           'descriptor':p['descriptor'],'weight_descriptor':w['descriptor'],
                           'divisor':10000 if '10000' in w['descriptor'] else 1000 if '1000' in w['descriptor'] else 100})
        result[country]={'database':db,'groups':groups}
        print(country,len(groups),[(g['weight'],g['index']) for g in groups],flush=True)
    CONFIG.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

def fetch(manifest):
    import Haver
    Haver.direct(1)
    old=json.loads(CACHE.read_text()) if CACHE.exists() else {}
    tickers=sorted({g[k] for v in manifest.values() for g in v['groups'] for k in ['index','weight']} | {c['ticker'] for c in core_manifest()})
    meta=Haver.metadata(tickers)
    if not isinstance(meta,pd.DataFrame):raise RuntimeError('Metadata lookup failed')
    frequencies={str(r['code']).lower()+'@'+str(r['database']).upper():r['frequency'] for _,r in meta.iterrows()}
    descriptors={str(r['code']).lower()+'@'+str(r['database']).upper():r['descriptor'] for _,r in meta.iterrows()}
    ordered=sorted(tickers,key=lambda t:(frequencies[t.lower().split('@')[0]+'@'+t.split('@')[1]],t))
    chunks=[]
    for freq in sorted(set(frequencies.values())):
        same=[t for t in ordered if frequencies[t.lower().split('@')[0]+'@'+t.split('@')[1]]==freq]
        chunks.extend(same[i:i+20] for i in range(0,len(same),20))
    for chunk in chunks:
        data=Haver.data(chunk,startdate='2017-01-01',dates=True,codeformat=['@','full'],underscore=False)
        if not isinstance(data,pd.DataFrame) or data.shape[1]!=len(chunk):
            raise RuntimeError(f'Haver incomplete batch: {chunk}')
        columns={str(c).lower():c for c in data.columns}
        for t in chunk:
            s=data[columns[t.lower()]].dropna()
            if s.empty: raise RuntimeError(f'No observations: {t}')
            old[t]={str(d)[:10]:float(v) for d,v in s.items()}
        print('Fetched',len(chunk),'series; frequency',frequencies[chunk[0].split('@')[0]+'@'+chunk[0].split('@')[1]],flush=True)
    CACHE.write_text(json.dumps(old),encoding='utf-8')
    META.write_text(json.dumps(descriptors,ensure_ascii=False),encoding='utf-8')

def monthly(values):
    s=pd.Series(values,dtype=float)
    s.index=pd.to_datetime(s.index).to_period('M')
    return s.groupby(level=0).last()

def build(manifest):
    raw=json.loads(CACHE.read_text())
    descriptions=json.loads(META.read_text(encoding='utf-8')) if META.exists() else {}
    dates=pd.period_range('2017-01',pd.Timestamp.today().to_period('M'),freq='M')
    countries={}
    for country,v in manifest.items():
        groups=[]
        for g in v['groups']:
            p=monthly(raw[g['index']]).reindex(dates)
            w=monthly(raw[g['weight']]).reindex(dates).ffill()/g['divisor']*100
            records=[]
            for lag,key in [(1,'mom'),(12,'yoy')]:
                rate=(p/p.shift(lag)-1)*100
                # Explicit estimate: reference-period basket weight times rate.
                contribution=rate*w.shift(lag)/100
                records.append((key,rate,contribution))
            obs=[]
            for i,d in enumerate(dates):
                if pd.isna(p.iloc[i]):continue
                row={'date':str(d),'weight':w.iloc[i]}
                for key,rate,contrib in records:
                    row[key]=rate.iloc[i];row[key+'_contribution']=contrib.iloc[i]
                    row[key+'_weight']=w.shift(1 if key=='mom' else 12).iloc[i]
                obs.append({k:(None if pd.isna(x) else round(float(x),5)) if k!='date' else x for k,x in row.items()})
            groups.append({**g,'descriptor':descriptions.get(g['index'],g['descriptor']),'observations':obs})
        countries[country]={'groups':groups,'method':'estimate'}
    payload={'generated':pd.Timestamp.now().isoformat(),'countries':countries,
             'method':'기준시점 가중치 × 항목 상승률 / 100. YoY는 12개월 전, MoM은 1개월 전 가중치. 공식 기여도가 아닌 근사치이며 연쇄지수·가중치 개편으로 총 CPI와 차이가 날 수 있습니다.'}
    cores=[]
    for c in core_manifest():
        p=monthly(raw[c['ticker']]).reindex(dates)
        yoy=(p/p.shift(12)-1)*100
        avg=p.rolling(3,min_periods=3).mean()
        momentum=((avg/avg.shift(3))**4-1)*100 if c['frequency']=='M' else p*float('nan')
        observations=[]
        for d in dates:
            if pd.isna(p[d]):continue
            observations.append({'date':str(d),'yoy':None if pd.isna(yoy[d]) else round(yoy[d],3),
                                 'momentum':None if pd.isna(momentum[d]) else round(momentum[d],3)})
        cores.append({**c,'descriptor':descriptions.get(c['ticker'],c['descriptor']),'observations':observations})
    payload['core']=cores
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',action='store_true');parser.add_argument('--fetch',action='store_true');args=parser.parse_args()
    if args.manifest:make_manifest()
    else:
        manifest=json.loads(CONFIG.read_text(encoding='utf-8'))
        if args.fetch:fetch(manifest)
        build(manifest)

