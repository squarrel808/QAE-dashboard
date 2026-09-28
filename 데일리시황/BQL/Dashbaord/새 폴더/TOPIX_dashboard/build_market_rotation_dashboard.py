"""Compatibility entry point; calculations live in BQL/Dashbaord/build_regional_dashboards.py."""

from pathlib import Path
import subprocess
import sys


if __name__ == "__main__":
    builder = Path(__file__).resolve().parent.parent / "build_regional_dashboards.py"
    raise SystemExit(subprocess.call([sys.executable, str(builder), "--region", "japan", *sys.argv[1:]]))
