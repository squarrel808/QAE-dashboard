from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any

import build_sp500_ai_value_chain as ai

HERE = Path(__file__).resolve().parent
BQL_ROOT = HERE.parents[2]
DEFAULT_MASTER = BQL_ROOT / "Rawfile" / "BQuant_Master.xlsx"
DEFAULT_OUTPUT = BQL_ROOT / "Theme" / "output"
PERIODS = ("1D", "5D", "1M", "3M", "6M")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def commentary_slot(kind: str, *parts: Any) -> str:
    """Return a stable, invisible hook for prose-only post processing."""
    raw = "\x1f".join([kind, *(str(part) for part in parts)])
    slot_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return (
        f'<div class="commentary-slot" data-commentary-slot="{esc(kind)}" '
        f'data-commentary-id="{slot_id}"></div>'
    )


def pct(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "데이터 부족"
    return f"{float(value) * 100:+.1f}%"


def cls(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "na"
    return "pos" if value > 0 else "neg" if value < 0 else "zero"


def cells(values: dict[str, float | None]) -> str:
    return "".join(f'<td class="num {cls(values.get(p))}">{pct(values.get(p))}</td>' for p in PERIODS)


def performance_table(data: dict[str, Any], mode: str, primary: str) -> str:
    rows = []
    ranked = sorted(data["stages"], key=lambda s: data["modes"][mode][s["key"]]["performance"][primary]["return"] or -999, reverse=True)
    for stage in ranked:
        perf = data["modes"][mode][stage["key"]]["performance"]
        values = {p: perf[p]["return"] for p in PERIODS}
        breadth = perf[primary]["breadth"]
        rows.append(f'<tr><td>{esc(stage["name"])}</td><td class="num">{perf[primary]["members"]}</td>{cells(values)}<td class="num">{pct(breadth)}</td></tr>')
    rows.append(f'<tr class="benchmark"><td>S&amp;P 500 BM</td><td class="num">{data["meta"]["spxMembers"]}</td>{cells(data["benchmark"]["returns"])}<td class="num">—</td></tr>')
    return '<div class="table-wrap"><table><thead><tr><th>밸류체인</th><th class="num">N</th>' + ''.join(f'<th class="num">{p}</th>' for p in PERIODS) + f'<th class="num">{primary} 상승 종목 비율</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def primary_table(data: dict[str, Any], mode: str, primary: str) -> str:
    benchmark = data["benchmark"]["returns"].get(primary)
    ranked = sorted(data["stages"], key=lambda s: data["modes"][mode][s["key"]]["performance"][primary]["return"] or -999, reverse=True)
    rows = []
    for stage in ranked:
        item = data["modes"][mode][stage["key"]]["performance"][primary]
        value = item["return"]
        excess = value - benchmark if value is not None and benchmark is not None else None
        rows.append(f'<tr><td>{esc(stage["name"])}</td><td class="num">{item["members"]}</td><td class="num {cls(value)}">{pct(value)}</td><td class="num">{pct(item["breadth"])}</td><td class="num {cls(excess)}">{pct(excess)}</td></tr>')
    rows.append(f'<tr class="benchmark"><td>S&amp;P 500 BM</td><td class="num">{data["meta"]["spxMembers"]}</td><td class="num {cls(benchmark)}">{pct(benchmark)}</td><td class="num">—</td><td class="num zero">0.0%</td></tr>')
    return f'<div class="table-wrap"><table><thead><tr><th>밸류체인</th><th class="num">N</th><th class="num">{primary} 수익률</th><th class="num">{primary} 상승 종목 비율</th><th class="num">BM 대비</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def stock_table(data: dict[str, Any], stage: dict[str, Any], mode: str, primary: str) -> str:
    allowed = {"Core"} if mode == "Core" else {"Core", "Adjacent"}
    stocks = [s for s in data["stocks"] if s["stage"] == stage["key"] and s["confidence"] in allowed]
    stocks.sort(key=lambda s: s["returns"].get(primary) if s["returns"].get(primary) is not None else -999, reverse=True)
    rows = []
    for stock in stocks:
        purity = "핵심" if stock["confidence"] == "Core" else "인접"
        rows.append(
            f'<tr><td><div class="stock-name">{esc(stock["company"])}</div>'
            f'<div class="stock-desc">{esc(stock["rationale"])}</div>'
            + commentary_slot("stock", stock["ticker"])
            + f'</td><td>{purity}</td>{cells(stock["returns"])}</tr>'
        )
    return '<div class="table-wrap"><table><thead><tr><th>종목 및 사업 설명</th><th>분류</th>' + ''.join(f'<th class="num">{p}</th>' for p in PERIODS) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def classification_table(data: dict[str, Any]) -> str:
    stage_by_key = {stage["key"]: stage for stage in data["stages"]}
    order = {stage["key"]: idx for idx, stage in enumerate(data["stages"])}
    stocks = sorted(data["stocks"], key=lambda s: (order[s["stage"]], s["confidence"] != "Core", s["company"]))
    rows = []
    for stock in stocks:
        stage = stage_by_key[stock["stage"]]
        purity = "핵심" if stock["confidence"] == "Core" else "인접"
        rows.append(
            f'<tr><td>{esc(stage["name"])}</td><td>{esc(stock["company"])}</td>'
            f'<td>{purity}</td><td class="reason">{esc(stock["rationale"])}</td></tr>'
        )
    return '<div class="table-wrap"><table><thead><tr><th>밸류체인</th><th>종목</th><th>분류</th><th>편입 근거·사업 내용</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def render(data: dict[str, Any], primary: str) -> str:
    starts = ' · '.join(f'{p}: {data["periodStarts"].get(p, "데이터 부족")}' for p in PERIODS)
    mode_panels = []
    for idx, mode in enumerate(("Core", "Expanded")):
        details = []
        for stage in data["stages"]:
            details.append(
                f'<section class="chain"><h3>{esc(stage["name"])}</h3>'
                f'<p class="desc">{esc(stage["description"])}</p>'
                + commentary_slot("stage", stage["key"])
                + stock_table(data, stage, mode, primary)
                + '</section>'
            )
        mode_panels.append(f'<section class="mode-panel{" active" if idx == 0 else ""}" data-mode="{mode}"><h2>1. 전체 AI 밸류체인 성과표 — {primary}</h2>{primary_table(data, mode, primary)}<h2>2. 밸류체인 로테이션 — 1D / 5D / 1M / 3M / 6M</h2>{performance_table(data, mode, primary)}<h2>3. 밸류체인별 종목 성과</h2>{"".join(details)}</section>')
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>S&P 500 AI 밸류체인 {primary}</title><style>
:root{{--navy:#17365d;--blue:#0070c0;--red:#c00000;--line:#cbd6e4;--pale:#f3f7fb;--text:#172033}}*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,"Malgun Gothic",sans-serif;color:var(--text)}}main{{max-width:1440px;margin:auto;padding:20px 24px 48px}}h1{{margin:0 0 5px;font-size:24px}}h2{{margin:24px 0 8px;border-bottom:2px solid var(--navy);padding-bottom:5px;font-size:18px}}h3{{margin:20px 0 2px;color:var(--navy);font-size:16px}}.meta,.desc{{color:#667085;font-size:11px;line-height:1.5}}.tabs{{position:sticky;top:0;z-index:5;background:#fff;padding:8px 0;border-bottom:1px solid var(--line)}}button{{border:1px solid #aebdce;background:#fff;color:var(--navy);border-radius:5px;padding:6px 12px;margin-right:5px;font-weight:700;cursor:pointer}}button.active{{background:var(--navy);color:#fff}}.mode-panel{{display:none}}.mode-panel.active{{display:block}}.table-wrap{{width:max-content;max-width:100%;overflow:auto;border:1px solid #b8c5d5;border-radius:5px}}table{{border-collapse:collapse;min-width:850px;font-size:12px;white-space:nowrap}}th{{background:var(--navy);color:#fff;text-align:left;padding:5px 8px;border:1px solid #3c587b}}td{{padding:5px 8px;border:1px solid var(--line);vertical-align:top}}tbody tr:nth-child(even){{background:var(--pale)}}.num{{text-align:right;font-variant-numeric:tabular-nums}}.pos{{color:var(--blue);font-weight:700}}.neg{{color:var(--red);font-weight:700}}.na{{color:#98a2b3}}.benchmark{{background:#e2eaf4!important;font-weight:700;border-top:2px solid var(--navy)}}.stock-name{{font-weight:700}}.stock-desc{{max-width:500px;margin-top:2px;color:#667085;font-size:10px;line-height:1.35;white-space:normal}}.chain{{page-break-inside:avoid}}.classification{{margin:12px 0 18px;border:1px solid var(--line);border-radius:6px;background:#fafcff;padding:8px}}.classification summary{{cursor:pointer;color:var(--navy);font-weight:700}}.classification .table-wrap{{margin-top:8px}}td.reason{{max-width:620px;white-space:normal;line-height:1.4}}.note{{margin-top:28px;padding:12px;border-left:4px solid var(--navy);background:var(--pale);font-size:11px;color:#596579}}
.commentary-slot:empty{{display:none}}.commentary-block{{margin:8px 0;padding:9px 11px;border-left:3px solid var(--navy);background:#f8fafc;font-size:11px;line-height:1.55;white-space:normal}}.commentary-block strong{{display:block;margin-bottom:2px;color:var(--navy)}}.commentary-block .commentary-meta{{margin-top:3px;color:#667085;font-size:10px}}.stock-desc+.commentary-block{{max-width:500px;margin-top:5px}}
</style></head><body><main data-report="ai" data-as-of="{esc(data["meta"]["asOf"])}" data-primary="{esc(primary)}"><h1>S&amp;P 500 AI 밸류체인 로테이션 — {primary}</h1><div class="meta">기준일 {esc(data["meta"]["asOf"])} · 기간 시작일 {esc(starts)} · Bloomberg 구성종목 가격, 배당 제외</div>{commentary_slot("global")}<nav class="tabs"><button class="mode-button active" onclick="showMode('Core',this)">핵심 종목</button><button class="mode-button" onclick="showMode('Expanded',this)">핵심 + 인접 종목</button></nav><details class="classification"><summary>분류 종목 / 편입 근거 보기</summary>{classification_table(data)}</details>{''.join(mode_panels)}<div class="note">밸류체인 수익률은 종목별 Shares를 반영한 집계가격으로 계산합니다. 현재 구성종목을 과거로 소급하므로 생존편향이 있으며, 분석용 분류는 공식 지수 분류가 아닙니다.</div></main><script>function showMode(m,b){{document.querySelectorAll('.mode-panel').forEach(x=>x.classList.toggle('active',x.dataset.mode===m));document.querySelectorAll('.mode-button').forEach(x=>x.classList.toggle('active',x===b));window.scrollTo({{top:0,behavior:'instant'}})}}</script></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="S&P 500 AI 밸류체인 표형 HTML")
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--primary", choices=("1D", "5D"), required=True)
    parser.add_argument("--open", action="store_true", dest="open_report")
    args = parser.parse_args()
    raw = ai.load_spx([args.master])
    data = ai.build_data(raw)
    tag = data["meta"]["asOf"].replace("-", "")
    out_dir = args.output_root / tag / "AI"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'SP500_AI_밸류체인_{args.primary}_보고서_{tag}.html'
    out.write_text(render(data, args.primary), encoding="utf-8")
    payload = {"primary": args.primary, "asOf": data["meta"]["asOf"], "outputs": [str(out.resolve())]}
    print(json.dumps(payload, ensure_ascii=False))
    if args.open_report:
        os.startfile(out)


if __name__ == "__main__":
    main()
