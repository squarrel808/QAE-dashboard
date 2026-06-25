# -*- coding: utf-8 -*-
"""
Macro Dashboard (Streamlit 뼈대)
================================
기존에 만들어 둔 HTML 대시보드들을 5개 대분류 + 하위 탭 구조로 묶은
Streamlit 골격입니다.

실행:
    pip install -r requirements.txt
    streamlit run app.py

구조:
    1. 경제지표        (단일)  -> assets/econ_dashboard.html
    2. 증권사 자료     (5탭)   -> ibreport (Vercel 라이브 화면 iframe)
    3. PCA            (단일)  -> assets/pca_dashboard.html
    4. Consensus      (3탭)   -> GDP / CPI / CPI Distribution
    5. Policy Tone    (단일)  -> assets/policy_hawkdove.html

뼈대 단계라 각 화면은 "기존 HTML 그대로" 끼워 넣습니다.
나중에 GS API 팩터 비교 같은 '순수 Streamlit' 페이지를 여기 추가하면 됩니다.
"""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

# ──────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Macro Dashboard",
    page_icon="📊",
    layout="wide",
)

# ──────────────────────────────────────────────
# 화면 꽉 채우기 CSS
#   Streamlit 기본 좌우 여백을 줄이고 폭을 최대로 넓혀
#   끼워 넣은 HTML 이 화면 가장자리까지 차도록 만듭니다.
# ──────────────────────────────────────────────
st.markdown(
    """
    <style>
      .block-container {
          padding-top: 1.2rem;
          padding-bottom: 0rem;
          padding-left: 1rem;
          padding-right: 1rem;
          max-width: 100% !important;
      }
      /* 끼워 넣은 iframe 을 가로 100% 로 */
      iframe { width: 100% !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

ASSETS = Path(__file__).parent / "assets"

# ibreport 는 React(Next.js) 앱이라 Streamlit 안에 코드로 못 넣습니다.
# 이미 Vercel 에 배포돼 있으니 그 라이브 화면을 iframe 으로 끼워 넣습니다.
IBREPORT_BASE = "https://ibreport-dashboard.vercel.app"


# ──────────────────────────────────────────────
# 헬퍼: 로컬 HTML 파일을 화면에 끼워 넣기
# ──────────────────────────────────────────────
def show_local_html(filename: str, height: int = 1200):
    """assets 폴더의 HTML 파일을 읽어 그대로 렌더링."""
    path = ASSETS / filename
    if not path.exists():
        st.error(f"파일을 찾을 수 없습니다: {filename}")
        return
    html = path.read_text(encoding="utf-8")
    components.html(html, height=height, scrolling=True)


def show_remote_iframe(url: str, height: int = 1200):
    """외부 URL(예: Vercel 배포 화면)을 iframe 으로 끼워 넣기.

    참고: 사이트가 iframe 임베드를 막아두면(X-Frame-Options) 화면이 빈칸으로
    보일 수 있습니다. 그럴 때를 대비해 '새 탭에서 열기' 링크를 함께 둡니다.
    """
    st.markdown(f"🔗 [새 탭에서 열기]({url})")
    components.iframe(url, height=height, scrolling=True)


# ──────────────────────────────────────────────
# 사이드바: 5개 대분류
# ──────────────────────────────────────────────
st.sidebar.title("📊 Macro Dashboard")
st.sidebar.caption("국민연금 QAE 매크로 대시보드")

CATEGORIES = [
    "① 경제지표",
    "② 증권사 자료 (Report)",
    "③ PCA",
    "④ Consensus",
    "⑤ Policy Tone",
]
category = st.sidebar.radio("대분류 선택", CATEGORIES, label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.caption(
    "뼈대(skeleton) 버전입니다.\n"
    "각 화면은 기존 HTML 대시보드를 그대로 끼워 넣었습니다."
)


# ──────────────────────────────────────────────
# 본문: 대분류별 화면
# ──────────────────────────────────────────────

# ① 경제지표 ─ 단일 화면
if category == CATEGORIES[0]:
    st.header("① 경제지표")
    st.caption("TradingEconomics 경제 캘린더 (★3 / 주요 10개국)")
    show_local_html("econ_dashboard.html")

# ② 증권사 자료 (ibreport) ─ 하위 5탭 (Vercel 라이브 화면)
elif category == CATEGORIES[1]:
    st.header("② 증권사 자료 (Report)")
    st.caption("IB 보고서 키워드/테마 대시보드 — Vercel 라이브 화면")

    tabs = st.tabs(
        ["보고서 목록", "키워드 트렌드", "Daily Brief", "북마크", "네트워크"]
    )
    sub_paths = ["/reports", "/keyword_trend", "/daily", "/saved", "/network"]
    for tab, path in zip(tabs, sub_paths):
        with tab:
            show_remote_iframe(IBREPORT_BASE + path)

# ③ PCA ─ 단일 화면
elif category == CATEGORIES[2]:
    st.header("③ PCA")
    st.caption("주성분 분석(PCA) 프레임워크 대시보드")
    show_local_html("pca_dashboard.html")

# ④ Consensus ─ 하위 3탭
elif category == CATEGORIES[3]:
    st.header("④ Consensus")
    st.caption("성장/물가 컨센서스 대시보드")

    t_gdp, t_cpi, t_dist = st.tabs(
        ["GDP Consensus", "CPI Consensus", "CPI Distribution"]
    )
    with t_gdp:
        show_local_html("consensus_gdp.html")
    with t_cpi:
        show_local_html("consensus_cpi.html")
    with t_dist:
        show_local_html("consensus_cpi_dist.html")

# ⑤ Policy Tone ─ 단일 화면
elif category == CATEGORIES[4]:
    st.header("⑤ Policy Tone")
    st.caption("중앙은행 발언 Hawkish/Dovish 스탠스 지수")
    show_local_html("policy_hawkdove.html")
