"""One local command for the entire Haver -> model -> validated dashboard pipeline."""
import argparse,json,subprocess,sys,shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
BASE=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cached',action='store_true',help='Rebuild from saved Haver data without network retrieval')
    args=parser.parse_args()
    now=datetime.now(ZoneInfo('Asia/Seoul'));logs=BASE/'logs';logs.mkdir(exist_ok=True)
    logfile=logs/(now.strftime('%Y%m%d_%H%M%S')+'.log')
    steps=[] if args.cached else ['fetch_data.py','fetch_supplement.py','fetch_blackrock.py']
    steps+=['build.py','test_model.py','build_dashboard.py']
    commands=[(step,[sys.executable,'-X','utf8',str(BASE/step)]) for step in steps]
    node=shutil.which('node')
    if not node:raise RuntimeError('Node.js is required to synchronize the dashboard snapshot')
    commands.append(('sync_dashboard',[node,str(BASE.parent/'macro_hub/scripts/sync_gdp_weighted.mjs')]))
    status={'started_kst':now.isoformat(),'cached':args.cached,'log':str(logfile),'steps':[],'success':False}
    try:
        with logfile.open('w',encoding='utf8') as log:
            for name,command in commands:
                print('Running',name,flush=True);log.write('\n### '+name+'\n');log.flush()
                result=subprocess.run(command,cwd=BASE,stdout=log,stderr=subprocess.STDOUT)
                status['steps'].append({'name':name,'returncode':result.returncode})
                if result.returncode:raise RuntimeError(f'{name} failed; see {logfile}')
        status['success']=True
        print('Growth PCA updated; annual weights preserved; dashboard snapshot synchronized.',flush=True)
    finally:
        status['finished_kst']=datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
        (BASE/'update_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
