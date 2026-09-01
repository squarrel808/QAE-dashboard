# -*- coding: utf-8 -*-
r"""
build_reports_json.py — DOCX 레코드로 Report 목록(reports.json)을 만든다.

기존에는 summarize.py 가 보따리의 PDF 를 열어 Claude 로 재요약했지만,
보따리\_자동화\daily_summary.py 가 이미 만든 통합요약 DOCX 에 같은 내용이 있다.
같은 자료를 두 번 요약할 이유가 없어 그 경로를 걷어내고 여기로 대체한다.

PDF 링크(file)는 넣지 않는다:
  - macro_hub/public/report_files 는 비어 있어 기존 링크도 전부 404 였다.
  - GS/HSBC 등 증권사 리서치는 라이선스 대상이라 공개 배포하면 안 된다.

입력 : report_pipeline/houseview_records.json  (parse_daily_docx.py 산출)
       macro_hub/public/data/houseviews.json    (있으면 키워드 보강에 사용)
출력 : macro_hub/public/data/reports.json
"""
import os, io, sys, json, hashlib, collections

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RECORDS = os.path.join(HERE, "houseview_records.json")
VIEWS = os.path.join(REPO, "macro_hub", "public", "data", "houseviews.json")
OUT = os.path.join(REPO, "macro_hub", "public", "data", "reports.json")

MAX_DAYS = int(os.environ.get("REPORTS_MAX_DAYS", "45"))   # 목록에 남길 최근 일수


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def bullets(body, limit=5):
    """본문을 문장 단위로 잘라 불릿으로. DOCX 본문은 이미 요약문이라 그대로 쪼갠다."""
    if not body:
        return []
    out, buf = [], ""
    for ch in body:
        buf += ch
        if ch in ".。!?" and len(buf.strip()) > 25:
            out.append(buf.strip())
            buf = ""
        if len(out) >= limit:
            break
    if buf.strip() and len(out) < limit:
        out.append(buf.strip())
    return [b for b in out if len(b) > 8]


def main():
    recs = load(RECORDS, [])
    if not recs:
        raise SystemExit("레코드 없음 — 먼저 parse_daily_docx.py 를 실행하세요: " + RECORDS)

    # houseviews 로 키워드 보강: 같은 (date,title) 의 자산군·권역·스탠스를 태그로
    tags = collections.defaultdict(set)
    for v in load(VIEWS, {}).get("views", []):
        k = (v.get("date"), v.get("title"))
        tags[k].add(v.get("asset"))
        if v.get("region") and v["region"] != "GLOBAL":
            tags[k].add(v["region"])
        tags[k].add(v.get("stance"))

    dates = sorted({r["date"] for r in recs if r.get("date")}, reverse=True)[:MAX_DAYS]
    keep = set(dates)

    rows, seen = [], set()
    for r in recs:
        if r.get("date") not in keep:
            continue
        if not r.get("house") or not r.get("title"):
            continue
        rid = hashlib.sha1(("%s|%s" % (r["date"], r["title"])).encode("utf-8")).hexdigest()[:12]
        if rid in seen:
            continue
        seen.add(rid)
        kw = sorted(x for x in tags.get((r["date"], r["title"]), set()) if x)
        rows.append({
            "id": rid,
            "date": r["pub_date"] or r["date"],
            "source": r["house"],
            "section": r.get("section") or "",
            "title": r["title"],
            "summary": bullets(r.get("body", "")),
            "keywords": kw or ([r.get("section")] if r.get("section") else []),
            # file 은 넣지 않는다 (라이선스·404). UI 는 file 부재를 견디게 되어 있다.
        })

    rows.sort(key=lambda x: (x["date"], x["source"]), reverse=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    print("reports.json %d건 -> %s" % (len(rows), OUT))
    print("  기간:", rows[-1]["date"], "~", rows[0]["date"] if rows else "-")
    print("  기관:", dict(collections.Counter(x["source"] for x in rows).most_common()))
    print("  요약 없음:", sum(1 for x in rows if not x["summary"]))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main()
