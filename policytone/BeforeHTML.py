# -*- coding: utf-8 -*-
"""BeforeHTML — policytone: HTML 직전까지 (수집 → 채점/집계)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # 루트(QAE-dashboard)
from _runner import run_paths

SCRIPTS = ["collect.py", "score.py"]   # 웹 수집 → stance_index.csv 까지

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="policytone BeforeHTML")
