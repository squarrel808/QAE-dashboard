# -*- coding: utf-8 -*-
"""BeforeHTML — PCA: 별도 데이터 단계 없음(융합형).
pca_gdp.py 가 데이터 처리(PCA→GDP 프록시→LEI)와 HTML 생성을 한 번에 수행하므로
데이터만 따로 떼는 단계가 없다. 실제 작업은 AfterHTML.py 가 수행."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = []   # 융합형 → Before 단계 없음

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="PCA BeforeHTML (없음)")
