"""
GS Marquee API 연결 테스트 스크립트
-----------------------------------
목적: HTML 대시보드에 붙이기 전에 (1) 인증이 되는지, (2) 페어 바스켓이
      어느 데이터셋 ID로 조회되는지, (3) 데이터가 어떤 형태로 나오는지 확인.

실행 전 준비:
  pip install gs-quant
  자격증명은 코드에 직접 박지 말고 환경변수로:
    Windows(PowerShell):  $env:GS_CLIENT_ID="..."; $env:GS_CLIENT_SECRET="..."
  (또는 아래 CLIENT_ID/SECRET 변수에 직접 넣고 돌려도 됨 — 테스트 후 지우기)
"""

import os
import datetime as dt
import pandas as pd
from dotenv import load_dotenv          # pip install python-dotenv
from gs_quant.session import GsSession, Environment
from gs_quant.data import Dataset

# ── 0) 자격증명 ───────────────────────────────────────────────
# 실행 위치와 상관없이 "이 스크립트가 있는 폴더"의 .env 를 읽음
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
CLIENT_ID     = os.getenv("GS_CLIENT_ID")
CLIENT_SECRET = os.getenv("GS_CLIENT_SECRET")
if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit("자격증명이 없습니다. 같은 폴더에 .env 파일을 만들고 "
                     "GS_CLIENT_ID / GS_CLIENT_SECRET 를 넣으세요.")

# ── 1) 인증 (세션 1회) ────────────────────────────────────────
GsSession.use(Environment.PROD, CLIENT_ID, CLIENT_SECRET, ('read_product_data',))
print("[OK] 인증 성공\n")

# ── 2) 조회 파라미터 ──────────────────────────────────────────
TEST_BBID = "GSPUGRVA"          # GS Growth vs Value (팩터 페어 하나로 테스트)
start = dt.date(2024, 1, 1)
end   = dt.date.today()

# 페어 바스켓이 어느 데이터셋 ID로 사는지 모르므로 후보 둘 다 시도
CANDIDATE_DATASETS = ["CUSTOM_BASKETS_LEVELS", "PAIR_BASKETS_LEVELS"]

def try_pull(ds_id, key, value):
    """ds_id 데이터셋을 key=value 로 조회 시도. 성공하면 DataFrame, 실패하면 None."""
    try:
        df = Dataset(ds_id).get_data(start, end, **{key: [value]})
        if df is not None and len(df) > 0:
            return df
        print(f"  - {ds_id} ({key}): 호출은 됐지만 데이터 0행")
    except Exception as e:
        print(f"  - {ds_id} ({key}): 실패 → {type(e).__name__}: {str(e)[:120]}")
    return None

# ── 3) 어느 조합이 되는지 자동 탐색 ───────────────────────────
print(f"[탐색] {TEST_BBID} 를 후보 데이터셋/식별자로 조회 시도")
result, used = None, None
for ds_id in CANDIDATE_DATASETS:
    for key in ("bbid", "assetId"):     # bbid 먼저, 안 되면 assetId
        df = try_pull(ds_id, key, TEST_BBID if key == "bbid" else "MA8MZG4ENC16TVNR")
        if df is not None:
            result, used = df, (ds_id, key)
            break
    if result is not None:
        break

# ── 4) 결과 출력 ─────────────────────────────────────────────
if result is None:
    print("\n[실패] 어떤 조합으로도 데이터가 안 나왔습니다. "
          "구독(entitlement) 상태나 BBID를 확인하세요.")
else:
    ds_id, key = used
    result = result.reset_index()        # date(인덱스)를 일반 컬럼으로 꺼냄
    print(f"\n[성공] 데이터셋='{ds_id}', 식별자='{key}' 로 조회됨")
    print(f"행 수: {len(result)}  |  컬럼: {list(result.columns)}\n")
    print("── 앞 5행 ──")
    print(result.head().to_string())
    # 눈으로 보게 CSV로도 저장 (스크립트 폴더에)
    out = os.path.join(SCRIPT_DIR, "gs_test_output.csv")
    result.to_csv(out, index=False)
    print(f"\n[저장] {out} 로 떨궜습니다. 엑셀로 열어보세요.")
