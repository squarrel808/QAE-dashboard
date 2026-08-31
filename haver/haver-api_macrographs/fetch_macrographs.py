# fetch_macrographs.py
"""
charts_config.xlsx 의 Series 시트에서 Haver 티커 목록을 읽어
시계열 전체를 다시 받아 macro_raw_data.xlsx 로 저장한다.

시트 구조:
  - Wide     : date × ticker_pk 패널 (레벨 원계열, 변환 전)
  - Metadata : ticker_pk / code / descriptor / frequency 등

PCA 파이프라인과 달리 증분수집 없이 매번 START 부터 전체 재수집한다
(series ~130개 수준이라 1~2분이면 충분하고, revision 문제도 없다).
"""
import logging
import sys
from pathlib import Path

import pandas as pd

import haver_client as hc

BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "charts_config.xlsx"
OUTPUT_FILE = BASE / "macro_raw_data.xlsx"
START = "2010-01-01"   # 대시보드 원본과 동일한 시작점

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("macrographs")


def load_tickers():
    series = pd.read_excel(CONFIG_FILE, sheet_name="Series")
    col = next(c for c in series.columns if str(c).strip().lower() == "haver_ticker")
    tickers = (
        series[col].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
    )
    return tickers


def main():
    tickers = load_tickers()
    log.info("티커 %d개 로드", len(tickers))

    if not hc.initialize():
        log.error("Haver 초기화 실패 — DLX Direct 로그인/경로 확인 필요")
        return 1

    meta = hc.fetch_metadata(tickers)
    long_df = hc.fetch_series(tickers, START)
    if long_df.empty:
        log.error("수집된 데이터가 없습니다")
        return 1

    wide = (
        long_df.pivot_table(index="date", columns="ticker_pk", values="value", aggfunc="last")
        .sort_index()
    )

    got = set(wide.columns)
    missing = [t for t in tickers if hc.ticker_to_pk(t) not in got]
    if missing:
        log.warning("데이터를 못 받은 티커 %d개: %s", len(missing), ", ".join(missing))

    keep = ["ticker_pk", "code", "descriptor", "datatype", "frequency", "startdate", "enddate"]
    if not meta.empty:
        meta_out = meta[[c for c in keep if c in meta.columns]].drop_duplicates("ticker_pk")
    else:
        meta_out = pd.DataFrame(columns=keep)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        wide.to_excel(writer, sheet_name="Wide")
        meta_out.to_excel(writer, sheet_name="Metadata", index=False)
    log.info("저장 완료: %s (%d행 × %d열)", OUTPUT_FILE.name, len(wide), len(wide.columns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
