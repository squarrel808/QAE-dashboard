# -*- coding: utf-8 -*-
"""AfterHTML — gs api: HTML 생성 (GS API 호출 포함, 융합형).
build_cai_map.py / build_pairbaskets.py 가 데이터 호출 + HTML 생성을 함께 수행."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = ["build_cai_map.py", "build_pairbaskets.py"]

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=False, label="gs api AfterHTML")
