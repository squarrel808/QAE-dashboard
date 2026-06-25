# -*- coding: utf-8 -*-
"""
raw 데이터 확인용 — 스크래퍼만 돌려서 CSV/JSON으로 저장
=====================================================
hawkdove 채점 없이, g7_scrapers 로 긁은 원본만 눈으로 보려는 용도.
원래 코드(g7_scrapers.py / hawkdove_pipeline.py)는 안 건드림.

실행:
  python check_raw.py            # 기본: FED 2021~2022
  (아래 BANKS / YEARS 만 바꾸면 됨)

결과:
  raw_speeches.csv   ← 엑셀로 열어 확인 (본문은 앞 300자만, 가벼움)
  raw_speeches.json  ← 본문 전체 포함 (원하면 전체 확인용)
"""
import os
import pandas as pd
from g7_scrapers import scrape, is_monetary_policy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 저장은 항상 이 스크립트 폴더에

# ── 여기만 바꾸면 됨 ──────────────────────────────
BANKS = ["BOJ"]            # ["FED", "BOJ"] 로 늘릴 수 있음
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]       # 보고 싶은 연도
ONLY_MONETARY = False      # True면 통화정책 연설만, False면 긁은 전부
# ────────────────────────────────────────────────

rows = []
for bank in BANKS:
    for year in YEARS:
        print(f"[{bank} {year}] 수집 중…")
        speeches = scrape(bank, year)
        for s in speeches:
            if ONLY_MONETARY and not is_monetary_policy(s, bank):
                continue
            rows.append({
                "bank": bank,
                "date": s.get("date"),
                "speaker": s.get("speaker", ""),
                "title": s.get("title", ""),
                "is_monetary": is_monetary_policy(s, bank),   # 통화정책 연설 여부
                "body_len": len(s.get("body") or ""),         # 본문 길이(0이면 본문 안 받은 것)
                "url": s.get("url", ""),
                "body": s.get("body", ""),
            })
        print(f"   → 누적 {len(rows)}건")

df = pd.DataFrame(rows)

# 1) 엑셀 확인용 CSV — 본문은 앞 300자만 (파일 가볍게)
df_view = df.copy()
df_view["body_preview"] = df_view["body"].str.slice(0, 300)
df_view.drop(columns=["body"]).to_csv(
    os.path.join(BASE_DIR, "raw_speeches.csv"), index=False, encoding="utf-8-sig")

# 2) 본문 전체 보고 싶으면 JSON
df.to_json(os.path.join(BASE_DIR, "raw_speeches.json"),
           orient="records", force_ascii=False, indent=2)

# 3) 콘솔 요약
print("\n=== 수집 요약 ===")
print(f"총 {len(df)}건")
if len(df):
    print(f"통화정책 연설(is_monetary=True): {df['is_monetary'].sum()}건")
    print(f"본문 있는 것(body_len>0): {(df['body_len']>0).sum()}건")
    print("\n샘플 5건:")
    print(df[["date","speaker","title","is_monetary","body_len"]].head().to_string(index=False))
print("\n저장: raw_speeches.csv (엑셀용) / raw_speeches.json (본문 전체)")