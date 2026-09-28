# -*- coding: utf-8 -*-
"""
build_domestic_baskets.py — 미국/유럽/일본 내수(Domestic) 바스켓 추이 탭 생성기
-----------------------------------------------------------------------------
하는 일:
  1) .env 의 자격증명으로 인증
  2) CUSTOM_BASKETS_LEVELS 에서 내수 바스켓 3종의 일별 종가를 당김
       · GSXUAMER  GS US Domestic Sales      (USD, 2010-01~)
       · GSXEDCON  GS EU Domestic Consumer   (EUR, 2017-09~)
       · GSXAJPDR  GS Japan Domestic Cons    (JPY, 2016-06~)  ※ Cons = Consumer
  3) 공통 날짜축(합집합 + ffill)으로 정렬, 세 계열이 모두 존재하는 날부터 사용
  4) 데이터를 박은 정적 HTML(domestic_dashboard.html) 한 장 생성
       - 100 리베이스 라인차트 (기간 드롭다운 1M~Max, 기준일은 창의 첫날)
       - 기간별 수익률 표 (1M/3M/6M/12M/YTD/Max)

실행:  python build_domestic_baskets.py
"""
import os
import json
import datetime as dt
import pandas as pd
from dotenv import load_dotenv
from gs_quant.session import GsSession, Environment
from gs_quant.data import Dataset

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 0) 인증 ───────────────────────────────────────────────────
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
CID, CSEC = os.getenv("GS_CLIENT_ID"), os.getenv("GS_CLIENT_SECRET")
if not CID or not CSEC:
    raise SystemExit(".env 에 GS_CLIENT_ID / GS_CLIENT_SECRET 가 필요합니다.")
GsSession.use(Environment.PROD, CID, CSEC, ("read_product_data",))
print("[OK] 인증")

DATASET = "CUSTOM_BASKETS_LEVELS"
START = dt.date(2010, 1, 1)
END = dt.date.today()

# bbid, 표시라벨, 통화
BASKETS = [
    ("GSXUAMER", "US · Domestic Sales",    "USD"),
    ("GSXEDCON", "EU · Domestic Consumer", "EUR"),
    ("GSXAJPDR", "Japan · Domestic Cons",  "JPY"),
]
BBIDS = [b[0] for b in BASKETS]

print(f"[..] {DATASET} 조회 — {', '.join(BBIDS)}")
df = Dataset(DATASET).get_data(START, END, bbid=BBIDS)
if "date" not in df.columns:
    df = df.reset_index()
df["date"] = pd.to_datetime(df["date"])

# ── 공통 날짜축: 합집합 + ffill (미/유/일 휴장일이 달라 교집합은 손실이 큼) ──
wide = (df.pivot_table(index="date", columns="bbid", values="closePrice")
          .sort_index()
          .ffill()
          .dropna())                      # 세 계열이 모두 생긴 날부터
wide = wide[BBIDS]
print(f"     {wide.index[0].date()} ~ {wide.index[-1].date()} · {len(wide):,}일")

data = {
    "dates": [d.strftime("%Y-%m-%d") for d in wide.index],
    "series": [{"bbid": b, "label": lb, "ccy": cc,
                "close": [round(float(x), 4) for x in wide[b].values]}
               for b, lb, cc in BASKETS],
}

# ── HTML ──
HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Domestic Baskets</title>
<style>
  :root{--ink:#1a1c1f;--muted:#9aa0a6;--line:#e8e8e6;--head:#f4f3f1;--up:#1a7a4c;--down:#c0392b;--card:#fff;--bg:#f7f6f3;}
  body { margin:0; background:var(--bg); color:var(--ink); font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",Arial,sans-serif; padding:14px 18px; }
  h2 { font-size:15px; margin:0; color:var(--ink); font-family:Georgia,serif; letter-spacing:-.2px; }
  select { background:var(--card); color:var(--ink); border:1px solid var(--line); border-radius:6px; padding:5px 9px; font-size:12px; }
  .lbl { font-size:12px; color:var(--muted); }
  .row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; margin-bottom:14px; }
  .chead { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px; flex-wrap:wrap; }
  table.ret { border-collapse:collapse; width:100%; font-size:12px; }
  table.ret th { color:var(--muted); font-weight:600; padding:6px 8px; text-align:right; white-space:nowrap; border-bottom:1px solid var(--line); }
  table.ret th:first-child { text-align:left; }
  table.ret td { padding:6px 8px; text-align:right; white-space:nowrap; border-bottom:1px solid var(--line); font-variant-numeric:tabular-nums; }
  table.ret td.name { text-align:left; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
  .meta { font-size:11px; color:var(--muted); margin-top:8px; }
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
</head>
<body>

<div class="row" style="margin-bottom:14px;"><h2>내수(Domestic) 바스켓 · 미국 / 유럽 / 일본</h2></div>

<div class="card">
  <div class="chead"><h2>추이 · 100 리베이스</h2>
    <span><span class="lbl">기간</span> <select id="rLines" onchange="draw()"></select></span></div>
  <div style="position:relative;height:380px;"><canvas id="lines"></canvas></div>
  <div class="meta" id="baseNote"></div>
</div>

<div class="card">
  <div class="chead"><h2>기간별 수익률 (%)</h2></div>
  <table class="ret"><thead><tr>
    <th>바스켓</th><th>1M</th><th>3M</th><th>6M</th><th>12M</th><th>YTD</th><th>Max</th><th>최근 종가</th>
  </tr></thead><tbody id="retBody"></tbody></table>
  <div class="meta">가격은 각 바스켓 표시통화(현지통화) 기준 · 환헤지 미반영 · 데이터: GS CUSTOM_BASKETS_LEVELS · 생성 __GEN_TIME__</div>
</div>

<script>
const D = __DATA_JSON__;
const PALETTE = ["#2f5d9e", "#c0722a", "#1a7a4c"];
const RANGES = [[1,"1M"],[3,"3M"],[6,"6M"],[12,"12M"],[24,"2Y"],[36,"3Y"],[60,"5Y"],[0,"Max"]];
let chart = null;

function fillRange(id, def){
  const s = document.getElementById(id);
  RANGES.forEach(function(r){ const o=document.createElement("option"); o.value=r[0]; o.textContent=r[1]; if(r[0]===def) o.selected=true; s.appendChild(o); });
}
// 창의 시작 인덱스 — 마지막 날짜에서 m개월 전
function startIdx(m){
  if(!m) return 0;
  const p = D.dates[D.dates.length-1].split("-").map(Number);
  const cut = new Date(Date.UTC(p[0], p[1]-1-m, p[2]));
  const key = cut.toISOString().slice(0,10);
  for(let i=0;i<D.dates.length;i++) if(D.dates[i] >= key) return i;
  return 0;
}
function rebase(close, i0){
  const b = close[i0];
  return close.slice(i0).map(function(v){ return +(v/b*100).toFixed(2); });
}
function draw(){
  const m = +document.getElementById("rLines").value, i0 = startIdx(m);
  const labels = D.dates.slice(i0);
  const ds = D.series.map(function(s,i){ return {label:s.label, data:rebase(s.close,i0),
    borderColor:PALETTE[i%PALETTE.length], borderWidth:1.6, pointRadius:0, spanGaps:false, tension:.15}; });
  if(chart) chart.destroy();
  chart = new Chart(document.getElementById("lines"), {type:"line", data:{labels:labels, datasets:ds},
    options:{responsive:true, maintainAspectRatio:false, animation:false,
      interaction:{mode:"index", intersect:false},
      plugins:{legend:{display:true, labels:{color:"#1a1c1f", boxWidth:10, font:{size:11}}},
               tooltip:{callbacks:{label:function(c){ return c.dataset.label+": "+c.parsed.y.toFixed(1); }}}},
      scales:{x:{ticks:{color:"#5a5f66", maxTicksLimit:10, autoSkip:true}, grid:{display:false}},
              y:{ticks:{color:"#5a5f66"}, grid:{color:"rgba(0,0,0,.07)"}}}}});
  document.getElementById("baseNote").textContent = "기준일 " + D.dates[i0] + " = 100  ·  최종 " + D.dates[D.dates.length-1];
}
function retPct(close, i0){ const a=close[i0], b=close[close.length-1]; return (b/a-1)*100; }
function ytdIdx(){
  const y = D.dates[D.dates.length-1].slice(0,4);
  for(let i=0;i<D.dates.length;i++) if(D.dates[i] >= y+"-01-01") return i;
  return 0;
}
function fmt(v){ const c = v>=0 ? "var(--up)" : "var(--down)";
  return '<td style="color:'+c+'">'+(v>=0?"+":"")+v.toFixed(1)+'</td>'; }
function drawRet(){
  const idx = [startIdx(1), startIdx(3), startIdx(6), startIdx(12), ytdIdx(), 0];
  document.getElementById("retBody").innerHTML = D.series.map(function(s,i){
    const cells = idx.map(function(j){ return fmt(retPct(s.close,j)); }).join("");
    const last = s.close[s.close.length-1];
    return '<tr><td class="name"><span class="dot" style="background:'+PALETTE[i%PALETTE.length]+'"></span>'
      + s.label + ' <span class="lbl">' + s.bbid + '</span></td>' + cells
      + '<td>' + last.toLocaleString(undefined,{maximumFractionDigits:2}) + ' <span class="lbl">' + s.ccy + '</span></td></tr>';
  }).join("");
}
(function(){ fillRange("rLines", 36); draw(); drawRet(); })();
</script>
</body>
</html>
"""

html = (HTML
        .replace("__DATA_JSON__", json.dumps(data))
        .replace("__GEN_TIME__", dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
out = os.path.join(SCRIPT_DIR, "domestic_dashboard.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"[저장] {out}  ({os.path.getsize(out)/1024:.0f} KB)")
