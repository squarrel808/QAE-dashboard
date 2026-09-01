# -*- coding: utf-8 -*-
r"""
parse_daily_docx.py — 보따리\YYMMDD\일일리서치통합요약_*.docx 를 레코드로 뜯는다.

이미 사람이 쓰는 요약 파이프라인(보따리\_자동화\daily_summary.py)이 만들어 둔
문서라 PDF 를 다시 열 필요가 없다. 구조는 아래처럼 규칙적이다.

    매크로                                     <- 자산군 섹션 헤더
    ▪ 잭슨홀 데뷔전에서 매파 선회 …                <- 리포트 제목
    Goldman Sachs · Jan Hatzius 외 · 2026-08-28  <- 기관 · 애널리스트 · 날짜
    본문 …                                      <- 요약
    출처: Goldman Sachs Global Investment Research

주의: 본문 표기가 월별로 다르다. 8월 문서는 "· " 불릿이지만 7월 문서는 평문이다.
그래서 접두사로 본문을 판별하면 안 되고, '제목 다음 한 줄 = 메타, 그 뒤는 전부 본문'
으로 위치 기반 판별을 한다.

출력: report_pipeline/houseview_records.json  (추출 단계의 입력)
"""
import os, re, json, glob, io, sys, collections

BASE = os.environ.get("BOTARI_ROOT", r"C:\Users\infomax\Desktop\보따리")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "houseview_records.json")

SECTIONS = {
    "매크로": "매크로", "경제": "매크로", "매크로/경제": "매크로",
    "채권": "채권", "금리": "채권", "채권/금리": "채권", "fx": "채권",
    "주식": "주식", "주식전략": "주식", "종목": "주식", "종목·섹터": "주식",
    "종목/섹터": "주식", "섹터": "주식", "주식/섹터": "주식",
    "코모디티": "코모디티", "원자재": "코모디티", "commodities": "코모디티",
    # 6월 구형식은 섹션명이 영문이다 ("Economics — 신규" 처럼 접미사가 붙는다)
    "economics": "매크로", "macro": "매크로", "economy": "매크로",
    "rates": "채권", "fx": "채권", "credit": "채권", "fixedincome": "채권",
    "equity": "주식", "equities": "주식", "strategy": "주식",
    "commodity": "코모디티",
}
HOUSE = [
    # "GS_리서치요약_….docx" 처럼 언더스코어가 붙으면 \b 가 성립하지 않아
    # ^gs\b 로는 안 잡힌다. 영문자만 경계로 본다.
    (r"goldman|(?:^|[^a-z])gs(?:[^a-z]|$)", "GS"), (r"morgan stanley|\bms\b", "MS"),
    (r"j\.?p\.?\s*morgan|jpm", "JPM"), (r"bofa|bank of america|merrill", "BofA"),
    (r"citi", "Citi"), (r"hsbc", "HSBC"), (r"\bubs\b", "UBS"),
    (r"barclays", "Barclays"), (r"nomura", "Nomura"),
    (r"deutsche", "DB"), (r"credit agricole|cacib", "CACIB"),
    (r"\bbnp\b", "BNP"), (r"soc\w*gen|\bsg\b", "SG"),
]
DATE_RE = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")
BULLET = "\u25aa"      # ▪
MIDDOT = "\u00b7"      # ·
NUMTITLE = re.compile(r"^\d{1,2}\.\s+\S")   # 6월 구형식 제목: "1. Global Markets Daily …"


def norm_house(text):
    t = (text or "").lower()
    for pat, name in HOUSE:
        if re.search(pat, t):
            return name
    return None


def parse_doc(path):
    from docx import Document
    ps = [p.text.strip() for p in Document(path).paragraphs if p.text.strip()]

    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    doc_date = m.group(1) if m else ""

    # 8월 문서의 "핵심 차트 8선"도 "1." 로 시작하므로, ▪ 가 하나도 없는
    # 6월 구형식 문서에서만 번호를 제목으로 인정한다.
    use_num = not any(x.startswith(BULLET) for x in ps)

    recs, section, cur, expect_meta = [], None, None, False
    for t in ps:
        key = t.lower().strip().rstrip(":\uff1a").replace(" ", "")

        # 1) 리포트 제목 — 새 레코드. 바로 다음 줄은 메타다.
        if t.startswith(BULLET) or (use_num and NUMTITLE.match(t)):
            if cur:
                recs.append(cur)
            cur = {"date": doc_date, "section": section or "기타",
                   "title": re.sub(r"^\d{1,2}\.\s*", "", t.lstrip(BULLET)).strip(),
                   "house": None,
                   "analysts": "", "pub_date": "", "body": []}
            expect_meta = True
            continue

        # 2) 섹션 헤더 (메타 대기 중이 아닐 때만)
        if (not expect_meta and len(t) <= 24 and key in SECTIONS
                and not t.startswith((MIDDOT, "출처"))):
            section = SECTIONS[key]
            continue

        if cur is None:
            continue

        # 3) 메타 줄 — 제목 바로 다음 한 줄
        if expect_meta:
            expect_meta = False
            cur["house"] = norm_house(t)
            dm = DATE_RE.search(t)
            if dm:
                cur["pub_date"] = "%s-%02d-%02d" % (dm.group(1), int(dm.group(2)), int(dm.group(3)))
            parts = [x.strip() for x in t.split(MIDDOT)]
            cur["analysts"] = parts[1] if len(parts) >= 3 else ""
            continue

        # 4) 출처 줄
        if t.startswith("출처"):
            cur["house"] = cur["house"] or norm_house(t)
            continue

        # 5) 나머지는 전부 본문
        cur["body"] += [x.strip(" " + MIDDOT) for x in t.split("\n") if x.strip(" " + MIDDOT)]

    if cur:
        recs.append(cur)

    # 6월 구형식은 메타가 "Economics Research · 2026-06-16" 처럼 기관명이 없고
    # 파일명("GS_리서치요약_…")에만 있다. 못 잡은 건 파일명으로 보강한다.
    from_name = norm_house(os.path.basename(path))
    for r in recs:
        r["body"] = " ".join(r["body"])[:2500]
        r["pub_date"] = r["pub_date"] or r["date"]
        r["house"] = r["house"] or from_name
    return recs


def main():
    files = sorted(glob.glob(os.path.join(BASE, "*", "*요약*.docx")))
    print("DOCX %d개" % len(files))
    allrecs, bad = [], []
    for f in files:
        try:
            rs = parse_doc(f)
            allrecs += rs
            if not rs:
                bad.append((f, "레코드 0"))
        except Exception as e:
            bad.append((f, "%s: %s" % (type(e).__name__, e)))

    seen, uniq = set(), []
    for r in allrecs:
        k = (r["date"], r["title"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(uniq, fp, ensure_ascii=False, indent=1)
    print("레코드 %d개 (중복 제거 후) -> %s" % (len(uniq), OUT))
    print("  섹션:", dict(collections.Counter(r["section"] for r in uniq)))
    print("  기관:", dict(collections.Counter(r["house"] or "?" for r in uniq).most_common(12)))
    print("  본문 없음:", sum(1 for r in uniq if not r["body"]))
    print("  본문 평균 길이:", int(sum(len(r["body"]) for r in uniq) / max(1, len(uniq))))
    if bad:
        print("  문제 파일 %d개:" % len(bad))
        for f, e in bad[:8]:
            print("   ", os.path.basename(f), e)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main()
