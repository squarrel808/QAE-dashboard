# -*- coding: utf-8 -*-
"""
수집 전용 스크립트 — 중앙은행 연설 스크래핑 → 엑셀(메타) + txt(본문)
=========================================================================
역할: 웹에서 연설 목록·본문을 한 번만 긁어 디스크에 저장한다.
      채점(score.py)은 이 결과를 '읽기만' 하므로 다시 웹을 긁지 않는다.

흐름:  scrape(웹) → is_monetary_policy 필터 → 본문은 txt, 메타는 엑셀로 저장

산출물(모두 이 스크립트가 있는 policytone 폴더 안에 저장):
  speeches_meta.xlsx   : id/date/bank/speaker/title/url/body_len/body_file
  bodies/<id>.txt      : 연설 본문 전체 (한 연설 = 한 파일)

실행:
  pip install -r requirements.txt
  python collect.py
"""

import os, sys, time, hashlib
import pandas as pd

# 콘솔이 cp949여도 비-cp949 문자 출력 시 죽지 않게 stdout/stderr UTF-8 고정
for _s in (sys.stdout, sys.stderr):
    _rc = getattr(_s, "reconfigure", None)
    if _rc:
        try:
            _rc(encoding="utf-8", errors="replace")
        except Exception:
            pass

from g7_scrapers import scrape, is_monetary_policy, set_body_cache

# ─────────────────────────────────────────────────────────────
# 설정 (hawkdove_pipeline.py 와 동일 범위로 맞춤)
# ─────────────────────────────────────────────────────────────
START_YEAR    = 2024
END_YEAR      = 2026
BANKS_TO_RUN  = ["FED", "BOJ", "ECB", "BOE"]

# 산출물 저장 폴더 = 이 스크립트(policytone)가 있는 폴더 (실행 위치와 무관)
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
BODY_DIR      = os.path.join(BASE_DIR, "bodies")               # 본문 txt 저장 폴더
META_XLSX     = os.path.join(BASE_DIR, "speeches_meta.xlsx")   # 메타데이터 엑셀
MIN_BODY_LEN  = 500                    # 본문 500자 미만은 제외(채점 단계 기준과 동일)
MAX_BODY_LEN  = 300_000                 # 비정상 과대 본문(슬라이드/색인 페이지) 제외


def _safe_id(bank: str, date, url: str) -> str:
    """파일명으로 쓸 안전한 고유 id. url 해시로 같은 연설 중복 저장 방지."""
    h = hashlib.md5((url or "").encode("utf-8")).hexdigest()[:8]
    return f"{bank}_{date or 'NA'}_{h}"


def _build_body_cache():
    """기존 speeches_meta.xlsx + bodies/ 로 {url: {date, body}} 구성.
       → 동일 URL 연설은 다시 웹에서 받지 않는다(목록만 새로 받아 신규분 탐지)."""
    if not os.path.exists(META_XLSX):
        return {}
    try:
        old = pd.read_excel(META_XLSX)
    except Exception as e:
        print("   [캐시] 기존 메타 읽기 실패 — 전체 재수집:", e)
        return {}
    cache = {}
    for _, r in old.iterrows():
        url = str(r.get("url") or "").strip()
        bf  = str(r.get("body_file") or "").strip()
        if not url or not bf:
            continue
        fp = bf if os.path.isabs(bf) else os.path.join(BASE_DIR, bf)
        if not os.path.exists(fp):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                body = f.read()
        except Exception:
            continue
        date = r.get("date")
        cache[url] = {"date": (None if pd.isna(date) else str(date)[:10]), "body": body}
    return cache


def main():
    os.makedirs(BODY_DIR, exist_ok=True)

    cache = _build_body_cache()
    set_body_cache(cache)
    print(f"[캐시] 기존 본문 {len(cache)}건 재사용(재다운로드 생략)" if cache
          else "[캐시] 기존 수집분 없음 — 전체 신규 수집")

    rows = []

    for bank in BANKS_TO_RUN:
        for year in range(START_YEAR, END_YEAR + 1):
            print(f"[{bank} {year}] 수집…")
            # scrape() 가 목록 + 본문까지 받아옴 → 통화정책 연설만 필터
            speeches = [s for s in scrape(bank, year) if is_monetary_policy(s, bank)]
            print(f"   통화정책 연설 {len(speeches)}건")

            kept = 0
            for s in speeches:
                body = s.get("body") or ""
                if not (MIN_BODY_LEN <= len(body) <= MAX_BODY_LEN):   # 너무 짧거나(빈약) 비정상 과대(슬라이드/색인) 컷
                    continue

                sid = _safe_id(bank, s.get("date"), s.get("url", ""))
                fp_abs = os.path.join(BODY_DIR, sid + ".txt")
                with open(fp_abs, "w", encoding="utf-8") as f:   # 본문 전체를 txt로
                    f.write(body)

                rows.append({
                    "id":        sid,
                    "date":      s.get("date"),
                    "bank":      bank,
                    "speaker":   s.get("speaker", ""),
                    "title":     s.get("title", ""),
                    "url":       s.get("url", ""),
                    "body_len":  len(body),
                    # 엑셀엔 폴더 기준 상대경로로 기록(가독성·이식성). score.py 가 BASE_DIR 로 복원.
                    "body_file": os.path.join("bodies", sid + ".txt"),
                })
                kept += 1

            print(f"   저장 {kept}건 (본문 ≥ {MIN_BODY_LEN}자)")
            time.sleep(1)

    if not rows:
        print("수집 결과 없음 — 종료")
        return

    # 같은 연설이 두 번 잡힌 경우 id 기준 중복 제거
    df = pd.DataFrame(rows).drop_duplicates(subset="id").reset_index(drop=True)
    df.to_excel(META_XLSX, index=False)
    print(f"\n저장 위치: {BASE_DIR}")
    print(f"  speeches_meta.xlsx ({len(df)}건 메타) / 본문 txt → bodies/")
    print("다음 단계: python score.py")


if __name__ == "__main__":
    main()
