from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
# Installed location: BQL/Theme/Material/Top10_Down10.
BQL_DIR = Path(os.environ.get("BQL_THEME_ROOT", HERE.parents[2])).resolve()
RAWFILE_DIR = BQL_DIR / "Rawfile"
MASTER_PATH = RAWFILE_DIR / "BQuant_Master.xlsx"
DEFAULT_MATERIAL_ROOT = HERE
TARGETS = ("SPX", "SHSZ300", "SXXP")

sys.path.insert(0, str(BQL_DIR / "Dashbaord"))
import build_regional_dashboards as raw_builder  # noqa: E402


def automatic_sources() -> list[Path]:
    """All production dashboards use one consolidated workbook."""
    if not MASTER_PATH.exists():
        raise FileNotFoundError(
            f"Master workbook not found: {MASTER_PATH}. "
            "Put the daily BQuant file in Rawfile/Daily_Input and run Rawfile/update_all.ps1."
        )
    return [MASTER_PATH]


def load_targets(sources: list[Path]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for source in sources:
        for raw in raw_builder.iter_raw_indices(source):
            if raw.code not in TARGETS:
                continue
            merged[raw.code] = (
                raw
                if raw.code not in merged
                else raw_builder.merge_raw_indices(merged[raw.code], raw)
            )
    missing = sorted(set(TARGETS) - set(merged))
    if missing:
        raise KeyError(f"Missing target indices: {missing}")
    return merged


def trading_sessions(prices: np.ndarray) -> list[int]:
    """Return actual sessions: >10% of valid constituents changed from prior row."""
    sessions: list[int] = []
    for j in range(1, prices.shape[1]):
        ok = np.isfinite(prices[:, j]) & np.isfinite(prices[:, j - 1]) & (prices[:, j - 1] != 0)
        if not ok.any():
            continue
        changed = ~np.isclose(prices[ok, j], prices[ok, j - 1], rtol=1e-7, atol=1e-9)
        if float(changed.mean()) > 0.10:
            sessions.append(j)
    return sessions


def record(raw, i: int, start: int, end: int, total_mcap: float) -> dict:
    start_price = float(raw.metrics["price"][i, start])
    end_price = float(raw.metrics["price"][i, end])
    mcap = float(raw.metrics["mcap"][i, end])
    return {
        "Ticker": raw.tickers[i],
        "Security_Name": raw.companies[i],
        "GICS_Sector": raw.sectors[i],
        "GICS_Industry_Group": raw.industries[i],
        "Price": end_price,
        "Index_Weight": mcap / total_mcap if np.isfinite(mcap) and total_mcap > 0 else None,
        "Price_start": start_price,
        "Return_10D": end_price / start_price - 1,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate current Top/Down 10 from the latest 11 valid price sessions."
    )
    parser.add_argument(
        "sources",
        nargs="*",
        type=Path,
        help="Optional BQuant workbook. Omit to use Rawfile/BQuant_Master.xlsx.",
    )
    parser.add_argument(
        "--material-root",
        type=Path,
        default=DEFAULT_MATERIAL_ROOT,
        help="Category material root. Dated calculation JSON is stored below YYYYMMDD.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional compatibility override for Market_10D_Rankings_latest.json.",
    )
    return parser.parse_args()


def atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    material_root = args.material_root.resolve()
    sources = [path.resolve() for path in args.sources] if args.sources else automatic_sources()
    raws = load_targets(sources)
    result: dict[str, dict] = {}
    for code in TARGETS:
        raw = raws[code]
        prices = raw.metrics["price"]
        sessions = trading_sessions(prices)
        if len(sessions) < 11:
            raise ValueError(f"{raw.code}: fewer than 11 valid trading sessions")
        end, start = sessions[-1], sessions[-11]
        ok = np.isfinite(prices[:, start]) & np.isfinite(prices[:, end]) & (prices[:, start] > 0)
        mcap = raw.metrics["mcap"][:, end]
        total_mcap = float(np.sum(mcap[np.isfinite(mcap) & (mcap > 0)]))
        rows = [record(raw, i, start, end, total_mcap) for i in np.flatnonzero(ok)]
        rows.sort(key=lambda item: item["Return_10D"], reverse=True)
        result[raw.code] = {
            "start": raw.dates[start].isoformat(),
            "latest": raw.dates[end].isoformat(),
            "constituents": len(rows),
            "top": rows[:10],
            "bottom": list(reversed(rows[-10:])),
        }

    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    as_of = max(block["latest"] for block in result.values())
    tag = as_of.replace("-", "")
    dated_dir = material_root / tag
    latest_path = (args.output or material_root / "Market_10D_Rankings_latest.json").resolve()
    dated_path = dated_dir / f"Market_10D_Rankings_{tag}.json"
    atomic_write(dated_path, payload)
    atomic_write(latest_path, payload)
    print(f"OUTPUT={latest_path}")
    print(f"RANKINGS={dated_path.resolve()}")
    print(f"MATERIAL_DATE_DIR={dated_dir.resolve()}")
    print(f"AS_OF={as_of}")
    print("SOURCES=" + ";".join(str(path) for path in sources))
    for code in TARGETS:
        block = result[code]
        print(f"{code}: {block['start']} -> {block['latest']} ({block['constituents']} stocks)")


if __name__ == "__main__":
    main()
