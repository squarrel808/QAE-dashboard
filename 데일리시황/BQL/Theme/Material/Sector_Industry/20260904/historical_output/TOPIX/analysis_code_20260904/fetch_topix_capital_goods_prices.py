from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests
import urllib3


DEFAULT_MASTER = Path(
    r"C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx"
)
REPORT_CODE_DIR = Path(
    r"C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Sector_Industry\Reports"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "topix_industrials_ai" / (
    "topix_capital_goods_prices_20260828_20260904.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start", default="2026-08-28")
    parser.add_argument("--end", default="2026-09-04")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument(
        "--universe",
        choices=("capital-goods", "all"),
        default="capital-goods",
        help="Fetch only TOPIX Capital Goods or the full TOPIX membership.",
    )
    return parser.parse_args()


def yahoo_symbol(bloomberg_ticker: str) -> str:
    return f"{bloomberg_ticker.split()[0]}.T"


def unix_start(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp())


def finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def fetch_one(
    row: dict[str, Any],
    start: date,
    end: date,
) -> dict[str, Any]:
    symbol = yahoo_symbol(row["ticker"])
    endpoint = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": unix_start(start),
        "period2": unix_start(date.fromordinal(end.toordinal() + 2)),
        "interval": "1d",
        "events": "history",
    }
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    error = None
    for attempt in range(4):
        try:
            response = requests.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=20,
                verify=False,
            )
            if response.status_code == 200:
                payload = response.json()
                result = (payload.get("chart", {}).get("result") or [None])[0]
                if not result:
                    raise ValueError(str(payload.get("chart", {}).get("error") or "empty result"))
                timestamps = result.get("timestamp") or []
                quote = ((result.get("indicators", {}).get("quote") or [{}])[0])
                closes = quote.get("close") or []
                by_date: dict[str, float] = {}
                for stamp, close in zip(timestamps, closes):
                    value = finite(close)
                    if value is None:
                        continue
                    key = datetime.fromtimestamp(int(stamp), tz=timezone.utc).date().isoformat()
                    by_date[key] = value
                start_close = by_date.get(start.isoformat())
                end_close = by_date.get(end.isoformat())
                return {
                    **row,
                    "yahooSymbol": symbol,
                    "prices": by_date,
                    "startClose": start_close,
                    "endClose": end_close,
                    "return5d": (
                        end_close / start_close - 1.0
                        if start_close is not None and end_close is not None and start_close > 0
                        else None
                    ),
                    "error": None,
                }
            error = f"HTTP {response.status_code}: {response.text[:120]}"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        if attempt < 3:
            time.sleep(1.5 * (attempt + 1))
    return {
        **row,
        "yahooSymbol": symbol,
        "prices": {},
        "startClose": None,
        "endClose": None,
        "return5d": None,
        "error": error,
    }


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start >= end:
        raise ValueError("start must precede end")

    sys.path.insert(0, str(REPORT_CODE_DIR))
    import build_sector_industry_5d as report_builder  # noqa: PLC0415

    panel = report_builder.load_market_panel(args.master, report_builder.MARKETS["TOPIX"])
    local_lookup = {value: idx for idx, value in enumerate(panel.dates)}
    rows: list[dict[str, Any]] = []
    for idx, ticker in enumerate(panel.tickers):
        if args.universe == "capital-goods" and panel.industries[idx] != "Capital Goods":
            continue
        local_prices: dict[str, float] = {}
        local_market_caps: dict[str, float] = {}
        for value_date in (date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4)):
            col = local_lookup.get(value_date)
            if col is None:
                continue
            value = finite(panel.prices[idx, col])
            if value is not None:
                local_prices[value_date.isoformat()] = value
            market_cap = finite(panel.market_caps[idx, col])
            if market_cap is not None:
                local_market_caps[value_date.isoformat()] = market_cap
        rows.append(
            {
                "ticker": ticker,
                "name": panel.names[idx],
                "sector": panel.sectors[idx],
                "industry": panel.industries[idx],
                "localPrices": local_prices,
                "localMarketCaps": local_market_caps,
            }
        )

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    completed: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(fetch_one, row, start, end) for row in rows]
        for position, future in enumerate(concurrent.futures.as_completed(futures), 1):
            completed.append(future.result())
            if position % 50 == 0:
                print(f"FETCHED={position}/{len(futures)}", flush=True)

    completed.sort(key=lambda row: row["ticker"])
    comparison_errors: list[float] = []
    comparison_count = 0
    for row in completed:
        anchor_key = "2026-09-02"
        anchor_price = row["localPrices"].get(anchor_key)
        anchor_market_cap = row["localMarketCaps"].get(anchor_key)
        start_close = row.get("startClose")
        row["startMarketCapEstimate"] = (
            anchor_market_cap * start_close / anchor_price
            if anchor_market_cap is not None
            and anchor_price is not None
            and start_close is not None
            and anchor_price > 0
            else None
        )
        for key in ("2026-09-02", "2026-09-03", "2026-09-04"):
            local = row["localPrices"].get(key)
            public = row["prices"].get(key)
            if local is None or public is None or local <= 0:
                continue
            comparison_count += 1
            comparison_errors.append(abs(public / local - 1.0))

    valid = [row for row in completed if row["return5d"] is not None]
    returns = np.asarray([row["return5d"] for row in valid], dtype=float)
    output = {
        "meta": {
            "source": "Yahoo Finance chart API query2; unadjusted local-currency close",
            "sourceWorkbook": str(args.master.resolve()),
            "membership": "Current TOPIX membership and GICS classification from TPX500 Raw",
            "universe": args.universe,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "requested": len(rows),
            "valid": len(valid),
            "coverage": len(valid) / len(rows) if rows else None,
            "localOverlapComparisons": comparison_count,
            "localOverlapMedianAbsolutePctError": (
                float(np.median(comparison_errors)) if comparison_errors else None
            ),
            "localOverlapMaxAbsolutePctError": max(comparison_errors) if comparison_errors else None,
            "universeEqualWeightReturn5d": float(returns.mean()) if returns.size else None,
            "universeMedianReturn5d": float(np.median(returns)) if returns.size else None,
            "universeBreadth5d": float((returns > 0).mean()) if returns.size else None,
        },
        "stocks": completed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.resolve())
    print(json.dumps(output["meta"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
