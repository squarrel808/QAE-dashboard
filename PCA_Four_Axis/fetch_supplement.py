"""Read-only housing GDP components and France capital-goods production from Haver."""
import json,warnings
from pathlib import Path
from collections import defaultdict
import pandas as pd
import Haver
BASE=Path(__file__).resolve().parent
WANTED=['usecon:fr', 'usecon:gdp', 'uk:l62tq', 'uk:l62rq', 'france:frsnfih', 'germany:desnfir', 'germany:desnfgr', 'g10:s156nprr', 'japan:n9dfd', 'anz:ausnfr', 'france:frsdk']

def main():
 warnings.filterwarnings('ignore');Haver.direct('force');meta={};values=[];errors=[]
 groups=defaultdict(list)
 for p in WANTED:groups[p.split(':')[0]].append(p)
 def tick(p):d,c=p.split(':');return c+'@'+d
 for db,ps in groups.items():
  try:
   m=Haver.metadata([tick(p) for p in ps])
   for r in json.loads(m.to_json(orient='records',date_format='iso')):meta[r['database'].lower()+':'+r['code'].lower()]=r
  except Exception as e:errors.append(str(e))
 groups=defaultdict(list)
 for p,m in meta.items():groups[(p.split(':')[0],m['frequency'])].append(p)
 for (db,f),ps in groups.items():
  try:
   d=Haver.data([tick(p) for p in ps],startdate='1995-01-01',dates=True)
   for p in ps:
    cols=[c for c in d if str(c).lower()==p.split(':')[1]]
    if len(cols)!=1:raise ValueError(p)
    s=pd.to_numeric(d[cols[0]],errors='coerce').dropna()
    values.extend(dict(pk=p,date=str(t)[:10],value=float(v)) for t,v in s.items())
  except Exception as e:errors.append(str(e))
  print(db,f,len(ps),flush=True)
 (BASE/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
 pd.DataFrame(values).to_csv(BASE/'values.csv',index=False,encoding='utf-8-sig')
 (BASE/'fetch_log.json').write_text(json.dumps({'checked_kst':pd.Timestamp.now(tz='Asia/Seoul').isoformat(),'requested':WANTED,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8')
 print('DONE',len(meta),'errors',errors)
 if errors:raise RuntimeError('Supplementary GDP data download incomplete; see fetch_log.json')
if __name__=='__main__':main()
