# -*- coding: utf-8 -*-
"""
list_basket_universe_v2.py — GS basket 유니버스 전수 조사 + 자동 분류
--------------------------------------------------------------------------------
list_basket_universe.py 의 업그레이드판.
  1) .env 인증 (기존과 동일)
  2) PAIR_BASKETS_LEVELS / CUSTOM_BASKETS_LEVELS 두 데이터셋 coverage(=수록 basket 전체)
  3) Marquee Assets API 로 assetId → 이름/bbid/region/type/currency 메타 부착
  4) basket_classify.classify() 로 category/sector/factor_or_theme/region/needs_review 자동 분류
  5) 결과 저장:
       · basket_universe_classified.csv   (전체 + 분류 컬럼)         ← 메인 산출물
       · basket_universe_review.csv        (needs_review=True 만)     ← 사람이 볼 목록
  6) 콘솔에 category/sector 분포 요약 출력

실행:  (gs_api 폴더에서)  python list_basket_universe_v2.py
       ※ basket_classify.py 가 같은 폴더에 있어야 함
필요:  pip install gs-quant python-dotenv pandas
"""
import os
import datetime as dt
import pandas as pd
from dotenv import load_dotenv
from gs_quant.session import GsSession, Environment
from gs_quant.data import Dataset
from gs_quant.api.gs.assets import GsAssetApi

from basket_classify import classify   # 같은 폴더의 분류기

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
CID, CSEC = os.getenv("GS_CLIENT_ID"), os.getenv("GS_CLIENT_SECRET")
if not CID or not CSEC:
    raise SystemExit(".env 에 GS_CLIENT_ID / GS_CLIENT_SECRET 가 필요합니다.")
GsSession.use(Environment.PROD, CID, CSEC, ("read_product_data",))
print("[OK] 인증")

DATASETS = ["PAIR_BASKETS_LEVELS", "CUSTOM_BASKETS_LEVELS"]
FIELDS = ["id", "bbid", "name", "region", "assetClass", "type", "exchange", "currency"]


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


rows = []
for ds_id in DATASETS:
    try:
        cov = Dataset(ds_id).get_coverage()
    except Exception as e:
        print(f"[실패] {ds_id} coverage: {type(e).__name__}: {str(e)[:150]}")
        continue
    if cov is None or len(cov) == 0:
        print(f"[경고] {ds_id} coverage 0건")
        continue
    ids = sorted(set(cov["assetId"])) if "assetId" in cov.columns else []
    print(f"[..] {ds_id}: basket {len(ids)}개 — 메타데이터 조회 중")

    meta = {}
    for ch in _chunks(ids, 200):
        try:
            assets = GsAssetApi.get_many_assets_data(id=ch, fields=FIELDS, limit=len(ch))
            for a in assets:
                meta[a.get("id")] = a
        except Exception as e:
            print(f"    [경고] 메타 chunk 실패 (건너뜀): {str(e)[:120]}")

    for aid in ids:
        a = meta.get(aid, {})
        name = a.get("name", "")
        bbid = a.get("bbid", "")
        region = a.get("region", "")
        typ = a.get("type", "")
        cls = classify(name, bbid, region, typ)
        rows.append({
            "dataset": ds_id,
            "category": cls["category"],
            "sector": cls["sector"],
            "factor_or_theme": cls["factor_or_theme"],
            "region": cls["region"],
            "bbid": bbid,
            "name": name,
            "currency": a.get("currency", ""),
            "type": typ,
            "assetId": aid,
            "needs_review": cls["needs_review"],
        })

if not rows:
    raise SystemExit("[실패] 어떤 데이터셋에서도 coverage 를 못 받았습니다. entitlement 확인 필요.")

df = pd.DataFrame(rows).sort_values(
    ["category", "sector", "factor_or_theme", "bbid"]).reset_index(drop=True)

out_all = os.path.join(SCRIPT_DIR, "basket_universe_classified.csv")
df.to_csv(out_all, index=False, encoding="utf-8-sig")
print(f"\n[저장] 전체 {len(df)}건 → {out_all}")

review = df[df["needs_review"]]
out_rev = os.path.join(SCRIPT_DIR, "basket_universe_review.csv")
review.to_csv(out_rev, index=False, encoding="utf-8-sig")
print(f"[저장] 검토필요 {len(review)}건 → {out_rev}")

# ── 요약 ──
print("\n── category 분포 ──")
print(df.groupby("category").size().sort_values(ascending=False).to_string())
print("\n── category × sector 분포 ──")
print(df.groupby(["category", "sector"]).size().to_string())
print("\n── 지역(region) 분포 ──")
print(df.groupby("region").size().sort_values(ascending=False).to_string())
print(f"\n생성: {dt.datetime.now():%Y-%m-%d %H:%M}")
print("이 CSV 2개(basket_universe_classified.csv / basket_universe_review.csv)를 Claude 세션이 회수합니다.")
