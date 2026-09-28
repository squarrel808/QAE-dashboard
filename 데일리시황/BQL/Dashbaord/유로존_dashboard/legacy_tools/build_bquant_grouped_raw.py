#!/usr/bin/env python3
"""Build index/sector/industry/stock daily datasets from Bloomberg BQL cache.

The input workbook is the refreshed Bquant_All_19_Raw template.  Bloomberg
legacy-array results are read directly from the cached OOXML values, so the
script does not require the Bloomberg Excel add-in.

Aggregation conventions
-----------------------
* MarketCap: sum of positive constituent market caps.
* PE_12MF: aggregate through earnings yield:
      sum(valid market cap) / sum(valid market cap / positive PE)
* EPS, Price, ROE and OPM: same-day market-cap-weighted average, with weights
  re-normalized over constituents that have a valid value for that metric.
* Missing/error observations: excluded only from the affected metric.
"""

from __future__ import annotations

import argparse
import math
import re
import zipfile
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"m": MAIN_NS, "r": OFFICE_REL_NS}

METRICS = [
    "PE_12MF",
    "EPS_12MF",
    "EPS_FY1",
    "EPS_FY2",
    "Price",
    "MarketCap",
    "ROE_Current",
    "OPM_Current",
    "ROE_12MF",
    "OPM_12MF",
]

WA_METRICS = [
    "EPS_12MF",
    "EPS_FY1",
    "EPS_FY2",
    "Price",
    "ROE_Current",
    "OPM_Current",
    "ROE_12MF",
    "OPM_12MF",
]

CURRENCY_BY_INDEX = {
    "SX5E": "EUR",
    "INDU": "USD",
    "SPX": "USD",
    "NDX": "USD",
    "SPTSX60": "CAD",
    "IBOV": "BRL",
    "UKX": "GBP",
    "CAC": "EUR",
    "DAX": "EUR",
    "IBEX": "EUR",
    "AEX": "EUR",
    "NKY": "JPY",
    "HSI": "HKD",
    "TPX": "JPY",
    "SHSZ300": "CNY",
    "STAR50": "CNY",
    "AS51": "AUD",
    "MEXBOL": "MXN",
    "SXXP": "EUR",
}


def column_number(column: str) -> int:
    number = 0
    for char in column:
        number = number * 26 + ord(char) - 64
    return number


def column_name(number: int) -> str:
    name = ""
    while number:
        name = chr((number - 1) % 26 + 65) + name
        number = (number - 1) // 26
    return name


def split_address(address: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Z]+)(\d+)", address)
    if not match:
        raise ValueError(f"Invalid cell address: {address}")
    return column_number(match.group(1)), int(match.group(2))


def split_range(address: str) -> tuple[int, int, int, int]:
    start, end = address.split(":")
    start_col, start_row = split_address(start)
    end_col, end_row = split_address(end)
    return start_col, start_row, end_col, end_row


def excel_date(value: Any) -> pd.Timestamp | None:
    if not isinstance(value, (int, float, np.integer, np.floating)):
        return None
    if not math.isfinite(float(value)) or not 20_000 <= float(value) <= 80_000:
        return None
    return pd.Timestamp(datetime(1899, 12, 30) + timedelta(days=float(value))).normalize()


class CachedWorkbook:
    """Minimal OOXML reader focused on cached BQL array results."""

    def __init__(self, path: Path):
        self.path = path
        self.zip = zipfile.ZipFile(path)
        broken = self.zip.testzip()
        if broken:
            raise ValueError(f"Corrupt ZIP entry in workbook: {broken}")
        self.shared_strings = self._read_shared_strings()
        self.sheet_paths = self._read_sheet_paths()

    def close(self) -> None:
        self.zip.close()

    def _read_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self.zip.namelist():
            return []
        root = ET.fromstring(self.zip.read("xl/sharedStrings.xml"))
        values: list[str] = []
        for item in root.findall("m:si", NS):
            values.append("".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")))
        return values

    def _read_sheet_paths(self) -> OrderedDict[str, str]:
        workbook = ET.fromstring(self.zip.read("xl/workbook.xml"))
        relationships = ET.fromstring(self.zip.read("xl/_rels/workbook.xml.rels"))
        relationship_map = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        paths: OrderedDict[str, str] = OrderedDict()
        for sheet in workbook.find("m:sheets", NS):
            relationship_id = sheet.attrib[f"{{{OFFICE_REL_NS}}}id"]
            target = relationship_map[relationship_id]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            paths[sheet.attrib["name"]] = target
        return paths

    def read_cells(self, sheet_name: str) -> dict[str, dict[str, Any]]:
        root = ET.fromstring(self.zip.read(self.sheet_paths[sheet_name]))
        cells: dict[str, dict[str, Any]] = {}
        for cell in root.findall(".//m:c", NS):
            formula = cell.find("m:f", NS)
            cached = cell.find("m:v", NS)
            inline = cell.find("m:is", NS)
            cell_type = cell.attrib.get("t")
            raw = None if cached is None else cached.text
            value: Any = None
            if cell_type == "e":
                value = None
            elif cell_type == "s" and raw is not None:
                value = self.shared_strings[int(raw)]
            elif cell_type == "inlineStr" and inline is not None:
                value = "".join(node.text or "" for node in inline.iter(f"{{{MAIN_NS}}}t"))
            elif cell_type in {"str", "d"}:
                value = raw
            elif raw not in (None, ""):
                try:
                    value = float(raw)
                except ValueError:
                    value = raw
            cells[cell.attrib["r"]] = {
                "type": cell_type,
                "raw": raw,
                "value": value,
                "formula": None if formula is None else formula.text,
                "formula_attributes": {} if formula is None else dict(formula.attrib),
            }
        return cells


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text == "0":
        return fallback
    return text


def finite_number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    return number if math.isfinite(number) else np.nan


def parse_index_sheet(
    workbook: CachedWorkbook,
    sheet_name: str,
) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    cells = workbook.read_cells(sheet_name)
    index_code = sheet_name.removesuffix(" Raw")
    title = clean_text(cells.get("A1", {}).get("value"), index_code)
    title_match = re.match(r"(.+?)\s*\(([^)]+ Index)\)", title)
    index_name = title_match.group(1).strip() if title_match else index_code
    index_ticker = title_match.group(2).strip() if title_match else f"{index_code} Index"
    currency = CURRENCY_BY_INDEX.get(index_code, "LOCAL")

    arrays: list[tuple[int, str, str, str]] = []
    for address, cell in cells.items():
        attributes = cell["formula_attributes"]
        if address.startswith("G") and attributes.get("t") == "array":
            arrays.append(
                (
                    split_address(address)[1],
                    address,
                    attributes["ref"],
                    cell["formula"] or "",
                )
            )
    arrays.sort()
    if len(arrays) != len(METRICS):
        raise ValueError(f"{sheet_name}: expected 10 BQL arrays, found {len(arrays)}")

    first_start_col, first_start_row, _, first_end_row = split_range(arrays[0][2])
    member_tickers = [
        clean_text(cells.get(f"G{row}", {}).get("value"))
        for row in range(first_start_row + 1, first_end_row + 1)
    ]
    member_tickers = [ticker for ticker in member_tickers if ticker]
    if not member_tickers:
        raise ValueError(f"{sheet_name}: no cached constituent IDs found")

    metadata: dict[str, dict[str, str]] = {}
    for row in range(8, first_start_row):
        ticker = clean_text(cells.get(f"A{row}", {}).get("value"))
        if not ticker:
            continue
        metadata[ticker] = {
            "Security_Name": clean_text(cells.get(f"B{row}", {}).get("value"), ticker),
            "GICS_Sector": clean_text(cells.get(f"C{row}", {}).get("value"), "Unclassified"),
            "GICS_Industry_Group": clean_text(
                cells.get(f"D{row}", {}).get("value"), "Unclassified"
            ),
        }

    block_data: dict[str, dict[tuple[str, pd.Timestamp], float]] = {}
    all_dates: set[pd.Timestamp] = set()
    invalid_date_headers = 0
    metric_diagnostics: list[dict[str, Any]] = []

    for metric, (_, _, reference, formula) in zip(METRICS, arrays):
        start_col, start_row, end_col, end_row = split_range(reference)
        valid_columns: list[tuple[int, pd.Timestamp]] = []
        for col in range(start_col + 1, end_col + 1):
            date = excel_date(cells.get(f"{column_name(col)}{start_row}", {}).get("value"))
            if date is None:
                invalid_date_headers += 1
                continue
            valid_columns.append((col, date))
            all_dates.add(date)

        values: dict[tuple[str, pd.Timestamp], float] = {}
        error_count = 0
        for row in range(start_row + 1, end_row + 1):
            ticker = clean_text(cells.get(f"G{row}", {}).get("value"))
            if not ticker:
                continue
            for col, date in valid_columns:
                cell = cells.get(f"{column_name(col)}{row}")
                number = finite_number(None if cell is None else cell.get("value"))
                if math.isnan(number):
                    error_count += 1
                values[(ticker, date)] = number
        block_data[metric] = values
        metric_diagnostics.append(
            {
                "Index_Code": index_code,
                "Source_Sheet": sheet_name,
                "Metric": metric,
                "BQL_Formula": formula,
                "Missing_or_Error": error_count,
            }
        )

    dates = sorted(all_dates)
    if not dates:
        raise ValueError(f"{sheet_name}: no valid cached dates found")

    row_count = len(member_tickers) * len(dates)
    stock = pd.DataFrame(
        {
            "Date": np.tile(np.array(dates, dtype="datetime64[ns]"), len(member_tickers)),
            "Ticker": np.repeat(member_tickers, len(dates)),
        }
    )
    stock.insert(1, "Index_Code", index_code)
    stock.insert(2, "Index_Ticker", index_ticker)
    stock.insert(3, "Index_Name", index_name)
    stock.insert(4, "Currency", currency)
    stock.insert(6, "Security_Name", stock["Ticker"].map(lambda x: metadata.get(x, {}).get("Security_Name", x)))
    stock.insert(
        7,
        "GICS_Sector",
        stock["Ticker"].map(lambda x: metadata.get(x, {}).get("GICS_Sector", "Unclassified")),
    )
    stock.insert(
        8,
        "GICS_Industry_Group",
        stock["Ticker"].map(
            lambda x: metadata.get(x, {}).get("GICS_Industry_Group", "Unclassified")
        ),
    )
    stock.insert(9, "Source_Sheet", sheet_name)

    keys = list(zip(stock["Ticker"], pd.to_datetime(stock["Date"])))
    for metric in METRICS:
        values = block_data[metric]
        stock[metric] = np.fromiter(
            (values.get((ticker, pd.Timestamp(date)), np.nan) for ticker, date in keys),
            dtype=float,
            count=row_count,
        )

    metadata_row = {
        "Index_Code": index_code,
        "Index_Ticker": index_ticker,
        "Index_Name": index_name,
        "Currency": currency,
        "Source_Sheet": sheet_name,
        "Member_Count": len(member_tickers),
        "Start_Date": dates[0],
        "End_Date": dates[-1],
        "Date_Count": len(dates),
        "Stock_Date_Rows": row_count,
        "Invalid_Date_Headers_Ignored": invalid_date_headers,
    }
    return stock, metadata_row, metric_diagnostics


def add_stock_weights(stock: pd.DataFrame) -> pd.DataFrame:
    market_cap = stock["MarketCap"].where(stock["MarketCap"].gt(0) & stock["MarketCap"].notna())
    stock = stock.copy()
    stock["_Valid_MarketCap"] = market_cap

    index_total = stock.groupby(["Date", "Index_Code"], dropna=False)["_Valid_MarketCap"].transform("sum")
    sector_total = stock.groupby(
        ["Date", "Index_Code", "GICS_Sector"], dropna=False
    )["_Valid_MarketCap"].transform("sum")
    industry_total = stock.groupby(
        ["Date", "Index_Code", "GICS_Sector", "GICS_Industry_Group"], dropna=False
    )["_Valid_MarketCap"].transform("sum")

    stock["Index_Weight"] = market_cap.div(index_total.where(index_total.gt(0)))
    stock["Sector_Weight"] = market_cap.div(sector_total.where(sector_total.gt(0)))
    stock["Industry_Weight"] = market_cap.div(industry_total.where(industry_total.gt(0)))
    return stock.drop(columns=["_Valid_MarketCap"])


def aggregate_groups(stock: pd.DataFrame, grouping: list[str]) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    grouped = stock.groupby(grouping, dropna=False, sort=True)
    for key, group in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(grouping, key))
        market_cap = pd.to_numeric(group["MarketCap"], errors="coerce")
        cap_valid = market_cap.notna() & np.isfinite(market_cap) & market_cap.gt(0)
        total_cap = float(market_cap[cap_valid].sum()) if cap_valid.any() else np.nan

        row["Stock_Count"] = int(group["Ticker"].nunique())
        row["MarketCap"] = total_cap

        pe = pd.to_numeric(group["PE_12MF"], errors="coerce")
        pe_valid = cap_valid & pe.notna() & np.isfinite(pe) & pe.gt(0)
        if pe_valid.any():
            valid_cap = market_cap[pe_valid]
            denominator = float((valid_cap / pe[pe_valid]).sum())
            row["PE_12MF"] = float(valid_cap.sum() / denominator) if denominator > 0 else np.nan
        else:
            row["PE_12MF"] = np.nan

        for metric in WA_METRICS:
            values = pd.to_numeric(group[metric], errors="coerce")
            valid = cap_valid & values.notna() & np.isfinite(values)
            if valid.any():
                weights = market_cap[valid]
                row[metric] = float((weights * values[valid]).sum() / weights.sum())
            else:
                row[metric] = np.nan

        eps = pd.to_numeric(group["EPS_12MF"], errors="coerce")
        eps_valid = cap_valid & eps.notna() & np.isfinite(eps)
        row["PE_Valid_Count"] = int(pe_valid.sum())
        row["EPS_12MF_Valid_Count"] = int(eps_valid.sum())
        row["PE_MCap_Coverage"] = (
            float(market_cap[pe_valid].sum() / total_cap)
            if pe_valid.any() and total_cap > 0
            else np.nan
        )
        row["EPS_12MF_MCap_Coverage"] = (
            float(market_cap[eps_valid].sum() / total_cap)
            if eps_valid.any() and total_cap > 0
            else np.nan
        )
        output.append(row)

    return pd.DataFrame(output)


def add_group_weights(
    grouped: pd.DataFrame,
    index_daily: pd.DataFrame,
) -> pd.DataFrame:
    totals = index_daily[["Date", "Index_Code", "MarketCap"]].rename(
        columns={"MarketCap": "Index_MarketCap"}
    )
    grouped = grouped.merge(totals, on=["Date", "Index_Code"], how="left", validate="many_to_one")
    grouped["Weight_in_Index"] = grouped["MarketCap"].div(
        grouped["Index_MarketCap"].where(grouped["Index_MarketCap"].gt(0))
    )
    return grouped.drop(columns=["Index_MarketCap"])


def build_coverage(stock: pd.DataFrame, diagnostics: list[dict[str, Any]]) -> pd.DataFrame:
    diagnostic_map = {
        (item["Index_Code"], item["Metric"]): item["Missing_or_Error"] for item in diagnostics
    }
    rows: list[dict[str, Any]] = []
    for index_code, group in stock.groupby("Index_Code", sort=True):
        latest_date = group["Date"].max()
        latest = group.loc[group["Date"].eq(latest_date)]
        for metric in METRICS:
            values = pd.to_numeric(group[metric], errors="coerce")
            latest_values = pd.to_numeric(latest[metric], errors="coerce")
            if metric in {"PE_12MF", "MarketCap"}:
                valid = values.notna() & np.isfinite(values) & values.gt(0)
                latest_valid = latest_values.notna() & np.isfinite(latest_values) & latest_values.gt(0)
                rule = "Positive numeric"
            else:
                valid = values.notna() & np.isfinite(values)
                latest_valid = latest_values.notna() & np.isfinite(latest_values)
                rule = "Numeric"
            rows.append(
                {
                    "Index_Code": index_code,
                    "Metric": metric,
                    "Total_Observations": len(group),
                    "Valid_Observations": int(valid.sum()),
                    "Valid_Pct": float(valid.mean()) if len(group) else np.nan,
                    "Latest_Date": latest_date,
                    "Latest_Total": len(latest),
                    "Latest_Valid": int(latest_valid.sum()),
                    "Latest_Valid_Pct": float(latest_valid.mean()) if len(latest) else np.nan,
                    "Rule": rule,
                    "Cached_Missing_or_Error": diagnostic_map.get((index_code, metric), np.nan),
                }
            )
    return pd.DataFrame(rows)


def relative_reconciliation(
    grouped: pd.DataFrame,
    index_daily: pd.DataFrame,
) -> float:
    summed = grouped.groupby(["Date", "Index_Code"], as_index=False)["MarketCap"].sum()
    merged = summed.merge(
        index_daily[["Date", "Index_Code", "MarketCap"]],
        on=["Date", "Index_Code"],
        how="inner",
        suffixes=("_groups", "_index"),
        validate="one_to_one",
    )
    denominator = merged["MarketCap_index"].abs().clip(lower=1.0)
    return float(((merged["MarketCap_groups"] - merged["MarketCap_index"]).abs() / denominator).max())


def weight_sum_error(grouped: pd.DataFrame) -> float:
    sums = grouped.groupby(["Date", "Index_Code"])["Weight_in_Index"].sum()
    return float((sums - 1.0).abs().max())


def build_checks(
    stock: pd.DataFrame,
    index_daily: pd.DataFrame,
    sector_daily: pd.DataFrame,
    industry_daily: pd.DataFrame,
    index_map: pd.DataFrame,
) -> pd.DataFrame:
    duplicate_rows = int(stock.duplicated(["Date", "Index_Code", "Ticker"]).sum())
    sector_recon = relative_reconciliation(sector_daily, index_daily)
    industry_recon = relative_reconciliation(industry_daily, index_daily)
    sector_weight_error = weight_sum_error(sector_daily)
    industry_weight_error = weight_sum_error(industry_daily)

    checks = [
        ("Index count", len(index_map), 19, len(index_map) == 19, "Expected 19 source indices"),
        ("Metric count", len(METRICS), 10, len(METRICS) == 10, "Ten requested Bloomberg fields"),
        ("Duplicate stock-date-index rows", duplicate_rows, 0, duplicate_rows == 0, "Key must be unique"),
        ("Sector market-cap max relative difference", sector_recon, 0.0, sector_recon < 1e-10, "Sector sums vs. index"),
        ("Industry market-cap max relative difference", industry_recon, 0.0, industry_recon < 1e-10, "Industry sums vs. index"),
        ("Sector weight max sum error", sector_weight_error, 0.0, sector_weight_error < 1e-10, "Weights should sum to 100%"),
        ("Industry weight max sum error", industry_weight_error, 0.0, industry_weight_error < 1e-10, "Weights should sum to 100%"),
    ]
    return pd.DataFrame(
        [
            {
                "Check": name,
                "Actual": actual,
                "Expected": expected,
                "Difference": float(actual - expected) if isinstance(actual, (int, float)) else np.nan,
                "Status": "PASS" if passed else "FAIL",
                "Notes": notes,
            }
            for name, actual, expected, passed, notes in checks
        ]
    )


def format_data_sheet(writer: pd.ExcelWriter, sheet_name: str, frame: pd.DataFrame) -> None:
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    rows, cols = frame.shape
    worksheet.freeze_panes(1, 0)
    worksheet.hide_gridlines(2)
    worksheet.set_tab_color("#4472C4")

    table_name = re.sub(r"[^A-Za-z0-9_]", "_", f"T_{sheet_name}")
    worksheet.add_table(
        0,
        0,
        rows,
        cols - 1,
        {
            "name": table_name,
            "style": "Table Style Medium 2",
            "columns": [{"header": column} for column in frame.columns],
        },
    )

    date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
    weight_format = workbook.add_format({"num_format": "0.00%"})
    multiple_format = workbook.add_format({"num_format": "0.00x;[Red](0.00x);-"})
    number_format = workbook.add_format({"num_format": "#,##0.000;[Red](#,##0.000);-"})
    market_cap_format = workbook.add_format({"num_format": "#,##0.0;[Red](#,##0.0);-"})
    ratio_format = workbook.add_format({"num_format": "0.00;[Red](0.00);-"})
    count_format = workbook.add_format({"num_format": "#,##0"})

    for col_index, column in enumerate(frame.columns):
        if column in {"Date", "Start_Date", "End_Date", "Latest_Date"}:
            worksheet.set_column(col_index, col_index, 12, date_format)
        elif "Weight" in column or "Coverage" in column or column.endswith("_Pct"):
            worksheet.set_column(col_index, col_index, 14, weight_format)
        elif column == "PE_12MF":
            worksheet.set_column(col_index, col_index, 13, multiple_format)
        elif column == "MarketCap":
            worksheet.set_column(col_index, col_index, 16, market_cap_format)
        elif column.startswith("EPS_") or column == "Price":
            worksheet.set_column(col_index, col_index, 14, number_format)
        elif column.startswith("ROE_") or column.startswith("OPM_"):
            worksheet.set_column(col_index, col_index, 14, ratio_format)
        elif "Count" in column or column.endswith("_Rows") or column in {
            "Total_Observations",
            "Valid_Observations",
            "Latest_Total",
            "Latest_Valid",
            "Cached_Missing_or_Error",
        }:
            worksheet.set_column(col_index, col_index, 14, count_format)
        elif column in {"Security_Name", "Index_Name", "GICS_Sector", "GICS_Industry_Group", "Notes"}:
            worksheet.set_column(col_index, col_index, 28)
        elif column in {"Ticker", "Index_Ticker", "Source_Sheet", "BQL_Formula"}:
            worksheet.set_column(col_index, col_index, 22)
        else:
            worksheet.set_column(col_index, col_index, max(12, min(20, len(column) + 2)))


def write_readme(
    writer: pd.ExcelWriter,
    input_path: Path,
    index_map: pd.DataFrame,
    stock: pd.DataFrame,
    index_daily: pd.DataFrame,
    sector_daily: pd.DataFrame,
    industry_daily: pd.DataFrame,
) -> None:
    workbook = writer.book
    worksheet = workbook.add_worksheet("README")
    writer.sheets["README"] = worksheet
    worksheet.hide_gridlines(2)
    worksheet.set_tab_color("#17365D")
    worksheet.set_column("A:A", 28)
    worksheet.set_column("B:B", 88)
    worksheet.set_column("C:H", 14)

    title = workbook.add_format(
        {"bold": True, "font_color": "#FFFFFF", "bg_color": "#17365D", "font_size": 16, "align": "left"}
    )
    section = workbook.add_format(
        {"bold": True, "font_color": "#FFFFFF", "bg_color": "#24557F", "align": "left"}
    )
    label = workbook.add_format({"bold": True, "font_color": "#17365D", "valign": "top"})
    body = workbook.add_format({"text_wrap": True, "valign": "top"})
    date_format = workbook.add_format({"num_format": "yyyy-mm-dd", "valign": "top"})

    worksheet.merge_range("A1:H1", "Bquant 19-Index Grouped Daily Fundamentals — Python Output", title)
    rows = [
        ("Source workbook", str(input_path)),
        ("Source system", "Bloomberg BQL cached values"),
        ("Index coverage", f"{len(index_map):,} indices"),
        ("Date range", f"{stock['Date'].min():%Y-%m-%d} to {stock['Date'].max():%Y-%m-%d}"),
        ("Stock daily rows", f"{len(stock):,}"),
        ("Index daily rows", f"{len(index_daily):,}"),
        ("Sector daily rows", f"{len(sector_daily):,}"),
        ("Industry daily rows", f"{len(industry_daily):,}"),
    ]
    worksheet.merge_range("A3:H3", "Output structure", section)
    for row_index, (name, value) in enumerate(rows, start=3):
        worksheet.write(row_index, 0, name, label)
        worksheet.merge_range(row_index, 1, row_index, 7, value, body)

    methodology_start = 13
    worksheet.merge_range(methodology_start, 0, methodology_start, 7, "Aggregation methodology", section)
    methods = [
        ("MarketCap", "Sum of positive same-day constituent market caps."),
        ("PE_12MF", "sum(valid market cap) / sum(valid market cap / positive P/E). Non-positive and missing P/E are excluded."),
        ("Other eight fields", "Same-day market-cap-weighted average. Weights are re-normalized separately for each metric after excluding missing/error values."),
        ("Sector/Industry weight", "Group MarketCap divided by Index MarketCap on the same date."),
        ("Price warning", "Price is a weighted-average constituent price, not an official index level."),
        ("ROE/OPM units", "Bloomberg percentage-point units are preserved; values are not divided by 100."),
    ]
    for offset, (name, value) in enumerate(methods, start=1):
        worksheet.write(methodology_start + offset, 0, name, label)
        worksheet.merge_range(methodology_start + offset, 1, methodology_start + offset, 7, value, body)

    caveat_start = methodology_start + len(methods) + 2
    worksheet.merge_range(caveat_start, 0, caveat_start, 7, "Important limitations for the final charts", section)
    caveats = [
        "The refreshed file currently contains only 21 calendar dates. A 4-week/13-week EPS chart and a 20-year P/E box plot require a longer Bloomberg refresh window.",
        "The members() cache is one refreshed constituent snapshot. It is not point-in-time historical membership unless the source workbook is changed to request dated members/weights.",
        "Absolute EPS levels are index-currency-specific. Cross-country comparisons should use percentage changes or momentum, as in the target charts.",
    ]
    for offset, value in enumerate(caveats, start=1):
        worksheet.write(caveat_start + offset, 0, f"Caveat {offset}", label)
        worksheet.merge_range(caveat_start + offset, 1, caveat_start + offset, 7, value, body)

    worksheet.set_row(0, 26)
    for row in range(2, caveat_start + len(caveats) + 1):
        worksheet.set_row(row, 32 if row > methodology_start else 22)


def write_workbook(
    output_path: Path,
    input_path: Path,
    index_map: pd.DataFrame,
    stock: pd.DataFrame,
    index_daily: pd.DataFrame,
    sector_daily: pd.DataFrame,
    industry_daily: pd.DataFrame,
    coverage: pd.DataFrame,
    checks: pd.DataFrame,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(
        output_path,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_urls": False}},
        datetime_format="yyyy-mm-dd",
    ) as writer:
        write_readme(
            writer,
            input_path,
            index_map,
            stock,
            index_daily,
            sector_daily,
            industry_daily,
        )

        sheets = OrderedDict(
            [
                ("Index_Map", index_map),
                ("Index_Daily", index_daily),
                ("Sector_Daily", sector_daily),
                ("Industry_Daily", industry_daily),
                ("Stock_Daily", stock),
                ("Coverage", coverage),
                ("Checks", checks),
            ]
        )
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False, na_rep="")
            format_data_sheet(writer, sheet_name, frame)

        coverage_sheet = writer.sheets["Coverage"]
        valid_pct_col = coverage.columns.get_loc("Valid_Pct")
        latest_pct_col = coverage.columns.get_loc("Latest_Valid_Pct")
        for col in [valid_pct_col, latest_pct_col]:
            coverage_sheet.conditional_format(
                1,
                col,
                len(coverage),
                col,
                {
                    "type": "3_color_scale",
                    "min_color": "#F8696B",
                    "mid_color": "#FFEB84",
                    "max_color": "#63BE7B",
                },
            )

        checks_sheet = writer.sheets["Checks"]
        status_col = checks.columns.get_loc("Status")
        green = writer.book.add_format({"bg_color": "#C6EFCE", "font_color": "#006100", "bold": True})
        red = writer.book.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006", "bold": True})
        checks_sheet.conditional_format(1, status_col, len(checks), status_col, {"type": "text", "criteria": "containing", "value": "PASS", "format": green})
        checks_sheet.conditional_format(1, status_col, len(checks), status_col, {"type": "text", "criteria": "containing", "value": "FAIL", "format": red})


def build(input_path: Path, output_path: Path) -> dict[str, Any]:
    cached = CachedWorkbook(input_path)
    try:
        stock_frames: list[pd.DataFrame] = []
        index_rows: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        raw_sheets = [name for name in cached.sheet_paths if name.endswith(" Raw")]
        for sheet_name in raw_sheets:
            frame, metadata, metric_diagnostics = parse_index_sheet(cached, sheet_name)
            stock_frames.append(frame)
            index_rows.append(metadata)
            diagnostics.extend(metric_diagnostics)
    finally:
        cached.close()

    stock = pd.concat(stock_frames, ignore_index=True)
    stock["Date"] = pd.to_datetime(stock["Date"])
    stock = add_stock_weights(stock)
    stock = stock.sort_values(
        ["Date", "Index_Code", "GICS_Sector", "GICS_Industry_Group", "Ticker"]
    ).reset_index(drop=True)

    common = ["Date", "Index_Code", "Index_Ticker", "Index_Name", "Currency"]
    index_daily = aggregate_groups(stock, common)
    index_daily["Weight_in_Index"] = 1.0
    sector_daily = aggregate_groups(stock, common + ["GICS_Sector"])
    sector_daily = add_group_weights(sector_daily, index_daily)
    industry_daily = aggregate_groups(
        stock, common + ["GICS_Sector", "GICS_Industry_Group"]
    )
    industry_daily = add_group_weights(industry_daily, index_daily)

    group_columns = [
        "Date",
        "Index_Code",
        "Index_Ticker",
        "Index_Name",
        "Currency",
        "GICS_Sector",
        "GICS_Industry_Group",
        "Stock_Count",
        "Weight_in_Index",
        "PE_Valid_Count",
        "EPS_12MF_Valid_Count",
        "PE_MCap_Coverage",
        "EPS_12MF_MCap_Coverage",
    ] + METRICS
    sector_columns = [column for column in group_columns if column != "GICS_Industry_Group"]
    index_columns = [
        column for column in group_columns if column not in {"GICS_Sector", "GICS_Industry_Group"}
    ]
    index_daily = index_daily[index_columns].sort_values(["Date", "Index_Code"]).reset_index(drop=True)
    sector_daily = sector_daily[sector_columns].sort_values(
        ["Date", "Index_Code", "GICS_Sector"]
    ).reset_index(drop=True)
    industry_daily = industry_daily[group_columns].sort_values(
        ["Date", "Index_Code", "GICS_Sector", "GICS_Industry_Group"]
    ).reset_index(drop=True)

    stock_columns = [
        "Date",
        "Index_Code",
        "Index_Ticker",
        "Index_Name",
        "Currency",
        "Ticker",
        "Security_Name",
        "GICS_Sector",
        "GICS_Industry_Group",
        "Source_Sheet",
        "Index_Weight",
        "Sector_Weight",
        "Industry_Weight",
    ] + METRICS
    stock = stock[stock_columns]

    index_map = pd.DataFrame(index_rows).sort_values("Index_Code").reset_index(drop=True)
    coverage = build_coverage(stock, diagnostics).sort_values(
        ["Index_Code", "Metric"]
    ).reset_index(drop=True)
    checks = build_checks(stock, index_daily, sector_daily, industry_daily, index_map)

    write_workbook(
        output_path,
        input_path,
        index_map,
        stock,
        index_daily,
        sector_daily,
        industry_daily,
        coverage,
        checks,
    )
    return {
        "output": str(output_path),
        "indices": len(index_map),
        "stock_rows": len(stock),
        "index_rows": len(index_daily),
        "sector_rows": len(sector_daily),
        "industry_rows": len(industry_daily),
        "checks_passed": int(checks["Status"].eq("PASS").sum()),
        "checks_total": len(checks),
        "start_date": stock["Date"].min().strftime("%Y-%m-%d"),
        "end_date": stock["Date"].max().strftime("%Y-%m-%d"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(r"C:\Users\infomax\Documents\python\BQL\Raw_Source_Files\Constituent_Raw\Bquant_All_19_Raw_Refreshed.xlsx"),
        help="Refreshed Bloomberg raw workbook",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(r"C:\Users\infomax\Documents\python\BQL\Bquant_All_19_Grouped_Raw.xlsx"),
        help="Output grouped workbook",
    )
    args = parser.parse_args()
    result = build(args.input.resolve(), args.output.resolve())
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
