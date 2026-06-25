# -*- coding: utf-8 -*-
"""AfterHTML — 경제지표가져오기: HTML 생성 (Selenium 스크래핑 포함, 융합형).
scraper_with_dashboard.py 가 데이터 스크래핑 + dashboard.html 생성을 함께 수행."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = ["scraper_with_dashboard.py"]

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="경제지표 AfterHTML")
