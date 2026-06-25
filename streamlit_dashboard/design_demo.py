# -*- coding: utf-8 -*-
"""
Streamlit 디자인 배우기 — 실행하면서 보는 데모
================================================
실행:
    streamlit run design_demo.py

왼쪽 코드와 오른쪽(브라우저) 화면을 비교하면서 보세요.
각 섹션이 "디자인 기법 하나"입니다. 위에서부터 쉬운 순서.
"""
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="디자인 데모", page_icon="🎨", layout="wide")

st.title("🎨 Streamlit 디자인 기법 모음")
st.caption("이 페이지 자체가 아래 기법들로 만들어졌습니다.")


# ──────────────────────────────────────────────
# 기법 1) 화면 나누기 — st.columns
#   가로로 영역을 쪼갭니다. 비유: 책상을 세로 칸막이로 나누기.
# ──────────────────────────────────────────────
st.header("1. 화면 나누기 (st.columns)")
st.write("`col1, col2, col3 = st.columns(3)` — 가로 3분할")

col1, col2, col3 = st.columns(3)
with col1:
    st.write("왼쪽 칸")
    st.button("버튼 A")
with col2:
    st.write("가운데 칸")
    st.button("버튼 B")
with col3:
    st.write("오른쪽 칸")
    st.button("버튼 C")

# 비율도 줄 수 있음: st.columns([2, 1]) → 2:1 비율
st.write("비율 지정도 가능: `st.columns([2, 1])`")
left, right = st.columns([2, 1])
left.info("넓은 칸 (비율 2)")
right.warning("좁은 칸 (비율 1)")

st.divider()  # 가로 구분선


# ──────────────────────────────────────────────
# 기법 2) 지표 카드 — st.metric  (가성비 최고, 대시보드 핵심)
#   숫자 + 증감을 예쁘게. delta 가 양수면 초록↑, 음수면 빨강↓.
# ──────────────────────────────────────────────
st.header("2. 지표 카드 (st.metric)")
st.write("숫자 하나를 '카드'로. 변동치(delta)는 색으로 자동 표시됩니다.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("보고서 수", "184건", "+12")
m2.metric("핫 키워드", "rates", "+5")
m3.metric("USD/KRW", "1,365", "-8.2")
m4.metric("VIX", "14.3", "+1.1")

st.divider()


# ──────────────────────────────────────────────
# 기법 3) 카드(테두리 박스) — st.container(border=True)
#   관련 내용을 박스로 묶으면 훨씬 정돈돼 보입니다.
# ──────────────────────────────────────────────
st.header("3. 테두리 박스 (st.container)")

with st.container(border=True):
    st.subheader("📦 박스 안의 내용")
    st.write("관련 있는 것들을 테두리로 묶으면 시선이 정리됩니다.")
    st.metric("박스 안 지표", "42%", "+3%p")

st.divider()


# ──────────────────────────────────────────────
# 기법 4) 탭 / 접기 — st.tabs, st.expander
#   화면을 안 늘리고 정보를 숨겼다 펴기.
# ──────────────────────────────────────────────
st.header("4. 탭과 접기 (st.tabs / st.expander)")

t1, t2 = st.tabs(["탭 1", "탭 2"])
with t1:
    st.write("첫 번째 탭 내용")
with t2:
    st.write("두 번째 탭 내용")

with st.expander("▶ 클릭하면 펼쳐지는 영역 (st.expander)"):
    st.write("긴 설명이나 보조 정보는 여기 접어두면 화면이 깔끔합니다.")

st.divider()


# ──────────────────────────────────────────────
# 기법 5) 표 예쁘게 — st.dataframe + 컬럼 설정
#   진행바, 색, 포맷을 컬럼별로 지정할 수 있습니다.
# ──────────────────────────────────────────────
st.header("5. 표 꾸미기 (st.dataframe)")

df = pd.DataFrame({
    "키워드": ["rates", "fed", "cpi", "jpy", "ai"],
    "언급수": [120, 95, 80, 60, 45],
    "비중": [0.30, 0.24, 0.20, 0.15, 0.11],
})

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        # 숫자 컬럼을 진행바로 표시
        "언급수": st.column_config.ProgressColumn(
            "언급수", min_value=0, max_value=120, format="%d"
        ),
        # 비중을 퍼센트로 포맷
        "비중": st.column_config.NumberColumn("비중", format="%.0f%%"),
    },
)

st.divider()


# ──────────────────────────────────────────────
# 기법 6) 차트 — 한 줄이면 됩니다
# ──────────────────────────────────────────────
st.header("6. 차트 (st.line_chart / st.bar_chart)")

chart_data = pd.DataFrame(
    np.random.randn(30, 2).cumsum(axis=0),
    columns=["Momentum", "Value"],
)
c1, c2 = st.columns(2)
with c1:
    st.write("선 차트")
    st.line_chart(chart_data)
with c2:
    st.write("막대 차트")
    st.bar_chart(chart_data)

st.divider()


# ──────────────────────────────────────────────
# 기법 7) 커스텀 CSS 주입 (고급, 자유도 최고)
#   진짜 웹 CSS 를 직접 넣어 폰트/여백/색을 세밀하게 제어.
#   unsafe_allow_html=True 가 "HTML 직접 넣기 허용" 스위치.
# ──────────────────────────────────────────────
st.header("7. 커스텀 CSS (고급)")
st.write("아래 색깔 박스는 순수 CSS 로 직접 그린 것입니다.")

st.markdown(
    """
    <style>
    .my-card {
        background: linear-gradient(135deg, #2a3b5f, #14181f);
        border: 1px solid #4d6aa3;
        border-radius: 12px;
        padding: 20px;
        color: #ffffff;
    }
    .my-card h3 { margin: 0 0 8px 0; }
    </style>

    <div class="my-card">
        <h3>커스텀 카드</h3>
        <p>CSS 로 그라데이션 배경 + 둥근 모서리 + 테두리를 직접 입혔습니다.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "💡 정리: 1~6번(레이아웃·metric·박스·탭·표·차트)만 잘 써도 "
    "충분히 '대시보드답게' 보입니다. 7번 CSS 는 더 욕심날 때만."
)
