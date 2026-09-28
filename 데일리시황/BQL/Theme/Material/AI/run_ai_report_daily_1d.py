from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(); p.add_argument('--open',action='store_true',dest='open_report'); a=p.parse_args()
    env=os.environ.copy(); env['PYTHONUTF8']='1'
    r=subprocess.run([sys.executable,str(HERE/'build_ai_value_chain_html.py'),'--primary','1D'],check=True,capture_output=True,text=True,encoding='utf-8',env=env)
    data=json.loads(r.stdout.strip().splitlines()[-1])
    for x in data['outputs']:
        print(x)
        if a.open_report: os.startfile(x)
if __name__=='__main__': main()
