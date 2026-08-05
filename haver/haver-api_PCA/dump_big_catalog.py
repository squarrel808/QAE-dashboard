# dump_big_catalog.py
"""
대형 Haver 데이터베이스 카탈로그 덤프 (청크 + 중간저장 + 이어받기).

dump_db_catalog_v2.py 는 DB 하나당 Haver.metadata(database=DB) 를 한 번에 호출한다.
UK 처럼 시리즈가 수십만 개인 DB 는 이 호출이 통째로 실패해서 CSV 가 아예 안 생긴다
(실제로 db_catalog 에 catalog_UK.csv 만 빠져 있었다).

이 스크립트는:
  1) 먼저 한 방 호출을 시도한다 (되면 그게 제일 빠름)
  2) 실패하면 dbcodes 로 코드 목록을 받아 CHUNK 개씩 나눠 metadata 를 조회
  3) 청크마다 CSV 에 append — 중간에 끊겨도 받은 데까지 남는다
  4) 다시 실행하면 이미 받은 코드는 건너뛴다 (이어받기)

실행:
    python dump_big_catalog.py                # 기본: UK
    python dump_big_catalog.py UK JAPAN       # DB 여러 개
    python dump_big_catalog.py UK --chunk 500 # 청크 크기 조정
    python dump_big_catalog.py UK --fresh     # 이어받기 무시하고 처음부터

결과: db_catalog/catalog_<DB>.csv (utf-8-sig)
"""
import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import Haver

BASE      = Path(__file__).resolve().parent
OUT_DIR   = BASE / "db_catalog"
CHUNK     = 1000          # 한 번에 조회할 코드 수 (실패하면 절반씩 자동 축소)
MIN_CHUNK = 25            # 이보다 작아지면 그 구간은 포기하고 넘어감

# 카탈로그에서 실제로 쓰는 컬럼. 없으면 있는 것만 저장한다.
WANT_COLS = ["database", "code", "startdate", "enddate", "frequency", "descriptor",
             "numobs", "datetimemod", "magnitude", "decprecision", "diftype",
             "aggtype", "datatype", "group", "geography1", "geography2",
             "shortsource", "longsource"]


def init_haver():
    try:
        Haver.direct(1)
        print("[init] DLX Direct on")
    except Exception as e:
        print(f"[init] Haver.direct 실패(계속 진행): {e}")


def normalize(df, db):
    df = pd.DataFrame(df)
    if df.empty:
        return df
    df.columns = [str(c).lower() for c in df.columns]
    if "database" not in df.columns:
        df["database"] = db.lower()
    keep = [c for c in WANT_COLS if c in df.columns]
    extra = [c for c in df.columns if c not in keep]
    return df[keep + extra]


def meta_call(arg):
    """Haver.metadata 호출. 실패하면 빈 DataFrame."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            out = Haver.metadata(arg)
    except Exception as e:
        return pd.DataFrame(), str(e)[:120]
    if isinstance(out, pd.DataFrame):
        return out, None
    return pd.DataFrame(), f"비정상 응답 {type(out).__name__}"


def load_done(path):
    """이미 받아둔 코드 집합 (이어받기용)."""
    if not path.exists():
        return set(), 0
    try:
        prev = pd.read_csv(path, low_memory=False)
    except Exception:
        return set(), 0
    col = "code" if "code" in prev.columns else prev.columns[0]
    return set(prev[col].astype(str).str.lower()), len(prev)


def dump(db, chunk_size, fresh):
    out = OUT_DIR / f"catalog_{db}.csv"
    t0 = time.time()

    # --- 1) 한 방 호출 시도 ---
    if fresh or not out.exists():
        print(f"[{db}] 전체 메타데이터 한 번에 시도...")
        df, err = meta_call_db(db)
        if not df.empty:
            normalize(df, db).to_csv(out, index=False, encoding="utf-8-sig")
            print(f"[{db}] 저장 → {out.name} ({len(df)}행, {time.time()-t0:.0f}초)")
            return True
        print(f"[{db}] 한 방 호출 실패 ({err}) → 청크 방식으로 전환")

    # --- 2) 코드 목록 ---
    try:
        codes = [str(c) for c in Haver.dbcodes(db)]
    except Exception as e:
        print(f"[{db}] dbcodes 실패 — 구독 없음일 수 있음: {str(e)[:100]}")
        return False
    print(f"[{db}] 총 코드 {len(codes):,}개")

    done, nrows = (set(), 0) if fresh else load_done(out)
    if fresh and out.exists():
        out.unlink()
    todo = [c for c in codes if c.lower() not in done]
    if done:
        print(f"[{db}] 이어받기 — 이미 {len(done):,}개 보유, 남은 {len(todo):,}개")
    if not todo:
        print(f"[{db}] 받을 것 없음 ({nrows:,}행)")
        return True

    # --- 3) 청크 조회 + 중간 저장 ---
    header = not out.exists()
    got = failed = 0
    i = 0
    size = chunk_size
    while i < len(todo):
        batch = todo[i:i + size]
        df, err = meta_call(batch)
        if df.empty and size > MIN_CHUNK:
            size = max(MIN_CHUNK, size // 2)   # 큰 배치가 터지면 줄여서 재시도
            print(f"  [{db}] {i:,}~ 실패({err}) → 청크 {size} 로 축소 후 재시도")
            continue
        if df.empty:
            failed += len(batch)
            print(f"  [{db}] {i:,}~{i+len(batch):,} 포기 ({err})")
        else:
            df = normalize(df, db)
            df.to_csv(out, mode="a", index=False, header=header, encoding="utf-8-sig")
            header = False
            got += len(df)
        i += len(batch)
        if i % (size * 10) < size:
            el = time.time() - t0
            print(f"  [{db}] {i:,}/{len(todo):,} ({got:,}행, {el:.0f}초, "
                  f"남은 예상 {el/max(i,1)*(len(todo)-i):.0f}초)")
        size = min(chunk_size, size * 2)        # 성공하면 다시 키움

    print(f"[{db}] 저장 → {out.name} (신규 {got:,}행, 실패 {failed:,}개, {time.time()-t0:.0f}초)")
    return got > 0


def meta_call_db(db):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            out = Haver.metadata(database=db)
    except Exception as e:
        return pd.DataFrame(), str(e)[:120]
    if isinstance(out, pd.DataFrame):
        return out, None
    return pd.DataFrame(), f"비정상 응답 {type(out).__name__}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    chunk = CHUNK
    if "--chunk" in sys.argv:
        chunk = int(sys.argv[sys.argv.index("--chunk") + 1])
    fresh = "--fresh" in sys.argv

    dbs = [a.upper() for a in args] or ["UK"]
    OUT_DIR.mkdir(exist_ok=True)
    init_haver()

    ok = []
    for db in dbs:
        print()
        if dump(db, chunk, fresh):
            ok.append(db)
    print(f"\n완료: {ok or '없음'}")
    print("이후 fill_preprocess_rules.py / 지표 선정 시 db_catalog 의 startdate·enddate 를 먼저 볼 것.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
