# -*- coding: utf-8 -*-
"""
extract_houseviews.py — 리서치 데일리 레코드에서 '하우스뷰'를 추출한다.

흐름:
  1) houseview_records.json (1880건) 를 읽는다
  2) 10건씩 묶어 Claude 에 한 번씩 호출 → 레코드별 뷰 배열을 받는다
  3) 배치마다 houseview_state.json 에 즉시 저장 (죽어도 다시 돌리면 이어서 함)
  4) 지금까지의 state 로 macro_hub/public/data/houseviews.json 을 만든다

실행:
  python extract_houseviews.py                # 남은 것 전부
  python extract_houseviews.py --limit 30     # 앞 30건만 (비용/품질 확인용)
  python extract_houseviews.py --dry-run      # API 호출 없이 첫 배치 프롬프트만 출력
  python extract_houseviews.py --rebuild      # API 호출 없이 state → 출력 JSON 재생성
  python extract_houseviews.py --reset        # state 비우고 처음부터

설정: report_pipeline/.env  (ANTHROPIC_API_KEY, CLAUDE_MODEL)
"""
import os
import io
import re
import sys
import json
import time
import random
import hashlib
import argparse
import datetime as dt

# ── Windows cp949 콘솔에서 한글 때문에 죽지 않게 stdout/stderr 를 utf-8 로 ──
for _name in ("stdout", "stderr"):
    _s = getattr(sys, _name, None)
    try:
        if _s is not None and getattr(_s, "buffer", None) is not None:
            setattr(sys, _name, io.TextIOWrapper(
                _s.buffer, encoding="utf-8", errors="replace", line_buffering=True))
    except Exception:
        pass

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

RECORDS_JSON = os.environ.get("HOUSEVIEW_RECORDS", os.path.join(HERE, "houseview_records.json"))
STATE_JSON = os.environ.get("HOUSEVIEW_STATE", os.path.join(HERE, "houseview_state.json"))
OUT_JSON = os.environ.get(
    "HOUSEVIEW_OUT",
    os.path.join(REPO, "macro_hub", "public", "data", "houseviews.json"))

MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
BATCH_SIZE = int(os.environ.get("HOUSEVIEW_BATCH", "10"))
MAX_TOKENS = int(os.environ.get("HOUSEVIEW_MAX_TOKENS", "4000"))
MAX_BODY = int(os.environ.get("HOUSEVIEW_MAX_BODY", "2000"))    # 레코드당 본문 상한(문자)
MAX_RETRY = int(os.environ.get("HOUSEVIEW_RETRY", "3"))
OUT_EVERY = int(os.environ.get("HOUSEVIEW_OUT_EVERY", "5"))     # N배치마다 출력 파일 갱신

# ── 공통 계약 (macro_hub/public/data/houseviews.json) — 임의로 바꾸지 말 것 ──
HOUSES = ["GS", "JPM", "BofA", "Citi", "HSBC", "UBS"]
ASSETS = ["매크로", "채권", "주식", "코모디티"]
REGIONS = ["US", "EU", "JP", "CN", "KR", "UK", "AU", "EM"]
STANCES = ("OW", "N", "UW")
CONFS = ("high", "mid", "low")

HOUSE_ALIAS = {
    "gs": "GS", "goldman": "GS", "goldmansachs": "GS", "gir": "GS",
    "jpm": "JPM", "jpmorgan": "JPM", "jpmorganchase": "JPM",
    "bofa": "BofA", "bankofamerica": "BofA", "baml": "BofA", "boa": "BofA",
    "merrill": "BofA", "merrilllynch": "BofA", "bofasecurities": "BofA",
    "citi": "Citi", "citigroup": "Citi", "citibank": "Citi",
    "hsbc": "HSBC",
    "ubs": "UBS", "ubsneo": "UBS",
}
# 모델은 보통 4개 카테고리 중 하나를 그대로 뱉지만, 주제어를 그대로 돌려주는 경우가 있다.
# 여기 없으면 원본 섹션 → "매크로" 로 흘러가서 시스템 프롬프트가 강조한 코모디티 재분류가
# 조용히 뒤집힌다. 그래서 프롬프트가 열거한 주제어를 그대로 별칭에 넣어 둔다.
ASSET_ALIAS = {
    "매크로": "매크로", "거시": "매크로", "macro": "매크로", "economics": "매크로", "fx": "매크로",
    "성장": "매크로", "growth": "매크로", "물가": "매크로", "인플레이션": "매크로",
    "inflation": "매크로", "고용": "매크로", "employment": "매크로", "정책": "매크로",
    "통화정책": "매크로", "policy": "매크로", "monetarypolicy": "매크로",
    "환율": "매크로", "달러": "매크로", "dollar": "매크로", "currency": "매크로",
    "지정학": "매크로", "geopolitics": "매크로",

    "채권": "채권", "금리": "채권", "rates": "채권", "rate": "채권", "bond": "채권", "bonds": "채권",
    "fixedincome": "채권", "credit": "채권", "크레딧": "채권",
    "국채": "채권", "treasury": "채권", "treasuries": "채권", "ust": "채권",
    "jgb": "채권", "gilt": "채권", "gilts": "채권", "bund": "채권", "sovereign": "채권",
    "커브": "채권", "curve": "채권", "듀레이션": "채권", "duration": "채권",
    "회사채": "채권", "ig": "채권", "hy": "채권", "highyield": "채권", "스프레드": "채권",

    "주식": "주식", "equity": "주식", "equities": "주식", "stock": "주식", "stocks": "주식",
    "지수": "주식", "섹터": "주식", "업종": "주식", "종목": "주식",
    "밸류에이션": "주식", "valuation": "주식", "이익": "주식", "earnings": "주식",

    "코모디티": "코모디티", "원자재": "코모디티", "commodity": "코모디티",
    "commodities": "코모디티", "에너지": "코모디티", "energy": "코모디티",
    "유가": "코모디티", "원유": "코모디티", "oil": "코모디티", "crudeoil": "코모디티",
    "crude": "코모디티", "브렌트": "코모디티", "brent": "코모디티", "wti": "코모디티",
    "opec": "코모디티", "정제마진": "코모디티", "크랙스프레드": "코모디티",
    "천연가스": "코모디티", "naturalgas": "코모디티", "gas": "코모디티", "lng": "코모디티",
    "금": "코모디티", "gold": "코모디티", "은": "코모디티", "silver": "코모디티",
    "구리": "코모디티", "copper": "코모디티", "금속": "코모디티", "metals": "코모디티",
    "곡물": "코모디티", "grain": "코모디티", "grains": "코모디티", "agriculture": "코모디티",
}
REGION_ALIAS = {
    "us": "US", "usa": "US", "미국": "US", "unitedstates": "US", "america": "US",
    "fed": "US", "fomc": "US", "연준": "US",
    "eu": "EU", "유럽": "EU", "유로": "EU", "유로존": "EU", "europe": "EU",
    "euroarea": "EU", "eurozone": "EU", "germany": "EU", "독일": "EU",
    "france": "EU", "프랑스": "EU", "ecb": "EU",
    "italy": "EU", "이탈리아": "EU", "spain": "EU", "스페인": "EU",
    "netherlands": "EU", "ez": "EU",
    "jp": "JP", "일본": "JP", "japan": "JP", "boj": "JP", "닛케이": "JP", "nikkei": "JP",
    "cn": "CN", "중국": "CN", "china": "CN", "pboc": "CN", "인민은행": "CN",
    "kr": "KR", "한국": "KR", "korea": "KR", "bok": "KR", "한은": "KR", "코스피": "KR", "kospi": "KR",
    "uk": "UK", "영국": "UK", "unitedkingdom": "UK", "britain": "UK",
    "gb": "UK", "boe": "UK", "길트": "UK",
    "au": "AU", "호주": "AU", "australia": "AU", "rba": "AU",
    "em": "EM", "신흥": "EM", "신흥국": "EM", "emergingmarkets": "EM", "emergingmarket": "EM",
    "asia": "EM", "india": "EM", "인도": "EM", "brazil": "EM", "브라질": "EM",
    "asean": "EM", "아세안": "EM", "indonesia": "EM", "인도네시아": "EM",
    "taiwan": "EM", "대만": "EM", "tw": "EM", "hongkong": "EM", "홍콩": "EM", "hk": "EM",
    "mexico": "EM", "멕시코": "EM", "vietnam": "EM", "베트남": "EM",
    "thailand": "EM", "태국": "EM", "turkey": "EM", "튀르키예": "EM",
    "southafrica": "EM", "남아공": "EM", "latam": "EM", "중남미": "EM",
    "global": "GLOBAL", "글로벌": "GLOBAL", "world": "GLOBAL", "dm": "GLOBAL", "g10": "GLOBAL",
    "전세계": "GLOBAL", "선진국": "GLOBAL", "developedmarkets": "GLOBAL", "crossasset": "GLOBAL",
}
STANCE_ALIAS = {
    "ow": "OW", "overweight": "OW", "비중확대": "OW", "positive": "OW", "bullish": "OW",
    "long": "OW", "buy": "OW", "확대": "OW", "매수": "OW", "outperform": "OW",
    "uw": "UW", "underweight": "UW", "비중축소": "UW", "negative": "UW", "bearish": "UW",
    "short": "UW", "sell": "UW", "축소": "UW", "매도": "UW", "underperform": "UW",
    "n": "N", "neutral": "N", "중립": "N", "hold": "N", "mw": "N", "marketweight": "N",
}
CONF_ALIAS = {
    "high": "high", "상": "high", "높음": "high", "강": "high",
    "mid": "mid", "medium": "mid", "중": "mid", "보통": "mid",
    "low": "low", "하": "low", "낮음": "low", "약": "low",
}

SYSTEM_PROMPT = """너는 글로벌 IB 리서치 데일리를 읽고 '하우스뷰'를 뽑아내는 시니어 애널리스트다.
하우스뷰 = 특정 기관이 특정 자산군·특정 권역에 대해 갖고 있는 방향성 판단.

## 출력 형식 — JSON 배열 하나만. 설명문·코드펜스·주석 금지.
[
  {"i": 0, "views": [
    {"asset": "채권", "region": "US", "stance": "OW", "confidence": "mid",
     "house": "GS",
     "title": "다시 프론트엔드로 — G10 금리 뷰",
     "rationale": "Warsh가 단기금리를 주된 수단으로 재규정 — 장기물 아웃퍼폼 근거"}
  ]},
  {"i": 1, "views": []}
]
- 입력에 준 인덱스를 하나도 빠짐없이 포함한다. 뷰가 없으면 "views": [] 로 명시한다.
- 한 레코드에서 최대 3개. 같은 (asset, region) 조합은 한 번만.
- 한 리포트가 여러 뷰를 낳을 수 있다(예: 미국 금리 OW + 일본 금리 UW).

## asset — 본문 내용으로 4개 중 하나에 재배정하라. 입력의 '원본 섹션'은 참고만 하라.
- 코모디티: 유가·브렌트·WTI·OPEC·정제마진·크랙스프레드·천연가스·LNG·금·은·구리·곡물 등 원자재 자체의 수급/가격 전망
- 채권: 국채·금리·커브·듀레이션·스프레드·크레딧(IG/HY)·중앙은행 정책금리 트레이드
- 주식: 지수·섹터·업종·개별종목·밸류에이션·이익 전망
- 매크로: 성장·물가·고용·정책·FX/달러·지정학 등 위 셋에 안 들어가는 판단
※ 원본 섹션이 매크로/주식이어도 내용이 원자재면 반드시 "코모디티"로 보낸다. 원본에 코모디티 섹션이 없어 섞여 있다.
※ 정유주·에너지 기업 주가 이야기는 "주식", 유가 자체 전망은 "코모디티".

## region — US EU JP CN KR UK AU EM 중 하나. 권역이 무의미하면 "GLOBAL".
- 유로존·독일·프랑스·ECB → EU / 영국·BOE·길트 → UK / 호주·RBA → AU / 한국·BOK → KR
- 신흥국 전반·인도·브라질·아세안 → EM
- 원자재, 글로벌 자산배분, 달러 전반, G10 묶음 → GLOBAL

## stance — 원문에 OW/N/UW 표기는 거의 없다. 논조로 추론하라.
- OW: 매수·비중확대·아웃퍼폼·롱·상승 전망·수혜 등 방향이 명확히 긍정
- UW: 매도·비중축소·언더퍼폼·숏·하락 전망·부담 등 방향이 명확히 부정
- N: 중립·혼조·양방향 리스크 병기·판단 유보
- 채권의 OW = 듀레이션/해당 채권을 늘리라(금리 하락 기대). 금리 상승 전망이면 UW.
- 매크로의 OW = 그 권역 전망이 위험자산에 우호적, UW = 비우호적.
- 애매하면 억지로 방향을 만들지 말고 N.

## confidence — 추론의 강도. 대부분 mid/low 가 정상이다.
- high: 명시적 투자의견·추천 문구가 있다("추천", "선호", "비중확대", "Buy", "OW")
- mid: 추천은 아니나 논조 방향이 분명하다
- low: 뉘앙스·정황으로만 추론했다

## house
- 입력 '기관'이 주어졌으면 그 값을 그대로 쓴다.
- '미상'이면 제목·본문의 출처 표기("Goldman Sachs Global Investment Research" 등),
  시리즈명, 문체로 추론해 GS / JPM / BofA / Citi / HSBC / UBS 중 하나를 넣는다.
- 추론 근거가 약하면 house 를 null 로 두고 "views": [] 를 반환한다. 찍지 마라.

## 뷰를 만들지 말 것 (views: [])
- 일정·컨퍼런스·웨비나·팟캐스트·로드쇼 안내, 목차/링크 나열
- "전일 요약 참조" 같은 중복 표기, 본문이 비었거나 사실상 두 문장 미만
- 데이터·수치 나열만 있고 방향성 판단이 없는 것
- 억지로 만들지 마라. 빈 배열이 정답인 경우가 흔하다.

## rationale / title
- rationale: 한국어 한 문장(40~120자). 왜 그 stance 인지 근거를 원문에서 가져온다.
  원문에 없는 숫자·전망치를 지어내지 마라.
- title: 그 뷰를 대표하는 짧은 한국어 제목(30자 이내). 원 제목이 영어면 자연스럽게 옮긴다."""


# ────────────────────────────── 유틸 ──────────────────────────────
def norm_key(s):
    """별칭 매칭용 — 소문자화 + 공백/구두점 제거."""
    return re.sub(r"[\s._\-/&,'()\[\]]+", "", (s or "").strip().lower())


def record_key(rec):
    """레코드 고유키 — records 파일을 다시 만들어도 같은 레코드면 같은 키."""
    raw = "|".join([
        rec.get("date") or "",
        rec.get("pub_date") or "",
        rec.get("house") or "",
        rec.get("title") or "",
        (rec.get("body") or "")[:200],
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_atomic(path, obj):
    """tmp 로 쓰고 replace — 저장 중에 죽어도 기존 파일이 깨지지 않는다."""
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ─────────────────────── 프롬프트 / 응답 파싱 ───────────────────────
def build_user_prompt(batch):
    """batch = [(배치내 인덱스, 레코드), ...]"""
    parts = ["다음은 리서치 데일리 레코드 %d건이다. 각 레코드에서 하우스뷰를 추출하라.\n" % len(batch)]
    for i, rec in batch:
        body = (rec.get("body") or "").strip()
        if len(body) > MAX_BODY:
            body = body[:MAX_BODY] + " …(이하 생략)"
        parts.append(
            "[%d]\n날짜: %s\n원본 섹션: %s\n기관: %s\n제목: %s\n본문: %s\n" % (
                i,
                rec.get("date") or "",
                rec.get("section") or "",
                rec.get("house") or "미상",
                (rec.get("title") or "").strip(),
                body if body else "(본문 없음)",
            ))
    parts.append(
        "\n위 %d건 각각에 대해 i(0~%d)를 키로 갖는 JSON 배열 하나만 출력하라. "
        "인덱스를 빠뜨리지 말고, 근거가 약하면 views 를 빈 배열로 둬라."
        % (len(batch), len(batch) - 1))
    return "\n".join(parts)


def strip_fences(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[A-Za-z0-9_+-]*\s*", "", t)
        t = re.sub(r"```\s*$", "", t.strip())
    return t.strip()


def scan_top_objects(text):
    """중괄호 균형을 세어 최상위 {...} 만 뽑는다 (응답이 잘려도 앞부분은 건진다)."""
    out, depth, start, in_str, esc = [], 0, -1, False, False
    for pos, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = pos
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    out.append(text[start:pos + 1])
                    start = -1
    return out


def parse_response(text):
    """방어적 파싱 — 코드펜스·앞뒤 설명문·잘린 응답에서도 최대한 살려낸다."""
    t = strip_fences(text)

    candidates = [t]
    if "[" in t and "]" in t:
        candidates.append(t[t.find("["):t.rfind("]") + 1])

    for cand in candidates:
        if not cand:
            continue
        try:
            obj = json.loads(cand)
        except Exception:
            continue
        if isinstance(obj, list):
            return [o for o in obj if isinstance(o, dict)]
        if isinstance(obj, dict):
            for k in ("results", "records", "items", "data", "views_by_record"):
                if isinstance(obj.get(k), list):
                    return [o for o in obj[k] if isinstance(o, dict)]
            if "i" in obj:
                return [obj]

    # 통짜 파싱 실패 → 객체 단위로 긁어모은다
    items = []
    for chunk in scan_top_objects(t):
        try:
            o = json.loads(chunk)
        except Exception:
            continue
        if isinstance(o, dict) and "i" in o:
            items.append(o)
    return items


# ─────────────────────────── 정규화 ───────────────────────────
def norm_house(value, fallback=None):
    h = HOUSE_ALIAS.get(norm_key(value))
    if h:
        return h
    return HOUSE_ALIAS.get(norm_key(fallback)) if fallback else None


def norm_view(raw, rec, stats):
    """모델이 준 뷰 하나를 계약 스키마로 정규화. 못 쓰면 None."""
    if not isinstance(raw, dict):
        return None

    # 기관을 못 채운 레코드는 뷰를 만들지 않는다 (요구사항 6)
    house = norm_house(raw.get("house"), rec.get("house"))
    if not house:
        stats["no_house"] += 1
        return None

    asset = ASSET_ALIAS.get(norm_key(raw.get("asset")))
    if not asset:
        asset = ASSET_ALIAS.get(norm_key(rec.get("section"))) or "매크로"

    region = REGION_ALIAS.get(norm_key(raw.get("region")), "GLOBAL")
    if asset == "코모디티" and not raw.get("region"):
        region = "GLOBAL"

    stance = STANCE_ALIAS.get(norm_key(raw.get("stance")), "N")
    conf = CONF_ALIAS.get(norm_key(raw.get("confidence")), "low")

    rationale = re.sub(r"\s+", " ", str(raw.get("rationale") or "")).strip()
    if len(rationale) < 6:
        stats["no_rationale"] += 1
        return None
    if len(rationale) > 240:
        rationale = rationale[:240].rstrip() + "…"

    title = re.sub(r"\s+", " ", str(raw.get("title") or "")).strip() or (rec.get("title") or "").strip()
    if len(title) > 80:
        title = title[:80].rstrip() + "…"

    return {
        "date": rec.get("date") or "",
        "house": house,
        "asset": asset,
        "region": region,
        "stance": stance if stance in STANCES else "N",
        "rationale": rationale,
        "title": title,
        "confidence": conf if conf in CONFS else "low",
    }


# ─────────────────────────── API 호출 ───────────────────────────
def make_client():
    try:
        from anthropic import Anthropic
    except ImportError:
        raise SystemExit("anthropic 필요: pip install -r requirements.txt")
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY 없음 — report_pipeline/.env 확인 (.env.example 참고)")
    return Anthropic(api_key=key)


def call_batch(client, batch, stats):
    """배치 1개 → {배치내 인덱스: [원시 뷰, ...]}. 실패하면 재시도, 끝내 안 되면 {}."""
    import anthropic

    user_prompt = build_user_prompt(batch)
    max_tokens = MAX_TOKENS
    last_err = None

    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                # 시스템 프롬프트는 매 배치 동일 → 캐시 태그 (모델 최소 길이 미달이면 그냥 무시됨)
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.AuthenticationError:
            raise SystemExit("인증 실패 — ANTHROPIC_API_KEY 확인")
        except anthropic.NotFoundError:
            raise SystemExit("모델을 찾을 수 없음 — CLAUDE_MODEL=%s 확인" % MODEL)
        except anthropic.BadRequestError as e:
            last_err = "BadRequest: %s" % getattr(e, "message", e)
            break  # 요청 자체가 잘못됨 — 재시도해도 같다
        except (anthropic.RateLimitError, anthropic.APIConnectionError,
                anthropic.APITimeoutError, anthropic.APIStatusError) as e:
            last_err = "%s: %s" % (type(e).__name__, getattr(e, "message", e))
            delay = min(60.0, 2.0 * (2 ** (attempt - 1))) + random.uniform(0, 1.0)
            print("    ! %s → %.1fs 후 재시도 (%d/%d)" % (last_err[:90], delay, attempt, MAX_RETRY))
            time.sleep(delay)
            continue

        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

        if resp.stop_reason == "max_tokens":
            stats["truncated"] += 1
            if attempt < MAX_RETRY:
                max_tokens = min(8000, int(max_tokens * 1.8))
                print("    ! 응답이 max_tokens 로 잘림 → max_tokens=%d 로 재시도" % max_tokens)
                continue

        items = parse_response(text)
        if items:
            out = {}
            for it in items:
                try:
                    i = int(it.get("i"))
                except (TypeError, ValueError):
                    continue
                views = it.get("views")
                out[i] = views if isinstance(views, list) else []
            if out:
                return out

        last_err = "JSON 파싱 실패 (응답 %d자)" % len(text)
        if attempt < MAX_RETRY:
            print("    ! %s → 재시도 (%d/%d)" % (last_err, attempt, MAX_RETRY))
            time.sleep(1.5 * attempt)

    stats["failed_batches"] += 1
    print("    x 배치 포기: %s" % last_err)
    return {}


# ─────────────────────────── 출력 생성 ───────────────────────────
def build_output(records, state):
    """state 에 쌓인 뷰들로 계약 스키마 JSON 을 만든다. id 는 여기서 부여."""
    done = state.get("records", {})
    views, seq = [], {}
    for rec in records:                      # 원본 순서 = id 채번 순서 (재실행해도 동일)
        entry = done.get(record_key(rec))
        if not entry:
            continue
        for v in entry.get("views", []):
            date = v.get("date") or rec.get("date") or ""
            house = v.get("house") or ""
            bucket = (date, house)
            n = seq.get(bucket, 0)
            seq[bucket] = n + 1
            views.append({
                "id": "%s-%s-%d" % (date.replace("-", ""), house.lower(), n),
                "date": date,
                "house": house,
                "asset": v.get("asset"),
                "region": v.get("region"),
                "stance": v.get("stance"),
                "rationale": v.get("rationale"),
                "title": v.get("title"),
                "confidence": v.get("confidence"),
            })

    views.sort(key=lambda v: (v["date"], v["house"], v["id"]), reverse=True)
    return {
        "generatedAt": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "houses": HOUSES,
        "assets": ASSETS,
        "regions": REGIONS,
        "views": views,
    }


# ─────────────────────────── 메인 ───────────────────────────
def main():
    global MODEL

    ap = argparse.ArgumentParser(description="리서치 데일리 → 하우스뷰 추출기")
    ap.add_argument("--limit", type=int, default=0, help="미처리 레코드 중 앞 N건만 처리 (0=전부)")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="배치당 레코드 수 (기본 10)")
    ap.add_argument("--model", default=MODEL, help="CLAUDE_MODEL 덮어쓰기")
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 첫 배치 프롬프트만 출력")
    ap.add_argument("--rebuild", action="store_true", help="API 호출 없이 state → 출력 JSON 재생성")
    ap.add_argument("--reset", action="store_true", help="state 를 비우고 처음부터")
    args = ap.parse_args()

    MODEL = args.model
    batch_size = max(1, args.batch_size)

    records = load_json(RECORDS_JSON, None)
    if not isinstance(records, list) or not records:
        raise SystemExit("레코드를 읽을 수 없음: %s" % RECORDS_JSON)

    if args.reset:
        state = {"model": MODEL, "updatedAt": "", "records": {}}
    else:
        state = load_json(STATE_JSON, {"model": MODEL, "updatedAt": "", "records": {}})
    state.setdefault("records", {})
    done = state["records"]

    print("레코드 %d건 · 처리완료 %d건 · 모델 %s" % (len(records), len(done), MODEL))

    if args.rebuild:
        out = build_output(records, state)
        save_json_atomic(OUT_JSON, out)
        print("재생성 완료 → %s (뷰 %d개)" % (OUT_JSON, len(out["views"])))
        return

    todo = [r for r in records if record_key(r) not in done]
    if args.limit > 0:
        todo = todo[:args.limit]

    if not todo:
        out = build_output(records, state)
        save_json_atomic(OUT_JSON, out)
        print("새로 처리할 레코드 없음 → %s (뷰 %d개)" % (OUT_JSON, len(out["views"])))
        return

    batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
    print("미처리 %d건 → 배치 %d개 (배치당 %d건)" % (len(todo), len(batches), batch_size))

    if args.dry_run:
        print("\n" + "=" * 70 + "\n[SYSTEM]\n" + SYSTEM_PROMPT)
        print("\n" + "=" * 70 + "\n[USER — 배치 1/%d]\n" % len(batches)
              + build_user_prompt(list(enumerate(batches[0]))))
        print("\n" + "=" * 70 + "\n(dry-run: API 호출 안 함)")
        return

    client = make_client()
    stats = {"no_house": 0, "no_rationale": 0, "truncated": 0,
             "failed_batches": 0, "missing_idx": 0}
    total_views = sum(len(e.get("views", [])) for e in done.values())
    t0 = time.time()

    for bi, batch in enumerate(batches, 1):
        pairs = list(enumerate(batch))
        result = call_batch(client, pairs, stats)

        added = 0
        for i, rec in pairs:
            raws = result.get(i)
            if raws is None:            # 모델이 인덱스를 빠뜨림 → 뷰 없음으로 확정
                stats["missing_idx"] += 1
                raws = []
            views, seen = [], set()
            for raw in raws[:3]:
                v = norm_view(raw, rec, stats)
                if not v:
                    continue
                sig = (v["asset"], v["region"])
                if sig in seen:         # 같은 (자산군, 권역) 중복 제거
                    continue
                seen.add(sig)
                views.append(v)
            done[record_key(rec)] = {"date": rec.get("date") or "", "views": views}
            added += len(views)

        total_views += added
        state["model"] = MODEL
        state["updatedAt"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json_atomic(STATE_JSON, state)      # ← 배치마다 즉시 저장 (재개 가능)

        elapsed = time.time() - t0
        eta = (elapsed / bi) * (len(batches) - bi)
        print("[%3d/%3d] 뷰 +%-2d  누적 %-5d  처리 %d/%d  경과 %.0fs  남은시간 ~%.0fs"
              % (bi, len(batches), added, total_views, len(done), len(records), elapsed, eta))

        if bi % OUT_EVERY == 0:
            save_json_atomic(OUT_JSON, build_output(records, state))

    out = build_output(records, state)
    save_json_atomic(OUT_JSON, out)

    print("-" * 70)
    print("완료: 레코드 %d/%d · 뷰 %d개 → %s"
          % (len(done), len(records), len(out["views"]), OUT_JSON))
    print("state: %s" % STATE_JSON)
    print("스킵 사유 — 기관 미상 %d · 근거 부족 %d · 인덱스 누락 %d · 응답잘림 %d · 실패배치 %d"
          % (stats["no_house"], stats["no_rationale"], stats["missing_idx"],
             stats["truncated"], stats["failed_batches"]))


if __name__ == "__main__":
    main()
