# -*- coding: utf-8 -*-
"""
dump_europe_pairs.py — GS Pair/Custom Baskets 중 '유럽' 것만 발굴 + levels 인출 + CSV 저장
-------------------------------------------------------------------------------------------
목적:
  Claude(클라우드)는 GS Marquee 망에 못 붙는다. 그래서 데이터 인출은 이 PC에서 이 스크립트로
  한 번만 돌리고, 나온 CSV 2개를 Claude 세션이 회수해서 대시보드를 만든다.

하는 일:
  1) .env 인증 (build_pairbaskets.py 와 동일)
  2) PAIR_BASKETS_LEVELS (+ CUSTOM_BASKETS_LEVELS) coverage 전수 → 메타데이터(region/name/bbid) 부착
  3) '유럽/유로존' 후보만 필터
  4) 그 후보들의 일별 closePrice 를 START~오늘 까지 당김
  5) 결과 저장:
       · europe_pairs_meta.csv    (bbid, name, region, currency, dataset)  ← 분류 참고용
       · europe_pairs_levels.csv  (date, bbid, name, closePrice)           ← 대시보드 원천

실행:  (gs_api 폴더에서)
       python dump_europe_pairs.py

옵션(환경변수):
       INCLUDE_CUSTOM=false  → CUSTOM_BASKETS_LEVELS 건너뜀 (기본 true)
       START=2015-01-01      → 시작일 변경 (기본 2012-01-01)
"""
import os
import re
import datetime as dt
import pandas as pd
from dotenv import load_dotenv
from gs_quant.session import GsSession, Environment
from gs_quant.data import Dataset
from gs_quant.api.gs.assets import GsAssetApi

# ── 인증 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
CID, CSEC = os.getenv("GS_CLIENT_ID"), os.getenv("GS_CLIENT_SECRET")
if not CID or not CSEC:
    raise SystemExit(".env 에 GS_CLIENT_ID / GS_CLIENT_SECRET 가 필요합니다.")
GsSession.use(Environment.PROD, CID, CSEC, ("read_product_data",))
print("[OK] 인증")

# ── 설정 ──
INCLUDE_CUSTOM = os.getenv("INCLUDE_CUSTOM", "true").lower() != "false"
DATASETS = ["PAIR_BASKETS_LEVELS"] + (["CUSTOM_BASKETS_LEVELS"] if INCLUDE_CUSTOM else [])
_start_env = os.getenv("START", "2012-01-01")
START = dt.date.fromisoformat(_start_env)
END = dt.date.today()
FIELDS = ["id", "bbid", "name", "region", "assetClass", "type", "exchange", "currency"]

# 유럽 판별: region 이 Europe 이거나, 이름/bbid 에 유럽 냄새가 나는 패턴
PAT = re.compile(r"europe|euro\b|eurozone|\bSXXP\b|\bSX5E\b|estoxx|stoxx|\bUK\b|britain|\bDAX\b|\bCAC\b|\bFTSE\b|\bIBEX\b|\bMIB\b|swiss|\bSMI\b", re.I)
PREFIX = re.compile(r"^(GSPE|GSXE|GSCBEU|GSEU|GSEP|GXE)")


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ── 1) 전 바스켓 메타데이터 수집 ──
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
            "currency": a.get("currency", ""),
        })

if not rows:
    raise SystemExit("[실패] coverage 를 못 받았습니다. entitlement 확인 필요.")

df_meta = pd.DataFrame(rows)

# ── 2) 유럽 필터 ──
mask = (
    df_meta["region"].astype(str).str.contains("Europe", case=False, na=False)
    | df_meta["name"].astype(str).apply(lambda s: bool(PAT.search(s)))
    | df_meta["bbid"].astype(str).apply(lambda s: bool(PREFIX.match(s)))
)
eu = df_meta[mask].drop_duplicates(subset=["bbid"]).sort_values(["dataset", "bbid"]).reset_index(drop=True)
eu_meta_out = os.path.join(SCRIPT_DIR, "europe_pairs_meta.csv")
eu[["dataset", "bbid", "name", "region", "currency"]].to_csv(eu_meta_out, index=False, encoding="utf-8-sig")
print(f"\n[저장] 유럽 후보 {len(eu)}건 → {eu_meta_out}")
if len(eu):
    print(eu[["dataset", "bbid", "name", "region", "currency"]].to_string(index=False))
else:
    raise SystemExit("유럽으로 보이는 basket 이 없습니다. 필터 패턴을 확인하세요.")

# ── 3) 유럽 후보 levels 인출 (데이터셋별로) ──
name_by_bbid = dict(zip(eu["bbid"], eu["name"]))
frames = []
for ds_id in DATASETS:
    bbids = eu.loc[eu["dataset"] == ds_id, "bbid"].tolist()
    if not bbids:
        continue
    print(f"\n[..] {ds_id}: 유럽 {len(bbids)}개 levels 인출 중 (시간 걸릴 수 있음)")
    for ch in _chunks(bbids, 50):
        try:
            part = Dataset(ds_id).get_data(START, END, bbid=ch)
            if len(part):
                frames.append(part)
        except Exception as e:
            print(f"    [경고] chunk 실패 (건너뜀): {str(e)[:120]}")

if not frames:
    raise SystemExit("[실패] levels 를 하나도 못 받았습니다.")

lv = pd.concat(frames)
if "date" not in lv.columns:
    lv = lv.reset_index()
lv["date"] = pd.to_datetime(lv["date"]).dt.date
lv["name"] = lv["bbid"].map(name_by_bbid).fillna(lv["bbid"])

out = lv[["date", "bbid", "name", "closePrice"]].dropna(subset=["closePrice"]).sort_values(["bbid", "date"])
lv_out = os.path.join(SCRIPT_DIR, "europe_pairs_levels.csv")
out.to_csv(lv_out, index=False, encoding="utf-8-sig")
print(f"\n[저장] {len(out):,}행, bbid {out['bbid'].nunique()}개 → {lv_out}")
print(f"[완료] 이 파일 2개를 Claude 세션이 회수합니다: europe_pairs_meta.csv / europe_pairs_levels.csv")
print(f"생성: {dt.datetime.now():%Y-%m-%d %H:%M}")
