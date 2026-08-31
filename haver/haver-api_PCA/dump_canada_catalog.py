# dump_canada_catalog.py
"""
캐나다 PCA 지표 선정용 — Haver 데이터베이스 카탈로그 덤프 스크립트.

haver-api_PCA 폴더에 놓고 실행하세요:
    python dump_canada_catalog.py

하는 일:
  1) CANADA 데이터베이스: 전체 메타데이터(코드/descriptor/주기/시작일) 덤프
  2) G10 / SURVEYS / CBDB / OECDMEI: 전체 메타데이터를 받은 뒤
     'Canada' 또는 코드에 '156'(Haver의 캐나다 국가코드)이 포함된 행만 필터
  3) 결과를 catalog_<DB>.csv (utf-8-sig, 엑셀에서 바로 열림)로 저장

구독이 없는 DB는 건너뛰고 로그만 남깁니다.
메타데이터 쿼리는 Haver.limits()의 영향을 받지 않으므로 (레퍼런스 가이드 4.9절)
전체 DB 덤프도 문제 없습니다. DLX Direct 모드에서는 몇 분 걸릴 수 있어요.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import Haver

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "canada_catalog"
OUT_DIR.mkdir(exist_ok=True)

# (DB이름, 필터모드)  필터모드: 'all'=전부 저장, 'canada'=Canada/156 행만
TARGETS = [
    ("CANADA",  "all"),      # StatCan 월간 지표 본진 (USECON의 캐나다 버전)
    ("G10",     "canada"),   # S&P Global PMI 등 — 캐나다는 S156* 패턴 예상
    ("SURVEYS", "canada"),   # 서베이 모음 (CFIB 등이 있을 수 있음)
    ("CBDB",    "canada"),   # Conference Board — 캐나다판 있는지 확인
    ("OECDMEI", "canada"),   # OECD MEI — N156* 패턴 (보조용)
]


def init_haver():
    try:
        Haver.direct(1)
        print("[init] DLX Direct on")
    except Exception as e:
        print(f"[init] Haver.direct 실패: {e} — 로컬 DB 경로로 시도")
    try:
        p = Haver.path()
        if not p:
            Haver.path("ini")
        print(f"[init] Haver.path = {Haver.path()!r}")
    except Exception as e:
        print(f"[init] path 확인 실패(직행 모드면 무시 가능): {e}")


def dump_db(db: str, mode: str) -> None:
    t0 = time.time()
    print(f"[{db}] 시리즈 개수 확인 중...")
    try:
        codes = Haver.dbcodes(db)
        print(f"[{db}] 총 {len(codes)}개 코드")
    except Exception as e:
        print(f"[{db}] dbcodes 실패 (구독 없음일 수 있음): {e} — 건너뜀")
        return

    print(f"[{db}] 전체 메타데이터 덤프 중... (수 분 걸릴 수 있음)")
    try:
        meta = Haver.metadata(database=db)
    except Exception as e:
        print(f"[{db}] metadata 실패: {e} — 건너뜀")
        return

    df = pd.DataFrame(meta)
    if df.empty:
        print(f"[{db}] 메타데이터 0행 — 건너뜀")
        return
    df.columns = [str(c).lower() for c in df.columns]

    if mode == "canada":
        code_col = "code" if "code" in df.columns else df.columns[0]
        mask = df[code_col].astype(str).str.contains("156", case=False, na=False)
        # 문자열 컬럼 어디든 'canada'가 들어간 행도 포함
        for c in df.columns:
            if df[c].dtype == object:
                mask |= df[c].astype(str).str.contains("canada", case=False, na=False)
        df = df[mask]
        print(f"[{db}] Canada/156 필터 후 {len(df)}행")

    out = OUT_DIR / f"catalog_{db}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[{db}] 저장 완료 → {out.name} ({len(df)}행, {time.time()-t0:.0f}초)")


def main():
    init_haver()
    for db, mode in TARGETS:
        dump_db(db, mode)
    print("\n완료. canada_catalog 폴더의 CSV들을 Claude 세션에 올려주세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
