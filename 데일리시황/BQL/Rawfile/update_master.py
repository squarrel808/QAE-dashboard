from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Any

import numpy as np
import xlsxwriter


HERE = Path(__file__).resolve().parent
BQL_DIR = HERE.parent
DASHBOARD_DIR = BQL_DIR / "Dashbaord"
DAILY_DIR = HERE / "Daily_Input"
MASTER_PATH = HERE / "BQuant_Master.xlsx"
MANIFEST_PATH = HERE / "rawfile_manifest.json"
SUPPORTED = {".xlsb", ".xlsx"}
# 새 원본은 QAE\____Rawdata___ 에 떨궈 넣으면 된다. 실행할 때 이 prefix 로 시작하는
# 파일을 자동으로 Daily_Input 에 복사한다(내용 해시가 같으면 복사하지 않는다).
REPO_DIR = BQL_DIR.parent.parent
RAWDATA_PREFIX = "Bquant_"
INDEX_ORDER = [
    "SX5E", "SXXP", "DAX", "CAC", "IBEX", "AEX", "UKX",
    "SPX", "NDX", "INDU", "SPTSX60", "IBOV", "NKY", "HSI",
    "SHSZ300", "STAR50", "AS51",
]

sys.path.insert(0, str(DASHBOARD_DIR))
import build_regional_dashboards as raw_builder  # noqa: E402

sys.path.insert(0, str(REPO_DIR))
import rawdata  # noqa: E402

METRICS = list(raw_builder.METRIC_PREFIXES.items())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 1, "processed": {}, "master": {}}
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    data.setdefault("version", 1)
    data.setdefault("processed", {})
    data.setdefault("master", {})
    return data


def save_manifest(data: dict[str, Any]) -> None:
    temp = MANIFEST_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, MANIFEST_PATH)


def daily_files() -> list[Path]:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        (
            path for path in DAILY_DIR.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED
            and not path.name.startswith("~$")
        ),
        key=lambda path: (path.stat().st_mtime, path.name.lower()),
    )


def copy_input(path: Path) -> Path:
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in SUPPORTED:
        raise ValueError(f"Unsupported file: {path}")
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(path)
    for existing in daily_files():
        if sha256_file(existing) == digest:
            return existing
    target = DAILY_DIR / path.name
    if target.exists():
        target = DAILY_DIR / f"{path.stem}_{digest[:10]}{path.suffix.lower()}"
    temp = target.with_suffix(target.suffix + ".tmp")
    shutil.copy2(path, temp)
    os.replace(temp, target)
    return target


def merge_sources(sources: list[Path]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in sources:
        print(f"PARSING={source}", flush=True)
        found = 0
        for raw in raw_builder.iter_raw_indices(source):
            found += 1
            merged[raw.code] = (
                raw
                if raw.code not in merged
                else raw_builder.merge_raw_indices(merged[raw.code], raw)
            )
        if found == 0:
            raise ValueError(f"No usable BQuant Raw sheet found: {source}")
    return merged


def ordered_codes(raws: dict[str, Any]) -> list[str]:
    preferred = [code for code in INDEX_ORDER if code in raws]
    return preferred + sorted(code for code in raws if code not in preferred)


def write_readme(workbook, raws: dict[str, Any], sources: list[Path]) -> None:
    ws = workbook.add_worksheet("README")
    title = workbook.add_format({"font_name": "Arial", "font_size": 18, "bold": True, "font_color": "#102A43"})
    header = workbook.add_format({"font_name": "Arial", "font_size": 10, "bold": True, "font_color": "white", "bg_color": "#102A43"})
    text = workbook.add_format({"font_name": "Arial", "font_size": 10, "font_color": "#102A43", "text_wrap": True})
    ws.set_column("A:A", 24)
    ws.set_column("B:B", 110)
    ws.write("A1", "BQuant Master", title)
    rows = [
        ("Purpose", "All production dashboards read this single consolidated workbook."),
        ("Generated", datetime.now().astimezone().isoformat(timespec="seconds")),
        ("Merge key", "Index + Bloomberg ticker + metric + observation date"),
        ("Overlap rule", "A later source overwrites only valid numeric observations; blanks keep the prior valid value."),
        ("Membership", "The source with the latest observation date supplies the current constituent list and GICS classification."),
        ("Workbook count", str(len(sources))),
        ("Index count", str(len(raws))),
        ("Sources", "\n".join(str(path) for path in sources)),
    ]
    ws.write("A3", "Item", header)
    ws.write("B3", "Description", header)
    for row, (key, value) in enumerate(rows, 3):
        ws.write(row, 0, key, text)
        ws.write(row, 1, value, text)
        ws.set_row(row, 34 if key != "Sources" else 90)
    ws.freeze_panes(3, 0)


def write_raw_sheet(workbook, raw) -> None:
    ws = workbook.add_worksheet(f"{raw.code} Raw"[:31])
    title = workbook.add_format({"font_name": "Arial", "font_size": 14, "bold": True, "font_color": "#102A43"})
    header = workbook.add_format({"font_name": "Arial", "font_size": 9, "bold": True, "font_color": "white", "bg_color": "#102A43"})
    text = workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": "#102A43"})
    metric = workbook.add_format({"font_name": "Arial", "font_size": 9, "bold": True, "font_color": "#2F6BDE"})
    date_fmt = workbook.add_format({"font_name": "Arial", "font_size": 8, "num_format": "yyyy-mm-dd", "rotation": 90})
    number = workbook.add_format({"font_name": "Arial", "font_size": 8, "num_format": "0.0000"})

    ws.write(0, 0, f"{raw.name} ({raw.code} Index)", title)
    ws.write(2, 4, "Live Member Count", header)
    ws.write_number(2, 5, len(raw.tickers), text)
    ws.write(3, 0, "Index", header)
    ws.write(3, 1, f"{raw.code} Index", text)
    ws.write(3, 2, "Currency", header)
    ws.write(3, 3, raw.currency, text)
    ws.write_row(6, 0, ["Ticker", "Security Name", "GICS Sector", "GICS Industry Group"], header)
    for row, ticker in enumerate(raw.tickers, 7):
        ws.write(row, 0, ticker, text)
        ws.write(row, 1, raw.companies[row - 7], text)
        ws.write(row, 2, raw.sectors[row - 7], text)
        ws.write(row, 3, raw.industries[row - 7], text)

    anchor = max(10, 7 + len(raw.tickers) + 2)
    for title_text, key in METRICS:
        values = raw.metrics[key]
        ws.write(anchor, 6, f"{title_text} | MASTER", metric)
        for col, value_date in enumerate(raw.dates, 7):
            ws.write_datetime(col=col, row=anchor + 1, date=datetime.combine(value_date, time()), cell_format=date_fmt)
        for member, ticker in enumerate(raw.tickers):
            row = anchor + 2 + member
            ws.write(row, 6, ticker, text)
            row_values = values[member]
            for offset, value in enumerate(row_values):
                if np.isfinite(value):
                    ws.write_number(row, 7 + offset, float(value), number)
        anchor += len(raw.tickers) + 2

    ws.set_column("A:A", 19)
    ws.set_column("B:B", 31)
    ws.set_column("C:D", 25)
    ws.set_column("G:G", 30)
    ws.set_column(7, 7 + len(raw.dates) - 1, 11)
    ws.freeze_panes(7, 7)


def write_master(raws: dict[str, Any], sources: list[Path]) -> None:
    temp = MASTER_PATH.with_name("BQuant_Master.tmp.xlsx")
    workbook = xlsxwriter.Workbook(str(temp), {"constant_memory": True, "nan_inf_to_errors": False})
    workbook.set_properties({
        "title": "BQuant Consolidated Master",
        "subject": "Current constituents and full available daily observations",
        "author": "OpenAI Codex",
        "comments": "Production input for Global/Europe rotation, AI Theme, and Top10/Down10 dashboards.",
    })
    write_readme(workbook, raws, sources)
    for code in ordered_codes(raws):
        print(f"WRITING={code} members={len(raws[code].tickers)} dates={len(raws[code].dates)}", flush=True)
        write_raw_sheet(workbook, raws[code])
    workbook.close()
    os.replace(temp, MASTER_PATH)


def validate_master(expected: dict[str, Any]) -> dict[str, Any]:
    actual = {raw.code: raw for raw in raw_builder.iter_raw_indices(MASTER_PATH)}
    if set(actual) != set(expected):
        raise AssertionError(f"Index mismatch: expected={sorted(expected)} actual={sorted(actual)}")
    checks: dict[str, Any] = {}
    for code, wanted in expected.items():
        got = actual[code]
        if got.dates != wanted.dates:
            raise AssertionError(f"{code}: date mismatch")
        if got.tickers != wanted.tickers:
            raise AssertionError(f"{code}: constituent mismatch")
        metric_counts = {}
        for key in raw_builder.METRIC_PREFIXES.values():
            wanted_count = int(np.isfinite(wanted.metrics[key]).sum())
            got_count = int(np.isfinite(got.metrics[key]).sum())
            if wanted_count != got_count:
                raise AssertionError(f"{code}/{key}: numeric count {got_count} != {wanted_count}")
            metric_counts[key] = got_count
        checks[code] = {
            "members": len(got.tickers),
            "dates": len(got.dates),
            "startDate": got.dates[0].isoformat(),
            "endDate": got.dates[-1].isoformat(),
            "metricNumericCells": metric_counts,
        }
    return checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append new Bloomberg/BQuant workbooks into one production BQuant_Master.xlsx."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Optional new daily files. They are copied into Daily_Input before append.",
    )
    parser.add_argument(
        "--bootstrap-source",
        action="append",
        type=Path,
        default=[],
        help="One-time legacy source used to create the first master; it is not copied to Daily_Input.",
    )
    parser.add_argument("--rebuild", action="store_true", help="Re-read every file in Daily_Input")
    parser.add_argument(
        "--no-rawdata",
        action="store_true",
        help=f"Skip the automatic pickup of {RAWDATA_PREFIX}* files from ____Rawdata___.",
    )
    return parser.parse_args()


def rawdata_inputs() -> list[Path]:
    """`____Rawdata___` 에서 BQuant 원본을 집어온다 (최신순, 없으면 빈 목록).

    복사·중복 판단은 copy_input 이 내용 해시로 한다. 같은 파일을 몇 번 떨궈 넣어도
    Daily_Input 이 불어나지 않고, 이름이 같은데 내용이 다르면 해시를 붙여 따로 남는다.
    """
    return [Path(p) for p in rawdata.find_all(
        RAWDATA_PREFIX, exts=tuple(sorted(SUPPORTED)))]


def main() -> int:
    args = parse_args()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    pending = list(args.inputs)
    if not args.no_rawdata:
        for path in rawdata_inputs():
            if path not in pending:
                print(f"RAWDATA={path}", flush=True)
                pending.append(path)
    copied = [copy_input(path) for path in pending]
    available_daily = daily_files()
    processed = manifest["processed"]
    if args.rebuild or not MASTER_PATH.exists():
        new_daily = available_daily
    else:
        new_daily = [path for path in available_daily if sha256_file(path) not in processed]

    bootstrap = [path.resolve() for path in args.bootstrap_source]
    for path in bootstrap:
        if not path.exists():
            raise FileNotFoundError(path)

    if MASTER_PATH.exists() and not bootstrap and not new_daily:
        print(f"NO_NEW_DATA={MASTER_PATH}")
        return 0

    sources = ([MASTER_PATH] if MASTER_PATH.exists() else []) + bootstrap + new_daily
    if not sources:
        raise FileNotFoundError(
            "No master or daily input exists. Use --bootstrap-source for the first build."
        )

    raws = merge_sources(sources)
    write_master(raws, sources)
    checks = validate_master(raws)

    for path in available_daily:
        digest = sha256_file(path)
        processed[digest] = {
            "file": path.name,
            "sizeBytes": path.stat().st_size,
            "processedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    manifest["master"] = {
        "path": str(MASTER_PATH),
        "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sizeBytes": MASTER_PATH.stat().st_size,
        "indices": checks,
    }
    save_manifest(manifest)
    print(f"MASTER={MASTER_PATH}")
    print(f"SIZE_BYTES={MASTER_PATH.stat().st_size}")
    print(f"INDICES={len(checks)}")
    print(f"DAILY_INPUTS={len(available_daily)}")
    if copied:
        print("COPIED=" + ";".join(str(path) for path in copied))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

