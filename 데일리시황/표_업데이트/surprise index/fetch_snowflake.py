"""Read canonical active Citi series from Snowflake; no DDL/DML or old-DB fallback."""
import argparse
from collections import defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import re
import snowflake.connector

NAMES={'US':'미국','EA':'유로존','GB':'영국','JP':'일본','CN':'중국','CA':'캐나다','AU':'호주','NZ':'뉴질랜드',
       'CH':'스위스','SE':'스웨덴','NO':'노르웨이','GLB':'전세계','G10':'G10','EM':'신흥국','APAC':'아시아퍼시픽',
       'BRIC':'BRIC','LATAM':'남미','CEEMEA':'CEEMEA'}

def collect(config, retrieved_at):
    if config.get('source')!='snowflake': raise ValueError('Only Snowflake is permitted')
    database=config['database']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',database): raise ValueError('Invalid database identifier')
    cutoff=datetime.fromisoformat(retrieved_at).date()
    start=date.fromisoformat(config['start_date'])
    bundle={'source':'snowflake','source_table':database+'.CORE.FACT_TIME_SERIES',
            'retrieved_at':retrieved_at,'start_date':str(start),'cutoff':str(cutoff),'economic':[],'inflation':[]}
    with snowflake.connector.connect(connection_name=config['connection_name'],role=config['role'],
          warehouse=config['warehouse'],database=database,authenticator='SNOWFLAKE_JWT',
          private_key_file=str(Path(config['private_key_file']).expanduser()),
          session_parameters={'QUERY_TAG':'QAE_CITI_SURPRISE_READ_ONLY','STATEMENT_TIMEOUT_IN_SECONDS':120}) as conn:
        with conn.cursor(snowflake.connector.DictCursor) as cur:
            cur.execute(f"""SELECT SERIES_ID,DISPLAY_NAME,SOURCE_PROVIDER,SOURCE_SERIES_KEY,FREQUENCY,GEOGRAPHY_CODE
                FROM {database}.CORE.SERIES_MASTER WHERE IS_ACTIVE=TRUE AND
                ((DISPLAY_NAME ILIKE '%Citi%Economic Surprise Index%' AND FREQUENCY='D') OR
                 (DISPLAY_NAME ILIKE '%Citi%Inflation Surprise Index%' AND SOURCE_PROVIDER='HAVER' AND FREQUENCY='M'))
                ORDER BY SERIES_ID""")
            masters=cur.fetchall()
            if not masters: raise ValueError('No active Citi series in Snowflake')
            ids=[int(m['SERIES_ID']) for m in masters]
            cur.execute(f"""SELECT SERIES_ID,DATE,VALUE,CORE_UPDATED_AT,COUNT(*) OVER (PARTITION BY SERIES_ID) AS EXPECTED_N
                FROM {database}.CORE.FACT_TIME_SERIES WHERE SERIES_ID IN ({','.join(map(str,ids))})
                AND DATE >= %s AND DATE <= %s ORDER BY SERIES_ID,DATE""",(start,cutoff))
            by_id=defaultdict(list)
            for row in cur.fetchall(): by_id[int(row['SERIES_ID'])].append(row)
    countries={'economic':set(),'inflation':set()}
    for m in masters:
        kind='economic' if m['FREQUENCY']=='D' else 'inflation'
        code=m['GEOGRAPHY_CODE']
        # SERIES_MASTER display names were shortened in November 2026.
        # Preserve the reviewed Haver series identities rather than matching
        # geographic words that disappeared from the new display labels.
        source_key=m['SOURCE_SERIES_KEY'] or ''
        if kind=='inflation' and int(m['SERIES_ID'])==36 and source_key.endswith('N505VCIS@G10'): code='APAC'
        if kind=='inflation' and int(m['SERIES_ID'])==1775 and source_key.endswith('N110VCIS@G10'): code='G10'
        if code=='DM' and 'G10' in m['DISPLAY_NAME']: code='G10'
        if code not in NAMES or code in countries[kind]: raise ValueError('Unknown or duplicate country: '+str(code))
        countries[kind].add(code)
        records=by_id[int(m['SERIES_ID'])]
        if not records or len(records)!=int(records[0]['EXPECTED_N']): raise ValueError('Incomplete series: '+str(m['SERIES_ID']))
        if len({r['DATE'] for r in records})!=len(records): raise ValueError('Duplicate CORE dates')
        last=max(r['DATE'] for r in records)
        if (cutoff-last).days>config['max_'+kind+'_age_days']:
            raise ValueError(f'Stale Snowflake series: {code} {kind} latest={last}')
        meta={'country_ISO':code,'country_KOR':NAMES[code],'ticker':m['SOURCE_SERIES_KEY'],
              'ticker_pk':m['SOURCE_SERIES_KEY'],'descriptor':m['DISPLAY_NAME'],'frequency':m['FREQUENCY'],
              'series_id':int(m['SERIES_ID']),'provider':m['SOURCE_PROVIDER']}
        rows=[{'date':str(r['DATE']),'value':r['VALUE'],'update_dt':r['CORE_UPDATED_AT'].isoformat() if r['CORE_UPDATED_AT'] else str(r['DATE'])} for r in records]
        bundle[kind].append({'meta':meta,'rows':rows})
        print(f'{kind}: {NAMES[code]} / Snowflake series {m["SERIES_ID"]} / {len(rows)} / latest {last}',flush=True)
    if countries['economic']!=set(NAMES) or countries['inflation']!=set(NAMES)-{'CN','BRIC'}:
        raise ValueError('Country coverage changed; inspect before replacing published report')
    return bundle

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--retrieved-at',required=True)
    args=p.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8'))
    result=collect(config,args.retrieved_at)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
