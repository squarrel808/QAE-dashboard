# fetch_haver_to_excel.py
"""
DB를 거치지 않고 Haver → Excel로 직행 + 증분 수집.

엑셀 구조 (시트 2개):
  - Wide      : 날짜 × 티커 패널. 컬럼 헤더는 descriptor 기준(중복 시 ticker_pk 병기)
  - Metadata  : 모든 티커의 ticker_pk / code / descriptor / datatype / frequency

부가:
  - last_dates.json 에 티커별 마지막 받은 날짜 저장
  - 다음 실행 시 그 날짜 이후만 받아 엑셀에 append
  - 시작점은 DEFAULT_START 이후로만 유지 (이전 데이터는 잘라냄)
"""
import json
import shutil
from pathlib import Path
from datetime import timedelta

import pandas as pd

import haver_provider as haver
from run_logging import setup_run_logging, log_event

BASE          = Path(__file__).resolve().parent
TICKERS_FILE  = BASE / "tickers.xlsx"
OUTPUT_FILE   = BASE / "dashboard_data_CPI Distribution.xlsx"
STATE_FILE    = BASE / "last_dates.json"
DEFAULT_START = "2018-01-01"   # 신규 티커 첫 시작일 + 패널 전체 하한
SAFETY_DAYS   = 7              # revision 흡수용 안전마진
CHUNK_SIZE    = 50             # Haver 한 번에 받을 티커 개수

META_COLS = ["code", "descriptor", "datatype", "frequency"]


# ─────────────────────────────────────────────────────
# 상태 파일
# ─────────────────────────────────────────────────────
def load_state():
    return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────────────────────────────
# 원본 티커(CODE@DATABASE) → metadata의 ticker_pk(database:code, 소문자) 정규화
# ─────────────────────────────────────────────────────
def ticker_to_pk(ticker):
    s = str(ticker).strip()
    if "@" in s:
        code, db = s.split("@", 1)
        return f"{db.strip().lower()}:{code.strip().lower()}"
    return s.lower()


# ─────────────────────────────────────────────────────
# Metadata 시트 빌드 (모든 티커의 code / descriptor / datatype / frequency / category)
# ─────────────────────────────────────────────────────
def build_metadata_sheet(all_tickers, logger, category_map=None):
    empty_cols = ["ticker_pk"] + META_COLS + ["category"]
    if not all_tickers:
        return pd.DataFrame(columns=empty_cols)

    log_event(logger, "info", "Fetching metadata", ticker_count=len(all_tickers))
    meta_df = haver.fetch_metadata(all_tickers)
    if meta_df.empty:
        log_event(logger, "warning", "Metadata fetch returned empty")
        return pd.DataFrame(columns=empty_cols)

    for col in META_COLS:
        if col not in meta_df.columns:
            meta_df[col] = ""

    out = meta_df[["ticker_pk"] + META_COLS].copy()
    out = out.drop_duplicates(subset=["ticker_pk"], keep="first")
    out = out.sort_values("ticker_pk").reset_index(drop=True)

    # tickers.xlsx의 Category 열을 ticker_pk 기준으로 마지막 열에 병기
    if category_map:
        out["category"] = out["ticker_pk"].astype(str).map(category_map).fillna("")
    else:
        out["category"] = ""
    return out


# ─────────────────────────────────────────────────────
# Wide 컬럼 헤더 = descriptor (중복이면 'descriptor (ticker_pk)')
# ─────────────────────────────────────────────────────
def build_header_map(ticker_pks, meta_sheet):
    """ticker_pk → 사용자에게 보일 header(descriptor) 매핑.
       동일 descriptor가 둘 이상이면 ticker_pk를 괄호로 병기해 유일성 보장.
       descriptor가 비어있으면 ticker_pk를 그대로 사용.
    """
    pk_to_desc = {}
    if meta_sheet is not None and not meta_sheet.empty:
        for _, row in meta_sheet.iterrows():
            pk = str(row["ticker_pk"])
            desc = str(row.get("descriptor", "")).strip()
            pk_to_desc[pk] = desc if desc else pk

    desc_count = {}
    for pk in ticker_pks:
        d = pk_to_desc.get(pk, pk)
        desc_count[d] = desc_count.get(d, 0) + 1

    header_map = {}
    for pk in ticker_pks:
        d = pk_to_desc.get(pk, pk)
        if d == pk:
            header_map[pk] = pk                       # descriptor 없으면 ticker_pk
        elif desc_count[d] > 1:
            header_map[pk] = f"{d} ({pk})"            # 중복이면 ticker_pk 병기
        else:
            header_map[pk] = d
    return header_map


# ─────────────────────────────────────────────────────
# 기존 엑셀 로드 (Wide → long-form, descriptor 헤더 역매핑)
# ─────────────────────────────────────────────────────
def load_existing_panel():
    if not OUTPUT_FILE.exists():
        return pd.DataFrame(columns=["date", "ticker_pk", "value"])
    try:
        wide = pd.read_excel(OUTPUT_FILE, sheet_name="Wide")
    except Exception:
        return pd.DataFrame(columns=["date", "ticker_pk", "value"])
    if wide.empty:
        return pd.DataFrame(columns=["date", "ticker_pk", "value"])

    # Metadata 시트도 읽어서 header → ticker_pk 역매핑 만들기
    try:
        meta = pd.read_excel(OUTPUT_FILE, sheet_name="Metadata")
    except Exception:
        meta = pd.DataFrame()

    rev = {}
    if not meta.empty and "ticker_pk" in meta.columns:
        ticker_pks = meta["ticker_pk"].astype(str).tolist()
        header_map = build_header_map(ticker_pks, meta)  # pk → header
        for pk, header in header_map.items():
            rev[header] = pk
            rev[pk] = pk  # ticker_pk 자체가 헤더로 와도 받아들임

    date_col = wide.columns[0]
    long_df = wide.melt(id_vars=[date_col], var_name="header", value_name="value")
    long_df["ticker_pk"] = long_df["header"].astype(str).map(lambda h: rev.get(h, h))
    long_df = long_df.drop(columns=["header"]).rename(columns={date_col: "date"})
    long_df["date"] = pd.to_datetime(long_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    long_df = long_df.dropna(subset=["date", "value"])
    return long_df[["date", "ticker_pk", "value"]]


# ─────────────────────────────────────────────────────
# Haver 시계열 chunk 호출
# ─────────────────────────────────────────────────────
def fetch_chunked(tickers, start_date):
    frames = []
    for i in range(0, len(tickers), CHUNK_SIZE):
        chunk = tickers[i:i + CHUNK_SIZE]
        df = haver.fetch_series_data(chunk, start_date)
        if not df.empty:
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ─────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────
def main():
    ctx = setup_run_logging()
    logger = ctx["logger"]

    if not haver.initialize():
        log_event(logger, "error", "Haver init failed")
        return 1

    _tickers_df = pd.read_excel(TICKERS_FILE)
    _ticker_col = next((c for c in _tickers_df.columns if str(c).strip().lower() == "ticker"), _tickers_df.columns[0])
    tickers = _tickers_df[_ticker_col].dropna().unique().tolist()

    # tickers.xlsx 2열(Category) → ticker_pk 기준 매핑 (Metadata 시트 마지막 열용)
    _cat_col = next((c for c in _tickers_df.columns if str(c).strip().lower() == "category"), None)
    category_map = {}
    if _cat_col is not None:
        for _, row in _tickers_df.iterrows():
            tk = row[_ticker_col]
            if pd.isna(tk):
                continue
            cat = row[_cat_col]
            category_map[ticker_to_pk(tk)] = "" if pd.isna(cat) else str(cat).strip()

    state   = load_state()

    # 1) 티커를 (기존 / 신규) 두 그룹으로 분리
    existing_tickers = [t for t in tickers if t in state]
    new_tickers      = [t for t in tickers if t not in state]

    frames = []

    # 2) 기존 티커: last_date - 안전마진 (단 DEFAULT_START 이전으로는 안 내려감)
    if existing_tickers:
        min_last = min(pd.to_datetime(state[t]) for t in existing_tickers)
        start_ts = min_last - timedelta(days=SAFETY_DAYS)
        floor_ts = pd.to_datetime(DEFAULT_START)
        if start_ts < floor_ts:
            start_ts = floor_ts
        start = start_ts.strftime("%Y-%m-%d")
        log_event(logger, "info", "Fetching incremental",
                  ticker_count=len(existing_tickers), start=start)
        df = fetch_chunked(existing_tickers, start)
        if not df.empty:
            frames.append(df)

    # 3) 신규 티커: 2018-01-01부터 통째로
    if new_tickers:
        log_event(logger, "info", "Fetching new tickers (since DEFAULT_START)",
                  ticker_count=len(new_tickers), start=DEFAULT_START)
        df = fetch_chunked(new_tickers, DEFAULT_START)
        if not df.empty:
            frames.append(df)

    new_data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # 4) 기존 엑셀 + 새 데이터 머지
    panel  = load_existing_panel()
    merged = pd.concat([panel, new_data], ignore_index=True)
    merged = merged.drop_duplicates(subset=["date", "ticker_pk"], keep="last")
    merged = merged.sort_values(["ticker_pk", "date"])

    # 5) DEFAULT_START 이전 잘라내기
    merged = merged[merged["date"] >= DEFAULT_START]

    # 6) Wide 피벗 (내부적으로는 ticker_pk 컬럼)
    wide_internal = (merged.pivot_table(index="date", columns="ticker_pk",
                                        values="value", aggfunc="last")
                            .sort_index())

    # 7) Metadata 시트 (모든 티커) — 마지막 열에 category 병기
    meta_sheet = build_metadata_sheet(tickers, logger, category_map)

    # 8) Wide 컬럼을 descriptor로 리네임
    header_map = build_header_map(list(wide_internal.columns), meta_sheet)
    wide_display = wide_internal.rename(columns=header_map)

    # 9) 저장 — Wide / Metadata 시트만 갱신하고, 사용자가 추가한 다른 시트는 보존
    tmp = OUTPUT_FILE.with_suffix(".xlsx.tmp")
    if OUTPUT_FILE.exists():
        # 기존 파일(추가 시트 포함)을 복사한 뒤 Wide/Metadata 시트만 교체
        shutil.copy2(OUTPUT_FILE, tmp)
        writer = pd.ExcelWriter(tmp, engine="openpyxl", mode="a", if_sheet_exists="replace")
    else:
        writer = pd.ExcelWriter(tmp, engine="openpyxl", mode="w")
    with writer:
        wide_display.to_excel(writer, sheet_name="Wide")
        meta_sheet.to_excel(writer,    sheet_name="Metadata", index=False)
    tmp.replace(OUTPUT_FILE)

    # 10) 상태(last_dates.json) 갱신
    for ticker_pk, grp in merged.groupby("ticker_pk"):
        state[ticker_pk] = grp["date"].max()
    save_state(state)

    log_event(logger, "info", "Excel saved",
              rows=len(merged),
              wide_cols=len(wide_display.columns),
              meta_rows=len(meta_sheet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
