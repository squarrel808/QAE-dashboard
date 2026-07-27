# -*- coding: utf-8 -*-
"""BeforeHTML — releasecalendar: 별도 데이터 단계 없음(융합형).
기업실적.xlsx 는 블룸버그에서 수동으로 받아 폴더에 두면 되고,
build_earnings_calendar.py 가 읽기+HTML 생성을 한 번에 수행."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = []   # 융합형 → Before 단계 없음

if __name__ == "__main__":
    run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="releasecalendar BeforeHTML (없음)")
