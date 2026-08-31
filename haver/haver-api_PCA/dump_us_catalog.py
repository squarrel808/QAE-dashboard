# dump_us_catalog.py — v3: US labor 코드 확정용 (USECON/CBDB/SURVEYS 전체 덤프)
# haver-api_PCA 폴더에서: python dump_us_catalog.py  →  db_catalog/catalog_<DB>.csv
import sys, time
from pathlib import Path
import pandas as pd
import Haver

BASE = Path(__file__).resolve().parent
OUT = BASE / "db_catalog"; OUT.mkdir(exist_ok=True)
TARGETS = ["USECON", "CBDB", "SURVEYS"]

try:
    Haver.direct(1); print("[init] DLX Direct on")
except Exception as e:
    print(f"[init] {e}")

for db in TARGETS:
    t0 = time.time()
    try:
        print(f"[{db}] {len(Haver.dbcodes(db))}개 코드, 메타데이터 덤프 중...")
        df = pd.DataFrame(Haver.metadata(database=db))
        if df.empty: print(f"[{db}] 0행"); continue
        df.columns = [str(c).lower() for c in df.columns]
        df.to_csv(OUT / f"catalog_{db}.csv", index=False, encoding="utf-8-sig")
        print(f"[{db}] 저장 ({len(df)}행, {time.time()-t0:.0f}초)")
    except Exception as e:
        print(f"[{db}] 실패: {e}")
print("완료")
sys.exit(0)
