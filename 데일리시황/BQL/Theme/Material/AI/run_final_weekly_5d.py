from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BQL=HERE.parents[2]
def main():
    p=argparse.ArgumentParser(description='섹터 + AI 주초 5D HTML 일괄 생성'); p.add_argument('--update-raw',action='store_true'); p.add_argument('--open',action='store_true',dest='open_report'); a=p.parse_args()
    if a.update_raw: subprocess.run(['powershell.exe','-ExecutionPolicy','Bypass','-File',str(BQL/'Rawfile'/'update_all.ps1')],check=True)
    scripts=[BQL/'Theme'/'Material'/'Sector_Industry'/'Reports'/'run_sector_report_weekly_5d.py',HERE/'run_ai_report_weekly_5d.py']
    for script in scripts: subprocess.run([sys.executable,str(script)]+(['--open'] if a.open_report else []),check=True)
if __name__=='__main__': main()
