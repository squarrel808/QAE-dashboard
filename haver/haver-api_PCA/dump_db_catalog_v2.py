# dump_db_catalog_v2.py
"""
다국가 PCA 티커 선정용 — Haver 데이터베이스 카탈로그 덤프 v2.

haver-api_PCA 폴더에 놓고 실행:
    python dump_db_catalog_v2.py

v1(dump_canada_catalog.py)과 동일 원리로, 이번엔 AU/DE/JP/UK용 DB들을 덤프.
결과는 db_catalog/catalog_<DB>.csv (utf-8-sig).

- DB 이름이 확실치 않은 것들은 후보를 여러 개 넣어뒀고, 없으면 자동 스킵.
- 대형 DB도 메타데이터 쿼리는 Haver.limits() 제한을 안 받음(가이드 4.9절).
  다만 DLX Direct라 DB당 수 분 걸릴 수 있음 → 전체 10~30분 각오.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import Haver

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "db_catalog"
OUT_DIR.mkdir(exist_ok=True)

# (DB이름 후보들, 필터 regex 또는 None=전부저장)
# 필터는 code/descriptor 어디든 매치되면 남김 (대형 다국가 DB 용량 절약용)
TARGETS = [
    (["ANZ", "AUSNZ", "AUSTRALIA"], None),            # 호주/뉴질랜드 (NAB, Westpac, ABS)
    (["GERMANY"], None),                               # 독일 (ifo, StBA, Bbk)
    (["JAPAN"], None),                                 # 일본 (METI, CAO, MHLW)
    (["UK", "UKDATA"], None),                          # 영국 (ONS, CBI, GfK, RICS)
    (["INTSRVYS"], None),                              # 국제 서베이 (S193* 등)
    (["G10"], None),                                   # 다국가 헤드라인 (S1xx/H1xx/N1xx)
    (["MARKIT", "PMI", "MARKITPMI", "SPGPMI"], None),  # S&P Global PMI류
    (["EUDATA"], r"germany|134"),                      # EC 서베이 중 독일만
    (["OECDMEI"], r"111|112|134|156|158|193"),         # OECD MEI 주요국만 (US/UK/DE/CA/JP/AU)
]

done = set()


def init_haver():
    try:
        Haver.direct(1)
        print("[init] DLX Direct on")
    except Exception as e:
        print(f"[init] Haver.direct 실패: {e}")


def dump_db(db: str, filt) -> bool:
    t0 = time.time()
    try:
        codes = Haver.dbcodes(db)
        print(f"[{db}] 총 {len(codes)}개 코드")
    except Exception as e:
        print(f"[{db}] 없음/구독없음 → 스킵 ({str(e)[:80]})")
        return False

    print(f"[{db}] 메타데이터 덤프 중...")
    try:
        meta = Haver.metadata(database=db)
    except Exception as e:
        print(f"[{db}] metadata 실패: {e}")
        return False

    df = pd.DataFrame(meta)
    if df.empty:
        print(f"[{db}] 0행 → 스킵")
        return False
    df.columns = [str(c).lower() for c in df.columns]

    if filt:
        code_col = "code" if "code" in df.columns else df.columns[0]
        mask = df[code_col].astype(str).str.contains(filt, case=False, na=False)
        for c in df.columns:
            if df[c].dtype == object:
                mask |= df[c].astype(str).str.contains(filt, case=False, na=False)
        df = df[mask]
        print(f"[{db}] 필터 후 {len(df)}행")

    out = OUT_DIR / f"catalog_{db}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[{db}] 저장 → {out.name} ({len(df)}행, {time.time()-t0:.0f}초)")
    return True


def main():
    init_haver()
    for candidates, filt in TARGETS:
        for db in candidates:
            if db in done:
                continue
            if dump_db(db, filt):
                done.add(db)
                break  # 후보 중 하나 성공하면 다음 타깃으로
    print("\n완료. db_catalog 폴더의 CSV들을 Claude 세션에 알려주세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
