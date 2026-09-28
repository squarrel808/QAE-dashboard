from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import math
import sys

import numpy as np
import pandas as pd


ROOT = Path(r"C:\Users\USER\Downloads\Telegram Desktop\ChatExport_2026-08-09 (2)")
BUILDER = Path(r"C:\Users\USER\Downloads\유로존\dashbaord\build_market_rotation_dashboard.py")
OLD = Path(r"C:\Users\USER\Downloads\유로존\BACKUP\Bquant_All_19_Grouped_Raw.xlsx")
NEW = Path(r"C:\Users\USER\Downloads\Bquant_All_19_Raw_Refreshed12시 (1).xlsb")
OUT = Path(r"C:\Users\USER\Downloads\유로존\Bquant_All_19_Grouped_Raw_Updated_20260901.xlsx")

spec = spec_from_file_location("bquant_builder", BUILDER)
builder = module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


def finite(v):
    return np.isfinite(v)


def wavg(values: np.ndarray, weights: np.ndarray) -> float:
    ok = finite(values) & finite(weights) & (weights > 0)
    if not ok.any():
        return np.nan
    return float(np.sum(values[ok] * weights[ok]) / np.sum(weights[ok]))


def harmonic_pe(values: np.ndarray, weights: np.ndarray) -> float:
    ok = finite(values) & finite(weights) & (weights > 0) & (values > 1)
    if not ok.any():
        return np.nan
    denom = np.sum(weights[ok] / values[ok])
    return float(np.sum(weights[ok]) / denom) if denom > 0 else np.nan


def aggregate_row(raw, j: int, mask: np.ndarray) -> dict:
    mcap = raw.metrics["mcap"][:, j]
    price = raw.metrics["price"][:, j]
    shares = np.divide(
        mcap,
        price,
        out=np.full_like(mcap, np.nan, dtype=float),
        where=finite(mcap) & finite(price) & (mcap > 0) & (price > 0),
    )
    group_mcap_mask = mask & finite(mcap) & (mcap > 0)
    group_mcap = float(np.sum(mcap[group_mcap_mask])) if group_mcap_mask.any() else np.nan
    total_mask = finite(mcap) & (mcap > 0)
    total_mcap = float(np.sum(mcap[total_mask])) if total_mask.any() else np.nan
    pe = raw.metrics["pe"][:, j]
    eps = raw.metrics["eps12"][:, j]
    pe_ok = group_mcap_mask & finite(pe) & (pe > 1)
    eps_ok = group_mcap_mask & finite(eps)
    return {
        "Stock_Count": int(mask.sum()),
        "Weight_in_Index": group_mcap / total_mcap if total_mcap > 0 and np.isfinite(group_mcap) else np.nan,
        "PE_Valid_Count": int(pe_ok.sum()),
        "EPS_12MF_Valid_Count": int(eps_ok.sum()),
        "PE_MCap_Coverage": float(np.sum(mcap[pe_ok]) / group_mcap) if group_mcap > 0 else np.nan,
        "EPS_12MF_MCap_Coverage": float(np.sum(mcap[eps_ok]) / group_mcap) if group_mcap > 0 else np.nan,
        "PE_12MF": harmonic_pe(pe[mask], mcap[mask]),
        "EPS_12MF": wavg(eps[mask], mcap[mask]),
        "EPS_FY1": wavg(raw.metrics["eps_fy1"][:, j][mask], mcap[mask]),
        "EPS_FY2": wavg(raw.metrics["eps_fy2"][:, j][mask], mcap[mask]),
        "Price": wavg(price[mask], shares[mask]),
        "MarketCap": group_mcap,
        "ROE_Current": wavg(raw.metrics["roe_current"][:, j][mask], mcap[mask]),
        "OPM_Current": wavg(raw.metrics["opm_current"][:, j][mask], mcap[mask]),
        "ROE_12MF": wavg(raw.metrics["roe_12m"][:, j][mask], mcap[mask]),
        "OPM_12MF": wavg(raw.metrics["opm_12m"][:, j][mask], mcap[mask]),
    }


def build_new_frames():
    index_rows, sector_rows, industry_rows, stock_rows = [], [], [], []
    for raw in builder.iter_raw_indices(NEW):
        sectors = np.array(raw.sectors, dtype=object)
        industries = np.array(raw.industries, dtype=object)
        tickers = np.array(raw.tickers, dtype=object)
        companies = np.array(raw.companies, dtype=object)
        for j, d in enumerate(raw.dates):
            mcap = raw.metrics["mcap"][:, j]
            mcap_ok = finite(mcap) & (mcap > 0)
            total_mcap = float(np.sum(mcap[mcap_ok])) if mcap_ok.any() else np.nan
            base = {
                "Date": pd.Timestamp(d),
                "Index_Code": raw.code,
                "Index_Ticker": f"{raw.code} Index",
                "Index_Name": raw.name,
                "Currency": raw.currency,
            }
            idx = dict(base)
            idx.update(aggregate_row(raw, j, np.ones(len(raw.tickers), dtype=bool)))
            index_rows.append(idx)

            for sector in sorted(set(raw.sectors)):
                mask = sectors == sector
                row = dict(base)
                row["GICS_Sector"] = sector
                row.update(aggregate_row(raw, j, mask))
                sector_rows.append(row)

            for sector, industry in sorted(set(zip(raw.sectors, raw.industries))):
                mask = (sectors == sector) & (industries == industry)
                row = dict(base)
                row["GICS_Sector"] = sector
                row["GICS_Industry_Group"] = industry
                row.update(aggregate_row(raw, j, mask))
                industry_rows.append(row)

            sector_mcaps = {s: float(np.nansum(mcap[(sectors == s) & mcap_ok])) for s in set(raw.sectors)}
            industry_mcaps = {(s, i): float(np.nansum(mcap[(sectors == s) & (industries == i) & mcap_ok])) for s, i in set(zip(raw.sectors, raw.industries))}
            for i in range(len(raw.tickers)):
                sm = sector_mcaps.get(raw.sectors[i], np.nan)
                im = industry_mcaps.get((raw.sectors[i], raw.industries[i]), np.nan)
                mc = mcap[i]
                stock_rows.append({
                    **base,
                    "Ticker": tickers[i],
                    "Security_Name": companies[i],
                    "GICS_Sector": sectors[i],
                    "GICS_Industry_Group": industries[i],
                    "Source_Sheet": raw.sheet,
                    "Index_Weight": mc / total_mcap if np.isfinite(mc) and total_mcap > 0 else np.nan,
                    "Sector_Weight": mc / sm if np.isfinite(mc) and sm > 0 else np.nan,
                    "Industry_Weight": mc / im if np.isfinite(mc) and im > 0 else np.nan,
                    "PE_12MF": raw.metrics["pe"][i, j],
                    "EPS_12MF": raw.metrics["eps12"][i, j],
                    "EPS_FY1": raw.metrics["eps_fy1"][i, j],
                    "EPS_FY2": raw.metrics["eps_fy2"][i, j],
                    "Price": raw.metrics["price"][i, j],
                    "MarketCap": raw.metrics["mcap"][i, j],
                    "ROE_Current": raw.metrics["roe_current"][i, j],
                    "OPM_Current": raw.metrics["opm_current"][i, j],
                    "ROE_12MF": raw.metrics["roe_12m"][i, j],
                    "OPM_12MF": raw.metrics["opm_12m"][i, j],
                })
    return {
        "Index_Daily": pd.DataFrame(index_rows),
        "Sector_Daily": pd.DataFrame(sector_rows),
        "Industry_Daily": pd.DataFrame(industry_rows),
        "Stock_Daily": pd.DataFrame(stock_rows),
    }


def replace_overlap(old: pd.DataFrame, new: pd.DataFrame, pair_cols: list[str], sort_cols: list[str]) -> pd.DataFrame:
    old["Date"] = pd.to_datetime(old["Date"])
    new["Date"] = pd.to_datetime(new["Date"])
    refresh_pairs = new[pair_cols].drop_duplicates().copy()
    marked = old.merge(refresh_pairs.assign(_refresh=1), on=pair_cols, how="left")
    kept = marked.loc[marked["_refresh"].isna(), old.columns]
    out = pd.concat([kept, new], ignore_index=True)
    return out.sort_values(sort_cols, kind="stable").reset_index(drop=True)


def make_index_map(stock: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code, g in stock.groupby("Index_Code", sort=True):
        end = g["Date"].max()
        latest = g[g["Date"] == end]
        rows.append({
            "Index_Code": code,
            "Index_Ticker": latest["Index_Ticker"].iloc[0],
            "Index_Name": latest["Index_Name"].iloc[0],
            "Currency": latest["Currency"].iloc[0],
            "Source_Sheet": latest["Source_Sheet"].iloc[0],
            "Member_Count": int(latest["Ticker"].nunique()),
            "Start_Date": g["Date"].min(),
            "End_Date": end,
            "Date_Count": int(g["Date"].nunique()),
            "Stock_Date_Rows": int(len(g)),
            "Invalid_Date_Headers_Ignored": 0,
        })
    return pd.DataFrame(rows)


def make_coverage(stock: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        ("PE_12MF", "PE_12MF", lambda s: pd.to_numeric(s, errors="coerce") > 0, "Positive numeric"),
        ("EPS_12MF", "EPS_12MF", lambda s: pd.to_numeric(s, errors="coerce").notna(), "Numeric"),
        ("EPS_FY1", "EPS_FY1", lambda s: pd.to_numeric(s, errors="coerce").notna(), "Numeric"),
        ("EPS_FY2", "EPS_FY2", lambda s: pd.to_numeric(s, errors="coerce").notna(), "Numeric"),
        ("Price", "Price", lambda s: pd.to_numeric(s, errors="coerce") > 0, "Positive numeric"),
        ("MarketCap", "MarketCap", lambda s: pd.to_numeric(s, errors="coerce") > 0, "Positive numeric"),
        ("ROE_Current", "ROE_Current", lambda s: pd.to_numeric(s, errors="coerce").notna(), "Numeric"),
        ("OPM_Current", "OPM_Current", lambda s: pd.to_numeric(s, errors="coerce").notna(), "Numeric"),
        ("ROE_12MF", "ROE_12MF", lambda s: pd.to_numeric(s, errors="coerce").notna(), "Numeric"),
        ("OPM_12MF", "OPM_12MF", lambda s: pd.to_numeric(s, errors="coerce").notna(), "Numeric"),
    ]
    rows = []
    for code, g in stock.groupby("Index_Code", sort=True):
        latest_date = g["Date"].max()
        latest = g[g["Date"] == latest_date]
        for label, col, fn, rule in metrics:
            ok = fn(g[col])
            latest_ok = fn(latest[col])
            rows.append({
                "Index_Code": code,
                "Metric": label,
                "Total_Observations": int(len(g)),
                "Valid_Observations": int(ok.sum()),
                "Valid_Pct": float(ok.mean()) if len(g) else np.nan,
                "Latest_Date": latest_date,
                "Latest_Total": int(len(latest)),
                "Latest_Valid": int(latest_ok.sum()),
                "Latest_Valid_Pct": float(latest_ok.mean()) if len(latest) else np.nan,
                "Rule": rule,
                "Cached_Missing_or_Error": int((~ok).sum()),
            })
    return pd.DataFrame(rows)


def make_checks(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    stock, idx, sec, ind = frames["Stock_Daily"], frames["Index_Daily"], frames["Sector_Daily"], frames["Industry_Daily"]
    dup = int(stock.duplicated(["Date", "Index_Code", "Ticker"]).sum())
    sec_sum = sec.groupby(["Date", "Index_Code"])["MarketCap"].sum()
    ind_sum = ind.groupby(["Date", "Index_Code"])["MarketCap"].sum()
    idx_mcap = idx.set_index(["Date", "Index_Code"])["MarketCap"]
    sec_rel = ((sec_sum - idx_mcap).abs() / idx_mcap.replace(0, np.nan)).max()
    ind_rel = ((ind_sum - idx_mcap).abs() / idx_mcap.replace(0, np.nan)).max()
    sec_w = (sec.groupby(["Date", "Index_Code"])["Weight_in_Index"].sum() - 1).abs().max()
    ind_w = (ind.groupby(["Date", "Index_Code"])["Weight_in_Index"].sum() - 1).abs().max()
    tests = [
        ("Index count", stock["Index_Code"].nunique(), 19, "Expected 19 source indices"),
        ("Metric count", 10, 10, "Ten requested Bloomberg fields"),
        ("Duplicate stock-date-index rows", dup, 0, "Key must be unique"),
        ("Sector market-cap max relative difference", float(sec_rel), 0, "Sector sums vs. index"),
        ("Industry market-cap max relative difference", float(ind_rel), 0, "Industry sums vs. index"),
        ("Sector weight max sum error", float(sec_w), 0, "Weights should sum to 100%"),
        ("Industry weight max sum error", float(ind_w), 0, "Weights should sum to 100%"),
    ]
    rows = []
    for name, actual, expected, note in tests:
        diff = actual - expected
        tol = 1e-9 if isinstance(actual, float) else 0
        rows.append({"Check": name, "Actual": actual, "Expected": expected, "Difference": diff, "Status": "PASS" if abs(diff) <= tol else "FAIL", "Notes": note})
    return pd.DataFrame(rows)


def write_workbook(frames: dict[str, pd.DataFrame], index_map: pd.DataFrame, coverage: pd.DataFrame, checks: pd.DataFrame):
    readme = pd.DataFrame([
        ["Bquant 19-Index Grouped Daily Fundamentals — Updated Python Output", None],
        [None, None],
        ["Output structure", None],
        ["Original grouped workbook", str(OLD)],
        ["Appended/refreshed source", str(NEW)],
        ["Source system", "Bloomberg BQL cached values"],
        ["Merge rule", "For overlapping Date × Index pairs, the new XLSB replaces the previous cached snapshot; non-overlapping rows are appended."],
        ["Index coverage", f"{index_map['Index_Code'].nunique()} indices"],
        ["Date range", f"{stock_min(frames):%Y-%m-%d} to {stock_max(frames):%Y-%m-%d}"],
        ["Stock daily rows", f"{len(frames['Stock_Daily']):,}"],
        ["Method", "Price uses shares weights (Shares = MarketCap / Price); non-price fundamentals use daily market-cap weights; P/E is aggregated through earnings yield using observations above 1x."],
        ["Membership note", "Rows after 2026-08-21 use the membership embedded in the 2026-09-01 refreshed workbook."],
        ["Created", "2026-09-01 (Asia/Seoul)"],
    ], columns=["Item", "Value"])

    with pd.ExcelWriter(OUT, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as writer:
        wb = writer.book
        header = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "border": 1, "font_name": "Arial", "align": "center"})
        text_fmt = wb.add_format({"font_name": "Arial"})
        date_fmt = wb.add_format({"font_name": "Arial", "num_format": "yyyy-mm-dd"})
        pct_fmt = wb.add_format({"font_name": "Arial", "num_format": "0.0%;(0.0%);-"})
        num_fmt = wb.add_format({"font_name": "Arial", "num_format": "0.000"})
        int_fmt = wb.add_format({"font_name": "Arial", "num_format": "#,##0"})
        money_fmt = wb.add_format({"font_name": "Arial", "num_format": "#,##0.00"})

        order = [
            ("README", readme), ("Index_Map", index_map), ("Index_Daily", frames["Index_Daily"]),
            ("Sector_Daily", frames["Sector_Daily"]), ("Industry_Daily", frames["Industry_Daily"]),
            ("Stock_Daily", frames["Stock_Daily"]), ("Coverage", coverage), ("Checks", checks),
        ]
        for name, df in order:
            df.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(df), max(0, len(df.columns) - 1))
            ws.set_row(0, 24, header)
            for c, col in enumerate(df.columns):
                ws.write(0, c, col, header)
                width = min(42, max(11, len(str(col)) + 2))
                fmt = text_fmt
                if col in {"Date", "Start_Date", "End_Date", "Latest_Date"}:
                    width, fmt = 12, date_fmt
                elif "Weight" in col or "Coverage" in col or col.endswith("_Pct"):
                    width, fmt = 14, pct_fmt
                elif "Count" in col or col in {"Stock_Date_Rows", "Total_Observations", "Valid_Observations", "Latest_Total", "Latest_Valid", "Cached_Missing_or_Error"}:
                    width, fmt = 14, int_fmt
                elif col in {"PE_12MF", "EPS_12MF", "EPS_FY1", "EPS_FY2", "Price", "ROE_Current", "OPM_Current", "ROE_12MF", "OPM_12MF"}:
                    width, fmt = 13, num_fmt
                elif col == "MarketCap":
                    width, fmt = 16, money_fmt
                elif col in {"Security_Name", "GICS_Industry_Group"}:
                    width = 34
                elif col in {"GICS_Sector", "Source_Sheet", "Index_Name"}:
                    width = 24
                ws.set_column(c, c, width, fmt)
            if name == "README":
                ws.set_column(0, 0, 26, text_fmt)
                ws.set_column(1, 1, 110, text_fmt)
                ws.hide_gridlines(2)


def stock_min(frames):
    return pd.to_datetime(frames["Stock_Daily"]["Date"]).min()


def stock_max(frames):
    return pd.to_datetime(frames["Stock_Daily"]["Date"]).max()


def main():
    print("Parsing refreshed XLSB...", flush=True)
    new_frames = build_new_frames()
    print("Loading existing grouped workbook...", flush=True)
    old_frames = {name: pd.read_excel(OLD, sheet_name=name) for name in ["Index_Daily", "Sector_Daily", "Industry_Daily", "Stock_Daily"]}
    frames = {
        "Index_Daily": replace_overlap(old_frames["Index_Daily"], new_frames["Index_Daily"], ["Date", "Index_Code"], ["Date", "Index_Code"]),
        "Sector_Daily": replace_overlap(old_frames["Sector_Daily"], new_frames["Sector_Daily"], ["Date", "Index_Code"], ["Date", "Index_Code", "GICS_Sector"]),
        "Industry_Daily": replace_overlap(old_frames["Industry_Daily"], new_frames["Industry_Daily"], ["Date", "Index_Code"], ["Date", "Index_Code", "GICS_Sector", "GICS_Industry_Group"]),
        "Stock_Daily": replace_overlap(old_frames["Stock_Daily"], new_frames["Stock_Daily"], ["Date", "Index_Code"], ["Date", "Index_Code", "Ticker"]),
    }
    index_map = make_index_map(frames["Stock_Daily"])
    coverage = make_coverage(frames["Stock_Daily"])
    checks = make_checks(frames)
    print(checks.to_string(index=False), flush=True)
    write_workbook(frames, index_map, coverage, checks)
    print(f"OUTPUT={OUT}")
    print(f"DATE_RANGE={stock_min(frames):%Y-%m-%d}..{stock_max(frames):%Y-%m-%d}")
    print(f"STOCK_ROWS={len(frames['Stock_Daily'])}")


if __name__ == "__main__":
    main()
