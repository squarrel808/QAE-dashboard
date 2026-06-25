# -*- coding: utf-8 -*-
"""
AfterHTML_master.py — 모든 폴더의 HTML 생성 + 통합 대시보드 갱신
=========================================================================
각 폴더의 AfterHTML.py 를 순서대로 호출(각 대시보드 HTML 생성) 후,
마지막에 build_master.py(부품)로 통합 master_dashboard.html 을 다시 찍는다.
한 폴더가 실패해도 다음 폴더는 계속 진행한다.

※ 융합형 폴더(gs_api·PCA·경제지표)는 AfterHTML 이 데이터까지 다시 당긴다.
   (데이터+HTML 이 한 스크립트라 분리 불가 — 기존 로직 보존)

데이터부터 새로 당기려면 먼저:  python BeforeHTML_master.py
HTML만 다시 그리려면:        python AfterHTML_master.py
"""
import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from _runner import run_paths

FOLDERS = ["경제지표가져오기", "PCA", "gs_api", "Consensus Builder", "policytone"]

if __name__ == "__main__":
    print("=== AfterHTML_master 시작 (모든 폴더 HTML 생성) ===")
    paths = [os.path.join(ROOT, f, "AfterHTML.py") for f in FOLDERS]
    paths.append(os.path.join(ROOT, "build_master.py"))   # 통합 대시보드 재생성(부품)
    run_paths(paths, stop_on_fail=False, label="AfterHTML_master")
    print("\n완료 → master_dashboard.html 을 브라우저에서 새로고침하세요.")
