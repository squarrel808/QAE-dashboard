# -*- coding: utf-8 -*-
"""
weco_dashboard.py — 블룸버그 WECO → 경제지표 캘린더 dashboard.html
----------------------------------------------------------------------
입력 : ../블벅경제지표/load_weco.py 의 load_rows()  (지표 + 연설·이벤트)
       없으면 ../블벅경제지표/weco_global.xlsx 로 폴백
출력 : dashboard.html (기존 셀레니움 스크래퍼 출력과 같은 파일명 → 탭/embed 연결 유지)

행 스키마: d / t / cc / flag / ev / p / svy / act / pri / rev / rel / kind
  kind = "ind"(지표) | "evt"(연설·이벤트)

표시 규칙:
  - 날짜별 그룹 헤더 + 시간/국가/지표/Actual/Survey/Prior/Revised
  - Relevance(블룸버그 관련도) ≥70 High, ≥30 Med, 그 외 Low — 국가 점 색·강조 행에만 사용
  - 값 표시는 로더(load_weco.fmt)가 만든 문자열을 그대로 쓴다. %환산은 하지 않는다
    (블룸버그 %지표는 0.022 식으로 저장되며 그대로 '0.022' 로 표시된다)
    ※ 아래 fmt()/load_rows_legacy() 는 폴백(weco_global.xlsx) 경로 전용이라
      거기서만 |v|<1 을 %로 환산한다

실행 : python weco_dashboard.py
"""
import os
import sys
import json
import datetime as dt
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(os.path.dirname(BASE), "블벅경제지표", "weco_global.xlsx")
OUT  = os.path.join(BASE, "dashboard.html")

# ── 새 로더(../블벅경제지표/load_weco.py) import, 없으면 폴백 ──────────────
LOADER_DIR = os.path.join(os.path.dirname(BASE), "블벅경제지표")
if LOADER_DIR not in sys.path:
    sys.path.insert(0, LOADER_DIR)
try:
    from load_weco import load_rows as _load_rows_ext   # type: ignore
    _LOADER_ERR = None
except Exception as _e:                                  # noqa: BLE001
    _load_rows_ext = None
    _LOADER_ERR = _e

FLAG = {"US": "🇺🇸", "GE": "🇩🇪", "CA": "🇨🇦", "AU": "🇦🇺", "UK": "🇬🇧", "FR": "🇫🇷", "JN": "🇯🇵"}
DISP = {"US": "US", "GE": "DE", "CA": "CA", "AU": "AU", "UK": "UK", "FR": "FR", "JN": "JP"}


def fmt(v):
    """값 포맷: '--'/NaN → '', |v|<1 소수는 % 환산(블룸버그식), 그 외 숫자는 그대로."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, str):
        s = v.strip()
        return "" if s in ("--", "nan", "NaT", "") else s
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f != f:  # NaN
        return ""
    if abs(f) < 1 and f != 0:
        return f"{f*100:.1f}%"
    if f == 0:
        return "0"
    if abs(f) >= 1000:
        return f"{f:,.0f}"
    return f"{f:.4g}"


def load_rows_legacy():
    """폴백: 기존 weco_global.xlsx 를 국가별 시트로 읽는다 (지표만, kind='ind')."""
    xl = pd.ExcelFile(SRC)
    rows = []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet, header=0)
        df.columns = [str(c).strip() for c in df.columns]
        need = ["Date Time", "Country Code", "Event"]
        if not all(c in df.columns for c in need):
            print(f"[skip] {sheet}: 헤더 불일치")
            continue
        for _, r in df.iterrows():
            t = pd.to_datetime(r["Date Time"], errors="coerce")
            ev = str(r.get("Event", "") or "").strip()
            if pd.isna(t) or not ev or ev == "Event":
                continue
            cc = str(r.get("Country Code", "") or "").strip()
            try:
                rel = float(r.get("Relevance"))
            except (TypeError, ValueError):
                rel = 0.0
            if rel != rel:
                rel = 0.0
            period = r.get("Period", "")
            if isinstance(period, (pd.Timestamp, dt.datetime)):
                period = period.strftime("%m/%d")
            rows.append({
                "d": t.strftime("%Y-%m-%d"),
                "t": t.strftime("%H:%M"),
                "cc": DISP.get(cc, cc),
                "flag": FLAG.get(cc, "🌐"),
                "ev": ev,
                "p": str(period or "").strip(),
                "svy": fmt(r.get("Survey")),
                "act": fmt(r.get("Actual")),
                "pri": fmt(r.get("Prior")),
                "rev": fmt(r.get("Revised")),
                "rel": round(rel, 1),
                "kind": "ind",
            })
    return rows


def normalize(rows):
    """로더가 준 행을 대시보드 계약대로 다듬는다 (누락 필드 채우고 정렬)."""
    out = []
    for r in rows:
        if not r.get("d") or not r.get("ev"):
            continue
        try:
            rel = float(r.get("rel") or 0.0)
        except (TypeError, ValueError):
            rel = 0.0
        if rel != rel:
            rel = 0.0
        kind = str(r.get("kind") or "ind").strip().lower()
        if kind not in ("ind", "evt"):
            kind = "ind"
        out.append({
            "d": str(r["d"]),
            "t": str(r.get("t") or ""),
            "cc": str(r.get("cc") or ""),
            "flag": str(r.get("flag") or "🌐"),
            "ev": str(r["ev"]),
            "p": str(r.get("p") or ""),
            "svy": str(r.get("svy") or ""),
            "act": str(r.get("act") or ""),
            "pri": str(r.get("pri") or ""),
            "rev": str(r.get("rev") or ""),
            "rel": round(rel, 1),
            "kind": kind,
        })
    out.sort(key=lambda x: (x["d"], x["t"], -x["rel"]))
    return out


def load_rows():
    if _load_rows_ext is not None:
        return normalize(_load_rows_ext())
    print(f"[fallback] load_weco.load_rows() 사용 불가 ({_LOADER_ERR}) -> {SRC}")
    return normalize(load_rows_legacy())


TEMPLATE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Economic Calendar</title>
<style>
:root{--ink:#1a1c1f;--muted:#9aa0a6;--line:#e8e8e6;--head:#f4f3f1;--badge:#6e1f1f;--up:#1a7a4c;--down:#c0392b;--evt:#4a5b74;}
*{box-sizing:border-box}
body{margin:0;background:#f7f6f3;color:var(--ink);font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;}
.num{font-variant-numeric:tabular-nums;}
.wrap{max-width:1100px;margin:0 auto;padding:26px 20px 80px;}
header.top{display:flex;align-items:flex-end;justify-content:space-between;border-bottom:2px solid var(--ink);padding-bottom:12px;margin-bottom:14px;flex-wrap:wrap;gap:10px;}
.brand{font-family:Georgia,serif;font-size:24px;font-weight:700;}
.brand small{display:block;font-family:sans-serif;font-size:11px;font-weight:600;letter-spacing:.18em;color:var(--muted);margin-top:4px;}
.gen{font-size:11px;color:var(--muted);}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;}
.chip{font-size:12px;font-weight:600;border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 11px;cursor:pointer;user-select:none;}
.chip.on{background:var(--ink);color:#fff;border-color:var(--ink);}
.board{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;}
table{width:100%;border-collapse:collapse;}
th{font-size:11px;color:var(--muted);font-weight:700;text-align:right;padding:9px 14px;background:var(--head);}
th.l{text-align:left;}
td{font-size:13px;padding:7px 14px;border-top:1px solid var(--line);text-align:right;}
td.l{text-align:left;}
tr.date td{background:var(--head);font-weight:800;font-size:12.5px;text-align:left;padding:8px 14px;}
td.time{color:var(--muted);white-space:nowrap;width:52px;font-variant-numeric:tabular-nums;}
td.cty{white-space:nowrap;width:66px;font-weight:700;}
td.ev{max-width:360px;}
td.ev .per{color:var(--muted);font-size:11px;margin-left:5px;}
.hi td.ev{font-weight:700;}
td.act{font-weight:700;}
.beat{color:var(--up);} .miss{color:var(--down);}
.upcoming td.act{color:var(--badge);}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:1px;}
.dot.h{background:var(--badge);} .dot.m{background:#d9a441;} .dot.l{background:#c9c9c6;}
tr.evt td.ev{color:var(--evt);}
.tag{display:inline-block;font-size:9.5px;font-weight:700;letter-spacing:.05em;color:var(--evt);background:#eef1f6;border:1px solid #dde3ec;border-radius:3px;padding:0 4px;margin-right:5px;vertical-align:1.5px;}
</style></head><body><div class="wrap">
<header class="top">
  <div class="brand">Economic Calendar<small>BLOOMBERG WECO</small></div>
  <div class="gen">generated __GEN__ · __CNT__ events</div>
</header>
<div class="chips" id="cty"></div>
<div class="chips">
  <span class="chip rng on" data-r="week">이번 주</span>
  <span class="chip rng" data-r="month">이번 달</span>
  <span class="chip rng" data-r="upcoming">예정만</span>
  <span class="chip rng" data-r="all">전체 기간</span>
</div>
<div class="board"><table>
<thead><tr><th class="l">시간</th><th class="l">국가</th><th class="l">지표</th><th>Actual</th><th>Survey</th><th>Prior</th><th>Revised</th></tr></thead>
<tbody id="tb"></tbody></table></div>
<script>
const ROWS = __DATA__;
const COUNTRIES = [...new Set(ROWS.map(r=>r.cc))];
const selC = new Set(COUNTRIES);
let rngF = 'week';
const today = new Date(); const ts = d => new Date(d+'T00:00:00');
function weekRange(){
  const d = new Date(today); const dow = (d.getDay()+6)%7;
  const mon = new Date(d); mon.setDate(d.getDate()-dow);
  const sun = new Date(mon); sun.setDate(mon.getDate()+6);
  const f = x=>x.toISOString().slice(0,10);
  return [f(mon), f(sun)];
}
function impCls(rel){ return rel>=70?'h':(rel>=30?'m':'l'); }
function esc(s){ return String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function render(){
  const [wa, wb] = weekRange();
  const tstr = today.toISOString().slice(0,10);
  let html='', lastD='';
  ROWS.forEach(r=>{
    if(!selC.has(r.cc)) return;
    if(rngF==='week' && (r.d<wa || r.d>wb)) return;
    if(rngF==='month' && r.d.slice(0,7)!==tstr.slice(0,7)) return;
    if(rngF==='upcoming' && r.d<tstr) return;
    if(r.d!==lastD){
      lastD=r.d;
      const day=['일','월','화','수','목','금','토'][ts(r.d).getDay()];
      html+='<tr class="date"><td colspan="7">'+r.d+' ('+day+')</td></tr>';
    }
    const isEvt = r.kind==='evt';
    const hi = r.rel>=70?' hi':'';
    const upc = (!isEvt && !r.act && r.d>=tstr)?' upcoming':'';
    let actCls='act';
    if(r.act && r.svy){
      const a=parseFloat(r.act), s=parseFloat(r.svy);
      if(!isNaN(a)&&!isNaN(s)){ if(a>s)actCls+=' beat'; else if(a<s)actCls+=' miss'; }
    }
    html+='<tr class="r'+hi+upc+(isEvt?' evt':'')+'"><td class="l time">'+esc(r.t)+'</td>'
      +'<td class="l cty"><span class="dot '+impCls(r.rel)+'"></span>'+r.flag+' '+esc(r.cc)+'</td>'
      +'<td class="l ev">'+(isEvt?'<span class="tag">EVENT</span>':'')+esc(r.ev)
        +(r.p?'<span class="per">'+esc(r.p)+'</span>':'')+'</td>'
      +'<td class="num '+actCls+'">'+esc(r.act)+'</td>'
      +'<td class="num">'+esc(r.svy)+'</td>'
      +'<td class="num">'+esc(r.pri)+'</td>'
      +'<td class="num">'+esc(r.rev)+'</td></tr>';
  });
  document.getElementById('tb').innerHTML = html || '<tr><td colspan="7" style="text-align:center;color:#9aa0a6;padding:30px">해당 조건의 지표가 없습니다</td></tr>';
}
const cty=document.getElementById('cty');
COUNTRIES.forEach(c=>{
  const s=document.createElement('span'); s.className='chip on'; s.textContent=c;
  s.onclick=()=>{ selC.has(c)?selC.delete(c):selC.add(c); s.classList.toggle('on'); render(); };
  cty.appendChild(s);
});
document.querySelectorAll('.chip.rng').forEach(el=>{
  el.onclick=()=>{ document.querySelectorAll('.chip.rng').forEach(x=>x.classList.remove('on')); el.classList.add('on'); rngF=el.dataset.r; render(); };
});
render();
</script></div></body></html>
"""


def main():
    rows = load_rows()
    n_evt = sum(1 for r in rows if r["kind"] == "evt")
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(rows, ensure_ascii=False))
            .replace("__GEN__", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__CNT__", str(len(rows))))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[saved] {OUT} ({len(rows)} rows, evt {n_evt} / ind {len(rows)-n_evt})")


if __name__ == "__main__":
    main()
