# -*- coding: utf-8 -*-
"""
BeforeHTML_master.py — 모든 폴더의 'HTML 직전까지' 작업을 한 번에 실행
=========================================================================
각 폴더의 BeforeHTML.py 를 순서대로 호출(데이터 수집·가공·채점 등).
한 폴더가 실패해도 다음 폴더는 계속 진행한다.

실행:  python BeforeHTML_master.py
그다음:  python AfterHTML_master.py   (HTML 생성·통합)
"""
import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from _runner import run_paths

# 데이터 단계를 가진 폴더 (순서대로)
FOLDERS = ["경제지표가져오기", "PCA", "gs_api", "Consensus Builder", "policytone"]

if __name__ == "__main__":
    print("=== BeforeHTML_master 시작 (모든 폴더 데이터 단계) ===")
    paths = [os.path.join(ROOT, f, "BeforeHTML.py") for f in FOLDERS]
    run_paths(paths, stop_on_fail=False, label="BeforeHTML_master")
    print("\n다음: python AfterHTML_master.py  (HTML 생성·통합)")
