"""Compatibility entry point; use the guarded daily runner in the Botari folder."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    target = Path(__file__).resolve().parents[3] / '\ubcf4\ub530\ub9ac' / 'macro_daily.py'
    runpy.run_path(str(target), run_name='__main__')
