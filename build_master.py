# -*- coding: utf-8 -*-
"""
build_master.py — Macro Dashboard (통합 탭) 생성기

사용법:
    python build_master.py
→ 같은 폴더에 master_dashboard.html 생성

탭을 추가/삭제/순서변경 하려면 아래 TABS 리스트만 고치고 다시 실행.
(id는 영문 소문자, path는 이 폴더 기준 상대경로)
"""
from pathlib import Path

TITLE = "Macro Dashboard"
OUTPUT = "master_dashboard.html"

# (탭 id, 버튼에 보일 이름, 상대 경로) — 위에서부터 탭 순서
TABS = [
    ("econ",      "경제지표",        "경제지표가져오기/dashboard.html"),
    ("research",  "증권사 자료",     "https://ibreport-dashboard.vercel.app"),
    ("pca",       "PCA",            "PCA/pca_dashboard.html"),
    ("caimap",    "CAI · MAP",      "gs_api/cai_map_dashboard.html"),
    ("equity",    "Equity Factors", "gs_api/pairbaskets_dashboard.html"),
    ("consensus", "Consensus",      "Consensus Builder/Consensus.html"),
    ("policy",    "Policy Tone",    "policytone/hawkdove_dashboard.html"),
]

TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
body {{ margin:0; background:#f7f6f3; color:#1a1c1f; font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",Arial,sans-serif; }}
.header {{ padding:16px 24px 8px 24px; }}
h1 {{ margin:0 0 12px 0; font-size:22px; color:#1a1c1f; font-family:Georgia,serif; }}
.tabs {{ display:flex; gap:8px; margin-bottom:12px; }}
.tab-btn {{ background:#fff; color:#1a1c1f; border:1px solid #e8e8e6; border-radius:8px;
            padding:10px 16px; cursor:pointer; font-size:14px; font-weight:600; }}
.tab-btn:hover {{ background:#f4f3f1; }}
.tab-btn.active {{ background:#6e1f1f; color:white; border-color:#6e1f1f; }}
.viewer {{ width:100%; height:calc(100vh - 100px); }}
.tab-frame {{ width:100%; height:100%; border:none; display:none; }}
.tab-frame.active {{ display:block; }}
.missing {{ padding:40px; color:#c0392b; font-size:15px; display:none; }}
.missing.active {{ display:block; }}
</style>
</head>
<body>

<div class="header">
    <h1>{title}</h1>
    <div class="tabs">
{buttons}
    </div>
</div>

<div class="viewer">
{frames}
</div>

<script>
function showTab(id, btn) {{
    document.querySelectorAll('.tab-frame').forEach(f => f.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const frame = document.getElementById(id);
    if (!frame.src && frame.dataset.src) frame.src = frame.dataset.src;  // 첫 클릭 시 로드
    frame.classList.add('active');
    btn.classList.add('active');
}}
</script>

</body>
</html>
"""


def main():
    base = Path(__file__).resolve().parent
    buttons, frames = [], []

    for i, (tab_id, label, rel_path) in enumerate(TABS):
        active = " active" if i == 0 else ""
        exists = rel_path.startswith("http") or (base / rel_path).exists()
        if not exists:
            print(f"[WARN] 파일 없음: {rel_path} — 탭은 만들지만 열면 빈 화면일 수 있음")
        buttons.append(
            f'        <button class="tab-btn{active}" '
            f'onclick="showTab(\'{tab_id}\', this)">{label}</button>'
        )
        # 첫 탭만 즉시 로드, 나머지는 첫 클릭 때 로드 (대용량 대비)
        src_attr = f'src="{rel_path}"' if i == 0 else f'data-src="{rel_path}"'
        frames.append(
            f'    <iframe id="{tab_id}" class="tab-frame{active}" {src_attr}></iframe>'
        )

    html = TEMPLATE.format(title=TITLE,
                           buttons="\n".join(buttons),
                           frames="\n".join(frames))
    out = base / OUTPUT
    out.write_text(html, encoding="utf-8")
    print(f"생성 완료: {out} (탭 {len(TABS)}개)")


if __name__ == "__main__":
    main()
