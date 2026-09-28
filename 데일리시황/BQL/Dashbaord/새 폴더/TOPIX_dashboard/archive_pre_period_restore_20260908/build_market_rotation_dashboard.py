from __future__ import annotations

import argparse
import html
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import openpyxl
from pyxlsb import open_workbook


DASHBOARD_DIR = Path(__file__).resolve().parent
BQL_DIR = DASHBOARD_DIR.parent
DEFAULT_SOURCES = [BQL_DIR / "Rawfile" / "BQuant_Master.xlsx"]
DEFAULT_TEMPLATE = DASHBOARD_DIR / "market_rotation_dashboard.template.html"
DEFAULT_D3 = DASHBOARD_DIR / "d3.v7.9.0.min.js"
DEFAULT_FRAGMENT = DASHBOARD_DIR / "topix_rotation_dashboard.incremental.fragment.html"
DEFAULT_STANDALONE = DASHBOARD_DIR / "TOPIX_Rotation_Dashboard.html"
DEFAULT_VALUATION_SOURCE = None

STOXX600_SECTOR_MAP = {
    "ENG": "Energy",
    "MAT": "Materials",
    "IND": "Industrials",
    "CS": "Consumer Staples",
    "HC": "Health Care",
    "CD": "Consumer Discretionary",
    "Telc": "Communication Services",
    "UTL": "Utilities",
    "FIN": "Financials",
    "IT": "Information Technology",
}

INDEX_NAMES = {
    "TPX500": "TOPIX",
    "SX5E": "EURO STOXX 50",
    "INDU": "Dow Jones Industrial Average",
    "SPX": "S&P 500",
    "NDX": "NASDAQ 100",
    "SPTSX60": "S&P/TSX 60",
    "IBOV": "Bovespa",
    "UKX": "FTSE 100",
    "CAC": "CAC 40",
    "DAX": "DAX 40",
    "IBEX": "IBEX 35",
    "AEX": "AEX",
    "NKY": "Nikkei 225",
    "HSI": "Hang Seng",
    "SHSZ300": "CSI 300",
    "STAR50": "STAR 50",
    "AS51": "S&P/ASX 200",
    "SXXP": "STOXX Europe 600",
    "MEXBOL": "S&P/BMV IPC",
}

EXPECTED_INDEX_ORDER = ["TPX500"]

METRIC_PREFIXES = {
    "12MF P/E Blended": "pe",
    "12MF EPS Blended": "eps12",
    "FY1 EPS": "eps_fy1",
    "FY2 EPS": "eps_fy2",
    "Price": "price",
    "Market Cap (Daily)": "mcap",
    "Current ROE": "roe_current",
    "Current Operating Margin": "opm_current",
    "12MF ROE": "roe_12m",
    "12MF Operating Margin": "opm_12m",
}

# Operating-margin feeds can contain mathematically valid but economically
# unusable observations when reported revenue is near zero (for example,
# holding companies).  Those points overwhelm a market-cap weighted sector
# average, so keep only a broad plausible range for cross-sectional charts.
OPM_ABS_LIMIT = 200.0
ATTRIBUTION_START = date(2026, 9, 2)
EARNINGS_START = date(2026, 9, 2)

ROW_FIELDS = [
    "index",
    "indexName",
    "level",
    "group",
    "members",
    "weight",
    "eps4",
    "eps13",
    "momentum",
    "breadth4",
    "breadth13",
    "top5Concentration",
    "epsCoverage13",
    "price1m",
    "price3m",
    "priceCoverage3m",
    "peCurrent",
    "pePercentile",
    "roeCurrent",
    "roe12m",
    "opmCurrent",
    "opm12m",
    "fy2Growth",
    "mcap",
    "price6m",
    "priceCoverage6m",
    "eps6m",
    "epsCoverage6m",
    "price1d",
    "eps1d",
    "priceCoverage1d",
    "epsCoverage1d",
    "price5d",
    "eps5d",
    "priceCoverage5d",
    "epsCoverage5d",
]


@dataclass
class RawIndex:
    code: str
    name: str
    currency: str
    source: str
    sheet: str
    dates: list[date]
    tickers: list[str]
    companies: list[str]
    sectors: list[str]
    industries: list[str]
    metrics: dict[str, np.ndarray]


def cell(rows: list[list[Any]], row: int, col: int) -> Any:
    if 0 <= row < len(rows) and 0 <= col < len(rows[row]):
        return rows[row][col]
    return None


def excel_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and math.isfinite(value):
        if 20_000 < value < 80_000:
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    return None


def numeric(value: Any) -> float:
    if isinstance(value, bool):
        return np.nan
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return np.nan


def index_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.endswith(" Index"):
        return None
    return text[:-6].strip()


def metric_key(label: str) -> str | None:
    title = label.split(" | ", 1)[0].strip()
    return METRIC_PREFIXES.get(title)


def parse_raw_rows(rows: list[list[Any]], source: str, sheet: str) -> RawIndex | None:
    if not rows or not cell(rows, 0, 0):
        return None
    code = index_code(cell(rows, 3, 1))
    if code is None:
        return None
    live_value = cell(rows, 2, 5)
    live = int(live_value) if isinstance(live_value, (int, float)) and live_value > 0 else 0
    if live <= 0:
        return None

    tickers: list[str] = []
    companies: list[str] = []
    sectors: list[str] = []
    industries: list[str] = []
    for r in range(7, min(7 + live, len(rows))):
        ticker = cell(rows, r, 0)
        if not isinstance(ticker, str) or not ticker.strip():
            continue
        tickers.append(ticker.strip())
        companies.append(str(cell(rows, r, 1) or ticker).strip())
        sectors.append(str(cell(rows, r, 2) or "Unclassified").strip())
        industries.append(str(cell(rows, r, 3) or "Unclassified").strip())

    if not tickers:
        return None

    ticker_pos = {ticker: i for i, ticker in enumerate(tickers)}
    anchors: list[tuple[int, str, str]] = []
    for r, row in enumerate(rows):
        label = row[6] if len(row) > 6 else None
        if isinstance(label, str) and " | " in label:
            key = metric_key(label)
            if key:
                anchors.append((r, key, label))
    if not anchors:
        return None

    master_dates: list[date] = []
    metrics: dict[str, np.ndarray] = {}
    for a, (anchor, key, _) in enumerate(anchors):
        end = anchors[a + 1][0] if a + 1 < len(anchors) else len(rows)
        header = rows[anchor + 1] if anchor + 1 < len(rows) else []
        date_columns: list[tuple[int, date]] = []
        for c in range(7, len(header)):
            parsed = excel_date(header[c])
            if parsed is not None:
                date_columns.append((c, parsed))
        if not date_columns:
            continue
        block_dates = [d for _, d in date_columns]
        if not master_dates:
            master_dates = block_dates
        master_lookup = {d: i for i, d in enumerate(master_dates)}
        matrix = np.full((len(tickers), len(master_dates)), np.nan, dtype=np.float64)
        for r in range(anchor + 2, end):
            ticker = cell(rows, r, 6)
            if not isinstance(ticker, str) or ticker not in ticker_pos:
                continue
            out_row = ticker_pos[ticker]
            source_row = rows[r]
            for c, d in date_columns:
                out_col = master_lookup.get(d)
                if out_col is not None and c < len(source_row):
                    matrix[out_row, out_col] = numeric(source_row[c])
        metrics[key] = matrix

    if not master_dates or "mcap" not in metrics:
        return None
    for key in METRIC_PREFIXES.values():
        if key not in metrics:
            metrics[key] = np.full((len(tickers), len(master_dates)), np.nan, dtype=np.float64)

    currency = str(cell(rows, 3, 3) or "").strip()
    return RawIndex(
        code=code,
        name=INDEX_NAMES.get(code, code),
        currency=currency,
        source=source,
        sheet=sheet,
        dates=master_dates,
        tickers=tickers,
        companies=companies,
        sectors=sectors,
        industries=industries,
        metrics=metrics,
    )


def rows_from_xlsb(path: Path, sheet: str) -> list[list[Any]]:
    with open_workbook(str(path)) as wb:
        with wb.get_sheet(sheet) as ws:
            return [[c.v for c in row] for row in ws.rows()]


def iter_raw_indices(path: Path) -> Iterable[RawIndex]:
    if path.suffix.lower() == ".xlsb":
        with open_workbook(str(path)) as wb:
            sheet_names = list(wb.sheets)
        for sheet in sheet_names:
            rows = rows_from_xlsb(path, sheet)
            parsed = parse_raw_rows(rows, path.name, sheet)
            if parsed is not None:
                yield parsed
    else:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in wb.sheetnames:
                rows = [list(row) for row in wb[sheet].iter_rows(values_only=True)]
                parsed = parse_raw_rows(rows, path.name, sheet)
                if parsed is not None:
                    yield parsed
        finally:
            wb.close()


def finite_count(raw: RawIndex) -> int:
    return sum(int(np.isfinite(values).sum()) for values in raw.metrics.values())


def merge_raw_indices(existing: RawIndex, incoming: RawIndex) -> RawIndex:
    """Merge two snapshots of the same index into one date-aware panel.

    The later snapshot is authoritative for the current constituent universe and
    reference classifications.  Historical observations are retained for those
    current constituents, while overlapping dates are overwritten by the later
    snapshot.  This matches the dashboard's existing current-membership
    methodology and prevents removed constituents from being double counted.
    """
    if existing.code != incoming.code:
        raise ValueError(f"Cannot merge {existing.code} with {incoming.code}")

    existing_end = max(existing.dates) if existing.dates else date.min
    incoming_end = max(incoming.dates) if incoming.dates else date.min
    latest, older = (incoming, existing) if incoming_end >= existing_end else (existing, incoming)

    merged_dates = sorted(set(existing.dates) | set(incoming.dates))
    date_pos = {value: position for position, value in enumerate(merged_dates)}
    latest_ticker_pos = {ticker: position for position, ticker in enumerate(latest.tickers)}

    merged_metrics: dict[str, np.ndarray] = {}
    for key in METRIC_PREFIXES.values():
        output = np.full((len(latest.tickers), len(merged_dates)), np.nan, dtype=np.float64)
        for raw in (older, latest):
            values = raw.metrics.get(key)
            if values is None:
                continue
            for source_row, ticker in enumerate(raw.tickers):
                output_row = latest_ticker_pos.get(ticker)
                if output_row is None:
                    continue
                for source_col, value_date in enumerate(raw.dates):
                    if source_row < values.shape[0] and source_col < values.shape[1]:
                        value = values[source_row, source_col]
                        if np.isfinite(value):
                            output[output_row, date_pos[value_date]] = value
        merged_metrics[key] = output

    return RawIndex(
        code=latest.code,
        name=latest.name,
        currency=latest.currency,
        source=f"{older.source} + {latest.source}",
        sheet=latest.sheet,
        dates=merged_dates,
        tickers=list(latest.tickers),
        companies=list(latest.companies),
        sectors=list(latest.sectors),
        industries=list(latest.industries),
        metrics=merged_metrics,
    )


def nearest_date_index(dates: list[date], target: date) -> int:
    candidates = [i for i, d in enumerate(dates) if d <= target]
    return candidates[-1] if candidates else 0


def business_day_back_index(dates: list[date], current: int, periods: int) -> int:
    """Return the observation index a requested number of weekdays earlier."""
    sessions = [i for i, value_date in enumerate(dates[: current + 1]) if value_date.weekday() < 5]
    if not sessions:
        return max(0, current - periods)
    return sessions[max(0, len(sessions) - 1 - periods)]


def safe_weighted_mean(values: np.ndarray, weights: np.ndarray, mask: np.ndarray | None = None) -> float:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if mask is not None:
        valid &= mask
    if not valid.any():
        return np.nan
    denominator = float(weights[valid].sum())
    return float(np.sum(values[valid] * weights[valid]) / denominator) if denominator > 0 else np.nan


def safe_bounded_weighted_mean(
    values: np.ndarray,
    weights: np.ndarray,
    abs_limit: float,
) -> float:
    return safe_weighted_mean(values, weights, np.abs(values) <= abs_limit)


def weighted_change(
    values: np.ndarray,
    weights: np.ndarray,
    current: int,
    back: int,
    use_current_weights: bool,
    clip_low: float,
    clip_high: float,
    require_positive: bool = True,
) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    now = values[:, current]
    before = values[:, back]
    valid = np.isfinite(now) & np.isfinite(before)
    if require_positive:
        valid &= (now > 0) & (before > 0)
    else:
        valid &= np.abs(before) > 1e-12
    changes = np.full(len(now), np.nan)
    changes[valid] = np.clip(now[valid] / before[valid] - 1.0, clip_low, clip_high)
    weight_col = weights[:, current] if use_current_weights else weights[:, back]
    valid &= np.isfinite(weight_col) & (weight_col > 0)
    value = safe_weighted_mean(changes, weight_col, valid)
    return value, changes, weight_col, valid


def harmonic_pe(pe: np.ndarray, mcap: np.ndarray) -> np.ndarray:
    # Bloomberg occasionally carries near-zero forward P/E observations during
    # estimate or corporate-action transitions. They dominate a harmonic mean,
    # so observations below 1x are treated as data-quality outliers.
    valid = np.isfinite(pe) & (pe >= 1.0) & np.isfinite(mcap) & (mcap > 0)
    numerator = np.where(valid, mcap, 0.0).sum(axis=0)
    denominator = np.where(valid, mcap / pe, 0.0).sum(axis=0)
    return np.divide(numerator, denominator, out=np.full_like(numerator, np.nan), where=denominator > 0)


def pe_box_stats(series: np.ndarray) -> dict[str, float | int | None]:
    clean = series[np.isfinite(series) & (series > 0)]
    if clean.size < 5:
        return {"low": None, "q1": None, "median": None, "q3": None, "high": None, "current": None, "mean": None, "percentile": None, "n": int(clean.size)}
    q1, median, q3 = np.quantile(clean, [0.25, 0.5, 0.75])
    iqr = q3 - q1
    low_candidates = clean[clean >= q1 - 1.5 * iqr]
    high_candidates = clean[clean <= q3 + 1.5 * iqr]
    current = float(clean[-1])
    return {
        "low": float(low_candidates.min()) if low_candidates.size else float(clean.min()),
        "q1": float(q1),
        "median": float(median),
        "q3": float(q3),
        "high": float(high_candidates.max()) if high_candidates.size else float(clean.max()),
        "current": current,
        "mean": float(clean.mean()),
        "percentile": float(np.mean(clean <= current)),
        "n": int(clean.size),
    }


def load_stoxx600_sector_valuation(
    path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    """Read the workbook's row-2 field and row-5 sector keys.

    The supplied dashboard workbook stores one date column followed by a sector
    block for each field.  Only the 12-month forward P/E block is needed for the
    historical valuation charts.  Daily observations are reduced to month-end
    points over the latest trailing ten years to keep the inline dashboard small.
    """
    if not path.exists():
        return [], [], None

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        sheet_name = next(
            (name for name in workbook.sheetnames if name.replace(" ", "").lower() == "stoxx600"),
            None,
        )
        if sheet_name is None:
            return [], [], None
        sheet = workbook[sheet_name]
        headers = list(sheet.iter_rows(min_row=1, max_row=13, values_only=True))
        field_row = headers[1]
        sector_row = headers[4]
        name_row = headers[12]

        columns: dict[str, int] = {}
        for position, (field, sector) in enumerate(zip(field_row, sector_row), start=1):
            if not isinstance(field, str) or not field.strip().lower().startswith("12m fwd per"):
                continue
            if isinstance(sector, str) and (sector in STOXX600_SECTOR_MAP or sector == "Stoxx 600"):
                columns[sector] = position
        if not columns:
            return [], [], None

        first_value_col = min(columns.values())
        date_col = next(
            (
                position
                for position in range(first_value_col - 1, 0, -1)
                if position <= len(name_row) and str(name_row[position - 1] or "").strip() == "Name"
            ),
            None,
        )
        if date_col is None:
            return [], [], None

        observations: dict[str, list[tuple[date, float]]] = {sector: [] for sector in columns}
        min_col = date_col
        max_col = max(columns.values())
        offsets = {sector: col - min_col for sector, col in columns.items()}
        for values in sheet.iter_rows(
            min_row=14,
            max_row=sheet.max_row,
            min_col=min_col,
            max_col=max_col,
            values_only=True,
        ):
            observation_date = excel_date(values[0])
            if observation_date is None:
                continue
            for sector, offset in offsets.items():
                value = numeric(values[offset])
                if np.isfinite(value) and value > 0:
                    observations[sector].append((observation_date, float(value)))

        latest = max((points[-1][0] for points in observations.values() if points), default=None)
        if latest is None:
            return [], [], None
        try:
            history_cutoff = latest.replace(year=latest.year - 15)
        except ValueError:
            history_cutoff = latest.replace(year=latest.year - 15, day=28)
        try:
            statistics_cutoff = latest.replace(year=latest.year - 10)
        except ValueError:
            statistics_cutoff = latest.replace(year=latest.year - 10, day=28)

        epoch = date(1970, 1, 1)
        histories: list[dict[str, Any]] = []
        boxes: list[dict[str, Any]] = []
        coverage: dict[str, str] = {}
        index_coverage: str | None = None
        series_specs = [("Stoxx 600", "STOXX Europe 600 — Full Index", "Index")]
        series_specs.extend((sector, group, "Sector") for sector, group in STOXX600_SECTOR_MAP.items())
        for sector, group, level in series_specs:
            points = [(d, value) for d, value in observations.get(sector, []) if d >= history_cutoff]
            if not points:
                continue
            sampled: dict[tuple[int, int], tuple[date, float]] = {}
            for observation_date, value in points:
                sampled[(observation_date.year, observation_date.month)] = (observation_date, value)
            monthly = [sampled[key] for key in sorted(sampled)]
            statistics_values = [value for observation_date, value in monthly if observation_date >= statistics_cutoff]
            statistics_series = np.asarray(statistics_values, dtype=np.float64)
            stats = pe_box_stats(statistics_series)
            histories.append(
                {
                    "index": "SXXP",
                    "indexName": INDEX_NAMES["SXXP"],
                    "level": level,
                    "group": group,
                    "mean": float(statistics_series.mean()),
                    "std": float(statistics_series.std()),
                    "values": [
                        [int((observation_date - epoch).days), round(value, 3)]
                        for observation_date, value in monthly
                    ],
                }
            )
            if level == "Sector":
                boxes.append(
                    {
                        "index": "SXXP",
                        "indexName": INDEX_NAMES["SXXP"],
                        "level": level,
                        "group": group,
                        "low": stats["low"],
                        "q1": stats["q1"],
                        "median": stats["median"],
                        "q3": stats["q3"],
                        "high": stats["high"],
                        "current": stats["current"],
                        "percentile": stats["percentile"],
                    }
                )
            series_coverage = f"{monthly[0][0].isoformat()}|{monthly[-1][0].isoformat()}|{len(monthly)}"
            if level == "Index":
                index_coverage = series_coverage
            else:
                coverage[group] = series_coverage

        metadata = {
            "source": path.name,
            "sheet": sheet_name,
            "field": "12m fwd PER",
            "startDate": history_cutoff.isoformat(),
            "endDate": latest.isoformat(),
            "statisticsStartDate": statistics_cutoff.isoformat(),
            "statisticsWindow": "trailing 10 years",
            "frequency": "month-end",
            "indexCoverage": index_coverage,
            "sectorCoverage": coverage,
        }
        return histories, boxes, metadata
    finally:
        workbook.close()


def pe_fan_history(
    dates: list[date],
    series: np.ndarray,
    eps_values: np.ndarray,
    fy1_values: np.ndarray,
    fy2_values: np.ndarray,
    price_values: np.ndarray,
    market_caps: np.ndarray,
    index: str,
    index_name: str,
    level: str,
    group: str,
) -> dict[str, Any]:
    clean_mask = np.isfinite(series) & (series > 0)
    clean = series[clean_mask]
    mean = float(clean.mean()) if clean.size else np.nan
    std = float(clean.std()) if clean.size else np.nan

    eps_contribution = np.full(len(dates), np.nan, dtype=np.float64)
    pe_contribution = np.full(len(dates), np.nan, dtype=np.float64)
    price_return = np.full(len(dates), np.nan, dtype=np.float64)
    baseline_candidates = [i for i, observation_date in enumerate(dates) if observation_date >= ATTRIBUTION_START]
    baseline: int | None = None
    if baseline_candidates:
        baseline = baseline_candidates[0]
        base_eps = eps_values[:, baseline]
        base_price = price_values[:, baseline]
        base_weight = market_caps[:, baseline]
        base_price_valid = (
            np.isfinite(base_price)
            & (base_price > 0)
            & np.isfinite(base_weight)
            & (base_weight > 0)
        )
        base_valid = (
            np.isfinite(base_eps)
            & (base_eps > 0)
            & np.isfinite(base_price)
            & (base_price > 0)
            & np.isfinite(base_weight)
            & (base_weight > 0)
        )
        for observation in range(baseline, len(dates)):
            current_eps = eps_values[:, observation]
            current_price = price_values[:, observation]
            price_valid = base_price_valid & np.isfinite(current_price) & (current_price > 0)
            if price_valid.any():
                stock_returns = current_price[price_valid] / base_price[price_valid] - 1.0
                plausible_returns = (stock_returns >= -0.95) & (stock_returns <= 5.0)
                if plausible_returns.any():
                    return_weights = base_weight[price_valid][plausible_returns]
                    return_denominator = float(return_weights.sum())
                    if return_denominator > 0:
                        price_return[observation] = float(
                            np.sum(stock_returns[plausible_returns] * return_weights) / return_denominator
                        )
            valid = base_valid & np.isfinite(current_eps) & (current_eps > 0) & np.isfinite(current_price) & (current_price > 0)
            if not valid.any():
                continue
            eps_change = current_eps[valid] / base_eps[valid] - 1.0
            price_change = current_price[valid] / base_price[valid] - 1.0
            plausible = (
                (eps_change >= -0.95)
                & (eps_change <= 5.0)
                & (price_change >= -0.95)
                & (price_change <= 5.0)
            )
            if not plausible.any():
                continue
            eps_change = eps_change[plausible]
            price_change = price_change[plausible]
            weights = base_weight[valid][plausible]
            pe_change = (1.0 + price_change) / (1.0 + eps_change) - 1.0
            cross = eps_change * pe_change
            eps_stock_contribution = eps_change + 0.5 * cross
            pe_stock_contribution = pe_change + 0.5 * cross
            denominator = float(weights.sum())
            if denominator > 0:
                eps_contribution[observation] = float(np.sum(eps_stock_contribution * weights) / denominator)
                pe_contribution[observation] = float(np.sum(pe_stock_contribution * weights) / denominator)

    fy1_change = np.full(len(dates), np.nan, dtype=np.float64)
    fy2_change = np.full(len(dates), np.nan, dtype=np.float64)
    fy1_breadth = np.full(len(dates), np.nan, dtype=np.float64)
    fy2_breadth = np.full(len(dates), np.nan, dtype=np.float64)
    earnings_candidates = [i for i, observation_date in enumerate(dates) if observation_date >= EARNINGS_START]
    earnings_baseline: int | None = None
    if earnings_candidates:
        earnings_baseline = earnings_candidates[0]
        earnings_weight = market_caps[:, earnings_baseline]

        def cumulative_change(values: np.ndarray, observation: int) -> float:
            base = values[:, earnings_baseline]
            current = values[:, observation]
            valid = (
                np.isfinite(base)
                & (base > 0)
                & np.isfinite(current)
                & (current > 0)
                & np.isfinite(earnings_weight)
                & (earnings_weight > 0)
            )
            if not valid.any():
                return np.nan
            changes = np.clip(current[valid] / base[valid] - 1.0, -1.0, 3.0)
            weights = earnings_weight[valid]
            denominator = float(weights.sum())
            return float(np.sum(changes * weights) / denominator) if denominator > 0 else np.nan

        def net_breadth(values: np.ndarray, observation: int) -> float:
            back = nearest_date_index(dates, dates[observation] - timedelta(days=28))
            before = values[:, back]
            current = values[:, observation]
            valid = np.isfinite(before) & (before > 0) & np.isfinite(current) & (current > 0)
            if not valid.any():
                return np.nan
            changes = current[valid] / before[valid] - 1.0
            signs = np.where(changes > 1e-12, 1.0, np.where(changes < -1e-12, -1.0, 0.0))
            return float(signs.mean())

        for observation in range(earnings_baseline, len(dates)):
            fy1_change[observation] = cumulative_change(fy1_values, observation)
            fy2_change[observation] = cumulative_change(fy2_values, observation)
            fy1_breadth[observation] = net_breadth(fy1_values, observation)
            fy2_breadth[observation] = net_breadth(fy2_values, observation)

    # Keep the last observation in each week for index charts and in each
    # month for the denser sector/industry small-multiple grids.
    sampled: dict[tuple[int, int], tuple[int, date, float]] = {}
    for observation, (observation_date, value) in enumerate(zip(dates, series)):
        if not np.isfinite(value) or value <= 0:
            continue
        if level == "Index":
            iso = observation_date.isocalendar()
            bucket = (iso.year, iso.week)
        else:
            bucket = (observation_date.year, observation_date.month)
        sampled[bucket] = (observation, observation_date, float(value))

    epoch = date(1970, 1, 1)
    def history_point(observation: int, observation_date: date, value: float) -> list[float | int | None]:
        point: list[float | int | None] = [int((observation_date - epoch).days), round(float(value), 3)]
        if baseline is not None and observation >= baseline:
            point.extend([
                round(float(eps_contribution[observation]), 4) if np.isfinite(eps_contribution[observation]) else None,
                round(float(pe_contribution[observation]), 4) if np.isfinite(pe_contribution[observation]) else None,
            ])
        if earnings_baseline is not None and observation >= earnings_baseline:
            while len(point) < 4:
                point.append(None)
            point.extend([
                round(float(fy1_change[observation]), 4) if np.isfinite(fy1_change[observation]) else None,
                round(float(fy2_change[observation]), 4) if np.isfinite(fy2_change[observation]) else None,
                round(float(fy1_breadth[observation]), 4) if np.isfinite(fy1_breadth[observation]) else None,
                round(float(fy2_breadth[observation]), 4) if np.isfinite(fy2_breadth[observation]) else None,
            ])
        if baseline is not None and observation >= baseline:
            while len(point) < 8:
                point.append(None)
            point.append(round(float(price_return[observation]), 4) if np.isfinite(price_return[observation]) else None)
        return point

    point_map: dict[int, list[float | int | None]] = {}
    for explicit in (baseline, earnings_baseline):
        if explicit is not None and np.isfinite(series[explicit]) and series[explicit] > 0:
            point = history_point(explicit, dates[explicit], float(series[explicit]))
            point_map[int(point[0])] = point
    for observation, observation_date, value in sampled.values():
        point = history_point(observation, observation_date, value)
        point_map[int(point[0])] = point
    values = [point_map[key] for key in sorted(point_map)]
    return {
        "index": index,
        "indexName": index_name,
        "level": level,
        "group": group,
        "mean": mean,
        "std": std,
        "values": values,
    }


def aggregate_group(
    raw: RawIndex,
    member_idx: np.ndarray,
    level: str,
    group: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metrics = {key: value[member_idx, :] for key, value in raw.metrics.items()}
    dates = raw.dates
    current = nearest_date_index(dates, dates[-1])
    back4 = nearest_date_index(dates, dates[current] - timedelta(days=28))
    back13 = nearest_date_index(dates, dates[current] - timedelta(days=91))
    back1m = back4
    back3m = back13
    back6m = nearest_date_index(dates, dates[current] - timedelta(days=182))
    back1d = business_day_back_index(dates, current, 1)
    back5d = business_day_back_index(dates, current, 5)
    mcap = metrics["mcap"]

    eps4, eps4_stock, eps4_weights, eps4_valid = weighted_change(
        metrics["eps12"], mcap, current, back4, True, -1.0, 1.0, True
    )
    eps13, eps13_stock, eps13_weights, eps13_valid = weighted_change(
        metrics["eps12"], mcap, current, back13, True, -1.0, 1.0, True
    )
    eps6m, _, _, eps6_valid = weighted_change(
        metrics["eps12"], mcap, current, back6m, True, -1.0, 1.0, True
    )
    price1m, _, _, price1_valid = weighted_change(
        metrics["price"], mcap, current, back1m, False, -0.95, 5.0, True
    )
    price3m, _, _, price3_valid = weighted_change(
        metrics["price"], mcap, current, back3m, False, -0.95, 5.0, True
    )
    price6m, _, _, price6_valid = weighted_change(
        metrics["price"], mcap, current, back6m, False, -0.95, 5.0, True
    )
    eps1d, _, _, eps1_valid = weighted_change(
        metrics["eps12"], mcap, current, back1d, True, -1.0, 1.0, True
    )
    eps5d, _, _, eps5_valid = weighted_change(
        metrics["eps12"], mcap, current, back5d, True, -1.0, 1.0, True
    )
    price1d, _, _, price1d_valid = weighted_change(
        metrics["price"], mcap, current, back1d, False, -0.95, 5.0, True
    )
    price5d, _, _, price5d_valid = weighted_change(
        metrics["price"], mcap, current, back5d, False, -0.95, 5.0, True
    )

    pe_series = harmonic_pe(metrics["pe"], mcap)
    pe_stats = pe_box_stats(pe_series)
    current_mcap = mcap[:, current]
    current_pe = pe_series[current] if current < len(pe_series) else np.nan

    breadth4 = float(np.mean(eps4_stock[eps4_valid] > 0)) if eps4_valid.any() else np.nan
    breadth13 = float(np.mean(eps13_stock[eps13_valid] > 0)) if eps13_valid.any() else np.nan
    contributions = np.zeros(len(member_idx))
    if eps13_valid.any():
        valid_weight_sum = eps13_weights[eps13_valid].sum()
        if valid_weight_sum > 0:
            contributions[eps13_valid] = eps13_weights[eps13_valid] / valid_weight_sum * eps13_stock[eps13_valid]
    abs_total = np.abs(contributions).sum()
    top5 = float(np.sort(np.abs(contributions))[-5:].sum() / abs_total) if abs_total > 0 else np.nan

    fy1 = metrics["eps_fy1"][:, current]
    fy2 = metrics["eps_fy2"][:, current]
    fy_valid = np.isfinite(fy1) & np.isfinite(fy2) & (fy1 > 0) & (fy2 > 0)
    fy_growth = np.full(len(member_idx), np.nan)
    fy_growth[fy_valid] = np.clip(fy2[fy_valid] / fy1[fy_valid] - 1.0, -1.0, 3.0)

    total_index_mcap = np.nansum(raw.metrics["mcap"][:, current][np.isfinite(raw.metrics["mcap"][:, current]) & (raw.metrics["mcap"][:, current] > 0)])
    group_mcap = np.nansum(current_mcap[np.isfinite(current_mcap) & (current_mcap > 0)])
    group_weight = float(group_mcap / total_index_mcap) if total_index_mcap > 0 else np.nan

    row = {
        "index": raw.code,
        "indexName": raw.name,
        "level": level,
        "group": group,
        "members": int(len(member_idx)),
        "weight": group_weight,
        "eps4": eps4,
        "eps13": eps13,
        "momentum": eps4 - (4.0 / 13.0) * eps13 if np.isfinite(eps4) and np.isfinite(eps13) else np.nan,
        "breadth4": breadth4,
        "breadth13": breadth13,
        "top5Concentration": top5,
        "epsCoverage13": float(eps13_valid.sum() / len(member_idx)) if len(member_idx) else np.nan,
        "price1m": price1m,
        "price3m": price3m,
        "priceCoverage3m": float(price3_valid.sum() / len(member_idx)) if len(member_idx) else np.nan,
        "peCurrent": float(current_pe) if np.isfinite(current_pe) else np.nan,
        "pePercentile": pe_stats["percentile"],
        "roeCurrent": safe_weighted_mean(metrics["roe_current"][:, current], current_mcap),
        "roe12m": safe_weighted_mean(metrics["roe_12m"][:, current], current_mcap),
        "opmCurrent": safe_bounded_weighted_mean(metrics["opm_current"][:, current], current_mcap, OPM_ABS_LIMIT),
        "opm12m": safe_bounded_weighted_mean(metrics["opm_12m"][:, current], current_mcap, OPM_ABS_LIMIT),
        "fy2Growth": safe_weighted_mean(fy_growth, current_mcap, fy_valid),
        "mcap": float(group_mcap) if np.isfinite(group_mcap) else np.nan,
        "price6m": price6m,
        "priceCoverage6m": float(price6_valid.sum() / len(member_idx)) if len(member_idx) else np.nan,
        "eps6m": eps6m,
        "epsCoverage6m": float(eps6_valid.sum() / len(member_idx)) if len(member_idx) else np.nan,
        "price1d": price1d,
        "eps1d": eps1d,
        "priceCoverage1d": float(price1d_valid.sum() / len(member_idx)) if len(member_idx) else np.nan,
        "epsCoverage1d": float(eps1_valid.sum() / len(member_idx)) if len(member_idx) else np.nan,
        "price5d": price5d,
        "eps5d": eps5d,
        "priceCoverage5d": float(price5d_valid.sum() / len(member_idx)) if len(member_idx) else np.nan,
        "epsCoverage5d": float(eps5_valid.sum() / len(member_idx)) if len(member_idx) else np.nan,
    }
    box = {
        "index": raw.code,
        "indexName": raw.name,
        "level": level,
        "group": group,
        "low": pe_stats["low"],
        "q1": pe_stats["q1"],
        "median": pe_stats["median"],
        "q3": pe_stats["q3"],
        "high": pe_stats["high"],
        "current": pe_stats["current"],
        "percentile": pe_stats["percentile"],
    }
    history = pe_fan_history(
        dates,
        pe_series,
        metrics["eps12"],
        metrics["eps_fy1"],
        metrics["eps_fy2"],
        metrics["price"],
        metrics["mcap"],
        raw.code,
        raw.name,
        level,
        group,
    )
    return row, box, history


def aggregate_index(
    raw: RawIndex,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] = []
    histories: list[dict[str, Any]] = []
    all_members = np.arange(len(raw.tickers), dtype=int)
    summary, box, history = aggregate_group(raw, all_members, "Index", "All")
    rows.append(summary)
    boxes.append(box)
    histories.append(history)

    for level, labels in (("Sector", raw.sectors), ("Industry", raw.industries)):
        label_array = np.asarray(labels, dtype=object)
        for group in sorted({str(x) for x in label_array if str(x).strip()}):
            members = np.flatnonzero(label_array == group)
            if members.size == 0:
                continue
            row, group_box, group_history = aggregate_group(raw, members, level, group)
            rows.append(row)
            boxes.append(group_box)
            histories.append(group_history)

    latest = raw.dates[-1]
    coverage = {
        "index": raw.code,
        "indexName": raw.name,
        "source": raw.source,
        "sheet": raw.sheet,
        "currency": raw.currency,
        "members": len(raw.tickers),
        "startDate": raw.dates[0].isoformat(),
        "endDate": latest.isoformat(),
        "metricCoverage": {
            key: float(np.isfinite(values[:, -1]).sum() / len(raw.tickers))
            for key, values in raw.metrics.items()
        },
    }
    return rows, boxes, histories, coverage


def map_industries_to_sectors(raw: RawIndex) -> dict[str, str]:
    """Map each industry group to its dominant current sector.

    GICS industry groups normally have a single parent sector.  The weighted
    fallback keeps the mapping deterministic if the source contains mixed or
    unclassified labels.
    """
    current_mcap = raw.metrics["mcap"][:, -1]
    scores: dict[str, dict[str, float]] = {}
    for position, (industry, sector) in enumerate(zip(raw.industries, raw.sectors)):
        industry_name = str(industry).strip() or "Unclassified"
        sector_name = str(sector).strip() or "Unclassified"
        weight = float(current_mcap[position]) if np.isfinite(current_mcap[position]) and current_mcap[position] > 0 else 1.0
        sector_scores = scores.setdefault(industry_name, {})
        sector_scores[sector_name] = sector_scores.get(sector_name, 0.0) + weight
    return {
        industry: max(sector_scores.items(), key=lambda item: (item[1], item[0]))[0]
        for industry, sector_scores in scores.items()
        if sector_scores
    }


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 6)
    return value


def build(
    sources: list[Path],
    template_path: Path,
    d3_path: Path,
    fragment_path: Path,
    valuation_source: Path | None = DEFAULT_VALUATION_SOURCE,
    standalone_path: Path | None = DEFAULT_STANDALONE,
) -> dict[str, Any]:
    chosen: dict[str, RawIndex] = {}
    skipped_duplicates: list[dict[str, str]] = []
    for source in sources:
        if not source.exists():
            continue
        for raw in iter_raw_indices(source):
            if raw.code == "TPX":
                continue
            if raw.code in chosen:
                skipped_duplicates.append({"index": raw.code, "source": raw.source, "action": "date-merged"})
                chosen[raw.code] = merge_raw_indices(chosen[raw.code], raw)
            else:
                chosen[raw.code] = raw

    rows: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] = []
    pe_histories: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    industry_sector_maps: dict[str, dict[str, str]] = {}
    for code in EXPECTED_INDEX_ORDER:
        raw = chosen.get(code)
        if raw is None:
            continue
        group_rows, group_boxes, group_histories, group_coverage = aggregate_index(raw)
        rows.extend(group_rows)
        boxes.extend(group_boxes)
        pe_histories.extend(group_histories)
        coverage.append(group_coverage)
        industry_sector_maps[code] = map_industries_to_sectors(raw)

    valuation_histories: list[dict[str, Any]] = []
    valuation_metadata = None
    if valuation_source is not None:
        valuation_histories, sector_boxes, valuation_metadata = load_stoxx600_sector_valuation(valuation_source)
        replacement_groups = {item["group"] for item in valuation_histories}
        if replacement_groups:
            boxes = [
                item
                for item in boxes
                if not (
                    item["index"] == "SXXP"
                    and item["level"] == "Sector"
                    and item["group"] in replacement_groups
                )
            ]
            boxes.extend(sector_boxes)

    available = [code for code in EXPECTED_INDEX_ORDER if code in chosen]
    missing = [code for code in EXPECTED_INDEX_ORDER if code not in chosen]
    all_starts = [item["startDate"] for item in coverage]
    all_ends = [item["endDate"] for item in coverage]
    data = sanitize(
        {
            "meta": {
                "title": "TOPIX Rotation Monitor",
                "available": available,
                "availableCount": len(available),
                "expectedCount": len(EXPECTED_INDEX_ORDER),
                "missing": missing,
                "excluded": ["TPX"],
                "startDate": max(all_starts) if all_starts else None,
                "endDate": min(all_ends) if all_ends else None,
                "duplicateSourcesSkipped": skipped_duplicates,
                "sectorValuationHistory": valuation_metadata,
                "method": "TOPIX constituent changes aggregated with market-cap weights; 1D and 5D use prior weekday observations and start-date price weights; P/E aggregated through earnings yield.",
            },
            "rows": [[item[field] for field in ROW_FIELDS] for item in rows],
            "industrySectorMap": industry_sector_maps,
            "boxes": [
                [
                    item["index"],
                    item["level"],
                    item["group"],
                    item["low"],
                    item["q1"],
                    item["median"],
                    item["q3"],
                    item["high"],
                    item["current"],
                    item["percentile"],
                ]
                for item in boxes
            ],
            "peHistory": [
                [
                    item["index"],
                    item["level"],
                    item["group"],
                    item["mean"],
                    item["std"],
                    item["values"],
                ]
                for item in pe_histories
            ],
            "sectorPEHistory": [
                [
                    item["index"],
                    item["level"],
                    item["group"],
                    item["mean"],
                    item["std"],
                    item["values"],
                ]
                for item in valuation_histories
            ],
            "coverage": coverage,
        }
    )

    template = template_path.read_text(encoding="utf-8")
    previous_fragment = fragment_path.read_text(encoding="utf-8") if fragment_path.exists() else None
    marker = "__DASHBOARD_DATA__"
    if marker not in template:
        raise RuntimeError(f"Template marker {marker} not found")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if "__D3_JS__" not in template:
        raise RuntimeError("Template marker __D3_JS__ not found")
    d3_source = d3_path.read_text(encoding="utf-8")
    output = template.replace("__D3_JS__", d3_source).replace(marker, payload)
    fragment_path.parent.mkdir(parents=True, exist_ok=True)
    fragment_path.write_text(output, encoding="utf-8")
    if standalone_path is not None and standalone_path.exists():
        wrapper = standalone_path.read_text(encoding="utf-8")
        srcdoc_match = re.search(r'(srcdoc=")(.*?)("\s*>\s*</iframe>)', wrapper, flags=re.DOTALL)
        if srcdoc_match:
            decoded = html.unescape(srcdoc_match.group(2))
            if previous_fragment and previous_fragment in decoded:
                decoded = decoded.replace(previous_fragment, output, 1)
            else:
                fragment_start = decoded.find('<div id="market-rotation-dashboard-17">')
                fragment_end = decoded.rfind("</body>")
                if fragment_start >= 0 and fragment_end > fragment_start:
                    decoded = decoded[:fragment_start] + output + decoded[fragment_end:]
                else:
                    decoded = f"<!doctype html><html><head><meta charset=\"utf-8\"></head><body>{output}</body></html>"
            encoded = html.escape(decoded, quote=True)
            wrapper = wrapper[: srcdoc_match.start(2)] + encoded + wrapper[srcdoc_match.end(2) :]
            standalone_path.write_text(wrapper, encoding="utf-8")
            print(f"standalone={standalone_path}")
    elif standalone_path is not None:
        standalone_path.parent.mkdir(parents=True, exist_ok=True)
        standalone_path.write_text(
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<style>:root{--foreground:#172033;--muted-foreground:#687386;"
            "--border:#dce2ea;--background:#ffffff}body{margin:0;padding:12px;"
            "font-family:Segoe UI,Arial,sans-serif;background:var(--background);"
            "color:var(--foreground)}</style></head><body>"
            + output
            + "</body></html>",
            encoding="utf-8",
        )
        print(f"standalone={standalone_path}")
    print(f"fragment={fragment_path}")
    print(f"indices={','.join(available)}")
    print(f"missing={','.join(missing)}")
    print(f"rows={len(rows)} boxes={len(boxes)} histories={len(pe_histories)} size={fragment_path.stat().st_size}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the available-index market rotation dashboard.")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--d3", type=Path, default=DEFAULT_D3)
    parser.add_argument("--fragment", type=Path, default=DEFAULT_FRAGMENT)
    parser.add_argument("--standalone", type=Path, default=DEFAULT_STANDALONE)
    parser.add_argument("--valuation-source", type=Path, default=DEFAULT_VALUATION_SOURCE)
    parser.add_argument("sources", nargs="*", type=Path, default=DEFAULT_SOURCES)
    args = parser.parse_args()
    build(args.sources or DEFAULT_SOURCES, args.template, args.d3, args.fragment, args.valuation_source, args.standalone)


if __name__ == "__main__":
    main()
