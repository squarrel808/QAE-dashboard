# -*- coding: utf-8 -*-
"""
summarize.py — 다운로드된 리서치 PDF를 Claude로 요약해 reports.json 으로 만든다.

흐름:
  1) 다운로드 폴더(보따리\\YYMMDD)의 *.pdf 중 아직 처리 안 한 것만 고른다(state.json 으로 중복 방지)
  2) 파일명에서 기관(source)·섹션(section)·대략 제목을 뽑는다
  3) PDF 텍스트 추출(pdfplumber) → Claude API 로 {title, summary[], keywords[]} 생성
  4) PDF를 저장소에 올린다 (STORAGE=local 이면 macro_hub/public/report_files 로 복사,
     STORAGE=r2 이면 Cloudflare R2 업로드) → 다운로드 URL 획득
  5) reports.json 에 레코드 append, state.json 갱신

실행:  python summarize.py
설정:  .env (.env.example 참고)
필요:  pip install -r requirements.txt
"""
import os
import re
import json
import time
import shutil
import hashlib
import datetime as dt

# ---- 선택적 의존성 (없으면 친절히 안내) ----
try:
    import pdfplumber
except ImportError:
    raise SystemExit("pdfplumber 필요: pip install -r requirements.txt")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# ===================== 설정 =====================
# 다운로드 루트 (셀레니움이 보따리\YYMMDD 로 떨군 곳) — 기본값: 이 폴더 안의 보따리
DOWNLOAD_ROOT = os.environ.get("DOWNLOAD_ROOT", os.path.join(HERE, "보따리"))
# reports.json 위치 (사이트가 읽는 곳)
REPORTS_JSON = os.environ.get("REPORTS_JSON", os.path.join(REPO, "macro_hub", "public", "data", "reports.json"))
# 로컬 저장 모드일 때 PDF 복사 위치 (사이트 public/)
PUBLIC_DIR = os.path.join(REPO, "macro_hub", "public")
STATE_FILE = os.path.join(HERE, "state.json")

STORAGE = os.environ.get("STORAGE", "local").lower()         # local | r2
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
MAX_PAGES = int(os.environ.get("MAX_PAGES", "8"))            # PDF 앞 N페이지만 읽음
MAX_CHARS = int(os.environ.get("MAX_CHARS", "12000"))       # Claude에 보낼 텍스트 상한

# R2 (STORAGE=r2 일 때만)
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "")
R2_PUBLIC_BASE = os.environ.get("R2_PUBLIC_BASE", "")        # 예: https://pub-xxxx.r2.dev

# 파일명 prefix → (기관, 섹션) 매핑
GS_SECTIONS = {
    "Overall_Most_Popular_Research": "Overall Most Popular",
    "Economics_Research": "Economics",
    "Equity_Research": "Equity",
    "Beyond_Research": "Beyond",
    "Portfolio_Strategy_Research": "Portfolio Strategy",
}
# ================================================

FNAME_RE = re.compile(r"^(?P<sec>.+?)_(?P<tf>1d|now|day|\d+d|\d{6})_(?P<idx>\d{2})_(?P<title>.*)\.pdf$", re.I)


def parse_filename(fname):
    """파일명 → (source, section, rough_title). 못 풀면 (Unknown, '', 파일명)."""
    m = FNAME_RE.match(fname)
    if not m:
        return "Unknown", "", os.path.splitext(fname)[0]
    sec = m.group("sec")
    title = m.group("title").strip()
    if sec in GS_SECTIONS:
        return "GS", GS_SECTIONS[sec], title
    if sec == "BofA":
        return "BofA", "Trending", title
    if sec == "JPMM_Research":
        return "JPM", "Research", title
    if sec == "HSBC_MostRead":
        return "HSBC", "Most Read", title
    if sec == "HSBC_HouseViews":
        return "HSBC", "House Views", title
    return sec.split("_")[0], sec.replace("_", " "), title


def pdf_text(path, max_pages=MAX_PAGES, max_chars=MAX_CHARS):
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:max_pages]:
            out.append(page.extract_text() or "")
    return "\n".join(out)[:max_chars].strip()


def claude_summarize(text, hint_title, source, section):
    """Claude API → {title, summary:[...], keywords:[...]} (JSON 고정)."""
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = (
        "다음은 증권사 리서치 리포트의 앞부분 텍스트입니다. 한국 기관투자가(펀드매니저)를 위해 "
        "핵심을 정리하세요. 반드시 아래 JSON 형식으로만 답하세요(설명·코드블록 없이 JSON만):\n"
        '{"title": "리포트 정식 제목(영문 원제 유지)", '
        '"summary": ["핵심 불릿 한국어 3~4개, 각 1문장"], '
        '"keywords": ["소문자 영문 태그 5~8개"]}\n\n'
        f"[기관] {source}  [섹션] {section}\n"
        f"[파일명에서 추정한 제목] {hint_title}\n\n"
        f"[본문]\n{text}"
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    # JSON만 추출 (혹시 군더더기 있으면 중괄호 범위로 잘라냄)
    s, e = raw.find("{"), raw.rfind("}")
    rec = json.loads(raw[s:e + 1])
    rec["title"] = str(rec.get("title") or hint_title).strip()
    rec["summary"] = [str(x).strip() for x in (rec.get("summary") or []) if str(x).strip()]
    rec["keywords"] = [str(x).strip().lower() for x in (rec.get("keywords") or []) if str(x).strip()]
    return rec


def store_pdf(local_path, date_str, fname):
    """PDF를 저장소에 올리고 다운로드 URL(또는 사이트 상대경로)을 반환."""
    if STORAGE == "r2":
        import boto3
        s3 = boto3.client(
            "s3", endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY, aws_secret_access_key=R2_SECRET_KEY,
            region_name="auto",
        )
        key = f"reports/{date_str}/{fname}"
        s3.upload_file(local_path, R2_BUCKET, key, ExtraArgs={"ContentType": "application/pdf"})
        return f"{R2_PUBLIC_BASE.rstrip('/')}/{key}"
    # local: 사이트 public/report_files 로 복사 → 상대경로 반환
    rel = f"/report_files/{date_str}/{fname}"
    dest = os.path.join(PUBLIC_DIR, rel.lstrip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(local_path, dest)
    return rel


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def find_target_folders():
    """오늘 폴더 우선, 없으면 보따리 하위 YYMMDD 폴더 전부."""
    if not os.path.isdir(DOWNLOAD_ROOT):
        raise SystemExit("다운로드 폴더 없음: " + DOWNLOAD_ROOT)
    today = dt.datetime.now().strftime("%y%m%d")
    todo = os.path.join(DOWNLOAD_ROOT, today)
    if os.path.isdir(todo):
        return [todo]
    return [os.path.join(DOWNLOAD_ROOT, d) for d in sorted(os.listdir(DOWNLOAD_ROOT))
            if re.fullmatch(r"\d{6}", d) and os.path.isdir(os.path.join(DOWNLOAD_ROOT, d))]


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(".env 에 ANTHROPIC_API_KEY 를 넣어주세요 (.env.example 참고)")

    state = load_json(STATE_FILE, {"done": []})
    done = set(state["done"])
    reports = load_json(REPORTS_JSON, [])
    existing_ids = {r.get("id") for r in reports}

    added = 0
    for folder in find_target_folders():
        date_iso = "20" + os.path.basename(folder)[:2] + "-" + os.path.basename(folder)[2:4] + "-" + os.path.basename(folder)[4:6]
        date_str = os.path.basename(folder)
        for fname in sorted(os.listdir(folder)):
            if not fname.lower().endswith(".pdf"):
                continue
            path = os.path.join(folder, fname)
            uid = hashlib.md5((date_str + "/" + fname).encode()).hexdigest()[:12]
            if uid in done or uid in existing_ids:
                continue
            source, section, hint = parse_filename(fname)
            try:
                text = pdf_text(path)
                if len(text) < 100:
                    print(f"  [skip] 텍스트 거의 없음(스캔 PDF?): {fname}")
                    done.add(uid); continue
                rec = claude_summarize(text, hint, source, section)
                url = store_pdf(path, date_str, fname)
                reports.append({
                    "id": uid, "date": date_iso, "source": source, "section": section,
                    "title": rec["title"], "summary": rec["summary"],
                    "keywords": rec["keywords"], "file": url,
                })
                done.add(uid); added += 1
                print(f"  [ok] {source}·{section}  {rec['title'][:50]}")
                time.sleep(0.5)
            except Exception as e:
                print(f"  [fail] {fname} -> {repr(e)[:120]}")

    # 최신순 정렬 후 저장
    reports.sort(key=lambda r: (r.get("date", ""), r.get("source", "")), reverse=True)
    os.makedirs(os.path.dirname(REPORTS_JSON), exist_ok=True)
    json.dump(reports, open(REPORTS_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"done": sorted(done)}, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n완료: 새 요약 {added}건  | 총 {len(reports)}건  -> {REPORTS_JSON}  (STORAGE={STORAGE})")


if __name__ == "__main__":
    main()
