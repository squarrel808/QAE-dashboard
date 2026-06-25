# -*- coding: utf-8 -*-
"""
중앙은행 Speech 스크래퍼 + 관련성 필터 (FED / BOJ / ECB / BOE)
==================================================
hawkdove_pipeline.py 가 import: scrape(bank, year), is_monetary_policy(speech, bank)

검증 상태:
  FED ✅  Chrome 검증: div.eventlist__event / 본문 #article (requests로 충분)
  BOJ ✅  Chrome 검증: table.res_tbl 3행 블록(Date/Speaker/Title), PDF 본문 대응
  ECB ⚠️ 공식 CSV(all_ECB_speeches.csv, '|' 구분) 일괄 다운로드 → 본문 포함. 첫 실행으로 검증 필요
  BOE ⚠️ sitemap/speeches 한 페이지에 /speech/YYYY/슬러그 링크 → 연설별 본문/날짜 fetch. 첫 실행으로 검증 필요
"""
import re, time, io, datetime as dt
from urllib.parse import urljoin
import requests
import pandas as pd
from bs4 import BeautifulSoup

HDR = {"User-Agent": "Mozilla/5.0 (research) speech-collector"}

# ─────────────────────────────────────────────────────────────
# 본문 캐시: 이미 받은 연설은 재다운로드하지 않는다.
#   collect.py 가 기존 speeches_meta.xlsx + bodies/ 로 {url: {date, body}} 를 주입.
#   목록(sitemap/list) 페이지는 새 연설 발견용으로 매번 받지만, 본문·PDF 재요청은 생략.
# ─────────────────────────────────────────────────────────────
MAX_BODY_LEN = 300_000   # 연설 1편 현실적 상한. 초과 시 슬라이드/색인 페이지로 보고 버림.
_BODY_CACHE = {}

def set_body_cache(mapping):
    """{url: {'date':..,'body':..}} 형태로 기존 수집분 주입. 빈 dict면 캐시 비활성."""
    _BODY_CACHE.clear()
    _BODY_CACHE.update(mapping or {})

def _use_cache(s) -> bool:
    """url 이 캐시에 있으면 본문·날짜를 채우고 True(재fetch 생략) 반환."""
    c = _BODY_CACHE.get(s["url"])
    if not c:
        return False
    s["body"] = c.get("body", "")
    if c.get("date"):
        s["date"] = c["date"]
    return True

BANKS = {
    "FED": {
        "origin": "https://www.federalreserve.gov",
        "list_url": "https://www.federalreserve.gov/newsevents/speech/{year}-speeches.htm",
        "voters": ["Powell","Jefferson","Williams","Bowman","Barr","Cook","Waller",
                   "Kugler","Miran","Logan","Goolsbee","Musalem","Schmid","Collins",
                   "Barkin","Yellen","Fischer","Dudley","Brainard","Clarida","Quarles"],
    },
    "BOJ": {
        "origin": "https://www.boj.or.jp",
        "list_url_candidates": [
            "https://www.boj.or.jp/en/about/press/koen_{year}/index.htm",
            "https://www.boj.or.jp/en/announcements/press/koen_{year}/index.htm/",
            "https://www.boj.or.jp/en/announcements/press/koen_{year}/index.htm",
        ],
        "voters": ["Ueda","Himino","Uchida","Adachi","Nakamura","Noguchi","Nakagawa",
                   "Takata","Tamura","Kuroda","Amamiya","Wakatabe","Iwata","Nakaso",
                   "Funo","Harada","Suzuki","Masai","Kataoka"],   # Kataoka: 2017~2022 정책위원(누락분 보완)
    },
    "ECB": {
        "origin": "https://www.ecb.europa.eu",
        # 전체 연설 1파일 CSV('|' 구분: date|speakers|title|subtitle|contents). 본문까지 들어있음.
        "csv_url": "https://www.ecb.europa.eu/press/key/shared/data/all_ECB_speeches.csv",
        # 집행이사회 + 주요 정책위원(국가별 총재). 필요시 가감.
        "voters": ["Lagarde","Guindos","Lane","Schnabel","Cipollone","Elderson","Panetta",
                   "McCaul","Nagel","Villeroy","Centeno","Knot","Rehn","Kazaks","Vujcic",
                   "Holzmann","Muller","Müller","Simkus","Šimkus","Kazimir","Kažimír","Wunsch",
                   "Escriva","Escrivá","Makhlouf","Stournaras","Vasle","Reinesch","Scicluna",
                   "Herodotou","Draghi","Visco","Weidmann","Coeure","Cœuré","Praet","Mersch"],
    },
    "BOE": {
        "origin": "https://www.bankofengland.co.uk",
        # 한 페이지에 전 연도 연설 목록(링크: /speech/YYYY/슬러그). 날짜·본문은 개별 페이지에서.
        "sitemap_url": "https://www.bankofengland.co.uk/sitemap/speeches",
        # MPC(통화정책위) 위원 중심. 규제·감독직 연설은 제목/화자 필터로 걸러짐.
        "voters": ["Bailey","Broadbent","Ramsden","Pill","Lombardelli","Breeden","Greene",
                   "Mann","Dhingra","Taylor","Haskel","Tenreyro","Cunliffe","Saunders",
                   "Vlieghe","Hauser","Bean","Carney","King"],
    },
}

INCLUDE_KW = ["monetary policy","economic outlook","inflation","interest rate",
              "price stability","economy","labor market","labour market"]
EXCLUDE_KW = ["basel","supervision","regulation","payment","cyber","fraud","fintech",
              "community bank","aml","climate","shadow bank","stablecoin","indigenous",
              "diversity","gender"]


# ─────────────────────────────────────────────────────────────
# 날짜 정규화
# ─────────────────────────────────────────────────────────────
def _normalize_date(raw):
    if not raw:
        return None
    raw = re.sub(r"\s+", " ", raw).strip()
    for fmt in ("%m/%d/%Y","%b. %d, %Y","%b %d, %Y","%B %d, %Y","%B %d,%Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return pd.to_datetime(raw).date().isoformat()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# 관련성 필터
# ─────────────────────────────────────────────────────────────
def _passes_title_prefilter(title, speaker, bank):
    """본문 받기 전 싼 필터: 제목 EXCLUDE 컷 + (가능하면) 투표권자."""
    t = (title or "").lower()
    if any(k in t for k in EXCLUDE_KW):
        return False
    sp = (speaker or "").lower()
    voters = [v.lower() for v in BANKS[bank]["voters"]]
    return any(v in sp for v in voters) if sp else True


def is_monetary_policy(speech: dict, bank: str) -> bool:
    """최종 필터: 제목 1차 + 본문 키워드 밀도."""
    if not _passes_title_prefilter(speech.get("title"), speech.get("speaker"), bank):
        return False
    title = (speech.get("title") or "").lower()
    if any(k in title for k in INCLUDE_KW):
        return True
    body = (speech.get("body") or "").lower()
    hits = sum(body.count(k) for k in ["inflation","rate","policy","growth","employ"])
    return hits >= 5


# ─────────────────────────────────────────────────────────────
# FED : 서버렌더 → requests 로 충분 (Selenium 불필요)
# ─────────────────────────────────────────────────────────────
def scrape_fed(year: int) -> list[dict]:
    url = BANKS["FED"]["list_url"].format(year=year)
    soup = BeautifulSoup(requests.get(url, headers=HDR, timeout=20).text, "html.parser")
    out = []
    for ev in soup.select("div.eventlist__event"):
        a = ev.select_one("a[href*='/speech/'][href$='.htm']")  # Watch Live 등 오선택 방지
        if not a:
            continue
        # 날짜: URL의 YYYYMMDD가 가장 확실 (예: kugler20241203a.htm → 2024-12-03)
        #   <time> 태그는 이벤트 블록 바깥(형제 열)에 있어 ev.find("time")로는 못 잡힘
        href = str(a["href"])
        m = re.search(r"(\d{8})[a-z]?\.htm", href)
        if m:
            date_iso = dt.datetime.strptime(m.group(1), "%Y%m%d").date().isoformat()
        else:
            par = ev.find_parent()                       # 폴백: 형제 <time> 태그
            tt  = par.find("time") if par else None
            date_iso = _normalize_date(tt.get_text(strip=True) if tt else None)
        sp = ev.find("p", class_="news__speaker")
        out.append({
            "date": date_iso,
            "speaker": sp.get_text(strip=True) if sp else "",
            "title": a.get_text(strip=True),
            "url": urljoin(BANKS["FED"]["origin"], href),
            "body": "",
        })
    # 중복 제거 (같은 연설 두 번 잡힘 방지)
    seen, uniq = set(), []
    for s in out:
        if s["url"] not in seen and s["title"]:
            seen.add(s["url"]); uniq.append(s)
    # 본문: 제목 1차 필터 통과분만 fetch
    for s in uniq:
        if _use_cache(s):                                    # 이미 받은 연설 → 재다운로드 생략
            continue
        if not _passes_title_prefilter(s["title"], s["speaker"], "FED"):
            continue
        try:
            bs = BeautifulSoup(requests.get(s["url"], headers=HDR, timeout=20).text, "html.parser")
            art = bs.find(id="article") or bs.find("div", class_="col-md-8")
            s["body"] = "\n".join(p.get_text(strip=True) for p in art.find_all("p")) if art else ""
            time.sleep(0.3)
        except Exception as e:
            print("   [FED] body fail:", s["url"], e)
    return uniq


# ─────────────────────────────────────────────────────────────
# BOJ : 연도별 경로 폴백 + PDF 본문 대응
# ─────────────────────────────────────────────────────────────
def _extract_pdf(url):
    try:
        import pdfplumber
    except ImportError:
        # BOE/BOJ 본문 상당수가 PDF로만 제공됨 → 이 모듈 없으면 그 연설들이 전부 누락된다.
        print("   PDF skip(모듈 없음): pip install pdfplumber  →", url)
        return ""
    try:
        r = requests.get(url, headers=HDR, timeout=40)
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except Exception as e:
        print("   PDF fail:", url, e); return ""


def scrape_boj(year: int) -> list[dict]:
    # ※ Chrome 진단: 브라우저에 보이는 table.res_tbl 은 JS(common2.js)가 런타임에
    #   다시 그린 것. requests 는 JS 미실행 → 원본 HTML 의 table.js-tbl 을 잡아야 함.
    #   원본 구조: 한 행(tr) = 한 연설, td 3개 [Date, Speaker, Title], row0=헤더.
    soup = None
    for cand in BANKS["BOJ"]["list_url_candidates"]:
        html = requests.get(cand.format(year=year), headers=HDR, timeout=20).text
        s = BeautifulSoup(html, "html.parser")
        if s.select_one("table.js-tbl"):     # res_tbl → js-tbl
            soup = s; break
    if soup is None:
        print(f"   [BOJ {year}] 목록 테이블 못 찾음"); return []

    out = []
    table = soup.select_one("table.js-tbl")
    for tr in table.select("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        a = tr.find("a")
        if not a or not a.get("href"):
            continue                          # 헤더행(Date/Speaker/Title) 자동 스킵
        out.append({
            "date": _normalize_date(cells[0].get_text(strip=True)),
            "speaker": cells[1].get_text(strip=True),
            "title": cells[2].get_text(strip=True),
            "url": urljoin(BANKS["BOJ"]["origin"], a["href"]),
            "body": "",
        })
    # 본문: 제목 1차 필터 통과분만 fetch
    for s in out:
        if _use_cache(s):                                    # 이미 받은 연설 → 재다운로드 생략
            continue
        if not _passes_title_prefilter(s["title"], s["speaker"], "BOJ"):
            continue
        try:
            if s["url"].lower().endswith(".pdf"):
                s["body"] = _extract_pdf(s["url"])
            else:
                bs = BeautifulSoup(requests.get(s["url"], headers=HDR, timeout=20).text, "html.parser")
                main = bs.find("main") or bs.find(id="contents") or bs
                s["body"] = "\n".join(p.get_text(strip=True) for p in main.find_all("p"))
            time.sleep(0.3)
        except Exception as e:
            print("   [BOJ] body fail:", s["url"], e)
    return out


# ─────────────────────────────────────────────────────────────
# ECB : 공식 CSV 한 방 다운로드 → 연도 필터 (본문이 CSV 안에 있어 페이지 fetch 불필요)
#   CSV 컬럼: date | speakers | title | subtitle | contents  ('|' 구분, 헤더 있음)
# ─────────────────────────────────────────────────────────────
_ECB_CSV_CACHE = None   # 연도마다 재다운로드 방지: 한 번 받아서 모듈에 캐시

def _load_ecb_csv():
    global _ECB_CSV_CACHE
    if _ECB_CSV_CACHE is None:
        url = BANKS["ECB"]["csv_url"]
        r = requests.get(url, headers=HDR, timeout=120)
        r.encoding = "utf-8"
        df = pd.read_csv(io.StringIO(r.text), sep="|", engine="python", on_bad_lines="skip")
        df.columns = [c.strip().lower() for c in df.columns]
        _ECB_CSV_CACHE = df
        print(f"   [ECB] CSV 로드: {len(df)}건, 컬럼={list(df.columns)}")
    return _ECB_CSV_CACHE


def scrape_ecb(year: int) -> list[dict]:
    df = _load_ecb_csv()
    if "date" not in df.columns:
        print("   [ECB] 'date' 컬럼 없음 → 구조 확인 필요:", list(df.columns)); return []
    d = df.copy()
    d["_dt"] = pd.to_datetime(d["date"], errors="coerce")
    d = d[d["_dt"].dt.year == year]
    out = []
    for _, r in d.iterrows():
        if pd.isna(r["_dt"]):
            continue
        date_iso = r["_dt"].date().isoformat()
        title    = str(r.get("title") or "").strip()
        subtitle = str(r.get("subtitle") or "").strip()
        contents = str(r.get("contents") or "").strip()
        speaker  = str(r.get("speakers") or "").strip()
        body = (subtitle + "\n" + contents).strip()
        out.append({
            "date": date_iso, "speaker": speaker, "title": title,
            # CSV엔 URL이 없어 dedup용 합성 키 사용(대시보드엔 표시 안 함)
            "url": f"ecb://{date_iso}/{title[:50]}",
            "body": body,
        })
    return out


# ─────────────────────────────────────────────────────────────
# BOE : sitemap/speeches(전 연도 한 페이지) → 연도별 링크 추출 → 연설별 본문/날짜 fetch
# ─────────────────────────────────────────────────────────────
def _boe_speaker(title: str) -> str:
    """'... - speech by Andrew Bailey' / 'Speech by X at ...' → 화자 추출."""
    m = re.search(r"\bby\s+([A-ZÀ-Þ][A-Za-zÀ-ÿ.''-]+(?:\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ.''-]+){0,3})", title or "")
    return m.group(1).strip() if m else ""


def _boe_page_date(bs):
    """BOE 연설 페이지에서 발행일 추출(여러 위치 시도)."""
    t = bs.find("time")
    if t and t.get("datetime"):
        return _normalize_date(str(t["datetime"])[:10])
    m = bs.find("meta", attrs={"property": "article:published_time"})
    if m and m.get("content"):
        return _normalize_date(str(m["content"])[:10])
    txt = bs.get_text(" ", strip=True)
    mm = re.search(r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
                   r"September|October|November|December)\s+\d{4})\b", txt)
    return _normalize_date(mm.group(1)) if mm else None


def scrape_boe(year: int) -> list[dict]:
    url = BANKS["BOE"]["sitemap_url"]
    soup = BeautifulSoup(requests.get(url, headers=HDR, timeout=30).text, "html.parser")
    out, seen = [], set()
    for a in soup.select(f"a[href*='/speech/{year}/']"):
        href = urljoin(BANKS["BOE"]["origin"], str(a["href"]))
        if href in seen:
            continue
        seen.add(href)
        title = a.get_text(strip=True)
        out.append({"date": None, "speaker": _boe_speaker(title),
                    "title": title, "url": href, "body": ""})
    if not out:
        print(f"   [BOE {year}] sitemap에서 /speech/{year}/ 링크 못 찾음")
    # 본문·날짜: 제목 1차 필터 통과분만 fetch
    for s in out:
        if _use_cache(s):                                    # 이미 받은 연설 → 재다운로드 생략
            continue
        if not _passes_title_prefilter(s["title"], s["speaker"], "BOE"):
            continue
        try:
            bs = BeautifulSoup(requests.get(s["url"], headers=HDR, timeout=25).text, "html.parser")
            s["date"] = _boe_page_date(bs) or f"{year}-01-01"   # 못 찾으면 연초로(누락 방지)
            main = bs.find("main") or bs.find(id="main-content") or bs
            txt = "\n".join(p.get_text(strip=True) for p in main.find_all("p"))
            if len(txt) < 1500:                                  # HTML 본문 빈약 → PDF 폴백 시도
                pdf = bs.find("a", href=re.compile(r"\.pdf$", re.I))
                if pdf:
                    pdf_txt = _extract_pdf(urljoin(BANKS["BOE"]["origin"], str(pdf["href"])))
                    if len(pdf_txt) > len(txt):                  # PDF가 더 풍부할 때만 교체(빈 PDF로 덮어쓰기 방지)
                        txt = pdf_txt
            if len(txt) > MAX_BODY_LEN:                           # 슬라이드/색인 페이지 등 비정상 거대 본문 컷
                print(f"   [BOE] 본문 과대({len(txt)}자) 스킵:", s["url"]); txt = ""
            s["body"] = txt
            time.sleep(0.3)
        except Exception as e:
            print("   [BOE] body fail:", s["url"], e)
    return out


# ─────────────────────────────────────────────────────────────
# 통합 디스패처
# ─────────────────────────────────────────────────────────────
def scrape(bank: str, year: int) -> list[dict]:
    if bank == "FED":
        return scrape_fed(year)
    if bank == "BOJ":
        return scrape_boj(year)
    if bank == "ECB":
        return scrape_ecb(year)
    if bank == "BOE":
        return scrape_boe(year)
    raise ValueError(f"미구현 은행: {bank} (FED/BOJ/ECB/BOE만 지원)")


if __name__ == "__main__":
    # 빠른 점검 (수집만)
    sp = scrape_fed(dt.date.today().year)
    print(f"FED 수집 {len(sp)}건, 본문 있는 것 {sum(1 for s in sp if s['body'])}건")
    for s in sp[:5]:
        print(" ", s["date"], "|", s["title"][:60])