# -*- coding: utf-8 -*-
"""AfterHTML — releasecalendar: 기업실적 달력 HTML 생성."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _runner import run_paths

SCRIPTS = ["build_earnings_calendar.py"]

if __name__ == "__main__":
    success = run_paths([os.path.join(HERE, s) for s in SCRIPTS],
              stop_on_fail=True, label="releasecalendar AfterHTML")
    raise SystemExit(0 if success else 1)
