# build_tickers_from_confirmed.py
"""
tickerlist_confirmed.xlsx (국가별 시트) → tickers.xlsx (Ticker / Category / Country) 변환.

확정판 시트 구조:
  시트명 = 국가코드 소문자 (au/de/jp/uk/us/ca) + 안내용 '읽어줘' 시트
  컬럼   = 카테고리 / 지표명 / Ticker / 시작 / 상태 / 비고
  - 카테고리가 대문자(CAPEX 등)이고 Ticker가 비어 있는 행 = 섹션 헤더 → 제외
  - Ticker 가 '-' 인 행 = 확보 실패(보류) → 제외
  - Ticker 에 '/' 가 있는 행 = 한 셀에 코드 2개(검증대기) → 제외
  - 상태가 '제외' 인 행 = 티커는 적혀 있지만 쓰지 않기로 확정 → 제외

한 티커가 여러 국가에 배정되면 Country 를 "US,CA" 처럼 콤마로 합친다.
(fetch_haver_to_excel.py 가 그대로 Metadata 에 넘기고, pca_gdp.py 가 split 해서 양쪽 국가에 포함시킴)

실행: python build_tickers_from_confirmed.py [--dry-run]
"""
import sys
from pathlib import Path

import pandas as pd

BASE      = Path(__file__).resolve().parent
SRC       = BASE / "tickerlist_confirmed.xlsx"
DST       = BASE / "tickers.xlsx"

# 시트명(소문자) → 국가코드. 이 순서가 tickers.xlsx 행 정렬 순서이기도 하다.
COUNTRY_SHEETS = ["us", "au", "ca", "de", "jp", "uk"]
CATEGORY_ORDER = ["capex", "consumer", "export", "housing", "labor", "lei"]

# 상태가 이 값이면 티커가 적혀 있어도 제외 (확정판에서 '쓰지 않기로 확정'한 행)
DROP_STATUS = {"제외", "보류"}

# 확정판과 무관하게 코드에서 강제 제외할 티커 (사유를 남겨둘 것)
EXCLUDE = {}

# PCA가 카테고리 지수를 만들려면 지표 2개 이상 필요 (pca_gdp.run_version)
MIN_PER_CATEGORY = 2


def load_confirmed():
    xl = pd.ExcelFile(SRC)
    rows, skipped = [], []

    for sheet in COUNTRY_SHEETS:
        if sheet not in xl.sheet_names:
            print(f"[WARN] 시트 없음: {sheet}")
            continue
        df = xl.parse(sheet)
        cc = sheet.upper()

        for _, r in df.iterrows():
            ticker = str(r.get("Ticker", "")).strip()
            cat    = str(r.get("카테고리", "")).strip().lower()
            name   = str(r.get("지표명", "")).strip()
            status = str(r.get("상태", "")).strip()

            if ticker in ("", "nan", "-"):
                # 섹션 헤더(카테고리만 대문자로 적힌 행) 또는 확보 실패(보류)
                if status and status != "nan":
                    skipped.append((cc, cat, name, "-", status, "티커 없음"))
                continue
            if status in DROP_STATUS:
                skipped.append((cc, cat, name, ticker, status, "상태가 제외/보류"))
                continue
            if "/" in ticker:
                skipped.append((cc, cat, name, ticker, status, "한 셀에 코드 2개"))
                continue
            if ticker in EXCLUDE:
                skipped.append((cc, cat, name, ticker, status, EXCLUDE[ticker]))
                continue

            rows.append({"Ticker": ticker, "Category": cat, "Country": cc,
                         "지표명": name, "상태": status})

    return pd.DataFrame(rows), skipped


def collapse(df):
    """같은 티커가 여러 국가에 있으면 Country 를 콤마로 합친다."""
    order = {cc: i for i, cc in enumerate(c.upper() for c in COUNTRY_SHEETS)}
    out, conflicts = [], []

    for ticker, grp in df.groupby("Ticker", sort=False):
        cats = sorted(set(grp["Category"]))
        if len(cats) > 1:
            conflicts.append((ticker, cats))
        ccs = sorted(set(grp["Country"]), key=lambda c: order.get(c, 99))
        out.append({
            "Ticker": ticker,
            "Category": cats[0],
            "Country": ",".join(ccs),
            "_first_cc": order.get(ccs[0], 99),
            "_cat": CATEGORY_ORDER.index(cats[0]) if cats[0] in CATEGORY_ORDER else 99,
            "지표명": grp["지표명"].iloc[0],
        })

    res = (pd.DataFrame(out)
             .sort_values(["_first_cc", "_cat", "Ticker"])
             .drop(columns=["_first_cc", "_cat"])
             .reset_index(drop=True))
    return res, conflicts


def main():
    dry = "--dry-run" in sys.argv

    raw, skipped = load_confirmed()
    df, conflicts = collapse(raw)

    print(f"확정판 유효행 {len(raw)} → 고유 티커 {len(df)}")
    print()
    print("--- 국가 x 카테고리 (다국가 티커는 배정된 모든 국가에 계상) ---")
    ct = pd.crosstab(raw["Category"], raw["Country"])
    print(ct.to_string())
    print()

    # 지표 1개짜리 카테고리는 pca_gdp 가 지수를 못 만들고 WARN 후 스킵한다
    thin = [(cc, cat, int(n))
            for cat in ct.index for cc, n in ct.loc[cat].items()
            if 0 < n < MIN_PER_CATEGORY]
    if thin:
        print(f"--- [WARN] 지표 {MIN_PER_CATEGORY}개 미만 — pca_gdp 에서 카테고리째 스킵됨 ---")
        for cc, cat, n in thin:
            print(f"  {cc} {cat}: {n}개")
        print()

    multi = df[df["Country"].str.contains(",")]
    if len(multi):
        print("--- 다국가 배정 티커 ---")
        for _, r in multi.iterrows():
            print(f"  {r['Ticker']:22s} {r['Country']:8s} {r['Category']:9s} {r['지표명'][:50]}")
        print()

    if conflicts:
        print("--- [WARN] 국가마다 카테고리가 다른 티커 (첫 번째 값 사용) ---")
        for t, cats in conflicts:
            print(f"  {t}: {cats}")
        print()

    if skipped:
        print("--- 제외된 행 ---")
        for cc, cat, name, tk, st, why in skipped:
            print(f"  {cc} {cat:9s} {tk:22s} [{st}] {name[:42]} — {why}")
        print()

    if dry:
        print("(--dry-run: 저장하지 않음)")
        return 0

    out = df[["Ticker", "Category", "Country"]]
    with pd.ExcelWriter(DST, engine="openpyxl") as wr:
        out.to_excel(wr, sheet_name="Tickers", index=False)
    print(f"저장: {DST}  ({len(out)}행)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
