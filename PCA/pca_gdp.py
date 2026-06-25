# -*- coding: utf-8 -*-
"""
pca_gdp.py — 카테고리별 Time-Varying PCA → GDP 프록시 + LEI + HTML 대시보드

입력: haver/haver-api_PCA/Meta data_Raw data.xlsx
  - Wide     : 날짜 x 지표 (헤더 = CODE@DATABASE)
  - Metadata : ticker_pk / code / descriptor / datatype / frequency / category
  - 전처리   : ticker_pk / code / (level | diffusion)

버전 2개:
  - YoY      : level은 12개월 로그차분, diffusion은 그대로. 반감기 24개월
  - Momentum : 3m/3m — 3개월평균의 3개월 전 대비 (level=로그차분, diffusion=차분). 반감기 12개월

구조:
  카테고리별 TV-PCA(EWM 상관행렬 + eigh) → 카테고리 지수(EWM z-score)
  → lei 제외 카테고리 동일가중 평균 = GDP 프록시 / lei는 별도 LEI 지수

출력:
  - pca_result.xlsx   (버전별 지수·기여도·지표 z-score)
  - pca_dashboard.html (탭: 경기지수 / LEI)
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================
BASE       = Path(__file__).resolve().parent
DATA_FILE  = BASE.parent / "haver" / "haver-api_PCA" / "Meta data_Raw data.xlsx"
OUT_XLSX   = BASE / "pca_result.xlsx"
OUT_HTML   = BASE / "pca_dashboard.html"

COUNTRY    = "United States"
LEI_CAT    = "lei"          # 합산에서 제외하고 별도 산출할 카테고리
MIN_EWM_OBS = 12            # EWM 평균/표준편차 최소 관측치

VERSIONS = {
    "YoY":      {"halflife": 24, "mode": "yoy"},
    "Momentum": {"halflife": 12, "mode": "m3m3"},
}

CAT_LABEL = {"consumer": "Consumer", "capex": "Capex", "export": "Export",
             "housing": "Housing", "lei": "LEI"}


# ============================================================
# 1. 로드 + 검증
# ============================================================
def ticker_to_pk(h):
    h = str(h).strip()
    if "@" in h:
        code, db = h.split("@", 1)
        return f"{db.strip().lower()}:{code.strip().lower()}"
    return h.lower()


def load_data():
    wide = pd.read_excel(DATA_FILE, sheet_name="Wide")
    meta = pd.read_excel(DATA_FILE, sheet_name="Metadata")
    pre  = pd.read_excel(DATA_FILE, sheet_name="전처리")

    date_col = wide.columns[0]
    wide[date_col] = pd.to_datetime(wide[date_col])
    wide = wide.set_index(date_col).sort_index()
    wide.columns = [ticker_to_pk(c) for c in wide.columns]
    wide = wide.apply(pd.to_numeric, errors="coerce")
    # 시계열 '중간'의 1~2개월 구멍만 선형 보간 (발표 지연으로 비는 끝부분은 보존)
    wide = wide.interpolate(method="linear", limit=2, limit_area="inside")

    cat_map  = dict(zip(meta["ticker_pk"].astype(str), meta["category"].astype(str).str.strip().str.lower()))
    rule_map = dict(zip(pre["ticker_pk"].astype(str), pre.iloc[:, -1].astype(str).str.strip().str.lower()))
    desc_map = dict(zip(meta["ticker_pk"].astype(str), meta["descriptor"].astype(str)))

    # --- 검증 게이트: 규칙/카테고리 없는 지표는 경고 후 제외 ---
    drop = sorted({c for c in wide.columns if c not in rule_map}
                  | {c for c in wide.columns if c not in cat_map or cat_map.get(c) in ("", "nan")})
    if drop:
        print(f"[WARN] 규칙/category 누락으로 제외: {drop}")
        wide = wide.drop(columns=drop)
    # 값이 거의 없는 고아 컬럼도 제외 (전체의 20% 미만)
    sparse = [c for c in wide.columns if wide[c].notna().sum() < len(wide) * 0.2]
    if sparse:
        print(f"[WARN] 데이터 부족으로 제외(<20%): {sparse}")
        wide = wide.drop(columns=sparse)

    bad = {c: rule_map[c] for c in wide.columns if rule_map[c] not in ("level", "diffusion")}
    if bad:
        raise SystemExit(f"[중단] 알 수 없는 전처리 라벨: {bad}")

    return wide, cat_map, rule_map, desc_map


def short_label(pk, desc_map):
    """descriptor를 차트용 짧은 이름으로."""
    d = str(desc_map.get(pk, pk))
    d = d.split("(")[0].strip()
    return d if len(d) <= 42 else d[:40] + "…"


# ============================================================
# 2. 변환 (버전별) + EWM z-score
# ============================================================
def transform(wide, rule_map, mode):
    out = pd.DataFrame(index=wide.index)
    for col in wide.columns:
        x = wide[col]
        if mode == "yoy":
            if rule_map[col] == "level":
                out[col] = np.log(x).diff(12) * 100          # YoY %
            else:
                out[col] = x                                  # diffusion 그대로
        elif mode == "m3m3":
            ma3 = x.rolling(3).mean()
            if rule_map[col] == "level":
                out[col] = np.log(ma3).diff(3) * 100          # 3m/3m %
            else:
                out[col] = ma3.diff(3)                        # diffusion: 3mma 차분
    return out.dropna(how="all")


def ewm_zscore(df, halflife):
    """EWM 평균/표준편차 기반 z-score (각 시점까지의 정보만 사용 — 룩어헤드 없음)"""
    m = df.ewm(halflife=halflife, min_periods=MIN_EWM_OBS).mean()
    s = df.ewm(halflife=halflife, min_periods=MIN_EWM_OBS).std()
    return (df - m) / s


# ============================================================
# 3. Time-Varying PCA (EWM 상관행렬 + 고유분해)
# ============================================================
def tv_pca(z, halflife):
    """
    z: 카테고리 내 지표들의 z-score DataFrame (dropna된 상태)
    반환: pc1(Series), loadings(DataFrame), contrib(DataFrame)
    """
    cols = list(z.columns)
    n = len(cols)
    # 모든 시점의 EWM 상관행렬을 한 번에 계산
    corr_panel = z.ewm(halflife=halflife, min_periods=n).corr()

    pc1_vals, load_rows, idx_used = [], [], []
    for i, t in enumerate(z.index):
        if i < n:                       # 워밍업: 지표 수만큼 관측치 필요
            continue
        cm = corr_panel.loc[t].values
        if np.isnan(cm).any():
            continue
        w, v = np.linalg.eigh(cm)       # 고유분해 (w 오름차순)
        loading = v[:, -1]              # 최대 고유값의 고유벡터 = PC1 방향
        if loading.sum() < 0:           # 시점별 부호 일관성 (대부분 경기순응 가정)
            loading = -loading
        pc1_vals.append(z.loc[t].values @ loading)
        load_rows.append(loading)
        idx_used.append(t)

    pc1 = pd.Series(pc1_vals, index=idx_used, name="PC1")
    loadings = pd.DataFrame(load_rows, index=idx_used, columns=cols)

    # 전체 부호 확정: 카테고리 평균 z와 양의 상관이 되도록
    anchor = z.mean(axis=1).reindex(idx_used)
    if pc1.corr(anchor) < 0:
        pc1, loadings = -pc1, -loadings

    contrib = z.reindex(idx_used) * loadings
    return pc1, loadings, contrib


# ============================================================
# 4. 버전 하나 전체 실행
# ============================================================
def run_version(wide, cat_map, rule_map, halflife, mode):
    z_all = ewm_zscore(transform(wide, rule_map, mode), halflife)

    cats = sorted(set(cat_map.get(c) for c in z_all.columns))
    res = {"z": z_all, "cat_index": {}, "cat_loadings": {}, "cat_contrib": {}}

    for cat in cats:
        cols = [c for c in z_all.columns if cat_map[c] == cat]
        sub = z_all[cols].dropna()
        if len(cols) < 2 or len(sub) <= len(cols):
            print(f"  [WARN] {cat}: 지표 {len(cols)}개/표본 {len(sub)} — 스킵")
            continue
        pc1, loadings, contrib = tv_pca(sub, halflife)
        # 카테고리 지수도 EWM z-score로 스케일 통일
        pc1_z = ewm_zscore(pc1.to_frame(), halflife).iloc[:, 0]
        res["cat_index"][cat] = pc1_z
        res["cat_loadings"][cat] = loadings
        res["cat_contrib"][cat] = contrib

    # GDP 프록시 = lei 제외 카테고리 동일가중 평균
    gdp_cats = [c for c in res["cat_index"] if c != LEI_CAT]
    panel = pd.DataFrame({c: res["cat_index"][c] for c in gdp_cats}).dropna()
    res["gdp"] = panel.mean(axis=1)
    res["gdp_contrib"] = panel / len(gdp_cats)   # 합 = GDP 프록시
    res["lei"] = res["cat_index"].get(LEI_CAT, pd.Series(dtype=float))
    return res


# ============================================================
# 5. 엑셀 저장
# ============================================================
def save_excel(results, cat_map, desc_map):
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as wr:
        readme = pd.DataFrame({
            "항목": ["국가", "버전", "전처리", "z-score", "PCA", "합산", "LEI"],
            "내용": [
                COUNTRY,
                "YoY(반감기24) / Momentum 3m3m(반감기12)",
                "level→로그차분(YoY=12개월, Mom=3mma 3개월), diffusion→그대로(Mom은 3mma 차분)",
                f"EWM 평균·표준편차 (min_periods={MIN_EWM_OBS}, 룩어헤드 없음)",
                "카테고리별 EWM 상관행렬 고유분해, 시점별 PC1",
                "lei 제외 카테고리 지수(z) 동일가중 평균 = GDP 프록시",
                "별도 산출 (합산 미포함)",
            ],
        })
        readme.to_excel(wr, sheet_name="README", index=False)

        for ver, r in results.items():
            idx_df = pd.DataFrame({"GDP_proxy": r["gdp"], "LEI": r["lei"]})
            for cat, s in r["cat_index"].items():
                if cat != LEI_CAT:
                    idx_df[CAT_LABEL.get(cat, cat)] = s
            idx_df.to_excel(wr, sheet_name=f"{ver}_indices")
            r["gdp_contrib"].rename(columns=lambda c: CAT_LABEL.get(c, c)).to_excel(
                wr, sheet_name=f"{ver}_gdp_contrib")
            r["z"].rename(columns=lambda c: short_label(c, desc_map)).to_excel(
                wr, sheet_name=f"{ver}_indicator_z")
    print(f"엑셀 저장: {OUT_XLSX}")


# ============================================================
# 6. 대시보드 데이터(JSON) 빌드
# ============================================================
def fmt_series(s, index):
    s = s.reindex(index)
    return [None if pd.isna(v) else round(float(v), 3) for v in s]


def build_payload(results, cat_map, desc_map):
    payload = {"country": COUNTRY, "versions": {}}
    for ver, r in results.items():
        idx = r["z"].index
        dates = [d.strftime("%Y-%m") for d in idx]
        gdp_cats = [c for c in r["cat_index"] if c != LEI_CAT]

        cat_block = {}
        for cat in r["cat_index"]:
            cols = [c for c in r["z"].columns if cat_map[c] == cat]
            cat_block[CAT_LABEL.get(cat, cat)] = {
                "index": fmt_series(r["cat_index"][cat], idx),
                "indicators": {short_label(c, desc_map): fmt_series(r["z"][c], idx) for c in cols},
            }

        payload["versions"][ver] = {
            "dates": dates,
            "gdp": {
                "index": fmt_series(r["gdp"], idx),
                "contrib": {CAT_LABEL.get(c, c): fmt_series(r["gdp_contrib"][c], idx) for c in gdp_cats},
            },
            "lei": {"index": fmt_series(r["lei"], idx)},
            "categories": cat_block,
        }
    return payload


# ============================================================
# 7. HTML 대시보드
# ============================================================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__COUNTRY__ Activity Index Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
--bg:#f7f6f3;--card:#ffffff;--panel:#ffffff;--text:#1a1c1f;--muted:#9aa0a6;--muted2:#5a5f66;
--border:#e8e8e6;--header:#f4f3f1;--accent:#6e1f1f;--up:#1a7a4c;--down:#c0392b;
--font:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",Arial,sans-serif;
--serif:Georgia,serif;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font);background:var(--bg);color:var(--text);padding:24px 32px}
h1{font-family:var(--serif);font-size:22px;font-weight:600;color:var(--text);margin-bottom:4px}
.sub{font-size:13px;color:var(--muted2);margin-bottom:24px}
.header-row{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
.header-left{flex:1}
.country-select{background:#ffffff;border:1px solid var(--border);color:var(--text);font-family:var(--font);
font-size:14px;font-weight:500;padding:10px 16px;border-radius:8px;cursor:pointer;outline:none;min-width:180px}
.country-select:hover{border-color:var(--muted)}
.country-select:focus{border-color:var(--accent)}
.tabs{display:flex;gap:8px;margin-bottom:18px}
.tab{padding:9px 24px;border:1px solid var(--border);border-radius:8px;background:#ffffff;
cursor:pointer;font-size:14px;font-weight:600;color:var(--muted2)}
.tab:hover{border-color:var(--muted)}
.tab.active{background:var(--accent);color:#ffffff;border-color:var(--accent)}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 14px 12px;margin-bottom:16px}
.card h2{font-family:var(--serif);font-size:16px;font-weight:600;color:var(--text);margin-bottom:10px;letter-spacing:0.3px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted2);margin-bottom:8px}
.legend span{display:inline-flex;align-items:center;gap:5px}
.swatch{width:11px;height:11px;border-radius:2px;display:inline-block}
canvas{width:100%;display:block}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:12px 10px 8px}
.panel .t{font-size:12.5px;font-weight:600;margin-bottom:6px;color:var(--text)}
.controls{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
select,.vbtn{background:#ffffff;border:1px solid var(--border);color:var(--text);font-family:var(--font);
padding:7px 14px;border-radius:8px;font-size:13px;cursor:pointer;outline:none}
select:hover,.vbtn:hover{border-color:var(--muted)}
.vbtn.active{background:var(--accent);color:#ffffff;border-color:var(--accent);font-weight:600}
.hidden{display:none}
</style>
</head>
<body>
<div class="header-row">
  <div class="header-left">
    <h1>__COUNTRY__ — Activity Index</h1>
    <p class="sub">Category PCA · Equal-Weight GDP Proxy · YoY half-life 24m / Momentum 3m3m half-life 12m · EWM z-score · generated __NOW__</p>
  </div>
  <select class="country-select" id="country-filter">
    <option value="US">__COUNTRY__</option>
  </select>
</div>

<div class="tabs">
  <div class="tab active" data-tab="gdp">경기지수</div>
  <div class="tab" data-tab="lei">LEI</div>
</div>

<div id="tab-gdp">
  <div class="controls" style="margin-bottom:10px"><span style="color:var(--muted2);font-size:13px">기간</span>
    <select id="range-select"></select></div>
  <div class="card"><h2>GDP Proxy — YoY (Contributions)</h2>
    <div class="legend" id="lg-yoy"></div><canvas id="gdp-yoy" height="290"></canvas></div>
  <div class="card"><h2>GDP Proxy — Momentum 3m/3m (Contributions)</h2>
    <div class="legend" id="lg-mom"></div><canvas id="gdp-mom" height="290"></canvas></div>
  <div class="card"><h2>카테고리별 지수 (YoY vs Momentum)</h2><div class="grid2" id="cat-grid"></div></div>
  <div class="card"><h2>카테고리 드릴다운 — 개별 지표 z-score</h2>
    <div class="controls">
      <select id="cat-select"></select>
      <button class="vbtn active" data-ver="YoY">YoY</button>
      <button class="vbtn" data-ver="Momentum">Momentum</button>
    </div>
    <div class="grid3" id="drill-grid"></div></div>
</div>

<div id="tab-lei" class="hidden">
  <div class="controls" style="margin-bottom:10px"><span style="color:var(--muted2);font-size:13px">기간</span>
    <select id="lei-range-select"></select></div>
  <div class="card"><h2>LEI — YoY</h2><canvas id="lei-yoy" height="240"></canvas></div>
  <div class="card"><h2>LEI — Momentum 3m/3m</h2><canvas id="lei-mom" height="240"></canvas></div>
  <div class="card"><h2>LEI 구성 지표 z-score</h2>
    <div class="controls">
      <button class="vbtn lei-vbtn active" data-ver="YoY">YoY</button>
      <button class="vbtn lei-vbtn" data-ver="Momentum">Momentum</button>
    </div>
    <div class="grid3" id="lei-grid"></div></div>
</div>

<script>
const DATA = __DATA__;
const COLORS = ['#4e79a7','#f28e2b','#e15759','#76b7b2','#59a14f','#edc948','#b07aa1',
'#ff9da7','#9c755f','#bab0ac','#86bcb6','#d37295','#fabfd2','#8cd17d','#499894','#e6a23c'];

function dpr(cv){const r=window.devicePixelRatio||1;const w=cv.clientWidth;
cv.width=w*r;cv.height=parseInt(cv.getAttribute('height'))*r;
const x=cv.getContext('2d');x.scale(r,r);return [x,w,parseInt(cv.getAttribute('height'))];}

function yearTicks(dates){const t=[];
if(dates.length<=14){dates.forEach((d,i)=>{if(i%Math.ceil(dates.length/8)==0)t.push([i,d]);});return t;}
let py='';dates.forEach((d,i)=>{const y=d.slice(0,4);if(y!==py){t.push([i,y]);py=y;}});return t;}

function range(arrs){let lo=0,hi=0;
arrs.forEach(a=>a.forEach(v=>{if(v!=null){if(v<lo)lo=v;if(v>hi)hi=v;}}));
const pad=(hi-lo)*0.08||1;return [lo-pad,hi+pad];}

// 스택바(기여도) + 검정 라인(지수)
function contribChart(cvId, dates, contrib, line, legendId){
const cv=document.getElementById(cvId);const [x,W,H]=dpr(cv);
const lP=44,rP=10,tP=10,bP=26;
const keys=Object.keys(contrib);
const sums=dates.map((_,i)=>{let p=0,n=0;keys.forEach(k=>{const v=contrib[k][i];
if(v!=null){v>0?p+=v:n+=v;}});return [p,n];});
let [yMin,yMax]=range([line,sums.map(s=>s[0]),sums.map(s=>s[1])]);
const xP=i=>lP+(W-lP-rP)*i/(dates.length-1);
const yP=v=>tP+(H-tP-bP)*(yMax-v)/(yMax-yMin);
x.strokeStyle='rgba(0,0,0,.07)';x.lineWidth=1;x.fillStyle='#5a5f66';x.font='10px Pretendard,Arial,sans-serif';
const st=(yMax-yMin)>6?2:1;
for(let v=Math.ceil(yMin/st)*st;v<=yMax;v+=st){x.beginPath();x.moveTo(lP,yP(v));x.lineTo(W-rP,yP(v));x.stroke();
x.textAlign='right';x.fillText(v.toFixed(0),lP-6,yP(v)+3);}
yearTicks(dates).forEach(([i,y])=>{x.textAlign='center';x.fillText(y,xP(i),H-8);});
const bw=Math.max(1.5,(W-lP-rP)/dates.length*0.72);
dates.forEach((_,i)=>{let pb=0,nb=0;
keys.forEach((k,ki)=>{const v=contrib[k][i];if(v==null)return;
x.fillStyle=COLORS[ki];x.globalAlpha=0.85;
if(v>0){x.fillRect(xP(i)-bw/2,yP(pb+v),bw,yP(pb)-yP(pb+v));pb+=v;}
else{x.fillRect(xP(i)-bw/2,yP(nb),bw,yP(nb+v)-yP(nb));nb+=v;}});});
x.globalAlpha=1;
x.strokeStyle='rgba(0,0,0,.25)';x.beginPath();x.moveTo(lP,yP(0));x.lineTo(W-rP,yP(0));x.stroke();
x.strokeStyle='#1a1c1f';x.lineWidth=2.2;x.beginPath();let started=false;
line.forEach((v,i)=>{if(v==null){return;}const px=xP(i),py=yP(v);
if(!started){x.moveTo(px,py);started=true;}else x.lineTo(px,py);});x.stroke();
if(legendId){const lg=document.getElementById(legendId);lg.innerHTML='';
keys.forEach((k,ki)=>{lg.innerHTML+=`<span><i class="swatch" style="background:${COLORS[ki]}"></i>${k}</span>`;});
lg.innerHTML+=`<span><i class="swatch" style="background:#1a1c1f"></i>Index</span>`;}}

// 라인차트 (복수 시리즈)
function lineChart(cv, dates, seriesArr, colors){
const [x,W,H]=dpr(cv);const lP=38,rP=8,tP=8,bP=22;
let [yMin,yMax]=range(seriesArr);
const xP=i=>lP+(W-lP-rP)*i/(dates.length-1);
const yP=v=>tP+(H-tP-bP)*(yMax-v)/(yMax-yMin);
x.strokeStyle='rgba(0,0,0,.07)';x.fillStyle='#5a5f66';x.font='9.5px Pretendard,Arial,sans-serif';
const st=(yMax-yMin)>6?2:1;
for(let v=Math.ceil(yMin/st)*st;v<=yMax;v+=st){x.beginPath();x.moveTo(lP,yP(v));x.lineTo(W-rP,yP(v));x.stroke();
x.textAlign='right';x.fillText(v.toFixed(0),lP-5,yP(v)+3);}
yearTicks(dates).forEach(([i,y],n)=>{if(n%2==0){x.textAlign='center';x.fillText(y,xP(i),H-7);}});
x.strokeStyle='rgba(0,0,0,.22)';x.beginPath();x.moveTo(lP,yP(0));x.lineTo(W-rP,yP(0));x.stroke();
seriesArr.forEach((s,si)=>{x.strokeStyle=colors[si];x.lineWidth=si==0?2:1.6;
x.beginPath();let st2=false;
s.forEach((v,i)=>{if(v==null)return;const px=xP(i),py=yP(v);
if(!st2){x.moveTo(px,py);st2=true;}else x.lineTo(px,py);});x.stroke();});}

// ---------- 렌더 ----------
const VY=DATA.versions['YoY'], VM=DATA.versions['Momentum'];
// ---- 기간 선택 (메인 차트 2개): 3,6,9,12,24,36개월 + 이후 1년 단위 + 전체 ----
const rangeSel=document.getElementById('range-select');
const RANGE_OPTS=[[1,'1M'],[3,'3M'],[6,'6M'],[12,'12M'],[24,'2Y'],[36,'3Y'],[48,'4Y'],[60,'5Y'],[120,'10Y'],[240,'20Y']];
function buildRange(sel,total){const avail=RANGE_OPTS.filter(([m])=>m<=total);
const list=avail.length?avail:[[total,'전체']];
list.forEach(([m,lab])=>{const o=document.createElement('option');o.value=m;o.textContent=lab;sel.appendChild(o);});
const oa=document.createElement('option');oa.value='all';oa.textContent='전체';sel.appendChild(oa);
let def=list.some(([m])=>m===36)?'36':String(list[list.length-1][0]);sel.value=def;}
(function(){buildRange(rangeSel,Math.max(VY.dates.length,VM.dates.length));})();
function sliceLast(a,n){return n==='all'?a:a.slice(-n);}
function sliceObj(o,n){const r={};Object.keys(o).forEach(k=>r[k]=sliceLast(o[k],n));return r;}
function renderMain(){const n=rangeSel.value==='all'?'all':parseInt(rangeSel.value);
contribChart('gdp-yoy',sliceLast(VY.dates,n),sliceObj(VY.gdp.contrib,n),sliceLast(VY.gdp.index,n),'lg-yoy');
contribChart('gdp-mom',sliceLast(VM.dates,n),sliceObj(VM.gdp.contrib,n),sliceLast(VM.gdp.index,n),'lg-mom');}
rangeSel.onchange=renderMain;
renderMain();
// ---- LEI 기간 선택 ----
const leiRangeSel=document.getElementById('lei-range-select');
(function(){buildRange(leiRangeSel,Math.max(VY.dates.length,VM.dates.length));})();
function renderLeiMain(){const n=leiRangeSel.value==='all'?'all':parseInt(leiRangeSel.value);
lineChart(document.getElementById('lei-yoy'),sliceLast(VY.dates,n),[sliceLast(VY.lei.index,n)],['#1a7a4c']);
lineChart(document.getElementById('lei-mom'),sliceLast(VM.dates,n),[sliceLast(VM.lei.index,n)],['#1a7a4c']);}
leiRangeSel.onchange=renderLeiMain;
renderLeiMain();

// 카테고리 패널 (YoY 검정 / Momentum 주황)
const catGrid=document.getElementById('cat-grid');
Object.keys(VY.categories).filter(c=>c!=='LEI').forEach(cat=>{
const p=document.createElement('div');p.className='panel';
p.innerHTML=`<div class="t">${cat} <span style="color:var(--muted2);font-weight:400">— YoY(검정) / Momentum(주황)</span></div><canvas height="170"></canvas>`;
catGrid.appendChild(p);
lineChart(p.querySelector('canvas'),VY.dates,
[VY.categories[cat].index, VM.categories[cat]?VM.categories[cat].index:[]],['#1a1c1f','#f28e2b']);});

// 드릴다운
const sel=document.getElementById('cat-select');
Object.keys(VY.categories).filter(c=>c!=='LEI').forEach(c=>{
const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o);});
let drillVer='YoY';
function renderDrill(){const V=DATA.versions[drillVer];const cat=sel.value;
const g=document.getElementById('drill-grid');g.innerHTML='';
const ind=V.categories[cat].indicators;
Object.keys(ind).forEach((name,i)=>{
const p=document.createElement('div');p.className='panel';
p.innerHTML=`<div class="t">${name}</div><canvas height="130"></canvas>`;
g.appendChild(p);
lineChart(p.querySelector('canvas'),V.dates,[ind[name]],[COLORS[i%COLORS.length]]);});}
sel.onchange=renderDrill;
document.querySelectorAll('.vbtn:not(.lei-vbtn)').forEach(b=>{b.onclick=()=>{
document.querySelectorAll('.vbtn:not(.lei-vbtn)').forEach(x=>x.classList.remove('active'));
b.classList.add('active');drillVer=b.dataset.ver;renderDrill();};});
renderDrill();

// LEI 지표 그리드
let leiVer='YoY';
function renderLei(){const V=DATA.versions[leiVer];
const g=document.getElementById('lei-grid');g.innerHTML='';
const ind=V.categories['LEI']?V.categories['LEI'].indicators:{};
Object.keys(ind).forEach((name,i)=>{
const p=document.createElement('div');p.className='panel';
p.innerHTML=`<div class="t">${name}</div><canvas height="120"></canvas>`;
g.appendChild(p);
lineChart(p.querySelector('canvas'),V.dates,[ind[name]],[COLORS[i%COLORS.length]]);});}
document.querySelectorAll('.lei-vbtn').forEach(b=>{b.onclick=()=>{
document.querySelectorAll('.lei-vbtn').forEach(x=>x.classList.remove('active'));
b.classList.add('active');leiVer=b.dataset.ver;renderLei();};});
renderLei();

// 탭
document.querySelectorAll('.tab').forEach(t=>{t.onclick=()=>{
document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
t.classList.add('active');
document.getElementById('tab-gdp').classList.toggle('hidden',t.dataset.tab!=='gdp');
document.getElementById('tab-lei').classList.toggle('hidden',t.dataset.tab!=='lei');
if(t.dataset.tab==='lei'){renderLeiMain();renderLei();}};});
</script>
</body>
</html>
"""


def save_dashboard(payload):
    html = (HTML_TEMPLATE
            .replace("__COUNTRY__", COUNTRY)
            .replace("__NOW__", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False)))
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"대시보드 저장: {OUT_HTML}")


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print(f"{COUNTRY} — Category PCA / GDP Proxy")
    print("=" * 60)
    wide, cat_map, rule_map, desc_map = load_data()
    print(f"데이터: {wide.shape[0]}행 x {wide.shape[1]}지표 "
          f"({wide.index[0]:%Y-%m} ~ {wide.index[-1]:%Y-%m})")

    results = {}
    for ver, cfg in VERSIONS.items():
        print(f"\n[{ver}] halflife={cfg['halflife']}, mode={cfg['mode']}")
        r = run_version(wide, cat_map, rule_map, cfg["halflife"], cfg["mode"])
        g = r["gdp"].dropna()
        print(f"  GDP proxy: {g.index[0]:%Y-%m} ~ {g.index[-1]:%Y-%m} "
              f"(mean {g.mean():.2f}, std {g.std():.2f})")
        if len(r["lei"].dropna()):
            l = r["lei"].dropna()
            print(f"  LEI      : {l.index[0]:%Y-%m} ~ {l.index[-1]:%Y-%m}")
        results[ver] = r

    save_excel(results, cat_map, desc_map)
    save_dashboard(build_payload(results, cat_map, desc_map))
    print("\n완료.")
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        DATA_FILE = Path(sys.argv[1])
    main()
