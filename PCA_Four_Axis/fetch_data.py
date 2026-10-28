"""Independent, read-only Haver retrieval; never touches BlackRock workbooks."""
import argparse,json,warnings,sys
from pathlib import Path
from collections import defaultdict
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent;BASE=Path(__file__).resolve().parent/'source'
BASE.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'PCA_GDP_Weighted'))
def main():
    import Haver
    p=argparse.ArgumentParser();p.add_argument('--start',default='1995-01-01');args=p.parse_args()
    review=json.loads((ROOT/'outputs/gdp_expenditure_review/report_data.json').read_text(encoding='utf-8'))
    from build_model import ALIAS,INVESTMENT_SCOPE
    dependencies={p for r in review['rows'] if r['monthly_available'] for p in r['dependencies']}
    replacements={ALIAS[p] for p in dependencies if p in ALIAS and not ALIAS[p].startswith('derived:')}
    investment={pk for r in INVESTMENT_SCOPE['countries'].values() for pk in [r['total'],r['gdp'],*r['government']]}
    wanted=sorted(dependencies|replacements|investment|{r['pk'] for r in review['anchors']})
    warnings.filterwarnings('ignore');Haver.direct('force');meta={};values=[];errors=[]
    groups=defaultdict(list)
    for pk in wanted:groups[pk.split(':')[0]].append(pk)
    def tick(pk):db,c=pk.split(':');return c+'@'+db
    for db,ps in groups.items():
        for i in range(0,len(ps),25):
            chunk=ps[i:i+25]
            try:
                m=Haver.metadata([tick(x) for x in chunk])
                for r in json.loads(m.to_json(orient='records',date_format='iso')):meta[r['database'].lower()+':'+r['code'].lower()]=r
            except Exception as e:errors.append({'phase':'metadata','codes':chunk,'error':str(e)})
        print('metadata',db,len(ps),flush=True)
    groups=defaultdict(list)
    for pk,m in meta.items():groups[(pk.split(':')[0],m['frequency'])].append(pk)
    for (db,freq),ps in groups.items():
        for i in range(0,len(ps),20):
            chunk=ps[i:i+20]
            try:
                d=Haver.data([tick(x) for x in chunk],startdate=args.start,dates=True)
                for pk in chunk:
                    cols=[c for c in d if str(c).lower()==pk.split(':')[1]]
                    if len(cols)!=1:errors.append({'phase':'column','pk':pk});continue
                    s=pd.to_numeric(d[cols[0]],errors='coerce').dropna()
                    values.extend({'pk':pk,'date':str(t)[:10],'value':float(v)} for t,v in s.items())
            except Exception as e:errors.append({'phase':'data','codes':chunk,'error':str(e)})
        print('values',db,freq,len(ps),flush=True)
    pd.DataFrame(values).to_csv(BASE/'raw_haver.csv',index=False,encoding='utf-8-sig')
    (BASE/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (BASE/'fetch_log.json').write_text(json.dumps({'date_kst':pd.Timestamp.now(tz='Asia/Seoul').isoformat(),'start':args.start,'requested':len(wanted),'metadata':len(meta),'observations':len(values),'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    print('DONE',len(wanted),len(meta),len(values),'errors',len(errors),flush=True)
    if errors:raise SystemExit('Read fetch_log.json before calculating; failed retrievals are not silently replaced with stale cache.')
if __name__=='__main__':main()
