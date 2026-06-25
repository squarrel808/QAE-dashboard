# -*- coding: utf-8 -*-
"""BeforeHTML — Consensus Builder: HTML 직전까지 (xlsb→xlsx 병합)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = ["merge_xlsb_to_xlsx.py"]   # 원본 데이터 병합 (CPI/GDP 가 읽을 xlsx 준비)

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="Consensus Builder BeforeHTML")
