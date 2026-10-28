"""Read-only Snowflake PMI snapshot and self-contained dashboard. No publication."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT.parent / 'outputs/pmi_preview/snapshot.json'
COUNTRIES = [('EA','유로존',[2212,2213,2214]),('DE','독일',[2623,2624,2625]),
 ('FR','프랑스',[2413,2414,2415]),('AU','호주',[315,316,317]),
 ('CA','캐나다',[733,734,735]),('US','미국',[6883,6884,6885]),
 ('JP','일본',[3843,3844,3845]),('CN','중국',[1377,1558,1559])]
DETAILS = {
 '미국 ISM 제조업': [(6588,'종합'),(6587,'신규주문'),(6589,'생산'),(6583,'고용'),(6590,'공급자 배송'),(6585,'재고'),(6606,'가격'),(6581,'수주잔고'),(6586,'신규 수출주문'),(6584,'수입'),(6582,'고객재고')],
 '미국 ISM 서비스업': [(6604,'종합'),(6595,'사업활동'),(6601,'신규주문'),(6596,'고용'),(6605,'공급자 배송'),(6603,'가격'),(6598,'재고'),(6602,'수주잔고'),(6600,'신규 수출주문'),(6597,'수입'),(6599,'재고심리')],
 '중국 공식 제조업': [(1546,'종합'),(1552,'신규주문'),(1553,'생산'),(1548,'고용'),(1550,'투입가격'),(1551,'신규 수출주문'),(1547,'수주잔고'),(1549,'수입'),(1554,'구매량'),(1555,'완제품 재고'),(1556,'원자재 재고'),(1557,'공급자 배송')],
 '캐나다 Ivey': [(705,'종합'),(704,'고용'),(706,'재고'),(707,'가격'),(703,'공급자 배송')],
}

def phase(x,y):
    if x < 0: return '회복' if y > x else '수축 후기'
    if y < 0: return '수축 초기'
    return '확장 초기' if y >= x else '확장 후기'

def cycle(points):
    out=[]
    for i in range(11,len(points)):
        w=points[i-11:i+1]
        months=[int(p[0][:4])*12+int(p[0][5:7]) for p in w]
        if any(b-a!=1 for a,b in zip(months,months[1:])): continue
        x=sum(p[1] for p in w)/12-50
        y=sum(p[1] for p in w[-3:])/3-50
        out.append([points[i][0],round(x,4),round(y,4),phase(x,y)])
    return out

def fetch():
    import snowflake.connector
    now=datetime.now(ZoneInfo('Asia/Seoul'))
    ids=sorted({i for _,_,items in COUNTRIES for i in items}|{i for items in DETAILS.values() for i,_ in items})
    with snowflake.connector.connect(connection_name='A8240085925871-NPS_TAA',role='TAA_DEVELOPER',warehouse='TAA_DEV_WH',database='TAA_DB_DEV',authenticator='SNOWFLAKE_JWT',private_key_file=str(Path.home()/'.snowflake/keys/jeyhyuk_snowflake_rsa_key.p8'),session_parameters={'QUERY_TAG':'QAE_PMI_READ_ONLY','STATEMENT_TIMEOUT_IN_SECONDS':120}) as conn:
        with conn.cursor(snowflake.connector.DictCursor) as cur:
            cur.execute('SELECT SERIES_ID,DISPLAY_NAME,SOURCE_PROVIDER,SOURCE_SERIES_KEY,FREQUENCY FROM TAA_DB_DEV.CORE.SERIES_MASTER WHERE IS_ACTIVE=TRUE AND SERIES_ID IN ('+','.join(map(str,ids))+')')
            meta={r['SERIES_ID']:r for r in cur.fetchall()}
            cur.execute('SELECT SERIES_ID,DATE,VALUE,SOURCE_COLLECTED_AT FROM TAA_DB_DEV.CORE.FACT_TIME_SERIES WHERE SERIES_ID IN ('+','.join(map(str,ids))+') AND DATE >= %s AND DATE <= LAST_DAY(TO_DATE(%s)) ORDER BY SERIES_ID,DATE',('2021-01-01',now.date()))
            rows=cur.fetchall()
    series={str(i):{'meta':meta[i],'points':[]} for i in ids}
    for r in rows:
        # Monthly dates represent reference periods, not release dates.
        if r['SOURCE_COLLECTED_AT'] and r['SOURCE_COLLECTED_AT']>now: continue
        v=r['VALUE']
        if v is None or not math.isfinite(v) or not 0<=v<=100: raise ValueError('Invalid PMI observation')
        series[str(r['SERIES_ID'])]['points'].append([r['DATE'].strftime('%Y-%m'),float(v)])
    for s in series.values():
        assert s['meta']['FREQUENCY']=='M' and s['points'], 'Missing monthly series'
        assert len({p[0] for p in s['points']})==len(s['points']), 'Duplicate month'
    return {'retrievedAt':now.isoformat(timespec='seconds'),'source':'Snowflake / Haver','series':series}

def build(data):
    countries=[]
    for code,name,ids in COUNTRIES:
        s={k:data['series'][str(i)] for k,i in zip(['composite','manufacturing','services'],ids)}
        countries.append({'code':code,'name':name,**s,'cycle':cycle(s['composite']['points'])})
    result={'retrievedAt':data['retrievedAt'],'source':data['source'],'countries':countries,
      'details':[{ 'name':name,'items':[{'name':label,**data['series'][str(i)]} for i,label in items]} for name,items in DETAILS.items()]}
    payload=json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    html=(ROOT/'scripts/pmi_template.html').read_text(encoding='utf-8').replace('__PAYLOAD__',payload)
    target=ROOT/'public/embeds/pmi.html'
    tmp=target.with_suffix('.tmp');tmp.write_text(html,encoding='utf-8');tmp.replace(target)
    print('Built:',target)
    for c in countries: print(c['name'],[(k,c[k]['points'][-1]) for k in ['composite','manufacturing','services']])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--from-cache',action='store_true');a=p.parse_args()
    if a.from_cache: data=json.loads(CACHE.read_text(encoding='utf-8'))
    else:
        data=fetch();CACHE.parent.mkdir(parents=True,exist_ok=True)
        CACHE.write_text(json.dumps(data,ensure_ascii=False,default=str),encoding='utf-8')
    build(data)

