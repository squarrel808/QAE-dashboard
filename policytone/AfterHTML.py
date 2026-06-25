# -*- coding: utf-8 -*-
"""AfterHTML — policytone: HTML 생성만 (stance_index.csv → 대시보드)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = ["hawkdove_dashboard.py"]

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="policytone AfterHTML")
