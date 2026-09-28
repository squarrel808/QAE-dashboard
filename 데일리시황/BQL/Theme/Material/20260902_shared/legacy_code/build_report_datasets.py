from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import xlsxwriter


HERE = Path(__file__).resolve().parent
BQL_DIR = HERE.parents[1]
MASTER = BQL_DIR / "Rawfile" / "BQuant_Master.xlsx"
EURO_DIR = BQL_DIR / "유로존_dashboard"
AI_DIR = BQL_DIR / "Theme" / "AI"
AI_OUT = HERE / "AI_Rotation"
TOP_OUT = HERE / "Top10_Down10"

sys.path.insert(0, str(EURO_DIR))
sys.path.insert(0, str(AI_DIR))
import build_market_rotation_dashboard as raw_builder  # noqa: E402
import build_sp500_ai_value_chain as ai_builder  # noqa: E402


def finite(value: Any) -> bool:
    return value is not None and np.isfinite(value)


def iso(value: date) -> str:
    return value.isoformat()


def actual_sessions(prices: np.ndarray) -> list[int]:
    sessions: list[int] = []
    for current in range(1, prices.shape[1]):
        before = prices[:, current - 1]
        after = prices[:, current]
        valid = np.isfinite(before) & np.isfinite(after) & (before > 0) & (after > 0)
        if not valid.any():
            continue
        changed = ~np.isclose(after[valid], before[valid], rtol=1e-7, atol=1e-9)
        if float(changed.mean()) > 0.10:
            sessions.append(current)
    return sessions


def shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(value.day, days[month - 1]))


def session_on_or_before(dates: list[date], sessions: list[int], target: date) -> int:
    eligible = [idx for idx in sessions if dates[idx] <= target]
    return eligible[-1] if eligible else sessions[0]


def simple_return(prices: np.ndarray, start: int, end: int) -> np.ndarray:
    before, after = prices[:, start], prices[:, end]
    valid = np.isfinite(before) & np.isfinite(after) & (before > 0) & (after > 0)
    result = np.full(prices.shape[0], np.nan)
    result[valid] = after[valid] / before[valid] - 1.0
    return result


def max_drawdown(values: np.ndarray) -> float | None:
    values = values[np.isfinite(values) & (values > 0)]
    if len(values) < 2:
        return None
    running = np.maximum.accumulate(values)
    return float(np.min(values / running - 1.0))


def implied_shares(prices: np.ndarray, market_caps: np.ndarray) -> np.ndarray:
    """Return shares outstanding implied by Bloomberg price and market cap.

    The current BQuant panel does not contain a separate shares field. For price
    aggregation only, shares are therefore reconstructed as market cap / price.
    Market cap itself must never be used as the weight of an aggregate Price.
    """
    shares = np.full(np.broadcast_shapes(prices.shape, market_caps.shape), np.nan, dtype=float)
    valid = (
        np.isfinite(prices) & np.isfinite(market_caps) &
        (prices > 0) & (market_caps > 0)
    )
    np.divide(market_caps, prices, out=shares, where=valid)
    return shares


def share_weighted_price(
    prices: np.ndarray,
    market_caps: np.ndarray,
    members: list[int] | np.ndarray,
    session: int,
) -> float:
    """Aggregate Price as sum(Price * Shares) / sum(Shares)."""
    px = prices[members, session]
    shares = implied_shares(px, market_caps[members, session])
    valid = np.isfinite(px) & np.isfinite(shares) & (px > 0) & (shares > 0)
    if not valid.any():
        return np.nan
    return float(np.average(px[valid], weights=shares[valid]))


def share_weighted_price_series(
    prices: np.ndarray,
    market_caps: np.ndarray,
    members: list[int] | np.ndarray,
    sessions: list[int],
) -> list[float]:
    """Build a rebased series, using the valid-member intersection for each step."""
    if not sessions:
        return []
    level = 100.0
    levels = [level]
    for previous, current in zip(sessions, sessions[1:]):
        step_return = share_weighted_price_return(
            prices, market_caps, members, previous, current
        )
        if finite(step_return) and step_return > -1.0:
            level *= 1.0 + step_return
        levels.append(level)
    return levels


def share_weighted_price_return(
    prices: np.ndarray,
    market_caps: np.ndarray,
    members: list[int] | np.ndarray,
    start: int,
    end: int,
) -> float:
    """Return of aggregate Price using the same valid members at both dates."""
    px0 = prices[members, start]
    px1 = prices[members, end]
    shares0 = implied_shares(px0, market_caps[members, start])
    shares1 = implied_shares(px1, market_caps[members, end])
    valid = (
        np.isfinite(px0) & np.isfinite(px1) &
        np.isfinite(shares0) & np.isfinite(shares1) &
        (px0 > 0) & (px1 > 0) & (shares0 > 0) & (shares1 > 0)
    )
    if not valid.any():
        return np.nan
    start_price = float(np.average(px0[valid], weights=shares0[valid]))
    end_price = float(np.average(px1[valid], weights=shares1[valid]))
    return float(end_price / start_price - 1.0)


def share_price_contributions(
    prices: np.ndarray,
    market_caps: np.ndarray,
    rows: list[int],
    start: int,
    end: int,
) -> dict[int, float]:
    """Price-change contribution using start-date shares (an attribution approximation)."""
    px0 = prices[rows, start]
    px1 = prices[rows, end]
    shares0 = implied_shares(px0, market_caps[rows, start])
    valid = (
        np.isfinite(px0) & np.isfinite(px1) & np.isfinite(shares0) &
        (px0 > 0) & (px1 > 0) & (shares0 > 0)
    )
    denominator = float(np.sum(px0[valid] * shares0[valid]))
    result: dict[int, float] = {}
    if denominator <= 0:
        return result
    for position in np.flatnonzero(valid):
        result[rows[position]] = float(shares0[position] * (px1[position] - px0[position]) / denominator)
    return result


def percentile(values: np.ndarray) -> np.ndarray:
    result = np.full(len(values), np.nan)
    valid_idx = np.flatnonzero(np.isfinite(values))
    if not len(valid_idx):
        return result
    ordered = np.argsort(values[valid_idx], kind="stable")
    ranks = np.empty(len(valid_idx), dtype=float)
    ranks[ordered] = np.arange(1, len(valid_idx) + 1)
    result[valid_idx] = ranks / len(valid_idx)
    return result


def corporate_action_mask(prices: np.ndarray, mcap: np.ndarray, start: int, previous: int, end: int) -> np.ndarray:
    """Flag price jumps that are inconsistent with the corresponding market-cap move.

    BQuant price histories can briefly mix adjusted and unadjusted observations around
    splits.  Such rows are not investable price returns, so they are excluded from the
    ranking universe and listed in the workbook audit instead of silently winsorising.
    """
    p1 = simple_return(prices, previous, end)
    p10 = simple_return(prices, start, end)
    m1 = simple_return(mcap, previous, end)
    m10 = simple_return(mcap, start, end)
    one_day = np.isfinite(p1) & np.isfinite(m1) & (np.abs(p1) >= 0.40) & (np.abs(m1) <= 0.20)
    ten_day = np.isfinite(p10) & np.isfinite(m10) & (np.abs(p10) >= 0.75) & (np.abs(m10) <= 0.30)
    return one_day | ten_day


def load_raws() -> dict[str, Any]:
    wanted = {"SPX", "NDX", "SHSZ300", "SX5E"}
    result: dict[str, Any] = {}
    for raw in raw_builder.iter_raw_indices(MASTER):
        if raw.code in wanted:
            result[raw.code] = raw
    missing = wanted - result.keys()
    if missing:
        raise RuntimeError(f"Missing indices in Master: {sorted(missing)}")

    # Amphenol distributed a 2-for-1 stock dividend on 2026-09-02.  Because the
    # Master is assembled from overlapping snapshots, the current APH history
    # contains both pre- and post-split price bases.  Reconcile split-like 2x
    # transitions in the reporting copy only; the source Master is deliberately
    # left untouched.  Exact 2.0 scaling preserves the economic return around
    # the transition instead of treating the split as a price move.
    spx = result["SPX"]
    aph_rows = [i for i, ticker in enumerate(spx.tickers) if ticker == "APH UN Equity"]
    if aph_rows:
        row = aph_rows[0]
        series = spx.metrics["price"][row]
        valid = np.flatnonzero(np.isfinite(series) & (series > 0))
        # First align any later segment that is approximately twice the earlier
        # segment (the 2026-09-02 snapshot transition).
        for left, right in zip(valid[:-1], valid[1:]):
            ratio = series[right] / series[left]
            if 1.8 <= ratio <= 2.2:
                series[right:] /= 2.0
        # Then align any earlier pre-split segment that is approximately twice
        # the later segment (the overlapping-history transition in August).
        valid = np.flatnonzero(np.isfinite(series) & (series > 0))
        for left, right in zip(valid[:-1], valid[1:]):
            ratio = series[right] / series[left]
            if 0.45 <= ratio <= 0.55:
                series[:right] /= 2.0
    return result


def ai_dataset(spx: Any, ndx: Any) -> dict[str, Any]:
    prices = spx.metrics["price"]
    market_caps = spx.metrics["mcap"]
    sessions = actual_sessions(prices)
    end = sessions[-1]
    sessions = [idx for idx in sessions if idx <= end]
    previous = sessions[-2]
    start_1w = session_on_or_before(spx.dates, sessions, spx.dates[end] - timedelta(days=7))
    start_1m = session_on_or_before(spx.dates, sessions, shift_months(spx.dates[end], -1))
    bounds = [
        session_on_or_before(spx.dates, sessions, shift_months(spx.dates[end], -3)),
        session_on_or_before(spx.dates, sessions, shift_months(spx.dates[end], -2)),
        session_on_or_before(spx.dates, sessions, shift_months(spx.dates[end], -1)),
        end,
    ]
    start_3m = bounds[0]
    relevant_sessions = [idx for idx in sessions if start_3m <= idx <= end]
    anomaly_mask = corporate_action_mask(
        prices, spx.metrics["mcap"], start_3m, previous, end
    )
    # A one-session move of 40% or more in an S&P 500 constituent is reviewed as
    # a corporate-action break even when shares outstanding and market cap update
    # on the same vendor row (which can defeat the market-cap consistency test).
    anomaly_mask |= np.abs(simple_return(prices, previous, end)) >= 0.40
    for earlier, later in zip(relevant_sessions, relevant_sessions[1:]):
        anomaly_mask |= np.abs(simple_return(prices, earlier, later)) >= 0.40
    symbol_to_row = {ai_builder.ticker_symbol(t): i for i, t in enumerate(spx.tickers)}
    stage_lookup: dict[str, dict[str, Any]] = {}
    ticker_stage: dict[str, dict[str, Any]] = {}
    for stage in ai_builder.STAGES:
        members = []
        classified_members = []
        for confidence, symbols in (("Core", stage["core"]), ("Adjacent", stage["adjacent"])):
            for symbol in symbols:
                if symbol in symbol_to_row:
                    row = symbol_to_row[symbol]
                    classified_members.append(row)
                    if not anomaly_mask[row]:
                        members.append(row)
                    ticker_stage[symbol] = {"key": stage["key"], "name": stage["name"], "confidence": confidence}
        stage_lookup[stage["key"]] = {
            **stage,
            "rows": members,
            "classifiedRows": classified_members,
        }

    stocks = []
    returns_1d = simple_return(prices, previous, end)
    returns_1w = simple_return(prices, start_1w, end)
    returns_1m = simple_return(prices, start_1m, end)
    returns_3m = simple_return(prices, start_3m, end)
    monthly = [simple_return(prices, bounds[i], bounds[i + 1]) for i in range(3)]
    for symbol, meta in ticker_stage.items():
        row = symbol_to_row[symbol]
        path = prices[row, relevant_sessions]
        excluded = bool(anomaly_mask[row])
        stocks.append({
            "ticker": symbol,
            "name": spx.companies[row],
            "sector": spx.sectors[row],
            "industry": spx.industries[row],
            "stageKey": meta["key"],
            "stage": meta["name"],
            "confidence": meta["confidence"],
            "rationale": ai_builder.RATIONALES.get(symbol, stage_lookup[meta["key"]]["description"]),
            "price3mStart": float(prices[row, start_3m]) if finite(prices[row, start_3m]) else None,
            "price1mStart": float(prices[row, start_1m]) if finite(prices[row, start_1m]) else None,
            "price1wStart": float(prices[row, start_1w]) if finite(prices[row, start_1w]) else None,
            "pricePrev": float(prices[row, previous]) if finite(prices[row, previous]) else None,
            "priceEnd": float(prices[row, end]) if finite(prices[row, end]) else None,
            "return1d": None if excluded else (float(returns_1d[row]) if finite(returns_1d[row]) else None),
            "return1w": None if excluded else (float(returns_1w[row]) if finite(returns_1w[row]) else None),
            "return1m": None if excluded else (float(returns_1m[row]) if finite(returns_1m[row]) else None),
            "month1": None if excluded else (float(monthly[0][row]) if finite(monthly[0][row]) else None),
            "month2": None if excluded else (float(monthly[1][row]) if finite(monthly[1][row]) else None),
            "month3": None if excluded else (float(monthly[2][row]) if finite(monthly[2][row]) else None),
            "return3m": None if excluded else (float(returns_3m[row]) if finite(returns_3m[row]) else None),
            "maxDrawdown3m": None if excluded else max_drawdown(path),
            "excluded": excluded,
            "exclusionReason": (
                "Corporate-action/adjustment break: price jump inconsistent with market-cap move"
                if excluded else None
            ),
        })

    stages = []
    for key, stage in stage_lookup.items():
        rows = stage["rows"]
        stage_sessions = [idx for idx in sessions if start_3m <= idx <= end]
        levels = share_weighted_price_series(prices, market_caps, rows, stage_sessions)
        session_to_level = dict(zip(stage_sessions, levels))
        def level_return(a: int, b: int) -> float:
            return session_to_level[b] / session_to_level[a] - 1.0
        stage_stocks = [item for item in stocks if item["stageKey"] == key]
        one_day_sorted = sorted((x for x in stage_stocks if finite(x["return1d"])), key=lambda x: x["return1d"], reverse=True)
        one_week_sorted = sorted((x for x in stage_stocks if finite(x["return1w"])), key=lambda x: x["return1w"], reverse=True)
        one_month_sorted = sorted((x for x in stage_stocks if finite(x["return1m"])), key=lambda x: x["return1m"], reverse=True)
        three_month_sorted = sorted((x for x in stage_stocks if finite(x["return3m"])), key=lambda x: x["return3m"], reverse=True)
        row_by_ticker = {ai_builder.ticker_symbol(spx.tickers[row]): row for row in rows}

        def ranked_contributors(items: list[dict[str, Any]], start: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            contributions = share_price_contributions(prices, market_caps, rows, start, end)
            ranked = sorted(
                (
                    {
                        "ticker": item["ticker"],
                        "contribution": contributions.get(row_by_ticker[item["ticker"]], 0.0),
                    }
                    for item in items
                ),
                key=lambda item: item["contribution"],
                reverse=True,
            )
            return ranked[:3], ranked[-3:][::-1]

        top1d, bottom1d = ranked_contributors(one_day_sorted, previous)
        top1w, bottom1w = ranked_contributors(one_week_sorted, start_1w)
        top1m, bottom1m = ranked_contributors(one_month_sorted, start_1m)
        top3m, bottom3m = ranked_contributors(three_month_sorted, start_3m)
        stages.append({
            "key": key,
            "name": stage["name"],
            "short": stage["short"],
            "description": stage["description"],
            "members": len(rows),
            "classifiedMembers": len(stage["classifiedRows"]),
            "return1d": level_return(previous, end),
            "return1w": level_return(start_1w, end),
            "return1m": level_return(start_1m, end),
            "month1": level_return(bounds[0], bounds[1]),
            "month2": level_return(bounds[1], bounds[2]),
            "month3": level_return(bounds[2], bounds[3]),
            "return3m": level_return(start_3m, end),
            "maxDrawdown3m": max_drawdown(np.asarray(levels)),
            "breadth1d": float(np.mean([x["return1d"] > 0 for x in one_day_sorted])) if one_day_sorted else None,
            "breadth1w": float(np.mean([x["return1w"] > 0 for x in one_week_sorted])) if one_week_sorted else None,
            "breadth1m": float(np.mean([x["return1m"] > 0 for x in one_month_sorted])) if one_month_sorted else None,
            "top1d": top1d,
            "bottom1d": bottom1d,
            "top1w": top1w,
            "bottom1w": bottom1w,
            "top1m": top1m,
            "bottom1m": bottom1m,
            "top3m": top3m,
            "bottom3m": bottom3m,
            "series": [[iso(spx.dates[idx]), level] for idx, level in zip(stage_sessions, levels)],
        })

    def index_proxy(raw: Any) -> dict[str, Any]:
        sess = actual_sessions(raw.metrics["price"])
        e = sess[-1]
        p = sess[-2]
        s1w = session_on_or_before(raw.dates, sess, raw.dates[e] - timedelta(days=7))
        s1m = session_on_or_before(raw.dates, sess, shift_months(raw.dates[e], -1))
        s = session_on_or_before(raw.dates, sess, shift_months(raw.dates[e], -3))
        members = list(range(len(raw.tickers)))
        return {
            "asOf": iso(raw.dates[e]),
            "return1dShareWeightProxy": share_weighted_price_return(raw.metrics["price"], raw.metrics["mcap"], members, p, e),
            "return1wShareWeightProxy": share_weighted_price_return(raw.metrics["price"], raw.metrics["mcap"], members, s1w, e),
            "return1mShareWeightProxy": share_weighted_price_return(raw.metrics["price"], raw.metrics["mcap"], members, s1m, e),
            "return3mShareWeightProxy": share_weighted_price_return(raw.metrics["price"], raw.metrics["mcap"], members, s, e),
        }

    return {
        "meta": {
            "asOf": iso(spx.dates[end]),
            "previous": iso(spx.dates[previous]),
            "start1w": iso(spx.dates[start_1w]),
            "start1m": iso(spx.dates[start_1m]),
            "start3m": iso(spx.dates[start_3m]),
            "monthBoundaries": [iso(spx.dates[idx]) for idx in bounds],
            "universe": "S&P 500 current constituents; AI classification Expanded (Core + Adjacent)",
            "priceAggregation": "sum(Price * Shares) / sum(Shares)",
            "sharesSource": "Implied as Bloomberg Market Cap / Price",
            "members": len(stocks),
            "validMembers": int(sum(not item["excluded"] for item in stocks)),
            "excludedCorporateActions": [
                {
                    "ticker": item["ticker"],
                    "name": item["name"],
                    "pricePrevious": item["pricePrev"],
                    "priceEnd": item["priceEnd"],
                    "rawReturn1d": (
                        item["priceEnd"] / item["pricePrev"] - 1.0
                        if item["pricePrev"] is not None and item["priceEnd"] is not None
                        else None
                    ),
                    "reason": item["exclusionReason"],
                }
                for item in stocks if item["excluded"]
            ],
        },
        "benchmarks": {"SPX_share_weight_proxy": index_proxy(spx), "NDX_share_weight_proxy": index_proxy(ndx)},
        "stages": sorted(stages, key=lambda x: x["return3m"], reverse=True),
        "stocks": stocks,
    }


def trend_label(return_1d: float, return_10d: float, pct_10d: float, median_abs_1d: float) -> str:
    if abs(return_1d) < median_abs_1d:
        return "중립"
    if return_1d >= 0 and return_10d < 0 and pct_10d <= 0.2:
        return "낙폭과대 반등"
    if return_1d < 0 and return_10d > 0 and pct_10d >= 0.8:
        return "차익실현"
    if return_1d * return_10d < 0:
        return "단기 반전"
    if return_1d * return_10d > 0:
        return "추세 강화"
    return "중립"


def market_dataset(raw: Any) -> dict[str, Any]:
    prices = raw.metrics["price"]
    sessions = actual_sessions(prices)
    end, previous, start = sessions[-1], sessions[-2], sessions[-11]
    period_sessions = [idx for idx in sessions if start <= idx <= end]
    ret1 = simple_return(prices, previous, end)
    ret10 = simple_return(prices, start, end)
    anomaly_mask = corporate_action_mask(prices, raw.metrics["mcap"], start, previous, end)
    ret1[anomaly_mask] = np.nan
    ret10[anomaly_mask] = np.nan
    pct1, pct10 = percentile(ret1), percentile(ret10)
    median_abs = float(np.nanmedian(np.abs(ret1)))
    rows = []
    for i, ticker in enumerate(raw.tickers):
        if not finite(ret1[i]) or not finite(ret10[i]):
            continue
        rows.append({
            "ticker": ticker,
            "name": raw.companies[i],
            "sector": raw.sectors[i],
            "industry": raw.industries[i],
            "priceStart": float(prices[i, start]),
            "pricePrevious": float(prices[i, previous]),
            "priceEnd": float(prices[i, end]),
            "return1d": float(ret1[i]),
            "return10d": float(ret10[i]),
            "maxDrawdown10d": max_drawdown(prices[i, period_sessions]),
            "percentile1d": float(pct1[i]),
            "percentile10d": float(pct10[i]),
            "direction": trend_label(float(ret1[i]), float(ret10[i]), float(pct10[i]), median_abs),
            "mcap": float(raw.metrics["mcap"][i, end]) if finite(raw.metrics["mcap"][i, end]) else None,
        })
    one = sorted(rows, key=lambda x: x["return1d"], reverse=True)
    ten = sorted(rows, key=lambda x: x["return10d"], reverse=True)
    valid_rows = np.flatnonzero(~anomaly_mask).tolist()
    proxy1 = share_weighted_price_return(prices, raw.metrics["mcap"], valid_rows, previous, end)
    proxy10 = share_weighted_price_return(prices, raw.metrics["mcap"], valid_rows, start, end)
    repeated_latest = int(np.sum(
        np.isfinite(prices[:, previous]) & np.isfinite(prices[:, end]) &
        np.isclose(prices[:, previous], prices[:, end], rtol=1e-7, atol=1e-9)
    ))
    missing_intersection = int(len(raw.tickers) - len(rows) - int(anomaly_mask.sum()))
    anomalies = []
    for i in np.flatnonzero(anomaly_mask):
        anomalies.append({
            "ticker": raw.tickers[i], "name": raw.companies[i],
            "pricePrevious": float(prices[i, previous]) if finite(prices[i, previous]) else None,
            "priceEnd": float(prices[i, end]) if finite(prices[i, end]) else None,
            "rawReturn1d": float(simple_return(prices, previous, end)[i]) if finite(simple_return(prices, previous, end)[i]) else None,
            "mcapReturn1d": float(simple_return(raw.metrics["mcap"], previous, end)[i]) if finite(simple_return(raw.metrics["mcap"], previous, end)[i]) else None,
            "reason": "Price jump inconsistent with market-cap move; probable corporate-action/adjustment break",
        })
    return {
        "code": raw.code,
        "name": raw.name,
        "start": iso(raw.dates[start]),
        "previous": iso(raw.dates[previous]),
        "end": iso(raw.dates[end]),
        "members": len(rows),
        "sourceMembers": len(raw.tickers),
        "missingIntersection": missing_intersection,
        "repeatedLatestPrices": repeated_latest,
        "excludedAnomalies": anomalies,
        "actualSessions": [iso(raw.dates[idx]) for idx in period_sessions],
        "marketReturn1dProxy": proxy1,
        "marketReturn10dProxy": proxy10,
        "advancers": sum(1 for row in rows if row["return1d"] > 0),
        "decliners": sum(1 for row in rows if row["return1d"] < 0),
        "best1d": one[:10],
        "worst1d": one[-10:][::-1],
        "best10d": ten[:10],
        "worst10d": ten[-10:][::-1],
        "all": rows,
    }


def cross_market_dataset(raws: dict[str, Any]) -> dict[str, Any]:
    return {
        "meta": {
            "source": str(MASTER),
            "method": "Current-constituent local-currency shares-weighted aggregate Price returns; dividends excluded",
            "priceAggregation": "sum(Price * Shares) / sum(Shares)",
            "sharesSource": "Implied as Bloomberg Market Cap / Price",
        },
        "markets": [market_dataset(raws[code]) for code in ("SPX", "SHSZ300", "SX5E")],
    }


def formats(workbook: xlsxwriter.Workbook) -> dict[str, Any]:
    workbook.set_properties({"author": "OpenAI Codex", "company": "NPS", "comments": "Calculated from BQuant_Master.xlsx"})
    return {
        "title": workbook.add_format({"font_name": "Arial", "font_size": 18, "bold": True, "font_color": "#102A43"}),
        "section": workbook.add_format({"font_name": "Arial", "font_size": 11, "bold": True, "font_color": "white", "bg_color": "#17365D"}),
        "header": workbook.add_format({"font_name": "Arial", "font_size": 9, "bold": True, "font_color": "white", "bg_color": "#4472C4", "text_wrap": True, "border": 1}),
        "text": workbook.add_format({"font_name": "Arial", "font_size": 9, "border": 1}),
        "pct": workbook.add_format({"font_name": "Arial", "font_size": 9, "num_format": "0.0%;(0.0%);-", "border": 1}),
        "price": workbook.add_format({"font_name": "Arial", "font_size": 9, "num_format": "#,##0.00", "border": 1}),
        "int": workbook.add_format({"font_name": "Arial", "font_size": 9, "num_format": "#,##0", "border": 1}),
        "note": workbook.add_format({"font_name": "Arial", "font_size": 9, "font_color": "#666666", "text_wrap": True}),
    }


def write_ai_workbook(data: dict[str, Any], path: Path) -> None:
    workbook = xlsxwriter.Workbook(path)
    f = formats(workbook)
    summary = workbook.add_worksheet("Stage_Performance")
    summary.set_column("A:A", 4); summary.set_column("B:B", 29); summary.set_column("C:K", 14); summary.set_column("L:L", 42)
    summary.set_column("N:S", 18)
    summary.write("A1", "US AI Value Chain — Calculation & Verification", f["title"])
    summary.write("A2", f"As of {data['meta']['asOf']} | Expanded classification | Shares-weighted aggregate Price", f["note"])
    summary.write("N1", "Benchmark proxies", f["section"])
    summary.write_row("N2", ["Benchmark", "As of", "1D", "1W", "1M", "3M"], f["header"])
    for offset, (label, values) in enumerate(data["benchmarks"].items(), 2):
        summary.write(offset, 13, label, f["text"])
        summary.write(offset, 14, values["asOf"], f["text"])
        summary.write_number(offset, 15, values["return1dShareWeightProxy"], f["pct"])
        summary.write_number(offset, 16, values["return1wShareWeightProxy"], f["pct"])
        summary.write_number(offset, 17, values["return1mShareWeightProxy"], f["pct"])
        summary.write_number(offset, 18, values["return3mShareWeightProxy"], f["pct"])
    headers = ["Rank", "Value Chain", "Members", "1D", "1W", "1M", "Month 1", "Month 2", "Month 3", "3M", "Max Drawdown", "Method"]
    summary.write_row(4, 0, headers, f["header"])
    for row_idx, stage in enumerate(sorted(data["stages"], key=lambda x: x["return3m"], reverse=True), 5):
        summary.write_number(row_idx, 0, row_idx - 4, f["int"]); summary.write(row_idx, 1, stage["name"], f["text"]); summary.write_number(row_idx, 2, stage["members"], f["int"])
        for col, key in enumerate(("return1d", "return1w", "return1m", "month1", "month2", "month3", "return3m", "maxDrawdown3m"), 3):
            summary.write_number(row_idx, col, stage[key], f["pct"])
        summary.write(row_idx, 11, "Aggregate Price = sum(Price × Shares) / sum(Shares); dividends excluded", f["text"])
    summary.freeze_panes(5, 2); summary.autofilter(4, 0, 4 + len(data["stages"]), len(headers) - 1)

    stocks = workbook.add_worksheet("Stock_Returns")
    stocks.set_column("A:A", 14); stocks.set_column("B:B", 31); stocks.set_column("C:E", 24); stocks.set_column("F:J", 14); stocks.set_column("K:R", 14)
    sh = ["Ticker", "Company", "Value Chain", "GICS Sector", "Confidence", "3M Start Price", "1M Start Price", "1W Start Price", "Previous Price", "End Price", "1D", "1W", "1M", "Month 1", "Month 2", "Month 3", "3M", "3M Max Drawdown"]
    stocks.write_row(0, 0, sh, f["header"])
    for r, item in enumerate(sorted(data["stocks"], key=lambda x: (x["stage"], x["ticker"])), 1):
        stocks.write_row(r, 0, [item["ticker"], item["name"], item["stage"], item["sector"], item["confidence"]], f["text"])
        for c, key in enumerate(("price3mStart", "price1mStart", "price1wStart", "pricePrev", "priceEnd"), 5):
            if finite(item[key]): stocks.write_number(r, c, item[key], f["price"])
        excel = r + 1
        stocks.write_formula(r, 10, f'=IFERROR(J{excel}/I{excel}-1,"")', f["pct"], item["return1d"])
        stocks.write_formula(r, 11, f'=IFERROR(J{excel}/H{excel}-1,"")', f["pct"], item["return1w"])
        stocks.write_formula(r, 12, f'=IFERROR(J{excel}/G{excel}-1,"")', f["pct"], item["return1m"])
        for c, key in enumerate(("month1", "month2", "month3"), 13): stocks.write_number(r, c, item[key], f["pct"])
        stocks.write_formula(r, 16, f'=IFERROR(J{excel}/F{excel}-1,"")', f["pct"], item["return3m"])
        stocks.write_number(r, 17, item["maxDrawdown3m"], f["pct"])
    stocks.freeze_panes(1, 2); stocks.autofilter(0, 0, len(data["stocks"]), len(sh) - 1)

    contrib = workbook.add_worksheet("Contributors")
    contrib.set_column("A:A", 29); contrib.set_column("B:B", 12); contrib.set_column("C:C", 14); contrib.set_column("D:D", 13)
    contrib.write_row(0, 0, ["Value Chain", "Period", "Ticker", "Shares-based price contribution"], f["header"])
    r = 1
    for stage in data["stages"]:
        for period_key, label in (("top1d", "1D Top"), ("bottom1d", "1D Bottom"), ("top1w", "1W Top"), ("bottom1w", "1W Bottom"), ("top1m", "1M Top"), ("bottom1m", "1M Bottom"), ("top3m", "3M Top"), ("bottom3m", "3M Bottom")):
            for item in stage[period_key]:
                contrib.write_row(r, 0, [stage["name"], label, item["ticker"]], f["text"])
                contrib.write_number(r, 3, item["contribution"], f["pct"]); r += 1
    contrib.autofilter(0, 0, r - 1, 3); contrib.freeze_panes(1, 0)

    method = workbook.add_worksheet("Methodology")
    method.set_column("A:A", 24); method.set_column("B:B", 100)
    method.write("A1", "Item", f["header"]); method.write("B1", "Definition", f["header"])
    notes = [
        ("Source", str(MASTER)), ("As of", data["meta"]["asOf"]), ("Previous", data["meta"]["previous"]),
        ("1W start", data["meta"]["start1w"]), ("1M start", data["meta"]["start1m"]),
        ("3M start", data["meta"]["start3m"]), ("Month boundaries", " / ".join(data["meta"]["monthBoundaries"])),
        ("Basket", "Aggregate Price = sum(Price × Shares) / sum(Shares); returns are changes in that aggregate Price; dividends excluded"),
        ("Shares", "Derived as Bloomberg Market Cap / Price because the current BQuant panel has no separate shares field"),
        ("Contribution", "Start-date shares × price change / start aggregate value; attribution approximation"),
        ("Benchmark", "SPX and NDX current-constituent shares-weighted aggregate-price proxies; not SPY/QQQ ETF total returns"),
        ("Bias", "Current membership is backfilled; survivorship bias exists"),
    ]
    for r, (key, value) in enumerate(notes, 1): method.write(r, 0, key, f["text"]); method.write(r, 1, value, f["text"])
    workbook.close()


def write_cross_workbook(data: dict[str, Any], path: Path) -> None:
    workbook = xlsxwriter.Workbook(path)
    f = formats(workbook)
    summary = workbook.add_worksheet("Summary")
    summary.set_column("A:A", 12); summary.set_column("B:F", 17); summary.set_column("G:G", 45)
    summary.write("A1", "US · China · Eurozone — 1D & 10D Verification", f["title"])
    summary.write_row(3, 0, ["Index", "Start", "Previous", "End", "Members", "1D Proxy", "10D Proxy"], f["header"])
    for r, market in enumerate(data["markets"], 4):
        summary.write_row(r, 0, [market["code"], market["start"], market["previous"], market["end"]], f["text"])
        summary.write_number(r, 4, market["members"], f["int"]); summary.write_number(r, 5, market["marketReturn1dProxy"], f["pct"]); summary.write_number(r, 6, market["marketReturn10dProxy"], f["pct"])
    summary.write("A9", "Index return note", f["section"]); summary.write("B9", "Shares-weighted aggregate Price return: Price = sum(Price × Shares) / sum(Shares), with Shares inferred as Market Cap / Price. Official index returns may differ.", f["note"])

    audit = workbook.add_worksheet("QA_Audit")
    audit.set_column("A:A", 16); audit.set_column("B:E", 18); audit.set_column("F:F", 72)
    audit.write_row(0, 0, ["Index", "Source members", "Ranked members", "Missing intersection", "Repeated latest", "Actual sessions / exclusions"], f["header"])
    audit_row = 1
    for market in data["markets"]:
        detail = "Sessions: " + ", ".join(market["actualSessions"])
        audit.write_row(audit_row, 0, [market["code"], market["sourceMembers"], market["members"], market["missingIntersection"], market["repeatedLatestPrices"], detail], f["text"])
        audit_row += 1
        for item in market["excludedAnomalies"]:
            audit.write(audit_row, 0, market["code"], f["text"])
            audit.write(audit_row, 1, item["ticker"], f["text"])
            audit.write(audit_row, 2, item["name"], f["text"])
            audit.write_number(audit_row, 3, item["rawReturn1d"], f["pct"])
            if finite(item["mcapReturn1d"]): audit.write_number(audit_row, 4, item["mcapReturn1d"], f["pct"])
            audit.write(audit_row, 5, "EXCLUDED — " + item["reason"], f["note"])
            audit_row += 1

    for market in data["markets"]:
        ws = workbook.add_worksheet(market["code"])
        ws.set_column("A:A", 15); ws.set_column("B:B", 31); ws.set_column("C:D", 25); ws.set_column("E:G", 14); ws.set_column("H:L", 13); ws.set_column("M:M", 18)
        headers = ["Ticker", "Company", "GICS Sector", "Industry Group", "Start Price", "Previous Price", "End Price", "1D Return", "10D Return", "10D Max Drawdown", "1D Percentile", "10D Percentile", "Direction"]
        ws.write_row(0, 0, headers, f["header"])
        for r, item in enumerate(sorted(market["all"], key=lambda x: x["return10d"], reverse=True), 1):
            ws.write_row(r, 0, [item["ticker"], item["name"], item["sector"], item["industry"]], f["text"])
            ws.write_number(r, 4, item["priceStart"], f["price"]); ws.write_number(r, 5, item["pricePrevious"], f["price"]); ws.write_number(r, 6, item["priceEnd"], f["price"])
            excel = r + 1
            ws.write_formula(r, 7, f'=IFERROR(G{excel}/F{excel}-1,"")', f["pct"], item["return1d"])
            ws.write_formula(r, 8, f'=IFERROR(G{excel}/E{excel}-1,"")', f["pct"], item["return10d"])
            for c, key in ((9, "maxDrawdown10d"), (10, "percentile1d"), (11, "percentile10d")): ws.write_number(r, c, item[key], f["pct"])
            ws.write(r, 12, item["direction"], f["text"])
        ws.freeze_panes(1, 2); ws.autofilter(0, 0, market["members"], len(headers) - 1)

        rank = workbook.add_worksheet(f"{market['code']}_Ranks")
        rank.set_column("A:A", 12); rank.set_column("B:B", 15); rank.set_column("C:C", 29); rank.set_column("D:H", 14); rank.set_column("I:I", 20)
        rank.write_row(0, 0, ["Bucket", "Ticker", "Company", "1D", "10D", "MDD", "1D Pctl", "10D Pctl", "Direction"], f["header"])
        row = 1
        for key, label in (("best1d", "1D Best"), ("worst1d", "1D Worst"), ("best10d", "10D Best"), ("worst10d", "10D Worst")):
            for item in market[key]:
                rank.write_row(row, 0, [label, item["ticker"], item["name"]], f["text"])
                for c, metric in ((3, "return1d"), (4, "return10d"), (5, "maxDrawdown10d"), (6, "percentile1d"), (7, "percentile10d")): rank.write_number(row, c, item[metric], f["pct"])
                rank.write(row, 8, item["direction"], f["text"]); row += 1
        rank.freeze_panes(1, 1); rank.autofilter(0, 0, row - 1, 8)

    method = workbook.add_worksheet("Methodology")
    method.set_column("A:A", 24); method.set_column("B:B", 100)
    rows = [
        ("Source", str(MASTER)), ("Universe", "Current SPX, SHSZ300 and SX5E constituents"),
        ("Actual session", "A row is a trading session when more than 10% of valid constituent prices change"),
        ("Repeated prices", "Market-wide repeated/holiday rows are removed by the actual-session rule; individual unchanged closes remain valid and are counted in QA_Audit"),
        ("Missing values", "Ranking uses the intersection with positive finite prices at 10D start, previous session and end; missing intersections are excluded"),
        ("Corporate actions", "Price jumps >=40% in 1D or >=75% in 10D are excluded when market-cap change is small, indicating an adjusted/unadjusted series break; see QA_Audit"),
        ("1D", "Latest valid close / previous valid close - 1"), ("10D", "Latest valid close / close 10 valid sessions earlier - 1"),
        ("MDD", "Minimum of price / running maximum - 1 across the selected 10-session window"),
        ("Index proxy", "Change in shares-weighted aggregate Price; Shares = Market Cap / Price when no direct field is supplied; not official index total return"),
        ("Return type", "Local-currency simple price return; dividends excluded"),
    ]
    method.write_row(0, 0, ["Item", "Definition"], f["header"])
    for r, (key, value) in enumerate(rows, 1): method.write(r, 0, key, f["text"]); method.write(r, 1, value, f["text"])
    workbook.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build report-ready datasets from BQuant_Master.xlsx")
    parser.add_argument("--ai-only", action="store_true", help="Build only the AI value-chain JSON/XLSX outputs")
    args = parser.parse_args()
    AI_OUT.mkdir(parents=True, exist_ok=True)
    TOP_OUT.mkdir(parents=True, exist_ok=True)
    raws = load_raws()
    ai = ai_dataset(raws["SPX"], raws["NDX"])
    ai_tag = ai["meta"]["asOf"].replace("-", "")
    ai_json = AI_OUT / f"US_AI_Value_Chain_Data_{ai_tag}.json"
    ai_json.write_text(json.dumps(ai, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    ai_xlsx = AI_OUT / f"US_AI_Value_Chain_Calculations_{ai_tag}.xlsx"
    write_ai_workbook(ai, ai_xlsx)
    print(f"AI_JSON={ai_json}")
    print(f"AI_XLSX={ai_xlsx}")
    for stage in ai["stages"]:
        print(f"AI {stage['name']}: 1D={stage['return1d']:+.4%} 1W={stage['return1w']:+.4%} 1M={stage['return1m']:+.4%} 3M={stage['return3m']:+.4%}")
    if not args.ai_only:
        cross = cross_market_dataset(raws)
        cross_tag = max(market["end"] for market in cross["markets"]).replace("-", "")
        cross_json = TOP_OUT / f"US_China_Eurozone_Top10_Data_{cross_tag}.json"
        cross_json.write_text(json.dumps(cross, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        cross_xlsx = TOP_OUT / f"US_China_Eurozone_1D_10D_Calculations_{cross_tag}.xlsx"
        write_cross_workbook(cross, cross_xlsx)
        print(f"CROSS_JSON={cross_json}")
        print(f"CROSS_XLSX={cross_xlsx}")
        for market in cross["markets"]:
            print(f"{market['code']}: {market['previous']}->{market['end']} | 10D {market['start']}->{market['end']} | N={market['members']}")


if __name__ == "__main__":
    main()
