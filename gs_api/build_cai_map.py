# -*- coding: utf-8 -*-
"""
build_cai_map.py — GS CAI + MAP 대시보드 탭 생성기
---------------------------------------------------
하는 일:
  1) .env 의 자격증명으로 인증
  2) CAI(월별) + MAP(일별) 데이터를 G10 + 아시아 주요국에 대해 당김
  3) 데이터를 박은 정적 HTML(cai_map_dashboard.html) 한 장 생성
       - 뷰1: 전체 CAI 히트맵 (국가 × 기간 선택)
       - 뷰2: 국가별 — CAI 콤보(섹터 누적막대 + 헤드라인 라인, 제목에 진척도%)
              + 섹터 히트맵(CAI_HEATMAP_SECTOR_*) + Hard/Soft 기여도,
              그 아래 MAP 섹터 라인(섹터 토글) + 기간 드롭다운(PCA 방식)

실행:
  cd "C:\\Users\\USER\\OneDrive\\문서\\QAE-dashboard\\gs api"
  python build_cai_map.py
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

# ── 1) 대상 국가 (geographyId, 표시이름) ──────────────────────
COUNTRIES = [
    ("US", "United States"), ("EAagg", "Euro Area"), ("JP", "Japan"),
    ("GB", "United Kingdom"), ("CA", "Canada"), ("CH", "Switzerland"),
    ("SE", "Sweden"), ("NO", "Norway"), ("AU", "Australia"), ("NZ", "New Zealand"),
    ("CN", "China"), ("KR", "Korea"), ("TW", "Taiwan"), ("IN", "India"),
    ("ID", "Indonesia"), ("HK", "Hong Kong"), ("SG", "Singapore"),
]
GEO = [c[0] for c in COUNTRIES]

CAI_START = dt.date(2010, 1, 1)
MAP_START = dt.date(dt.date.today().year - 5, 1, 1)   # MAP은 일별이라 최근 5년만
END = dt.date.today()

# CAI metricName (대문자)
CAI_SECTORS = {
    "Consumer": "CAI_CONTRIBUTION_SECTOR_CONSUMER",
    "Housing": "CAI_CONTRIBUTION_SECTOR_HOUSING",
    "Labor": "CAI_CONTRIBUTION_SECTOR_LABOR",
    "Manufacturing": "CAI_CONTRIBUTION_SECTOR_MANUFACTURING",
    "Other": "CAI_CONTRIBUTION_SECTOR_OTHER",
}
CAI_TYPES = {
    "Hard": "CAI_CONTRIBUTION_TYPE_HARD",
    "Soft": "CAI_CONTRIBUTION_TYPE_SOFT",
}
CAI_HEADLINE = "CAI_HEADLINE"
CAI_COMPLETION = "CAI_PERCENT_COMPONENTS_RELEASED"
# CAI_HEATMAP_SECTOR_* — 섹터별 히트맵 지표(GS 라이브). contribution과 별개 metric.
CAI_HEATMAP = {
    "Consumer": "CAI_HEATMAP_SECTOR_CONSUMER",
    "Housing": "CAI_HEATMAP_SECTOR_HOUSING",
    "Labor": "CAI_HEATMAP_SECTOR_LABOR",
    "Manufacturing": "CAI_HEATMAP_SECTOR_MANUFACTURING",
    "Other": "CAI_HEATMAP_SECTOR_OTHER",
}
# 참고: CAI_INNOVATION_* / LEADING_CAI 는 GS가 2020-10-23 이후 발표를 중단(문서 명시). 최신값 없어 제외.

# MAP metricName (소문자)
MAP_SECTORS = {
    "Consumer": "map_sector_consumer",
    "Housing": "map_sector_housing",
    "Labor": "map_sector_labor",
    "Manufacturing": "map_sector_manufacturing",
    "Other": "map_sector_other",
}
MAP_HEADLINE = "map"


def fetch(ds_id, start, end):
    print(f"[..] {ds_id} 조회")
    df = Dataset(ds_id).get_data(startDate=start, endDate=end, geographyId=GEO)
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    print(f"     {len(df):,}행, {df['geographyId'].nunique()}개 지역")
    return df


def pivot_geo(df, geo):
    sub = df[df["geographyId"] == geo]
    if sub.empty:
        return None, []
    p = (sub.pivot_table(index="date", columns="metricName",
                         values="metricValue", aggfunc="last")
            .sort_index())
    return p, list(p.index)


def col(p, name):
    if p is None or name not in p.columns:
        return None
    return [None if pd.isna(v) else round(float(v), 4) for v in p[name]]


# ── 2) 데이터 당기기 ──────────────────────────────────────────
cai_df = fetch("CAI", CAI_START, END)
print("[info] CAI metricNames:", sorted(cai_df["metricName"].dropna().unique().tolist()))
# 월별 항목만 남김 — 일별 지표가 섞이면 월 단위 막대 정렬이 깨짐
MONTHLY_CAI = ({CAI_HEADLINE, CAI_COMPLETION}
               | set(CAI_SECTORS.values()) | set(CAI_TYPES.values())
               | set(CAI_HEATMAP.values()))
cai_df = cai_df[cai_df["metricName"].isin(MONTHLY_CAI)].copy()

map_df = fetch("MAP", MAP_START, END)
print("[info] MAP metricNames:", sorted(map_df["metricName"].dropna().unique().tolist()))

data = {"countries": [{"id": i, "label": l} for i, l in COUNTRIES],
        "cai": {}, "map": {}, "sectors": list(CAI_SECTORS.keys())}

for geo, label in COUNTRIES:
    p, dates = pivot_geo(cai_df, geo)
    if p is not None:
        data["cai"][geo] = {
            "dates": dates,
            "headline": col(p, CAI_HEADLINE),
            "sectors": {k: col(p, v) for k, v in CAI_SECTORS.items()},
            "heatmap": {k: col(p, v) for k, v in CAI_HEATMAP.items()},
            "types": {k: col(p, v) for k, v in CAI_TYPES.items()},
            "completion": col(p, CAI_COMPLETION),
        }
    pm, dm = pivot_geo(map_df, geo)
    if pm is not None:
        data["map"][geo] = {
            "dates": dm,
            "headline": col(pm, MAP_HEADLINE),
            "sectors": {k: col(pm, v) for k, v in MAP_SECTORS.items()},
        }

print(f"[OK] CAI {len(data['cai'])}개국 · MAP {len(data['map'])}개국")

# ── 3) HTML 생성 ─────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>CAI / MAP</title>
<style>
  :root{
    --bg:#f7f6f3; --panel:#ffffff; --text:#1a1c1f; --muted:#9aa0a6; --muted2:#5a5f66;
    --border:#e8e8e6; --header:#f4f3f1; --accent:#6e1f1f; --pos:#1a7a4c; --neg:#c0392b;
    --serif:Georgia, serif;
    --sans:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",Arial,sans-serif;
  }
  body { margin:0; background:var(--bg); color:var(--text); font-family:var(--sans); padding:14px 18px; }
  h1,h2,h3,.cap { font-family:var(--serif); color:var(--text); }
  .row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px; }
  .seg button { background:var(--panel); color:var(--text); border:1px solid var(--border); border-radius:8px;
                padding:7px 12px; cursor:pointer; font-size:13px; font-weight:bold; }
  .seg button.on { background:var(--accent); color:#fff; border-color:var(--accent); }
  select { background:var(--panel); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:6px 10px; font-size:13px; }
  select:hover { border-color:var(--muted); }
  .lbl { font-size:12px; color:var(--muted2); }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:10px 12px; margin-bottom:14px; }
  .cap { font-size:12px; color:var(--muted2); margin:0 0 6px 2px; }
  .legend { display:flex; flex-wrap:wrap; gap:12px; font-size:12px; color:var(--muted2); margin:4px 0 8px; }
  .legend span { display:flex; align-items:center; gap:5px; }
  .sw { width:11px; height:11px; border-radius:2px; display:inline-block; }
  .chk { display:flex; flex-wrap:wrap; gap:10px; font-size:12px; margin:2px 0 8px; }
  .chk label { display:flex; align-items:center; gap:4px; cursor:pointer; color:var(--text); }
  table.heat { border-collapse:separate; border-spacing:2px; width:100%; font-size:11px; }
  table.heat th { color:var(--muted2); font-weight:normal; padding:2px 3px; text-align:center; white-space:nowrap; }
  table.heat td { padding:0; text-align:center; }
  table.heat td.name { text-align:left; color:var(--text); padding:2px 10px 2px 2px; white-space:nowrap; }
  .cell { display:block; padding:6px 5px; border-radius:4px; color:#14181f; font-weight:bold; min-width:30px; }
  .hide { display:none; }
  .meta { font-size:11px; color:var(--muted); margin-top:8px; }
</style>
</head>
<body>

<div class="row">
  <div class="seg">
    <button id="bHeat" class="on" onclick="setView('heat')">전체 히트맵</button>
    <button id="bCty" onclick="setView('cty')">국가별</button>
  </div>
  <span id="ctyPick" class="row hide" style="margin:0;">
    <span class="lbl">국가</span>
    <select id="country" onchange="drawCountry()"></select>
    <span class="lbl" style="margin-left:6px;">기간</span>
    <select id="rangeSel" onchange="RANGE=parseInt(this.value); drawCountry();"></select>
  </span>
</div>

<!-- 뷰1: 히트맵 -->
<div id="viewHeat">
  <div class="row" style="margin-bottom:8px;">
    <span class="lbl">CAI 헤드라인 · 국가별 (초록=확장 / 빨강=둔화, z-score)</span>
    <span class="lbl" style="margin-left:6px;">기간</span>
    <select id="heatRange" onchange="HEATN=parseInt(this.value); buildHeat();"></select>
  </div>
  <div class="card" style="overflow-x:auto;"><div id="heat"></div></div>
  <div class="legend" style="align-items:center;">
    <span>둔화</span>
    <span style="display:inline-block; width:200px; height:12px; border-radius:3px;
                 background:linear-gradient(to right,#c0392b,#f4f3f1,#1a7a4c);"></span>
    <span>확장</span>
    <span style="color:#9aa0a6;">진하기 = 화면 내 상대 강도</span>
  </div>
</div>

<!-- 뷰2: 국가별 -->
<div id="viewCty" class="hide">
  <div class="card">
    <p class="cap" id="caiCap">CAI</p>
    <div id="caiLeg" class="legend"></div>
    <div style="position:relative;height:260px;"><canvas id="caiCombo"></canvas></div>
  </div>
  <div class="card">
    <p class="cap" id="typeCap">CAI — Hard / Soft 기여도</p>
    <div id="typeLeg" class="legend"></div>
    <div style="position:relative;height:200px;"><canvas id="caiType"></canvas></div>
  </div>
  <div class="card">
    <p class="cap" id="mapCap">MAP · 섹터별 서프라이즈 (선택 토글)</p>
    <div id="mapChk" class="chk"></div>
    <div style="position:relative;height:240px;"><canvas id="mapLines"></canvas></div>
  </div>
</div>

<p class="meta" id="meta"></p>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const D = __DATA_JSON__;
const GEN = "__GEN_TIME__";
const SCOL = {Consumer:"#378ADD", Housing:"#1D9E75", Labor:"#BA7517", Manufacturing:"#D4537E", Other:"#888780"};
const TCOL = {Hard:"#378ADD", Soft:"#BA7517"};
const HEAD = "#1a1c1f";
const GRID = {color:"rgba(0,0,0,.07)"};
document.getElementById("meta").textContent = "데이터: GS Marquee (CAI, MAP) · 생성 " + GEN;

// 표준 기간 토글: 1M,3M,6M,12M,2Y,3Y,4Y,5Y,10Y,20Y (월 단위)
const PERIODS = [
  {m:1,t:"1M"},{m:3,t:"3M"},{m:6,t:"6M"},{m:12,t:"12M"},
  {m:24,t:"2Y"},{m:36,t:"3Y"},{m:48,t:"4Y"},{m:60,t:"5Y"},
  {m:120,t:"10Y"},{m:240,t:"20Y"}
];
const DEFAULT_M = 36;    // 기본값 3Y
let RANGE = DEFAULT_M;    // 국가별 뷰 기간(개월)
let HEATN = DEFAULT_M;    // 히트맵 표시 개월 수

function maxHistoryMonths(){
  let n = 0;
  for (const g in D.cai){ const c=D.cai[g]; if(c&&c.dates) n=Math.max(n, c.dates.length); }
  for (const g in D.map){ const c=D.map[g]; if(c&&c.dates) n=Math.max(n, c.dates.length); }
  return n || 12;
}
function fillPeriods(selEl, def){
  const hist = maxHistoryMonths();
  let prev = 0, chosen = null;
  PERIODS.forEach(p=>{
    if (p.m <= hist){ const o=document.createElement("option"); o.value=p.m; o.textContent=p.t; selEl.appendChild(o); prev=p.m; }
  });
  // 사용 가능한 옵션 중 기본값(def)에 가장 가깝되 초과하지 않는 값으로 클램프
  PERIODS.forEach(p=>{ if (p.m<=hist && p.m<=def) chosen=p.m; });
  if (chosen===null) chosen = prev || def;
  selEl.value = chosen;
  return chosen;
}

const sel = document.getElementById("country");
D.countries.forEach(c => { if (D.cai[c.id] || D.map[c.id]) {
  const o = document.createElement("option"); o.value = c.id; o.textContent = c.label; sel.appendChild(o);
}});

// 기간 드롭다운 옵션 (표준: 1M,3M,6M,12M,2Y,3Y,4Y,5Y,10Y,20Y · 기본 3Y · 히스토리에 맞춰 클램프)
(function(){
  RANGE = fillPeriods(document.getElementById("rangeSel"), DEFAULT_M);
  HEATN = fillPeriods(document.getElementById("heatRange"), DEFAULT_M);
})();

// ── 히트맵 색 (화면 내 최대값 기준 상대 정규화 + sqrt 로 저강도 구분 강화) ──
const NEUTRAL=[244,243,241], C_GREEN=[26,122,76], C_RED=[192,57,43];
function mixc(a,b,t){ return [Math.round(a[0]+(b[0]-a[0])*t), Math.round(a[1]+(b[1]-a[1])*t), Math.round(a[2]+(b[2]-a[2])*t)]; }
function lum(c){ return (0.299*c[0]+0.587*c[1]+0.114*c[2])/255; }
function colorFor(v, maxAbs){
  if (v===null || v===undefined || !maxAbs) return {bg:"#f4f3f1", fg:"#9aa0a6"};
  const t = Math.sqrt(Math.min(1, Math.abs(v)/maxAbs));     // 크기 → 진하기 (sqrt 로 저강도 확대)
  const c = mixc(NEUTRAL, v>=0 ? C_GREEN : C_RED, t);       // 부호 → 색상
  return {bg:`rgb(${c[0]},${c[1]},${c[2]})`, fg: lum(c)>0.55 ? "#14181f" : "#fff"};
}
function allMonths(){
  const s=new Set(); for (const g in D.cai) D.cai[g].dates.forEach(d=>s.add(d));
  return [...s].sort();
}
function buildHeat(){
  let m = allMonths();
  if (HEATN!=="all") m = m.slice(-HEATN);
  // 보이는 셀들의 최대 절대값으로 정규화 — 그래야 다 비슷한 초록으로 안 뭉개짐
  let maxAbs = 0;
  D.countries.forEach(c => { const cai=D.cai[c.id]; if(!cai||!cai.headline) return;
    const dm={}; cai.dates.forEach((d,i)=>dm[d]=cai.headline[i]);
    m.forEach(d=>{ const v=dm[d]; if(v!=null) maxAbs=Math.max(maxAbs, Math.abs(v)); }); });
  if (!maxAbs) maxAbs = 1;
  let h = '<table class="heat"><tr><th></th>';
  m.forEach(d => h += '<th>'+d.slice(2,7)+'</th>');
  h += '</tr>';
  D.countries.forEach(c => {
    const cai = D.cai[c.id]; if (!cai || !cai.headline) return;
    const dm = {}; cai.dates.forEach((d,i)=> dm[d]=cai.headline[i]);
    h += '<tr><td class="name">'+c.label+'</td>';
    m.forEach(d => {
      const v = dm[d]; const col = colorFor(v, maxAbs);
      const txt = (v===null||v===undefined) ? '' : v.toFixed(1);
      h += '<td><span class="cell" style="background:'+col.bg+';color:'+col.fg+'">'+txt+'</span></td>';
    });
    h += '</tr>';
  });
  document.getElementById("heat").innerHTML = h + '</table>';
}

function setView(v){
  document.getElementById("bHeat").classList.toggle("on", v==="heat");
  document.getElementById("bCty").classList.toggle("on", v==="cty");
  document.getElementById("viewHeat").classList.toggle("hide", v!=="heat");
  document.getElementById("viewCty").classList.toggle("hide", v!=="cty");
  document.getElementById("ctyPick").classList.toggle("hide", v!=="cty");
  if (v==="cty") drawCountry();
}

let charts = {};
function destroy(){ Object.values(charts).forEach(c => c && c.destroy()); charts = {}; }
function isoCut(n){ if(n==="all") return "0000-00-00"; const d=new Date(); d.setMonth(d.getMonth()-n); return d.toISOString().slice(0,10); }
function keepIdx(dates,n){ const c=isoCut(n),k=[]; for(let i=0;i<dates.length;i++) if(dates[i]>=c) k.push(i); return k; }
function pick(a,idx){ return a? idx.map(i=>a[i]) : []; }
function lastVal(a){ if(!a) return null; for(let i=a.length-1;i>=0;i--) if(a[i]!=null) return a[i]; return null; }

function comboOpts(){
  return {responsive:true, maintainAspectRatio:false, animation:false,
    plugins:{legend:{display:false}},
    scales:{x:{stacked:true, ticks:{color:"#5a5f66", maxTicksLimit:12}, grid:{display:false}},
            y:{stacked:true, ticks:{color:"#5a5f66"}, grid:GRID}}};
}
function legendHTML(colors){
  let s = '<span style="display:flex;align-items:center;gap:5px;"><span class="sw" style="background:'+HEAD+';width:14px;height:2px;border-radius:0;"></span>CAI 헤드라인</span>';
  for (const k in colors) s += '<span><span class="sw" style="background:'+colors[k]+'"></span>'+k+'</span>';
  return s;
}

function drawCountry(){
  destroy();
  const geo = sel.value;
  const cai = D.cai[geo];
  const label = (D.countries.find(c=>c.id===geo)||{}).label || geo;

  if (cai){
    const ci = keepIdx(cai.dates, RANGE);
    const cdates = pick(cai.dates, ci);
    const comp = lastVal(cai.completion);
    document.getElementById("caiCap").textContent =
      label + " — CAI (섹터 기여도 누적 + 헤드라인)" + (comp!=null ? "   ·   지표 발표 진척도 " + Math.round(comp) + "%" : "");

    const ds = D.sectors.map(s => ({type:"bar", label:s, data:pick(cai.sectors[s], ci), backgroundColor:SCOL[s], stack:"cai", order:2}));
    ds.push({type:"line", label:"CAI", data:pick(cai.headline, ci), borderColor:HEAD, backgroundColor:HEAD, borderWidth:2, pointRadius:0, tension:.3, stack:"line", order:0});
    charts.cai = new Chart(document.getElementById("caiCombo"), {data:{labels:cdates, datasets:ds}, options:comboOpts()});
    document.getElementById("caiLeg").innerHTML = legendHTML(SCOL);

    const types = cai.types || {};
    document.getElementById("typeCap").textContent = label + " — CAI Hard / Soft 기여도";
    const tds = Object.keys(TCOL).map(t => ({type:"bar", label:t, data:pick(types[t], ci), backgroundColor:TCOL[t], stack:"cai", order:2}));
    tds.push({type:"line", label:"CAI", data:pick(cai.headline, ci), borderColor:HEAD, backgroundColor:HEAD, borderWidth:2, pointRadius:0, tension:.3, stack:"line", order:0});
    charts.type = new Chart(document.getElementById("caiType"), {data:{labels:cdates, datasets:tds}, options:comboOpts()});
    document.getElementById("typeLeg").innerHTML = legendHTML(TCOL);
  }

  const mp = D.map[geo];
  const chkBox = document.getElementById("mapChk");
  if (mp){
    document.getElementById("mapCap").textContent = label + " — MAP 섹터별 서프라이즈";
    if (!chkBox.dataset.built){
      let html = '<label><input type="checkbox" value="__head" checked onchange="drawMap()"> 헤드라인</label>';
      D.sectors.forEach(s => html += '<label><input type="checkbox" value="'+s+'" checked onchange="drawMap()"><span class="sw" style="background:'+SCOL[s]+'"></span>'+s+'</label>');
      chkBox.innerHTML = html; chkBox.dataset.built = "1";
    }
    drawMap();
  }
}

function drawMap(){
  if (charts.map) charts.map.destroy();
  const geo = sel.value, mp = D.map[geo];
  if (!mp) return;
  const mi = keepIdx(mp.dates, RANGE);
  const mdates = pick(mp.dates, mi);
  const on = {}; document.querySelectorAll('#mapChk input').forEach(i => on[i.value] = i.checked);
  const ds = [];
  if (on["__head"]) ds.push({label:"MAP", data:pick(mp.headline, mi), borderColor:HEAD, borderWidth:2, pointRadius:0, tension:.2});
  D.sectors.forEach(s => { if (on[s]) ds.push({label:s, data:pick(mp.sectors[s], mi), borderColor:SCOL[s], borderWidth:1.4, pointRadius:0, tension:.2}); });
  charts.map = new Chart(document.getElementById("mapLines"), {
    type:"line", data:{labels:mdates, datasets:ds},
    options:{responsive:true, maintainAspectRatio:false, animation:false,
      plugins:{legend:{display:false}},
      scales:{x:{ticks:{color:"#5a5f66", maxTicksLimit:10}, grid:{display:false}},
              y:{ticks:{color:"#5a5f66"}, grid:GRID}}}
  });
}

buildHeat();
</script>
</body>
</html>
"""

html = (HTML
        .replace("__DATA_JSON__", json.dumps(data))
        .replace("__GEN_TIME__", dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
out = os.path.join(SCRIPT_DIR, "cai_map_dashboard.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"[저장] {out}")
print("이어서 상위 폴더에서  python build_master.py  실행하세요. (또는 build_all.py)")
