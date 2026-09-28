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
DEFAULT_D3 = DASHBOARD_DIR / "유로존_dashboard" / "d3.v7.9.0.min.js"

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

EUROPE_INDEX_ORDER = [
    "SX5E",
    "SXXP",
    "DAX",
    "CAC",
    "IBEX",
    "UKX",
    "SPX",
    "NDX",
    "INDU",
    "SPTSX60",
    "NKY",
    "TPX500",
    "HSI",
    "SHSZ300",
    "STAR50",
    "AS51",
    "MEXBOL",
]
US_INDEX_ORDER = ["SPX", "NDX", "INDU"]
JAPAN_INDEX_ORDER = ["TPX500"]

REGIONS = {
    "europe": {
        "directory": "유로존_dashboard",
        "title": "Global Equity Rotation Monitor",
        "indices": EUROPE_INDEX_ORDER,
        "fragment": "market_rotation_dashboard.incremental.fragment.html",
        "standalone": "Market_Rotation_Dashboard_17_Indices.html",
        "attribution_start": date(2025, 7, 1),
        "earnings_start": date(2026, 1, 1),
        "valuation_source": "data/Dashboard_Global Equity_2606 (1).xlsx",
    },
    "us": {
        "directory": "US_dashboard",
        "title": "US Equity Rotation Monitor",
        "indices": US_INDEX_ORDER,
        "fragment": "us_rotation_dashboard.incremental.fragment.html",
        "standalone": "US_Rotation_Dashboard.html",
        "attribution_start": date(2025, 7, 1),
        "earnings_start": date(2026, 1, 1),
        "valuation_source": None,
    },
    "japan": {
        "directory": "TOPIX_dashboard",
        "title": "TOPIX Rotation Monitor",
        "indices": JAPAN_INDEX_ORDER,
        "fragment": "topix_rotation_dashboard.incremental.fragment.html",
        "standalone": "TOPIX_Rotation_Dashboard.html",
        "attribution_start": None,
        "earnings_start": None,
        "valuation_source": None,
    },
}

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
    "earningsWeight4",
    "earningsWeight13",
    "earningsWeight6m",
    "earningsWeight1d",
    "earningsWeight5d",
    "priceWeight1d",
    "priceWeight5d",
    "priceWeight1m",
    "priceWeight3m",
    "priceWeight6m",
]

STOCK_FIELDS = [
    "index",
    "sector",
    "industry",
    "ticker",
    "company",
    "currentWeight",
    "price1d",
    "price5d",
    "price1m",
    "price3m",
    "price6m",
    "priceWeight1d",
    "priceWeight5d",
    "priceWeight1m",
    "priceWeight3m",
    "priceWeight6m",
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


def active_market_session_indices(
    dates: list[date],
    prices: np.ndarray,
    min_changed_fraction: float = 0.02,
) -> list[int]:
    """Return dates containing a genuine market-price update.

    The BQL workbook carries the last close across weekends, holidays and a
    not-yet-closed current date.  Treating every weekday as a trading session
    can therefore create a false 0% 1D return.  A date is accepted only when a
    material share of constituents changed versus the last accepted session.
    """
    if not dates or prices.ndim != 2 or prices.shape[1] != len(dates):
        return []

    sessions: list[int] = []
    last_active: int | None = None
    for observation in range(len(dates)):
        current_values = prices[:, observation]
        current_valid = np.isfinite(current_values) & (current_values > 0)
        if last_active is None:
            if current_valid.any():
                sessions.append(observation)
                last_active = observation
            continue

        previous_values = prices[:, last_active]
        valid = current_valid & np.isfinite(previous_values) & (previous_values > 0)
        valid_count = int(valid.sum())
        if valid_count == 0:
            continue
        tolerance = np.maximum(np.abs(previous_values[valid]) * 1e-10, 1e-10)
        changed_count = int((np.abs(current_values[valid] - previous_values[valid]) > tolerance).sum())
        required = max(1, int(math.ceil(valid_count * min_changed_fraction)))
        if changed_count >= required:
            sessions.append(observation)
            last_active = observation
    return sessions


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


def aggregate_earnings_change(
    eps: np.ndarray,
    price: np.ndarray,
    mcap: np.ndarray,
    current: int,
    back: int,
    clip_low: float,
    clip_high: float,
) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """Aggregate EPS estimates after rebuilding each stock's total earnings.

    Implied shares are market cap divided by price.  Multiplying those shares
    by the per-share EPS estimate produces a comparable total-earnings amount
    for each constituent.  The group change is therefore earnings weighted,
    rather than a market-cap-weighted average of per-share EPS changes.
    """
    current_eps = eps[:, current]
    base_eps = eps[:, back]
    current_price = price[:, current]
    base_price = price[:, back]
    current_mcap = mcap[:, current]
    base_mcap = mcap[:, back]
    valid = (
        np.isfinite(current_eps)
        & (current_eps > 0)
        & np.isfinite(base_eps)
        & (base_eps > 0)
        & np.isfinite(current_price)
        & (current_price > 0)
        & np.isfinite(base_price)
        & (base_price > 0)
        & np.isfinite(current_mcap)
        & (current_mcap > 0)
        & np.isfinite(base_mcap)
        & (base_mcap > 0)
    )
    base_earnings = np.full(len(base_eps), np.nan, dtype=np.float64)
    current_earnings = np.full(len(current_eps), np.nan, dtype=np.float64)
    changes = np.full(len(current_eps), np.nan, dtype=np.float64)
    if not valid.any():
        return np.nan, changes, base_earnings, valid
    base_shares = base_mcap[valid] / base_price[valid]
    current_shares = current_mcap[valid] / current_price[valid]
    base_earnings[valid] = base_eps[valid] * base_shares
    current_earnings[valid] = current_eps[valid] * current_shares
    valid &= (
        np.isfinite(base_earnings)
        & (base_earnings > 0)
        & np.isfinite(current_earnings)
        & (current_earnings > 0)
    )
    if not valid.any():
        return np.nan, changes, base_earnings, valid
    changes[valid] = np.clip(
        current_earnings[valid] / base_earnings[valid] - 1.0,
        clip_low,
        clip_high,
    )
    denominator = float(base_earnings[valid].sum())
    value = (
        float(np.sum(base_earnings[valid] * changes[valid]) / denominator)
        if denominator > 0
        else np.nan
    )
    return value, changes, base_earnings, valid


def aggregate_forward_earnings_growth(
    fy1_eps: np.ndarray,
    fy2_eps: np.ndarray,
    price: np.ndarray,
    mcap: np.ndarray,
) -> float:
    """Return FY2 versus FY1 growth from summed constituent earnings."""
    valid = (
        np.isfinite(fy1_eps)
        & (fy1_eps > 0)
        & np.isfinite(fy2_eps)
        & (fy2_eps > 0)
        & np.isfinite(price)
        & (price > 0)
        & np.isfinite(mcap)
        & (mcap > 0)
    )
    if not valid.any():
        return np.nan
    shares = mcap[valid] / price[valid]
    fy1_earnings = fy1_eps[valid] * shares
    fy2_earnings = fy2_eps[valid] * shares
    changes = np.clip(fy2_earnings / fy1_earnings - 1.0, -1.0, 3.0)
    denominator = float(fy1_earnings.sum())
    return float(np.sum(fy1_earnings * changes) / denominator) if denominator > 0 else np.nan


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
    attribution_start: date,
    earnings_start: date,
) -> dict[str, Any]:
    clean_mask = np.isfinite(series) & (series > 0)
    clean = series[clean_mask]
    mean = float(clean.mean()) if clean.size else np.nan
    std = float(clean.std()) if clean.size else np.nan

    eps_contribution = np.full(len(dates), np.nan, dtype=np.float64)
    pe_contribution = np.full(len(dates), np.nan, dtype=np.float64)
    price_return = np.full(len(dates), np.nan, dtype=np.float64)
    baseline_candidates = [i for i, observation_date in enumerate(dates) if observation_date >= attribution_start]
    baseline: int | None = None
    if baseline_candidates:
        baseline = baseline_candidates[0]
        base_price = price_values[:, baseline]
        base_weight = market_caps[:, baseline]
        base_price_valid = (
            np.isfinite(base_price)
            & (base_price > 0)
            & np.isfinite(base_weight)
            & (base_weight > 0)
        )
        for observation in range(baseline, len(dates)):
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
            earnings_change, _, _, earnings_valid = aggregate_earnings_change(
                eps_values,
                price_values,
                market_caps,
                observation,
                baseline,
                -0.95,
                5.0,
            )
            if not earnings_valid.any() or not np.isfinite(earnings_change) or not np.isfinite(price_return[observation]):
                continue
            if earnings_change <= -0.999999:
                continue
            pe_change = (1.0 + price_return[observation]) / (1.0 + earnings_change) - 1.0
            cross = earnings_change * pe_change
            eps_contribution[observation] = earnings_change + 0.5 * cross
            pe_contribution[observation] = pe_change + 0.5 * cross

    fy1_change = np.full(len(dates), np.nan, dtype=np.float64)
    fy2_change = np.full(len(dates), np.nan, dtype=np.float64)
    fy1_breadth = np.full(len(dates), np.nan, dtype=np.float64)
    fy2_breadth = np.full(len(dates), np.nan, dtype=np.float64)
    earnings_candidates = [i for i, observation_date in enumerate(dates) if observation_date >= earnings_start]
    earnings_baseline: int | None = None
    if earnings_candidates:
        earnings_baseline = earnings_candidates[0]

        def cumulative_change(values: np.ndarray, observation: int) -> float:
            change, _, _, _ = aggregate_earnings_change(
                values,
                price_values,
                market_caps,
                observation,
                earnings_baseline,
                -1.0,
                3.0,
            )
            return change

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
    active_sessions: list[int] | None = None,
    attribution_start: date | None = None,
    earnings_start: date | None = None,
    strict_lookback: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metrics = {key: value[member_idx, :] for key, value in raw.metrics.items()}
    dates = raw.dates
    current = nearest_date_index(dates, dates[-1])
    back4 = nearest_date_index(dates, dates[current] - timedelta(days=28))
    back13 = nearest_date_index(dates, dates[current] - timedelta(days=91))
    back1m = back4
    back3m = back13
    back6m = nearest_date_index(dates, dates[current] - timedelta(days=182))
    sessions = active_sessions or [current]
    short_current = sessions[-1]
    back1d = sessions[max(0, len(sessions) - 2)]
    back5d = sessions[max(0, len(sessions) - 6)]
    mcap = metrics["mcap"]

    eps4, eps4_stock, eps4_base_earnings, eps4_valid = aggregate_earnings_change(
        metrics["eps12"], metrics["price"], mcap, current, back4, -1.0, 1.0
    )
    eps13, eps13_stock, eps13_base_earnings, eps13_valid = aggregate_earnings_change(
        metrics["eps12"], metrics["price"], mcap, current, back13, -1.0, 1.0
    )
    eps6m, _, eps6_base_earnings, eps6_valid = aggregate_earnings_change(
        metrics["eps12"], metrics["price"], mcap, current, back6m, -1.0, 1.0
    )
    price1m, _, price1_base_mcap, price1_valid = weighted_change(
        metrics["price"], mcap, current, back1m, False, -0.95, 5.0, True
    )
    price3m, _, price3_base_mcap, price3_valid = weighted_change(
        metrics["price"], mcap, current, back3m, False, -0.95, 5.0, True
    )
    price6m, _, price6_base_mcap, price6_valid = weighted_change(
        metrics["price"], mcap, current, back6m, False, -0.95, 5.0, True
    )
    eps1d, _, eps1_base_earnings, eps1_valid = aggregate_earnings_change(
        metrics["eps12"], metrics["price"], mcap, short_current, back1d, -1.0, 1.0
    )
    eps5d, _, eps5_base_earnings, eps5_valid = aggregate_earnings_change(
        metrics["eps12"], metrics["price"], mcap, short_current, back5d, -1.0, 1.0
    )
    price1d, _, price1d_base_mcap, price1d_valid = weighted_change(
        metrics["price"], mcap, short_current, back1d, False, -0.95, 5.0, True
    )
    price5d, _, price5d_base_mcap, price5d_valid = weighted_change(
        metrics["price"], mcap, short_current, back5d, False, -0.95, 5.0, True
    )

    # A short new feed must not be relabeled as a full calendar lookback.
    if strict_lookback and dates[0] > dates[current] - timedelta(days=28):
        eps4 = np.nan
        price1m = np.nan
        eps4_valid = np.zeros_like(eps4_valid, dtype=bool)
        price1_valid = np.zeros_like(price1_valid, dtype=bool)
    if strict_lookback and dates[0] > dates[current] - timedelta(days=91):
        eps13 = np.nan
        price3m = np.nan
        eps13_valid = np.zeros_like(eps13_valid, dtype=bool)
        price3_valid = np.zeros_like(price3_valid, dtype=bool)
    if strict_lookback and dates[0] > dates[current] - timedelta(days=182):
        eps6m = np.nan
        price6m = np.nan
        eps6_valid = np.zeros_like(eps6_valid, dtype=bool)
        price6_valid = np.zeros_like(price6_valid, dtype=bool)

    pe_series = harmonic_pe(metrics["pe"], mcap)
    pe_stats = pe_box_stats(pe_series)
    current_mcap = mcap[:, current]
    current_pe = pe_series[current] if current < len(pe_series) else np.nan

    eps4_per_share = np.full(len(member_idx), np.nan, dtype=np.float64)
    eps13_per_share = np.full(len(member_idx), np.nan, dtype=np.float64)
    eps4_per_share[eps4_valid] = (
        metrics["eps12"][eps4_valid, current] / metrics["eps12"][eps4_valid, back4] - 1.0
    )
    eps13_per_share[eps13_valid] = (
        metrics["eps12"][eps13_valid, current] / metrics["eps12"][eps13_valid, back13] - 1.0
    )
    breadth4 = float(np.mean(eps4_per_share[eps4_valid] > 0)) if eps4_valid.any() else np.nan
    breadth13 = float(np.mean(eps13_per_share[eps13_valid] > 0)) if eps13_valid.any() else np.nan
    contributions = np.zeros(len(member_idx))
    if eps13_valid.any():
        valid_weight_sum = eps13_base_earnings[eps13_valid].sum()
        if valid_weight_sum > 0:
            contributions[eps13_valid] = eps13_base_earnings[eps13_valid] / valid_weight_sum * eps13_stock[eps13_valid]
    abs_total = np.abs(contributions).sum()
    top5 = float(np.sort(np.abs(contributions))[-5:].sum() / abs_total) if abs_total > 0 else np.nan

    fy1 = metrics["eps_fy1"][:, current]
    fy2 = metrics["eps_fy2"][:, current]
    fy2_growth = aggregate_forward_earnings_growth(
        fy1,
        fy2,
        metrics["price"][:, current],
        current_mcap,
    )

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
        "fy2Growth": fy2_growth,
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
        "_earningsBase4": float(eps4_base_earnings[eps4_valid].sum()) if eps4_valid.any() else np.nan,
        "_earningsBase13": float(eps13_base_earnings[eps13_valid].sum()) if eps13_valid.any() else np.nan,
        "_earningsBase6m": float(eps6_base_earnings[eps6_valid].sum()) if eps6_valid.any() else np.nan,
        "_earningsBase1d": float(eps1_base_earnings[eps1_valid].sum()) if eps1_valid.any() else np.nan,
        "_earningsBase5d": float(eps5_base_earnings[eps5_valid].sum()) if eps5_valid.any() else np.nan,
        "_priceBase1d": float(price1d_base_mcap[price1d_valid].sum()) if price1d_valid.any() else np.nan,
        "_priceBase5d": float(price5d_base_mcap[price5d_valid].sum()) if price5d_valid.any() else np.nan,
        "_priceBase1m": float(price1_base_mcap[price1_valid].sum()) if price1_valid.any() else np.nan,
        "_priceBase3m": float(price3_base_mcap[price3_valid].sum()) if price3_valid.any() else np.nan,
        "_priceBase6m": float(price6_base_mcap[price6_valid].sum()) if price6_valid.any() else np.nan,
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
        attribution_start or dates[0],
        earnings_start or dates[0],
    )
    return row, box, history


def build_stock_rows(raw: RawIndex, strict_lookback: bool = False) -> list[dict[str, Any]]:
    """Build compact constituent return rows without stock-level P/E histories.

    Each period's contribution reconciles to the reconstructed index price
    return because its weight uses the same valid-universe, start-date market
    capitalization as :func:`weighted_change`.
    """
    dates = raw.dates
    if not dates or not raw.tickers:
        return []

    prices = raw.metrics["price"]
    mcap = raw.metrics["mcap"]
    current = nearest_date_index(dates, dates[-1])
    sessions = active_market_session_indices(dates, prices)
    if not sessions:
        return []
    short_current = sessions[-1]
    period_indices = {
        "1d": (short_current, sessions[max(0, len(sessions) - 2)]),
        "5d": (short_current, sessions[max(0, len(sessions) - 6)]),
        "1m": (current, nearest_date_index(dates, dates[current] - timedelta(days=28))),
        "3m": (current, nearest_date_index(dates, dates[current] - timedelta(days=91))),
        "6m": (current, nearest_date_index(dates, dates[current] - timedelta(days=182))),
    }

    period_data: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for period, (end_index, start_index) in period_indices.items():
        _, changes, base_mcap, valid = weighted_change(
            prices, mcap, end_index, start_index, False, -0.95, 5.0, True
        )
        required_days = {"1m": 28, "3m": 91, "6m": 182}.get(period)
        if required_days is not None and strict_lookback and dates[0] > dates[current] - timedelta(days=required_days):
            changes = np.full(len(raw.tickers), np.nan, dtype=np.float64)
            valid = np.zeros(len(raw.tickers), dtype=bool)
        weights = np.full(len(raw.tickers), np.nan, dtype=np.float64)
        denominator = float(base_mcap[valid].sum()) if valid.any() else 0.0
        if denominator > 0:
            weights[valid] = base_mcap[valid] / denominator
        period_data[period] = (changes, weights)

    current_mcap = mcap[:, current]
    current_valid = np.isfinite(current_mcap) & (current_mcap > 0)
    current_total = float(current_mcap[current_valid].sum()) if current_valid.any() else 0.0
    rows: list[dict[str, Any]] = []
    for stock_index, ticker in enumerate(raw.tickers):
        row: dict[str, Any] = {
            "index": raw.code,
            "sector": raw.sectors[stock_index] if stock_index < len(raw.sectors) else "",
            "industry": raw.industries[stock_index] if stock_index < len(raw.industries) else "",
            "ticker": ticker,
            "company": raw.companies[stock_index] if stock_index < len(raw.companies) else "",
            "currentWeight": (
                float(current_mcap[stock_index] / current_total)
                if current_total > 0 and current_valid[stock_index]
                else np.nan
            ),
        }
        for period, (changes, weights) in period_data.items():
            row[f"price{period}"] = (
                float(changes[stock_index]) if np.isfinite(changes[stock_index]) else np.nan
            )
            row[f"priceWeight{period}"] = (
                float(weights[stock_index]) if np.isfinite(weights[stock_index]) else np.nan
            )
        rows.append(row)
    return rows


def aggregate_index(
    raw: RawIndex,
    attribution_start: date | None = None,
    earnings_start: date | None = None,
    strict_lookback: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] = []
    histories: list[dict[str, Any]] = []
    all_members = np.arange(len(raw.tickers), dtype=int)
    active_sessions = active_market_session_indices(raw.dates, raw.metrics["price"])
    summary, box, history = aggregate_group(raw, all_members, "Index", "All", active_sessions, attribution_start, earnings_start, strict_lookback)
    rows.append(summary)
    boxes.append(box)
    histories.append(history)

    for level, labels in (("Sector", raw.sectors), ("Industry", raw.industries)):
        label_array = np.asarray(labels, dtype=object)
        for group in sorted({str(x) for x in label_array if str(x).strip()}):
            members = np.flatnonzero(label_array == group)
            if members.size == 0:
                continue
            row, group_box, group_history = aggregate_group(raw, members, level, group, active_sessions, attribution_start, earnings_start, strict_lookback)
            rows.append(row)
            boxes.append(group_box)
            histories.append(group_history)

    base_pairs = (
        ("earningsWeight4", "_earningsBase4"),
        ("earningsWeight13", "_earningsBase13"),
        ("earningsWeight6m", "_earningsBase6m"),
        ("earningsWeight1d", "_earningsBase1d"),
        ("earningsWeight5d", "_earningsBase5d"),
        ("priceWeight1d", "_priceBase1d"),
        ("priceWeight5d", "_priceBase5d"),
        ("priceWeight1m", "_priceBase1m"),
        ("priceWeight3m", "_priceBase3m"),
        ("priceWeight6m", "_priceBase6m"),
    )
    for weight_field, base_field in base_pairs:
        index_base = summary.get(base_field, np.nan)
        for row in rows:
            group_base = row.get(base_field, np.nan)
            row[weight_field] = (
                float(group_base / index_base)
                if np.isfinite(group_base) and np.isfinite(index_base) and index_base > 0
                else np.nan
            )

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
        "activePriceEndDate": raw.dates[active_sessions[-1]].isoformat() if active_sessions else latest.isoformat(),
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


def standalone_document(fragment: str) -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<style>:root{--foreground:#172033;--muted-foreground:#687386;"
        "--border:#dce2ea;--background:#ffffff}body{margin:0;padding:12px;"
        "font-family:Segoe UI,Arial,sans-serif;background:var(--background);"
        "color:var(--foreground)}</style></head><body>"
        + fragment
        + "</body></html>"
    )


def recover_template_from_standalone(
    template_path: Path,
    standalone_path: Path,
    d3_path: Path,
) -> None:
    """Recover a missing live template from the latest generated dashboard.

    The legacy standalone keeps the complete current dashboard in iframe
    ``srcdoc``.  Restoring only the two build markers avoids falling back to an
    old archive and preserves every later UI change.
    """
    if template_path.exists():
        return
    if not standalone_path.exists():
        raise FileNotFoundError(template_path)
    wrapper = standalone_path.read_text(encoding="utf-8")
    match = re.search(r'srcdoc="(.*?)"\s*>\s*</iframe>', wrapper, flags=re.DOTALL)
    if not match:
        raise FileNotFoundError(
            f"Missing template and standalone srcdoc could not be recovered: {template_path}"
        )
    decoded = html.unescape(match.group(1))
    fragment_start = decoded.find('<div id="market-rotation-dashboard-17">')
    fragment_end = decoded.rfind("</body>")
    if fragment_start < 0 or fragment_end <= fragment_start:
        raise RuntimeError("Dashboard fragment was not found in the standalone HTML")
    template = decoded[fragment_start:fragment_end]

    d3_source = d3_path.read_text(encoding="utf-8")
    if template.count(d3_source) != 1:
        raise RuntimeError("Embedded D3 source could not be identified uniquely")
    template = template.replace(d3_source, "__D3_JS__", 1)
    template, replacements = re.subn(
        r"const DATA\s*=\s*.*?;\s*(?=const rowFields\s*=)",
        "const DATA = __DASHBOARD_DATA__;\n    ",
        template,
        count=1,
        flags=re.DOTALL,
    )
    if replacements != 1:
        raise RuntimeError("Embedded dashboard data could not be replaced with a build marker")
    if template.count("__D3_JS__") != 1 or template.count("__DASHBOARD_DATA__") != 1:
        raise RuntimeError("Recovered template markers are invalid")
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(template, encoding="utf-8")
    print(f"template_recovered={template_path}")


def load_sources(sources: list[Path]) -> tuple[dict[str, RawIndex], list[dict[str, str]]]:
    """Parse the master once, then reuse the same observations for every region."""
    chosen: dict[str, RawIndex] = {}
    skipped_duplicates: list[dict[str, str]] = []
    for source in sources:
        if not source.exists():
            raise FileNotFoundError(source)
        for raw in iter_raw_indices(source):
            if raw.code == "TPX":
                continue
            if raw.code in chosen:
                skipped_duplicates.append({"index": raw.code, "source": raw.source, "action": "date-merged"})
                chosen[raw.code] = merge_raw_indices(chosen[raw.code], raw)
            else:
                chosen[raw.code] = raw
    return chosen, skipped_duplicates


def build(
    chosen: dict[str, RawIndex],
    skipped_duplicates: list[dict[str, str]],
    region: str,
    template_path: Path,
    d3_path: Path,
    fragment_path: Path,
    valuation_source: Path | None,
    standalone_path: Path,
) -> dict[str, Any]:
    config = REGIONS[region]
    expected_index_order = config["indices"]

    rows: list[dict[str, Any]] = []
    stock_rows: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] = []
    pe_histories: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    industry_sector_maps: dict[str, dict[str, str]] = {}
    for code in expected_index_order:
        raw = chosen.get(code)
        if raw is None:
            continue
        group_rows, group_boxes, group_histories, group_coverage = aggregate_index(
            raw, config["attribution_start"], config["earnings_start"], True
        )
        rows.extend(group_rows)
        stock_rows.extend(build_stock_rows(raw, True))
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

    available = [code for code in expected_index_order if code in chosen]
    missing = [code for code in expected_index_order if code not in chosen]
    if not available:
        raise ValueError(f"{region} 대시보드에 필요한 지수가 원본에 없습니다: {missing}")
    all_starts = [item["startDate"] for item in coverage]
    all_ends = [item["endDate"] for item in coverage]
    data = sanitize(
        {
            "meta": {
                "title": config["title"],
                "available": available,
                "availableCount": len(available),
                "expectedCount": len(expected_index_order),
                "missing": missing,
                "excluded": ["TPX"],
                "startDate": min(all_starts) if all_starts else None,
                "endDate": max(all_ends) if all_ends else None,
                "duplicateSourcesSkipped": skipped_duplicates,
                "sectorValuationHistory": valuation_metadata,
                "method": "EPS estimates are converted to constituent earnings using implied shares (market cap divided by price) and aggregated with base-period earnings weights; 1D and 5D use the latest active price session and prior active sessions, with EPS aligned to the same dates; price returns use start-date market-cap weights; P/E is total market cap divided by total earnings.",
            },
            "rows": [[item[field] for field in ROW_FIELDS] for item in rows],
            "stockRows": [[item[field] for field in STOCK_FIELDS] for item in stock_rows],
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
        else:
            # New dashboards use a direct document, not a legacy srcdoc iframe.
            # Refresh it on every run instead of freezing after its first build.
            standalone_path.write_text(standalone_document(output), encoding="utf-8")
            print(f"standalone={standalone_path}")
    elif standalone_path is not None:
        standalone_path.parent.mkdir(parents=True, exist_ok=True)
        standalone_path.write_text(standalone_document(output), encoding="utf-8")
        print(f"standalone={standalone_path}")
    print(f"region={region}")
    print(f"fragment={fragment_path}")
    print(f"indices={','.join(available)}")
    print(f"missing={','.join(missing)}")
    print(f"rows={len(rows)} boxes={len(boxes)} histories={len(pe_histories)} size={fragment_path.stat().st_size}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Europe, US, and Japan dashboards from one BQuant master.")
    parser.add_argument("--region", choices=("all", *REGIONS), default="all")
    parser.add_argument("--asset-root", type=Path, default=DASHBOARD_DIR, help="Dashboard directory containing the region templates and D3 asset")
    parser.add_argument("--output-root", type=Path, default=None, help="Output directory; defaults to --asset-root")
    parser.add_argument("--europe-template", type=Path, default=None, help="Optional Europe template override for validation")
    parser.add_argument("--us-template", type=Path, default=None, help="Optional US template override for validation")
    parser.add_argument("--japan-template", type=Path, default=None, help="Optional Japan template override for validation")
    parser.add_argument("sources", nargs="*", type=Path)
    args = parser.parse_args()
    asset_root = args.asset_root.resolve()
    output_root = (args.output_root or asset_root).resolve()
    sources = args.sources or DEFAULT_SOURCES
    chosen, skipped_duplicates = load_sources(sources)
    regions = list(REGIONS) if args.region == "all" else [args.region]
    d3_path = asset_root / "유로존_dashboard" / "d3.v7.9.0.min.js"
    for region in regions:
        config = REGIONS[region]
        directory = config["directory"]
        overrides = {"europe": args.europe_template, "us": args.us_template, "japan": args.japan_template}
        template_path = overrides[region] or asset_root / directory / "market_rotation_dashboard.template.html"
        valuation_source = asset_root / directory / config["valuation_source"] if config["valuation_source"] else None
        standalone_path = output_root / directory / config["standalone"]
        recover_template_from_standalone(template_path, standalone_path, d3_path)
        build(
            chosen,
            skipped_duplicates,
            region,
            template_path,
            d3_path,
            output_root / directory / config["fragment"],
            valuation_source,
            standalone_path,
        )


if __name__ == "__main__":
    main()
