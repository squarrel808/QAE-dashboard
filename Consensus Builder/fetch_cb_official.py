import json,Haver,pandas as pd
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
root=Path(__file__).resolve().parent;spec=json.loads((root/'cb_official_spec.json').read_text(encoding='utf-8'));Haver.direct('force');result={'retrievedAt':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'countries':{}}
for country,items in spec.items():
 out=[]
 for name,ticker,freq,kind in items:
  try:
   d=Haver.data([ticker],startdate='2021-01-01',dates=True)
   if not isinstance(d,pd.DataFrame) or d.empty:raise ValueError('No observations')
   s=pd.to_numeric(d.iloc[:,0],errors='coerce');s.index=pd.to_datetime(s.index);s=s.dropna().sort_index();s=s[s.index<=pd.Timestamp.now().to_period('M').end_time]
   if kind=='index':
    s=s.groupby(s.index.to_period('M')).last();s=s.reindex(pd.period_range(s.index.min(),s.index.max(),freq='M'));s=(s/s.shift(12)-1)*100;s.index=s.index.to_timestamp('M')
   points=[[str(dt.date()),round(float(v),4)] for dt,v in s.dropna().items()]
   if not points:raise ValueError('No annual observations')
   out.append({'name':name.replace('公式','공식'),'ticker':ticker,'frequency':freq,'kind':kind,'points':points,'source':'Haver API','status':'ok'})
   print(country,ticker,points[-1],flush=True)
  except Exception as e:out.append({'name':name,'ticker':ticker,'frequency':freq,'points':[],'status':'unavailable','error':str(e)[:150]});print('FAILED',ticker,str(e)[:100],flush=True)
 result['countries'][country]=out
 (Path(__file__).resolve().parent/'cb_official_snapshot.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
