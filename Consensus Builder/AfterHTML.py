# -*- coding: utf-8 -*-
"""AfterHTML — Consensus Builder: HTML 생성만 (병합 xlsx → CPI/GDP 대시보드)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = ["CPI consensus.py", "GDP consensus.py"]

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=False, label="Consensus Builder AfterHTML")
