"""Read-only Haver retrieval for reviewed BlackRock reference candidates.

Quarterly/stale/unavailable reference rows remain in the audit, not model inputs.
Network errors are fatal: a failed download must never silently shrink the model.
"""
import json,warnings
from pathlib import Path
from collections import defaultdict
import pandas as pd
import Haver
B=Path(__file__).resolve().parent
def main():
 warnings.filterwarnings('ignore');Haver.direct('force')
 ref=json.loads((B/'blackrock_reference.json').read_text(encoding='utf8'))
 wanted=sorted({p for r in ref for p in ([r['pk']] if r['pk'] else [])+([r['fallback_pk']] if r.get('fallback_pk') else [])+r.get('dependencies',[])})
 groups=defaultdict(list);meta={};values=[];errors=[]
 def tick(p):db,c=p.split(':');return c+'@'+db
 for p in wanted:groups[p.split(':')[0]].append(p)
 for db,ps in groups.items():
  for i in range(0,len(ps),20):
   batch=ps[i:i+20]
   try:
    m=Haver.metadata([tick(p) for p in batch])
    for r in json.loads(m.to_json(orient='records',date_format='iso')):meta[r['database'].lower()+':'+r['code'].lower()]=r
   except Exception as e:errors.append(dict(stage='metadata',codes=batch,error=str(e)))
  print('metadata',db,len(ps),flush=True)
 groups=defaultdict(list)
 for p,m in meta.items():
  if m['frequency']=='M':groups[p.split(':')[0]].append(p)
 for db,ps in groups.items():
  for i in range(0,len(ps),20):
   batch=ps[i:i+20]
   try:
    d=Haver.data([tick(p) for p in batch],startdate='1995-01-01',dates=True)
    for p in batch:
     col=[c for c in d if str(c).lower()==p.split(':')[1]]
     if len(col)!=1:raise ValueError('Missing data column '+p)
     s=pd.to_numeric(d[col[0]],errors='coerce').dropna()
     values.extend(dict(pk=p,date=str(t)[:10],value=float(v)) for t,v in s.items())
   except Exception as e:errors.append(dict(stage='data',codes=batch,error=str(e)))
  print('data',db,len(ps),flush=True)
 folder=B/'blackrock_source';folder.mkdir(exist_ok=True)
 log={'checked_kst':pd.Timestamp.now(tz='Asia/Seoul').isoformat(),'requested':len(wanted),'metadata':len(meta),'observations':len(values),'missing':sorted(set(wanted)-set(meta)),'errors':errors}
 (folder/'fetch_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf8')
 if errors or log['missing']:raise RuntimeError('BlackRock candidate retrieval incomplete; see blackrock_source/fetch_log.json')
 (folder/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
 pd.DataFrame(values).to_csv(folder/'values.csv',index=False,encoding='utf-8-sig')
 print(log,flush=True)
if __name__=='__main__':main()
