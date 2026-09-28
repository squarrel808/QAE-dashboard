from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np


REPORT_CODE_DIR = Path(
    r"C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Sector_Industry\Reports"
)
DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "artifacts" / "topix_industrials_ai" / (
    "topix_all_prices_20260828_20260904.json"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "topix_sector_industry_corrected"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a corrected TOPIX sector/industry 5D payload from validated recovered closes."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-n", type=int, default=8)
    return parser.parse_args()


def finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if np.isfinite(value) else None


def main() -> int:
    args = parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    meta = raw["meta"]
    rows = raw["stocks"]
    start = date.fromisoformat(meta["start"])
    end = date.fromisoformat(meta["end"])
    dates = sorted(
        {
            date.fromisoformat(key)
            for row in rows
            for key in row.get("prices", {})
            if start <= date.fromisoformat(key) <= end
        }
    )
    if len(dates) != 6:
        raise ValueError(f"Expected six completed closes for a five-session return, found {dates}")

    tickers = [row["ticker"] for row in rows]
    names = [row["name"] for row in rows]
    sectors = [row["sector"] for row in rows]
    industries = [row["industry"] for row in rows]
    prices = np.full((len(rows), len(dates)), np.nan, dtype=np.float64)
    market_caps = np.full_like(prices, np.nan)
    anchor_key = "2026-09-02"
    for out_row, row in enumerate(rows):
        anchor_price = finite(row.get("prices", {}).get(anchor_key))
        anchor_mcap = finite(row.get("localMarketCaps", {}).get(anchor_key))
        shares = (
            anchor_mcap / anchor_price
            if anchor_mcap is not None and anchor_price is not None and anchor_price > 0
            else None
        )
        for out_col, value_date in enumerate(dates):
            close = finite(row.get("prices", {}).get(value_date.isoformat()))
            if close is None:
                continue
            prices[out_row, out_col] = close
            if shares is not None:
                market_caps[out_row, out_col] = shares * close

    if int(np.isfinite(prices[:, 0]).sum()) != len(rows) or int(np.isfinite(prices[:, -1]).sum()) != len(rows):
        raise ValueError("Recovered price coverage is incomplete at a window endpoint")

    sys.path.insert(0, str(REPORT_CODE_DIR))
    import build_sector_industry_5d as builder  # noqa: PLC0415

    panel = builder.MarketPanel(
        key="TOPIX",
        title="TOPIX",
        source_sheet="TPX500 Raw + validated public daily closes",
        source_code="TOPIX current membership / JPY closes",
        currency="JPY",
        source_workbook=str(args.input.resolve()),
        source_mode="public_price_recovery",
        tickers=tickers,
        names=names,
        sectors=sectors,
        industries=industries,
        dates=dates,
        prices=prices,
        market_caps=market_caps,
    )

    # Every column is an explicitly enumerated completed Tokyo trading-day close.
    # The legacy detector omitted the first close and therefore required seven raw
    # observations for a five-session return.  Supplying the six verified close
    # indices here both corrects that off-by-one and keeps the legacy aggregation.
    original_actual_sessions = builder.actual_sessions
    builder.actual_sessions = lambda _: list(range(len(dates)))
    try:
        market = builder.build_market(panel, args.top_n)
    finally:
        builder.actual_sessions = original_actual_sessions

    builder.validate_market(market, args.top_n)
    chart_dir = args.output_dir / "charts" / "TOPIX"
    builder.create_charts(market, chart_dir)
    market["recoveryValidation"] = {
        "publicPriceCoverage": meta.get("coverage"),
        "localOverlapComparisons": meta.get("localOverlapComparisons"),
        "localOverlapMedianAbsolutePctError": meta.get("localOverlapMedianAbsolutePctError"),
        "localOverlapMaxAbsolutePctError": meta.get("localOverlapMaxAbsolutePctError"),
        "localOverlapDates": ["2026-09-02", "2026-09-03", "2026-09-04"],
    }
    payload = {
        "meta": {
            "schemaVersion": 1,
            "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "sourceWorkbook": meta.get("sourceWorkbook"),
            "recoveredPriceFile": str(args.input.resolve()),
            "recoveredPriceSource": meta.get("source"),
            "period": "5D",
            "periodDefinition": "2026-09-04 close divided by 2026-08-28 close minus one",
            "aggregation": "equal-weight arithmetic mean of valid constituent JPY price returns",
            "hierarchy": "GICS Sector > GICS Industry Group > constituent",
            "topBottomLimit": args.top_n,
            "notes": [
                "The user's current TOPIX membership and GICS mapping are retained.",
                "Public unadjusted JPY closes fill the three missing earlier closes; every overlapping local close was checked.",
                "Returns exclude dividends and current constituents are backfilled, leaving survivorship bias.",
            ],
        },
        "markets": [market],
    }
    data_dir = args.output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "TOPIX_Sector_Industry_5D_20260904_corrected.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path.resolve())
    print(json.dumps({"overall": market["overall"], "sessions": market["sessionDates"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
