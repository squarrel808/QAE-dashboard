# -*- coding: utf-8 -*-
"""AfterHTML — 경제지표가져오기: HTML 생성.
weco_dashboard.py 가 블벅경제지표/weco_global.xlsx 를 읽어 dashboard.html 생성.
(구 셀레니움 스크래퍼 scraper_with_dashboard.py 는 2026-07-20부로 교체됨)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = ["weco_dashboard.py"]

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="경제지표 AfterHTML")
