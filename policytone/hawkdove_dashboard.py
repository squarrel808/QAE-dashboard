# -*- coding: utf-8 -*-
"""
매파/완화(Hawk-Dove) RAW 스탠스 대시보드 생성기 — 막대그래프 버전
=========================================================================
score.py 산출물(stance_index.csv + speech_scores_full.json)을 읽어
Consensus Builder 양식(라이트 테마·국가 드롭다운)의 HTML 대시보드를 만든다.

  · 막대 : 연설일 1일 = 막대 1개. 높이 = 그날 연설들의 raw stance 평균(-2~+2)
           위(+) = 매파(빨강) / 아래(-) = 완화(초록) / 0 부근 = 중립(회색)
  · 추세선: 위원 참여도(coverage) 가중 최근 N일 평균 (얇은 선)
  · hover : 날짜 / 위원 / reasoning 한 문장 요약 (+개별 stance)

실행:  python hawkdove_dashboard.py   →  hawkdove_dashboard.html 생성
"""
import os, json, datetime as dt
import pandas as pd

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
INDEX_CSV   = os.path.join(BASE_DIR, "stance_index.csv")
SCORES_JSON = os.path.join(BASE_DIR, "speech_scores_full.json")
OUT_HTML    = os.path.join(BASE_DIR, "hawkdove_dashboard.html")

SMOOTH_WINDOW = 30   # coverage 가중평균 창(달력일)
NEUTRAL_BAND  = 0.15 # |stance| 가 이 이하면 '중립' 색

BANK_LABEL = {"FED": "미국 (Fed)", "BOJ": "일본 (BOJ)",
              "ECB": "유로존 (ECB)", "BOE": "영국 (BoE)"}

def _iso(v):
    s = str(v)
    if s.isdigit():
        return pd.to_datetime(int(s), unit="ms").date().isoformat()
    return pd.to_datetime(s).date().isoformat()

def main():
    idx = pd.read_csv(INDEX_CSV, encoding="utf-8-sig", parse_dates=["date"])
    with open(SCORES_JSON, encoding="utf-8") as f:
        scores = json.load(f)

    data = {}
    for bank, g in idx.groupby("bank"):
        g = g.sort_values("date").reset_index(drop=True)
        cov = g["coverage"].fillna(0)
        sp_stance = g["stance"].where(cov > 0)
        num = (sp_stance * cov).fillna(0).rolling(SMOOTH_WINDOW, min_periods=1).sum()
        den = cov.rolling(SMOOTH_WINDOW, min_periods=1).sum()
        g["wma"] = (num / den).ffill()

        sp = g[cov > 0]                       # 연설일만
        data[bank] = {
            "label": BANK_LABEL.get(bank, bank),
            "dates": [d.date().isoformat() for d in sp["date"]],
            "bar":   [round(float(v), 3) for v in sp["stance"]],
            "trend": [round(float(v), 3) for v in sp["wma"]],
            "events": {},
        }

    for r in scores:
        bank = r.get("bank")
        if bank not in data:
            continue
        d = _iso(r.get("date"))
        data[bank]["events"].setdefault(d, []).append({
            "sp": str(r.get("speaker") or "").strip() or "(unknown)",
            "rs": str(r.get("reasoning") or "").strip(),
            "st": round(float(r.get("stance") or 0), 2),
        })

    updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False)) \
                   .replace("__UPDATED__", updated) \
                   .replace("__WIN__", str(SMOOTH_WINDOW)) \
                   .replace("__NB__", str(NEUTRAL_BAND))
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"저장: {OUT_HTML}")
    for b, v in data.items():
        print(f"  {b}: 막대 {len(v['dates'])}개")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Central Bank Hawk-Dove Stance</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{
  --page-bg:#f7f6f3; --card-bg:#ffffff; --header-bg:#f4f3f1;
  --text:#1a1c1f; --muted:#9aa0a6; --muted-strong:#5a5f66;
  --border:#e8e8e6; --accent:#6e1f1f;
  --pos:#1a7a4c; --neg:#c0392b; --neut:#9aa0a6;
  --font:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",Arial,sans-serif;
  --serif:Georgia, serif;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font);background:var(--page-bg);color:var(--text);padding:24px 32px}
h1{font-family:var(--serif);font-size:22px;font-weight:600;color:var(--text);margin-bottom:4px}
.sub{font-size:13px;color:var(--muted-strong);margin-bottom:24px}
.header-row{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px}
.header-left{flex:1}
.country-select{background:var(--header-bg);border:1px solid var(--border);color:var(--text);font-family:var(--font);font-size:14px;font-weight:500;padding:10px 16px;border-radius:8px;cursor:pointer;outline:none;min-width:180px}
.country-select:hover{border-color:var(--muted)}
.country-select:focus{border-color:var(--accent)}
.panel{background:var(--card-bg);border:1px solid var(--border);border-radius:10px;padding:16px 14px 10px}
.plabel{font-family:var(--serif);font-size:16px;font-weight:600;color:var(--text);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px}
.legend{font-size:12px;color:var(--muted-strong);margin-top:8px}
.chart-wrap{position:relative;height:520px}
</style>
</head>
<body>
<div class="header-row">
<div class="header-left">
<h1>Central bank hawk-dove stance</h1>
<p class="sub">raw stance (-2 dovish ~ +2 hawkish) · 연설일 막대 · updated __UPDATED__</p>
</div>
<select class="country-select" id="country-filter" onchange="render(this.value)"></select>
</div>
<div class="panel">
<div class="plabel" id="ptitle">Hawk-Dove Stance</div>
<div class="chart-wrap"><canvas id="cv"></canvas></div>
<div class="legend">막대 = 연설일 raw stance (▲매파 빨강 / ▼완화 초록 / 중립 회색) · 선 = 위원 참여도 가중 __WIN__일 평균 — 막대에 마우스를 올리면 날짜 · 위원 · 핵심 요약</div>
</div>
<script>
const DATA = __DATA__;
const NB = __NB__;
const BANKC  = {FED:'#6e1f1f', BOJ:'#b8860b', ECB:'#3a5a8c', BOE:'#7a4a6e'};   // 전체 모드 막대색(은행 구분)
const HAWK='#c0392b', DOVE='#1a7a4c', NEUT='#9aa0a6';   // 매파=red, 완화=green, 중립=gray

const sel = document.getElementById('country-filter');
const banks = Object.keys(DATA);
sel.innerHTML = '<option value="ALL">전체 (All)</option>' +
  banks.map(b=>`<option value="${b}">${DATA[b].label}</option>`).join('');

function wrap(s, w){
  const out=[]; let line='';
  for(const word of String(s).split(' ')){
    if((line+' '+word).trim().length>w){ out.push(line.trim()); line=word; }
    else line+=' '+word;
  }
  if(line.trim()) out.push(line.trim());
  return out;
}
const signColor=v=> v>NB?HAWK:(v<-NB?DOVE:NEUT);

function buildDatasets(bank, mode){
  const D=DATA[bank];
  const bars={
    type:'bar', label:D.label, order:2, _bank:bank, _isBar:true,
    data:D.dates.map((d,i)=>({x:d,y:D.bar[i]})),
    backgroundColor: mode==='ALL'
        ? BANKC[bank]
        : D.bar.map(signColor),
    borderWidth:0, borderRadius:2,
    categoryPercentage:0.9, barPercentage:0.9
  };
  const trend={
    type:'line', label:D.label+' 추세', order:1, _bank:bank,
    data:D.dates.map((d,i)=>({x:d,y:D.trend[i]})),
    borderColor: mode==='ALL' ? BANKC[bank] : '#5a5f66',
    borderWidth:1.2, borderDash:[5,4],
    pointRadius:0, pointHitRadius:0, tension:0.3, fill:false
  };
  return [bars, trend];
}

let chart=null;
function render(mode){
  const show = mode==='ALL' ? banks : [mode];
  const ds = show.flatMap(b=>buildDatasets(b, mode));
  document.getElementById('ptitle').textContent =
    'Hawk-Dove Stance — ' + (mode==='ALL' ? '미국 · 일본' : DATA[mode].label);
  const cfg={
    data:{datasets:ds},
    options:{
      responsive:true, maintainAspectRatio:false, animation:false,
      interaction:{mode:'nearest', intersect:true},
      scales:{
        x:{type:'category', stacked:false,
           labels:[...new Set(show.flatMap(b=>DATA[b].dates))].sort(),
           ticks:{color:'#5a5f66', maxTicksLimit:14, maxRotation:0, font:{family:'DM Sans',size:11}},
           grid:{display:false}},
        y:{min:-2.2, max:2.2,
           ticks:{color:'#5a5f66', stepSize:1, font:{family:'DM Sans',size:11},
                  callback:v=>v>0?('+'+v+(v===2?' 매파':'')):(v<0?(v+(v===-2?' 완화':'')):'0 중립')},
           grid:{color:ctx=>ctx.tick.value===0?'rgba(0,0,0,.25)':'rgba(0,0,0,.07)',
                 lineWidth:ctx=>ctx.tick.value===0?1.2:1}}
      },
      plugins:{
        legend:{display:mode==='ALL', labels:{color:'#1a1c1f', usePointStyle:true,
                filter:i=>!i.text.includes('추세')}},
        tooltip:{
          filter:item=>item.dataset._isBar,
          backgroundColor:'#ffffff', borderColor:'#e8e8e6', borderWidth:1,
          titleColor:'#6e1f1f', bodyColor:'#1a1c1f', titleFont:{weight:'600'},
          padding:10, displayColors:false,
          callbacks:{
            title:items=>items.length?('📅 '+items[0].raw.x):'',
            label:item=>{
              const evs=DATA[item.dataset._bank].events[item.raw.x]||[];
              const lines=[];
              evs.forEach((e,i)=>{
                if(i>0) lines.push('');
                lines.push('👤 '+e.sp+'  (stance '+(e.st>0?'+':'')+e.st+')');
                wrap(e.rs,54).forEach(l=>lines.push(l));
              });
              return lines;
            }
          }
        }
      }
    }
  };
  if(chart) chart.destroy();
  chart=new Chart(document.getElementById('cv'), cfg);
}
render(banks.includes('FED')?'FED':banks[0]);
sel.value = banks.includes('FED')?'FED':banks[0];
</script>
</body>
</html>"""

if __name__ == "__main__":
    main()
