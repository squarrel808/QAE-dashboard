# -*- coding: utf-8 -*-
"""
list_basket_universe.py — GS Marquee basket 유니버스 전수 조사 (+ 유럽/유로존 필터)
--------------------------------------------------------------------------------
하는 일:
  1) .env 인증 (build_pairbaskets.py 와 동일)
  2) PAIR_BASKETS_LEVELS / CUSTOM_BASKETS_LEVELS 두 데이터셋의 coverage(=수록 basket 전체)를 당김
  3) Marquee Assets API 로 assetId → 이름/bbid/region 메타데이터를 붙임
  4) 전체 목록을 basket_universe.csv 로 저장
  5) 유럽/유로존으로 보이는 것만 추려 basket_universe_europe.csv 로 저장 + 콘솔 출력

유럽 판별 기준(둘 중 하나라도 걸리면 포함):
  - 메타데이터 region 필드가 Europe
  - 이름/bbid 에 유럽 냄새가 나는 패턴 (GSPE/GSXE 프리픽스, Europe/Euro/SXXP/SX5E/EU 단어 등)

실행:  (gs_api 폴더에서)  python list_basket_universe.py
"""
import os
import re
import datetime as dt
import pandas as pd
from dotenv import load_dotenv
from gs_quant.session import GsSession, Environment
from gs_quant.data import Dataset
from gs_quant.api.gs.assets import GsAssetApi

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
        rows.append({
            "dataset": ds_id,
            "assetId": aid,
            "bbid": a.get("bbid", ""),
            "name": a.get("name", ""),
            "region": a.get("region", ""),
            "type": a.get("type", ""),
            "currency": a.get("currency", ""),
        })

if not rows:
    raise SystemExit("[실패] 어떤 데이터셋에서도 coverage 를 못 받았습니다. entitlement 확인 필요.")

df = pd.DataFrame(rows)
out_all = os.path.join(SCRIPT_DIR, "basket_universe.csv")
df.to_csv(out_all, index=False, encoding="utf-8-sig")
print(f"\n[저장] 전체 {len(df)}건 → {out_all}")

# ── 유럽/유로존 필터 ──
pat = re.compile(r"europe|euro\b|eurozone|\bSXXP\b|\bSX5E\b|estoxx|stoxx", re.I)
prefix = re.compile(r"^(GSPE|GSXE|GSCBEU|GSEU)")
mask = (
    df["region"].astype(str).str.contains("Europe", case=False, na=False)
    | df["name"].astype(str).apply(lambda s: bool(pat.search(s)))
    | df["bbid"].astype(str).apply(lambda s: bool(prefix.match(s)))
)
eu = df[mask].sort_values(["dataset", "bbid"])
out_eu = os.path.join(SCRIPT_DIR, "basket_universe_europe.csv")
eu.to_csv(out_eu, index=False, encoding="utf-8-sig")
print(f"[저장] 유럽 후보 {len(eu)}건 → {out_eu}\n")

if len(eu):
    print(eu[["dataset", "bbid", "name", "region", "currency"]].to_string(index=False))
else:
    print("유럽/유로존으로 보이는 basket 이 없습니다 (두 데이터셋 기준).")

# 참고용: 지역 분포 요약
print("\n── region 분포 ──")
print(df.groupby(["dataset", "region"]).size().to_string())
print("\n── bbid 프리픽스(앞 4자리) 분포 ──")
print(df.assign(pfx=df["bbid"].str[:4]).groupby("pfx").size().sort_values(ascending=False).head(30).to_string())
print(f"\n생성: {dt.datetime.now():%Y-%m-%d %H:%M}")
