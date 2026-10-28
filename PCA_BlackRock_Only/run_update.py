"""Repeatable Haver -> BlackRock-only PCA -> validated published snapshot."""
import argparse,json,subprocess,sys,shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

BASE=Path(__file__).resolve().parent
SOURCE=BASE.parent/'PCA_Four_Axis'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cached',action='store_true',help='Use the saved Haver source data')
    args=p.parse_args()
    now=datetime.now(ZoneInfo('Asia/Seoul'))
    logs=BASE/'logs';logs.mkdir(exist_ok=True)
    logfile=logs/(now.strftime('%Y%m%d_%H%M%S')+'.log')
    scripts=[] if args.cached else [SOURCE/s for s in ['fetch_data.py','fetch_supplement.py','fetch_blackrock.py']]
    scripts += [BASE/s for s in ['build.py','test_model.py','build_dashboard.py']]
    commands=[(s.name,[sys.executable,'-X','utf8',str(s)]) for s in scripts]
    node=shutil.which('node')
    if not node:raise RuntimeError('Node.js is required for dashboard synchronization')
    commands.append(('sync_pca_iii',[node,str(BASE.parent/'macro_hub/scripts/sync_pca_iii.mjs')]))
    status={'started_kst':now.isoformat(),'cached':args.cached,'log':str(logfile),'steps':[],'success':False}
    try:
        with logfile.open('w',encoding='utf8') as log:
            for name,command in commands:
                print('Running',name,flush=True);log.write('\n### '+name+'\n');log.flush()
                result=subprocess.run(command,cwd=BASE,stdout=log,stderr=subprocess.STDOUT)
                status['steps'].append({'name':name,'returncode':result.returncode})
                if result.returncode:raise RuntimeError(f'{name} failed; see {logfile}')
        status['success']=True
        print('PCA III updated and synchronized. PCA and PCA II outputs preserved.',flush=True)
    finally:
        status['finished_kst']=datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
        (BASE/'update_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
