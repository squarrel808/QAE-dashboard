from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
BQL_ROOT = HERE.parents[3]


def main() -> None:
    parser = argparse.ArgumentParser(description="유럽·미국·일본 데일리 1D 섹터 HTML 보고서")
    parser.add_argument("--market", choices=("ALL", "STOXX600", "SP500", "TOPIX"), default="ALL")
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--update-raw", action="store_true")
    parser.add_argument("--open", action="store_true", dest="open_report")
    args = parser.parse_args()

    if args.update_raw:
        update_script = BQL_ROOT / "Rawfile" / "update_all.ps1"
        subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(update_script)],
            check=True,
        )

    command = [
        sys.executable,
        str(HERE / "build_sector_rotation_html.py"),
        "--master", str(BQL_ROOT / "Rawfile" / "BQuant_Master.xlsx"),
        "--output-root", str(BQL_ROOT / "Theme" / "output"),
        "--primary", "1D",
        "--market", args.market,
        "--top-n", "5",
    ]
    if args.as_of:
        command.extend(["--as-of", args.as_of.isoformat()])

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8", env=env)
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    for output in payload["outputs"]:
        print(output)
        if args.open_report:
            os.startfile(output)


if __name__ == "__main__":
    main()
