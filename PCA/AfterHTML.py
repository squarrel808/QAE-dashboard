# -*- coding: utf-8 -*-
"""AfterHTML — PCA: HTML 생성 (데이터 처리 포함, 융합형).
pca_gdp.py 가 PCA→GDP 프록시→LEI 계산 + pca_dashboard.html 생성을 함께 수행."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = ["pca_gdp.py"]

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="PCA AfterHTML")
