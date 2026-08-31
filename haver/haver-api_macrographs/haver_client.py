# haver_client.py
"""
Haver DLX Direct 최소 래퍼 (haver-api_PCA/haver_provider.py 축약판).
- initialize(): Haver.direct(1) + HAVER_PATH/DLXPAR 경로 복구
- fetch_metadata(tickers): DataFrame(database, code, descriptor, frequency, ...) + ticker_pk
- fetch_series(tickers, start): long-form DataFrame(date, ticker_pk, value)
"""
import os
import warnings
import logging

import pandas as pd
import Haver

log = logging.getLogger("macrographs")


def ticker_to_pk(ticker: str) -> str:
    """'CODE@DATABASE' -> 'database:code' (소문자). Haver metadata의 키 형식과 통일."""
    s = str(ticker).strip()
    if "@" in s:
        code, db = s.split("@", 1)
        return f"{db.strip().lower()}:{code.strip().lower()}"
    return s.lower()


def initialize() -> bool:
    try:
        haver_path = os.getenv("HAVER_PATH", "").strip()
        if haver_path:
            Haver.path(haver_path)
        Haver.direct(1)
        # 경로가 비어 있으면 ini/auto로 복구 시도 (PCA 파이프라인과 동일한 순서)
        try:
            current = Haver.path()
        except Exception:
            current = None
        if current in ("", None):
            for mode, env in (("ini", "DLXPAR"), ("auto", "DLXDB")):
                if os.getenv(env, "").strip():
                    try:
                        Haver.path(mode)
                        break
                    except Exception:
                        pass
        return True
    except Exception as exc:
        log.error("Haver init 실패: %s", exc)
        return False


def fetch_metadata(tickers):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            meta = Haver.metadata(tickers)
    except Exception as exc:
        log.warning("metadata 배치 실패(%s) — 티커별 재시도", exc)
        meta = None

    if not isinstance(meta, pd.DataFrame) or meta.empty:
        frames = []
        for t in tickers:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    one = Haver.metadata([t])
                if isinstance(one, pd.DataFrame) and not one.empty:
                    frames.append(one)
                else:
                    log.warning("metadata 없음: %s", t)
            except Exception as exc:
                log.warning("metadata 실패: %s (%s)", t, exc)
        meta = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if meta.empty:
        return meta
    meta = meta.copy()
    meta.columns = [c.lower() for c in meta.columns]
    meta["ticker_pk"] = (
        meta["database"].astype(str).str.lower() + ":" + meta["code"].astype(str).str.lower()
    )
    return meta


def _to_long(data, ticker_names):
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.Series):
        data = data.to_frame()
    if not isinstance(data, pd.DataFrame) or data.empty:
        return pd.DataFrame()
    if data.shape[1] != len(ticker_names):
        log.warning("컬럼 수 불일치: 기대 %d, 실제 %d", len(ticker_names), data.shape[1])
        return pd.DataFrame()
    df = data.copy()
    df.columns = [ticker_to_pk(t) for t in ticker_names]
    df = df.reset_index().rename(columns={df.reset_index().columns[0]: "date"})
    long_df = df.melt(id_vars=["date"], var_name="ticker_pk", value_name="value").dropna(subset=["value"])
    long_df["date"] = pd.to_datetime(long_df["date"], errors="coerce")
    return long_df.dropna(subset=["date"])


def fetch_series(tickers, start, chunk_size=50):
    frames = []
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        try:
            data = Haver.data(chunk, startdate=start, dates=True)
            df = _to_long(data, chunk)
        except Exception as exc:
            log.warning("청크 실패(%s) — 티커별 재시도", exc)
            df = pd.DataFrame()
        if df.empty and len(chunk) > 1:
            parts = []
            for t in chunk:
                try:
                    one = Haver.data([t], startdate=start, dates=True)
                    p = _to_long(one, [t])
                    if not p.empty:
                        parts.append(p)
                    else:
                        log.warning("데이터 없음: %s", t)
                except Exception as exc:
                    log.warning("실패: %s (%s)", t, exc)
            df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        if not df.empty:
            frames.append(df)
        log.info("수집 %d/%d", min(i + chunk_size, len(tickers)), len(tickers))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
