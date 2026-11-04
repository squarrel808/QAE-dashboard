# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사전 준비 (터미널에서 1번만 실행)
#   pip install -q google-api-python-client youtube-transcript-api requests python-dotenv
#
# 설정은 이 폴더의 .env 파일에서 읽습니다. (.env.example 참고)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import os
import re
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import requests
import certifi
import httplib2

# 로깅
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 회사 프록시(Somansa) SSL 인증서 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사내망은 TLS를 가로채 Somansa Root CA로 재서명하므로 이 인증서를 신뢰해야 한다.
# certifi 공인 CA 번들에 회사 인증서를 덧붙여, 사내망/사외망 양쪽에서 동작하게 한다.
# 라이브러리마다 읽는 환경변수가 다르므로 둘 다 설정해야 한다:
#   REQUESTS_CA_BUNDLE → requests (youtube_transcript_api)
#   SSL_CERT_FILE      → httpx (anthropic), urllib
CORPORATE_CERT = BASE_DIR / "ssl.cer"
CA_BUNDLE = None


def _setup_ca_bundle():
    """certifi 번들 + 회사 인증서를 합친 파일을 만들고 경로를 반환한다."""
    if not CORPORATE_CERT.exists():
        log.warning(f"⚠️ 회사 인증서 없음 ({CORPORATE_CERT.name}) — 기본 CA 번들 사용")
        return None
    bundle = BASE_DIR / "ca-bundle.pem"
    bundle.write_text(
        Path(certifi.where()).read_text(encoding="utf-8")
        + "\n"
        + CORPORATE_CERT.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    os.environ["REQUESTS_CA_BUNDLE"] = str(bundle)
    os.environ["SSL_CERT_FILE"] = str(bundle)
    log.info(f"🔒 CA 번들 구성 완료 (certifi + {CORPORATE_CERT.name})")
    return str(bundle)


CA_BUNDLE = _setup_ca_bundle()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 설정 로드 (.env)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
load_dotenv(BASE_DIR / ".env")


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"{key} 가 .env 에 설정되어 있지 않습니다. (.env.example 참고)")
    return value


CONFIG = {
    "youtube_api_key": _require("YOUTUBE_API_KEY"),
    "openai_api_key": _require("OPENAI_API_KEY"),
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-5-nano"),

    "hours_back": int(os.getenv("HOURS_BACK", "24")),
    "output_dir": os.getenv("OUTPUT_DIR", r"C:\Users\infomax\Desktop\보따리\유투브"),
}

# 채널 목록
CHANNELS = [
    {
        "name": "Bloomberg",
        "channel_id": "UCIALMKvObZNtJ6AmdCLP7Lg",
        "keywords": [
            "the close", "wall street week", "closing bell", "real yield",
            "open interest", "surveillance", "the pulse", "daybreak",
            "bloomberg insight", "this weekend", "asia trade", "businessweek daily", "china show",
        ],
        "badge_label": "Bloomberg", "badge_bg": "#1a3a5c", "badge_color": "#4a9eff",
    },
    {
        "name": "FedGuy",
        "channel_id": "UCxaKNMYPDgOHaGwMQoKQO8g",
        "keywords": [],
        "badge_label": "FedGuy", "badge_bg": "#2d1515", "badge_color": "#f85149",
    },
]

PANEL_KEYWORDS = [
    "surveillance", "wall street week", "open interest", "the pulse",
    "businessweek daily", "closing bell", "the close", "bloomberg insight",
    "real yield", "china show", "asia trade", "daybreak",
]

# 실행 위치와 무관하게 스크립트 폴더 기준으로 경로를 잡는다
PROCESSED_FILE = BASE_DIR / "processed_videos.json"

# OUTPUT_DIR 은 절대경로면 그대로, 상대경로면 스크립트 폴더 기준으로 해석한다.
# 리포트는 이 아래에 실행 날짜 폴더(YYYY-MM-DD)를 만들어 그 안에 저장한다.
OUTPUT_DIR = Path(CONFIG["output_dir"]).expanduser()
if not OUTPUT_DIR.is_absolute():
    OUTPUT_DIR = BASE_DIR / OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_processed():
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_processed(processed: set):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(processed), f)


def fetch_recent_videos(hours_back=24):
    # httplib2 는 환경변수를 읽지 않으므로 CA 번들 경로를 직접 넘긴다.
    try:
        http = httplib2.Http(ca_certs=CA_BUNDLE) if CA_BUNDLE else httplib2.Http()
        youtube = build("youtube", "v3", developerKey=CONFIG["youtube_api_key"], http=http)
    except Exception:
        youtube = build("youtube", "v3", developerKey=CONFIG["youtube_api_key"])
    published_after = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_videos = []

    for channel in CHANNELS:
        log.info(f"📡 [{channel['name']}] 채널 스캔 중...")
        log.info(f"    publishedAfter={published_after} channelId={channel['channel_id']}")
        try:
            response = youtube.search().list(
                part="snippet", channelId=channel["channel_id"],
                publishedAfter=published_after, order="date", maxResults=50, type="video",
            ).execute()
        except Exception as e:
            log.error(f"❌ [{channel['name']}] API 호출 실패: {e}")
            continue

        items = response.get("items", [])
        log.info(f"    fetched {len(items)} items from API")
        for item in items:
            title = item["snippet"]["title"]
            title_lower = title.lower()
            keywords = channel.get("keywords", [])
            if keywords:
                matched = any(kw in title_lower for kw in keywords)
                if not matched:
                    log.info(f"    - SKIP (no keyword match): {title}")
                    continue
            all_videos.append({
                "id": item["id"]["videoId"], "title": title,
                "published_at": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "channel_name": channel["name"],
                "badge_label": channel["badge_label"],
                "badge_bg": channel["badge_bg"], "badge_color": channel["badge_color"],
            })
            log.info(f" ✅ {title}")
    return all_videos


def get_transcript(video_id):
    try:
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id, languages=["en"])
        full_text = " ".join([s.text for s in fetched])
        log.info(f" 📝 자막 추출 완료: {len(full_text)} 글자")
        return full_text
    except Exception:
        pass
    try:
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id, languages=["en-US", "en-GB"])
        full_text = " ".join([s.text for s in fetched])
        log.info(f" 📝 자막 추출 완료 (자동생성): {len(full_text)} 글자")
        return full_text
    except Exception as e:
        log.warning(f" ⚠️ 자막 추출 실패 ({video_id}): {e}")
        return None


def summarize_with_openai(title, transcript, channel_name):
    # requests는 위에서 구성한 REQUESTS_CA_BUNDLE로 사내 인증서를 검증한다.
    transcript_trimmed = transcript[:80000]
    is_panel_format = any(k in title.lower() for k in PANEL_KEYWORDS)

    if is_panel_format:
        panel_section = """
## 🎙️ 패널별 상세 요약
- 각 패널(화자)별로 약 8~10줄 내외로 자세히 정리
- 형식:
  - **패널 이름 (직함/소속):**
    - 주장, 근거, 시장 전망 등
- 각 패널이 무엇을 근거로 어떤 관점을 말했는지 드러나게 작성
- 서로 의견이 갈린 부분이 있으면 비교해서 표시
- 자막에 화자명이 없으면 '패널 A/B/C'로 구분하고, 추정임을 표시
"""
    else:
        panel_section = ""

    prompt = f"""다음은 {channel_name} YouTube 영상의 자막입니다.

영상 제목: {title}

자막 내용:
{transcript_trimmed}

아래 형식으로 한국어 요약을 작성해주세요.

중요 규칙:
- 사실관계 왜곡 없이 작성
- 숫자/금리/지수/정책 관련 표현은 최대한 정확히 유지
- 과장하지 말고, 자막에 없는 내용 추측 금지
- 영상이 패널 토론/인터뷰 형식이면 화자별 관점을 구분해서 정리

## 📌 한줄 요약
- 영상 핵심을 1~2문장

## 📊 핵심 요약 (3~5줄)
- 전체 내용을 자연스럽게 요약

## 💹 주요 시장/매크로 포인트
- 금리 / 주식 / 달러 / 원자재 / 정책 / 경기지표 중심
- 핵심 숫자와 방향성 포함

## 🔑 핵심 토픽 (3~5개)
- 토픽별로 구분하여 정리

## 💬 주요 발언 / 인사이트
- 의미 있는 주장, 해석, 전망 정리
{panel_section}
## ⚡ 실무 체크포인트
- 시장 점검할 때 다시 볼 포인트 3~5개"""

    # 추론 토큰도 출력 한도에 포함된다. 잘린 응답은 성공으로 저장하지 않는다.
    max_tokens = 8000 if is_panel_format else 6000
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {CONFIG['openai_api_key']}"},
            json={
                "model": CONFIG["openai_model"], "input": prompt,
                "reasoning": {"effort": "minimal"},
                "max_output_tokens": max_tokens, "store": False,
            },
            timeout=(15, 180),
        )
        if not response.ok:
            # 오류 응답의 원문 대신 코드만 기록하여 인증 정보 노출을 방지한다.
            try:
                error = response.json().get("error", {})
                code = error.get("code") or error.get("type") or "unknown"
            except (ValueError, AttributeError):
                code = "invalid_error_response"
            raise RuntimeError(f"OpenAI HTTP {response.status_code}: {code}")
        data = response.json()
        if data.get("status") != "completed":
            raise RuntimeError(f"OpenAI 응답 미완료: {data.get('status')}")
        summary = "\n".join(
            part["text"] for item in data.get("output", [])
            if item.get("type") == "message"
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        ).strip()
        if not summary:
            raise RuntimeError("OpenAI 요약 내용 없음")
        usage = data.get("usage", {})
        log.info(f" ✅ OpenAI 요약 완료: {len(summary)} 글자 "
                 f"(model={CONFIG['openai_model']}, "
                 f"input={usage.get('input_tokens')}, output={usage.get('output_tokens')})")
        return {"summary": summary}
    except Exception as e:
        detail = str(e) if isinstance(e, RuntimeError) else type(e).__name__
        log.error(f"❌ OpenAI 요약 실패: {detail}")
        return None


def generate_html_report(videos_data):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    now = datetime.now().strftime("%Y%m%d_%H%M")
    cards_html = ""
    for v in videos_data:
        summary_html = v["summary"]
        summary_html = re.sub(r"#{1,3} (.+)", r"<h3>\1</h3>", summary_html)
        summary_html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", summary_html)
        summary_html = re.sub(r"^- (.+)", r"<li>\1</li>", summary_html, flags=re.MULTILINE)
        summary_html = summary_html.replace("\n", "<br>")
        pub_time = v["published_at"].replace("T", " ").replace("Z", " UTC")
        cards_html += f"""
        <div class="card">
            <div class="card-header">
                <a href="https://www.youtube.com/watch?v={v['id']}" target="_blank">
                    <img src="{v['thumbnail']}" alt="thumbnail" class="thumbnail">
                </a>
                <div class="meta">
                    <h2><a href="https://www.youtube.com/watch?v={v['id']}" target="_blank">{v['title']}</a></h2>
                    <span class="badge" style="background:{v['badge_bg']};color:{v['badge_color']}">{v['badge_label']}</span>
                    <span class="time">🕐 {pub_time}</span>
                </div>
            </div>
            <div class="summary">{summary_html}</div>
        </div>"""

    html = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>마켓 요약 리포트 - {today}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, sans-serif; background: #0a0e1a; color: #e0e6f0; padding: 20px; line-height: 1.7; }}
        .header {{ text-align: center; padding: 40px 20px; border-bottom: 1px solid #1e2d4a; margin-bottom: 30px; }}
        .header h1 {{ font-size: 2em; color: #4a9eff; margin-bottom: 8px; }}
        .header .date {{ color: #8899bb; font-size: 0.95em; }}
        .cards-container {{ max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }}
        .card {{ background: #111827; border: 1px solid #1e2d4a; border-radius: 12px; overflow: hidden; }}
        .card-header {{ display: flex; gap: 16px; padding: 20px; background: #0d1520; }}
        .thumbnail {{ width: 180px; min-width: 180px; border-radius: 8px; object-fit: cover; }}
        .meta {{ flex: 1; }}
        .meta h2 {{ font-size: 1.1em; margin-bottom: 10px; }}
        .meta h2 a {{ color: #e0e6f0; text-decoration: none; }}
        .badge {{ display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 0.75em; margin-right: 8px; }}
        .time {{ color: #8899bb; font-size: 0.85em; }}
        .summary {{ padding: 24px; font-size: 0.93em; }}
        .summary h3 {{ color: #4a9eff; margin: 16px 0 8px; font-size: 1em; }}
        .summary li {{ margin-left: 20px; margin-bottom: 4px; color: #c0cce0; }}
        .summary strong {{ color: #e8d44d; }}
        .footer {{ text-align: center; padding: 30px; color: #445566; font-size: 0.85em; margin-top: 40px; }}
    </style></head><body>
    <div class="header"><h1>📊 마켓 데일리 요약</h1>
    <div class="date">{today} · 총 {len(videos_data)}개 영상</div></div>
    <div class="cards-container">{cards_html}</div>
    <div class="footer">자동 생성 · Bloomberg / FedGuy YouTube 자막 기반 · OpenAI 번역 요약</div>
    </body></html>"""

    # 실행 날짜 폴더를 만들고 그 안에 저장
    day_dir = OUTPUT_DIR / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    filepath = day_dir / f"report_{now}.html"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    log.info(f"📄 HTML 리포트 저장: {filepath}")
    return str(filepath), html


def run_job():
    log.info("=" * 50)
    log.info("🚀 요약 작업 시작")
    processed = load_processed()
    videos = fetch_recent_videos(hours_back=CONFIG.get("hours_back",24))
    new_videos = [v for v in videos if v["id"] not in processed]
    log.info(f"새 영상: {len(new_videos)}개")

    if not new_videos:
        log.info("새로운 영상이 없습니다.")
        return

    results = []
    summary_failures = 0
    for video in new_videos:
        log.info(f"\n▶ 처리 중: [{video['channel_name']}] {video['title']}")
        transcript = get_transcript(video["id"])
        if not transcript:
            log.warning(" 자막 없음, 건너뜀")
            processed.add(video["id"])
            continue
        result = summarize_with_openai(video["title"], transcript, video["channel_name"])
        if result is None:
            summary_failures += 1
            continue
        results.append({**video, **result})
        processed.add(video["id"])
        time.sleep(2)

    if results:
        filepath, _ = generate_html_report(results)
        log.info(f"\n✅ 완료! {len(results)}개 영상 처리됨")
        log.info(f"📂 리포트: {filepath}")
    else:
        log.info("처리된 영상이 없습니다.")
    save_processed(processed)
    if summary_failures:
        raise RuntimeError(f"요약 실패 {summary_failures}개 — 처리 완료로 저장하지 않음")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 실행! 🚀
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    run_job()
