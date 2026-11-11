import json,pathlib,os,re,datetime as dt
import pandas as pd
from dotenv import load_dotenv
from gs_quant.session import GsSession,Environment
from gs_quant.data import Dataset
root=pathlib.Path(__file__).resolve().parents[2]
p=root/'macro_hub/public/embeds/theme.html'
s=p.read_text(encoding='utf-8'); tail=s.split('const DATA=',1)[1]; d,n=json.JSONDecoder().raw_decode(tail)
load_dotenv(root/'gs_api/.env'); GsSession.use(Environment.PROD,os.environ['GS_CLIENT_ID'],os.environ['GS_CLIENT_SECRET'],('read_product_data',))
series=d['series']; codes=[k for k in series if not k.startswith('LS_')]; updated=set()
end=dt.date.today()
start=dt.date.fromisoformat(min(series[k]['dates'][-1] for k in codes))-dt.timedelta(days=7)
for dataset in ['CUSTOM_BASKETS_LEVELS','PAIR_BASKETS_LEVELS']:
    df=Dataset(dataset).get_data(start,end,bbid=codes)
    if df.empty: continue
    if 'date' not in df: df=df.reset_index()
    for code,sub in df.groupby('bbid'):
        if code not in series: continue
        v=series[code]; pts=dict(zip(v['dates'],v['levels']))
        for _,r in sub.iterrows():
            if pd.notna(r['closePrice']): pts[str(pd.Timestamp(r['date']).date())]=float(r['closePrice'])
        v['dates']=sorted(pts);v['levels']=[pts[x] for x in v['dates']]
        if v['dates'][-1]>=(end-dt.timedelta(days=7)).isoformat(): updated.add(code)
print('updated',len(updated),'of',len(codes),flush=True)
d['stale_series'] = sorted(set(codes)-updated)
for code,v in series.items():
    if not code.startswith('LS_'):continue
    _,a,b=code.split('_');aa=dict(zip(series[a]['dates'],series[a]['levels']));bb=dict(zip(series[b]['dates'],series[b]['levels']));dates=sorted(set(aa)&set(bb)); oldlast=v['dates'][-1]; level=v['levels'][-1]
    for i,date in enumerate(dates):
        if date<=oldlast:continue
        prev=dates[i-1];level*=1+aa[date]/aa[prev]-bb[date]/bb[prev];v['dates'].append(date);v['levels'].append(level)
d['end']=max(v['dates'][-1] for v in series.values())
for panel in d['panels']:panel['price_end']=min(series[c]['dates'][-1] for c in panel['codes'])
stamp=f"갱신: {end.isoformat()} · {len(updated)}/{len(codes)}개 원계열 최근 자료 확인 · {len(codes)-len(updated)}개 지연. Source: Goldman Sachs Marquee API"
s=re.sub(r'(?:갱신: [^<]*?\. )?Source: Goldman Sachs Marquee API',lambda _:stamp,s)
head,rest=s.split('const DATA=',1)
_,payload_end=json.JSONDecoder().raw_decode(rest)
output=head+'const DATA='+json.dumps(d,ensure_ascii=False)+rest[payload_end:]
tmp=p.with_suffix('.tmp');tmp.write_text(output,encoding='utf-8');tmp.replace(p)
print('Saved',d['end'])

