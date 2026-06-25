# -*- coding: utf-8 -*-
"""
build_pairbaskets.py — GS Pair Baskets (Equity Factors) 탭 생성기  [v2: 4박스 레이아웃]
---------------------------------------------------------------------------------
하는 일:
  1) .env 인증
  2) PAIR_BASKETS_LEVELS 에서 shortlist(팩터+테크) + sector_factor_grid 의 bbid 들을 당김
  3) (옵션) 전체 coverage 를 당겨 'universe' 로 적재  → TOP10/체크박스 그래프용
       · 환경변수 FULL_UNIVERSE=false 면 건너뜀 (기본 true)
       · 실패해도 groups+sector 로 자동 대체 (HTML이 알아서 fallback)
  4) 월별로 정리해 정적 HTML(pairbaskets_dashboard.html) 생성 — 4박스 레이아웃
       ① 섹터 × 팩터 히트맵 (VIP행 / HF Positioning열 제외)
       ② 섹터별 팩터 추이 (라인)
       ③ 수익률 TOP10 (전체 유니버스)
       ④ TOP10 기본선택 + 유니버스 체크박스 추이 비교
     · 박스마다 독립 기간 토글, 규격: 1M/3M/6M/12M/2Y/3Y/4Y/5Y/10Y/20Y

실행:  python build_pairbaskets.py
"""
import os
import csv
import json
import datetime as dt
import pandas as pd
from dotenv import load_dotenv
from gs_quant.session import GsSession, Environment
from gs_quant.data import Dataset

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
CID, CSEC = os.getenv("GS_CLIENT_ID"), os.getenv("GS_CLIENT_SECRET")
if not CID or not CSEC:
    raise SystemExit(".env 에 GS_CLIENT_ID / GS_CLIENT_SECRET 가 필요합니다.")
GsSession.use(Environment.PROD, CID, CSEC, ("read_product_data",))
print("[OK] 인증")

DATASET = "PAIR_BASKETS_LEVELS"
START = dt.date(2012, 1, 1)
END = dt.date.today()
FULL_UNIVERSE = os.getenv("FULL_UNIVERSE", "true").lower() != "false"


def read_csv(name):
    with open(os.path.join(SCRIPT_DIR, name), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def series_monthly(sub):
    s = sub.set_index("date")["closePrice"].sort_index()
    m = s.groupby(s.index.to_period("M")).last().dropna()
    return [str(p) for p in m.index], [round(float(x), 4) for x in m.values]


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


short = read_csv("pair_baskets_shortlist.csv")     # group,label,bbid,...
grid = read_csv("sector_factor_grid.csv")          # sector,factor,bbid,...
curated_bbids = sorted({r["bbid"] for r in short} | {r["bbid"] for r in grid})
print(f"[..] {DATASET} 조회 — 큐레이션 bbid {len(curated_bbids)}개")

df = Dataset(DATASET).get_data(START, END, bbid=curated_bbids)
if "date" not in df.columns:
    df = df.reset_index()
df["date"] = pd.to_datetime(df["date"])
print(f"     {len(df):,}행, bbid {df['bbid'].nunique()}개")

series = {}
for bbid, sub in df.groupby("bbid"):
    series[bbid] = series_monthly(sub)

# ── 데이터 구조화 (groups + sector) ──
data = {"groups": {"Factor": [], "Tech": []}, "sector": {}, "universe": []}
known_label = {}
for r in short:
    b = r["bbid"]
    known_label[b] = r["label"]
    if b in series:
        d, c = series[b]
        data["groups"].setdefault(r["group"], []).append(
            {"label": r["label"], "bbid": b, "dates": d, "close": c})

sectors, factors, items = [], [], []
for r in grid:
    if r["sector"] not in sectors:
        sectors.append(r["sector"])
    if r["factor"] not in factors:
        factors.append(r["factor"])
    b = r["bbid"]
    if b in series:
        d, c = series[b]
        items.append({"sector": r["sector"], "factor": r["factor"],
                      "bbid": b, "dates": d, "close": c})
data["sector"] = {"sectors": sectors, "factors": factors, "items": items}
print(f"[OK] 팩터 {len(data['groups'].get('Factor',[]))} · 테크 {len(data['groups'].get('Tech',[]))} · 섹터셀 {len(items)}")

# ── (옵션) 전체 universe — TOP10/체크박스 그래프용 ──
# 실패하면 universe 를 비워두고, HTML이 groups+sector 로 자동 대체한다.
if FULL_UNIVERSE:
    try:
        cov = Dataset(DATASET).get_coverage()
        cov_ids = sorted(set(cov["assetId"])) if "assetId" in cov.columns else []
        print(f"[..] 전체 coverage {len(cov_ids)}개 basket 풀링 (시간이 걸릴 수 있음)")
        frames = []
        for ch in _chunks(cov_ids, 50):
            try:
                frames.append(Dataset(DATASET).get_data(START, END, assetId=ch))
            except Exception as e:
                print(f"    [경고] chunk 실패 (건너뜀): {e}")
        udf = pd.concat(frames) if frames else pd.DataFrame()
        if len(udf):
            if "date" not in udf.columns:
                udf = udf.reset_index()
            udf["date"] = pd.to_datetime(udf["date"])
            uni = []
            for bbid, sub in udf.groupby("bbid"):
                d, c = series_monthly(sub)
                if len(c) >= 2:
                    uni.append({"label": known_label.get(bbid, bbid),
                                "bbid": bbid, "dates": d, "close": c})
            data["universe"] = uni
            print(f"[OK] universe {len(uni)}개 적재")
        else:
            print("[건너뜀] coverage 데이터 비어있음 — groups+sector로 대체")
    except Exception as e:
        print(f"[건너뜀] 전체 universe 풀 실패 ({e}) — groups+sector로 대체")
else:
    print("[i] FULL_UNIVERSE=false — universe 풀 생략 (groups+sector 사용)")

# universe 가 비면 키 제거 → HTML이 fallback (groups+sector) 사용
if not data["universe"]:
    data.pop("universe", None)

# ── HTML (4박스 레이아웃) ──
HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Equity Factors</title>
<style>
  :root{--ink:#1a1c1f;--muted:#9aa0a6;--line:#e8e8e6;--head:#f4f3f1;--badge:#6e1f1f;--up:#1a7a4c;--down:#c0392b;--card:#fff;--bg:#f7f6f3;}
  body { margin:0; background:var(--bg); color:var(--ink); font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",Arial,sans-serif; padding:14px 18px; }
  h2 { font-size:15px; margin:0; color:var(--ink); font-family:Georgia,serif; letter-spacing:-.2px; }
  .row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  select { background:var(--card); color:var(--ink); border:1px solid var(--line); border-radius:6px; padding:5px 9px; font-size:12px; }
  .lbl { font-size:12px; color:var(--muted); }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; margin-bottom:14px; }
  .chead { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px; flex-wrap:wrap; }
  .board { display:flex; flex-direction:column; gap:5px; }
  .brow { display:grid; grid-template-columns:230px 1fr 64px; align-items:center; gap:8px; font-size:12px; }
  .bar { position:relative; height:13px; }
  .bzero { position:absolute; left:50%; top:0; bottom:0; width:1px; background:var(--line); }
  .bfill { position:absolute; top:2px; height:9px; border-radius:2px; }
  table.heat { border-collapse:separate; border-spacing:2px; width:100%; font-size:11px; }
  table.heat th { color:var(--muted); font-weight:600; padding:2px 3px; text-align:center; white-space:nowrap; }
  table.heat td { padding:0; text-align:center; }
  table.heat td.name { text-align:left; color:var(--ink); padding:2px 8px 2px 2px; white-space:nowrap; }
  .cell { display:block; padding:5px 4px; border-radius:4px; color:#14181f; font-weight:bold; min-width:26px; }
  .checks { max-height:160px; overflow-y:auto; display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:2px 14px;
            border:1px solid var(--line); border-radius:8px; padding:8px 10px; margin-bottom:10px; background:var(--card); }
  .chk { font-size:12px; color:var(--ink); display:flex; align-items:center; gap:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .btn { background:var(--card); color:var(--ink); border:1px solid var(--line); border-radius:6px; padding:5px 10px; cursor:pointer; font-size:12px; }
  .btn:hover { background:var(--head); }
  .meta { font-size:11px; color:var(--muted); margin-top:8px; }
</style>
</head>
<body>

<div class="row" style="margin-bottom:14px;"><h2>Equity Factors · GS Pair Baskets</h2></div>

<div class="card">
  <div class="chead"><h2>① 섹터 × 팩터 · 수익률(%)</h2>
    <span><span class="lbl">기간</span> <select id="rHeat" onchange="drawHeat()"></select></span></div>
  <div style="overflow-x:auto;"><div id="heat"></div></div>
</div>

<div class="card">
  <div class="chead"><h2>② 섹터별 팩터 추이 · 100 리베이스</h2>
    <span><span class="lbl">섹터</span> <select id="secSel" onchange="drawLines()"></select>
      &nbsp;<span class="lbl">기간</span> <select id="rLines" onchange="drawLines()"></select></span></div>
  <div id="linesLeg" class="row" style="gap:12px;font-size:12px;margin-bottom:6px;"></div>
  <div style="position:relative;height:300px;"><canvas id="lines"></canvas></div>
</div>

<div class="card">
  <div class="chead"><h2>③ 수익률 TOP10 · 전체 유니버스</h2>
    <span><span class="lbl">기간</span> <select id="rTop" onchange="drawTop()"></select></span></div>
  <div class="board" id="top"></div>
</div>

<div class="card">
  <div class="chead"><h2>④ 수익률 BOTTOM10 · 전체 유니버스</h2>
    <span><span class="lbl">기간</span> <select id="rBot" onchange="drawBot()"></select></span></div>
  <div class="board" id="bot"></div>
</div>

<div class="card">
  <div class="chead"><h2>⑤ 추이 비교 · TOP10 기본 선택 + 유니버스 추가</h2>
    <span><button class="btn" onclick="resetTop()">현재 기간 TOP10로 리셋</button>
      &nbsp;<span class="lbl">기간</span> <select id="rUniv" onchange="drawUniv()"></select></span></div>
  <div class="checks" id="checks"></div>
  <div style="position:relative;height:340px;"><canvas id="univ"></canvas></div>
</div>

<p class="meta" id="meta"></p>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const D = __DATA_JSON__;
const GEN = "__GEN_TIME__";
const POS="#1a7a4c", NEG="#c0392b";
const PALETTE=["#378ADD","#1D9E75","#BA7517","#D4537E","#9b8cff","#46b0c9","#e0833b","#cf5fd0","#6fcf6f","#d24b4a","#5fa8ff","#9aa0a6"];
let charts={};
document.getElementById("meta").textContent = "데이터: GS Marquee PAIR_BASKETS_LEVELS (월별) · 생성 " + GEN;

const RANGES=[["1M",1],["3M",3],["6M",6],["12M",12],["2Y",24],["3Y",36],["4Y",48],["5Y",60],["10Y",120],["20Y",240]];

const UNIV=[]; const _seen=new Set();
function _addU(label,b,dates,close){ if(!b||_seen.has(b))return; _seen.add(b); UNIV.push({label:label,bbid:b,dates:dates,close:close}); }
if(D.universe&&D.universe.length){ D.universe.forEach(p=>_addU(p.label,p.bbid,p.dates,p.close)); }
else {
  Object.keys(D.groups||{}).forEach(g=>(D.groups[g]||[]).forEach(p=>_addU(p.label,p.bbid,p.dates,p.close)));
  (D.sector&&D.sector.items||[]).forEach(it=>{ if(/^VIP vs Short/.test(it.sector)||it.factor==="HF Positioning") return; _addU(it.sector+" · "+it.factor,it.bbid,it.dates,it.close); });
}

const ALLM=(function(){const s=new Set(); UNIV.forEach(p=>p.dates.forEach(d=>s.add(d))); return [...s].sort();})();

function hx(h){return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];}
function mix(a,b,t){const x=hx(a),y=hx(b);return `rgb(${Math.round(x[0]+(y[0]-x[0])*t)},${Math.round(x[1]+(y[1]-x[1])*t)},${Math.round(x[2]+(y[2]-x[2])*t)})`;}
function ramp(st,t){for(let i=1;i<st.length;i++){if(t<=st[i][0]){const a=st[i-1],b=st[i];return mix(a[1],b[1],(t-a[0])/(b[0]-a[0]));}}return st[st.length-1][1];}
function heatColor(pct,scale){ if(pct===null||pct===undefined||isNaN(pct)) return "#f4f3f1";
  let t=Math.max(-1,Math.min(1,pct/scale));
  return t>=0 ? ramp([[0,"#eef3ef"],[0.5,"#6abf95"],[1,"#1a7a4c"]],t) : ramp([[0,"#f7eeec"],[0.5,"#dd8d84"],[1,"#c0392b"]],-t); }
function chgN(close,m){ const n=close.length; if(n<2)return null; let bi=n-1-m; if(bi<0)bi=0; const a=close[bi],z=close[n-1]; return (a&&z!=null&&a!==0)? z/a-1 : null; }
function winMonths(m){ const k=Math.min(m+1, ALLM.length); return ALLM.slice(-k); }
function rebaseOn(p,months){ const dm={}; p.dates.forEach((d,i)=>dm[d]=p.close[i]); let base=null;
  return months.map(d=>{ const v=dm[d]; if(v==null) return null; if(base==null) base=v; return base? v/base*100 : null; }); }
function fillRange(id,defM){ const el=document.getElementById(id); RANGES.forEach(([lab,m])=>{const o=document.createElement("option");o.value=m;o.textContent=lab;if(m===defM)o.selected=true;el.appendChild(o);}); }

const REALSEC=(D.sector&&D.sector.sectors||[]).filter(s=>!/^VIP vs Short/.test(s));
const FACT=(D.sector&&D.sector.factors||[]).filter(f=>f!=="HF Positioning");
function drawHeat(){ const m=+document.getElementById("rHeat").value;
  let h='<table class="heat"><tr><th></th>'; FACT.forEach(f=>h+='<th>'+f+'</th>'); h+='</tr>';
  REALSEC.forEach(sec=>{ h+='<tr><td class="name">'+sec+'</td>';
    FACT.forEach(f=>{ const it=D.sector.items.find(x=>x.sector===sec&&x.factor===f);
      const pc=it?chgN(it.close,m):null;
      h+='<td><span class="cell" style="background:'+heatColor(pc,0.08)+'">'+(pc==null?'':(pc*100).toFixed(0))+'</span></td>'; });
    h+='</tr>'; });
  document.getElementById("heat").innerHTML=h+'</table>'; }

function drawLines(){ if(charts.lines)charts.lines.destroy();
  const m=+document.getElementById("rLines").value, sec=document.getElementById("secSel").value;
  const its=D.sector.items.filter(x=>x.sector===sec), months=winMonths(m);
  const ds=[]; let leg="";
  its.forEach((it,i)=>{ const col=PALETTE[i%PALETTE.length];
    ds.push({label:it.factor,data:rebaseOn(it,months),borderColor:col,borderWidth:1.5,pointRadius:0,spanGaps:false,tension:.2});
    leg+='<label class="chk" style="cursor:pointer"><input type="checkbox" checked data-i="'+i+'" onchange="toggleLine(this)"><span style="width:11px;height:11px;border-radius:2px;background:'+col+'"></span>'+it.factor+'</label>'; });
  document.getElementById("linesLeg").innerHTML=leg;
  charts.lines=new Chart(document.getElementById("lines"),{type:"line",data:{labels:months,datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},
      scales:{x:{ticks:{color:"#5a5f66",maxTicksLimit:10},grid:{display:false}},y:{ticks:{color:"#5a5f66"},grid:{color:"rgba(0,0,0,.07)"}}}}}); }
function toggleLine(el){ if(!charts.lines)return; const i=+el.getAttribute("data-i"); charts.lines.setDatasetVisibility(i, el.checked); charts.lines.update(); }

function topList(m){ return UNIV.map(p=>({label:p.label,bbid:p.bbid,v:chgN(p.close,m)})).filter(r=>r.v!=null).sort((a,b)=>b.v-a.v); }
function drawTop(){ const m=+document.getElementById("rTop").value;
  const rows=topList(m).slice(0,10); const mx=Math.max(...rows.map(r=>Math.abs(r.v)),0.0001);
  document.getElementById("top").innerHTML=rows.map(r=>{ const w=Math.abs(r.v)/mx*50, col=r.v>=0?POS:NEG, pct=(r.v*100).toFixed(1);
    return '<div class="brow"><span style="text-align:right;color:#cfd3da;overflow:hidden;text-overflow:ellipsis">'+r.label+'</span>'+
      '<span class="bar"><span class="bzero"></span><span class="bfill" style="background:'+col+';'+(r.v>=0?('left:50%;width:'+w+'%;'):('right:50%;width:'+w+'%;'))+'"></span></span>'+
      '<span style="text-align:right;color:'+col+'">'+(r.v>=0?'+':'')+pct+'%</span></div>'; }).join(""); }

function drawBot(){ const m=+document.getElementById("rBot").value;
  const rows=topList(m).slice().reverse().slice(0,10); const mx=Math.max(...rows.map(r=>Math.abs(r.v)),0.0001);
  document.getElementById("bot").innerHTML=rows.map(r=>{ const w=Math.abs(r.v)/mx*50, col=r.v>=0?POS:NEG, pct=(r.v*100).toFixed(1);
    return '<div class="brow"><span style="text-align:right;color:#cfd3da;overflow:hidden;text-overflow:ellipsis">'+r.label+'</span>'+
      '<span class="bar"><span class="bzero"></span><span class="bfill" style="background:'+col+';'+(r.v>=0?('left:50%;width:'+w+'%;'):('right:50%;width:'+w+'%;'))+'"></span></span>'+
      '<span style="text-align:right;color:'+col+'">'+(r.v>=0?'+':'')+pct+'%</span></div>'; }).join(""); }

let CHECKED=null;
function buildChecks(){ const m=+document.getElementById("rUniv").value;
  if(CHECKED===null){ CHECKED=new Set(topList(m).slice(0,10).map(r=>r.bbid)); }
  document.getElementById("checks").innerHTML=UNIV.map(p=>'<label class="chk"><input type="checkbox" data-b="'+p.bbid+'"'+(CHECKED.has(p.bbid)?' checked':'')+' onchange="toggleU(this)"> '+p.label+'</label>').join(""); }
function toggleU(el){ const b=el.getAttribute("data-b"); if(el.checked)CHECKED.add(b); else CHECKED.delete(b); drawUniv(); }
function resetTop(){ const m=+document.getElementById("rUniv").value; CHECKED=new Set(topList(m).slice(0,10).map(r=>r.bbid)); buildChecks(); drawUniv(); }
function drawUniv(){ if(charts.univ)charts.univ.destroy();
  const m=+document.getElementById("rUniv").value, months=winMonths(m);
  const sel=UNIV.filter(p=>CHECKED.has(p.bbid));
  const ds=sel.map((p,i)=>({label:p.label,data:rebaseOn(p,months),borderColor:PALETTE[i%PALETTE.length],borderWidth:1.3,pointRadius:0,spanGaps:false,tension:.2}));
  charts.univ=new Chart(document.getElementById("univ"),{type:"line",data:{labels:months,datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,animation:false,
      plugins:{legend:{display:true,labels:{color:"#1a1c1f",boxWidth:10,font:{size:10}}}},
      scales:{x:{ticks:{color:"#5a5f66",maxTicksLimit:10},grid:{display:false}},y:{ticks:{color:"#5a5f66"},grid:{color:"rgba(0,0,0,.07)"}}}}}); }

(function(){
  fillRange("rHeat",3); fillRange("rLines",36); fillRange("rTop",12); fillRange("rBot",12); fillRange("rUniv",36);
  const ss=document.getElementById("secSel"); REALSEC.forEach(s=>{const o=document.createElement("option");o.value=s;o.textContent=s;ss.appendChild(o);});
  drawHeat(); drawLines(); drawTop(); drawBot(); buildChecks(); drawUniv();
})();
</script>
</body>
</html>
"""

html = (HTML
        .replace("__DATA_JSON__", json.dumps(data))
        .replace("__GEN_TIME__", dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
out = os.path.join(SCRIPT_DIR, "pairbaskets_dashboard.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"[저장] {out}")
print("이어서 상위 폴더에서  python build_master.py  (또는 build_all.py) 실행하세요.")
