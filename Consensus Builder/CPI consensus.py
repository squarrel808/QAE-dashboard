"""
2026 CPI Consensus Dashboard Generator
==============================================
엑셀 파일을 읽어서 Ridge Plot + Median Line 대시보드 HTML을 생성합니다.

사용법:
    python generate_cpi_dashboard.py

설정:
    아래 CONFIG 섹션에서 엑셀 파일 경로와 시트명을 수정하세요.
    OUTPUT_PATH에 생성될 HTML 경로를 지정하세요.
"""

import glob
import json
import os
import re
from datetime import datetime

import numpy as np
import pandas as pd

# ============================================================
# CONFIG - 여기만 수정하면 됩니다
# ============================================================
_BASE_DIR = r'C:\Users\USER\OneDrive\문서\QAE-dashboard\Consensus Builder'
_HISTORY_DIR = os.path.join(_BASE_DIR, 'history')
_FILE_PREFIX = 'ECFC_Inflation Consesus'


def _find_latest_excel(prefix: str, history_dir: str, base_dir: str) -> str:
    """history 폴더의 {prefix}_YYYYMMDD.xlsx 중 가장 큰 날짜 파일을 반환. 없으면 base의 {prefix}_수정.xlsx."""
    pattern = os.path.join(history_dir, f'{prefix}_*.xlsx')
    candidates = []
    for fp in glob.glob(pattern):
        m = re.search(r'_(\d{8})\.xlsx$', fp)
        if m:
            candidates.append((m.group(1), fp))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return os.path.join(base_dir, f'{prefix}_수정.xlsx')


_LATEST_INFLATION = _find_latest_excel(_FILE_PREFIX, _HISTORY_DIR, _BASE_DIR)
print(f'[Excel file in use] {_LATEST_INFLATION}')

EXCEL_FILES = {
    '미국': _LATEST_INFLATION,
    '영국': _LATEST_INFLATION,
    '일본': _LATEST_INFLATION,
    '독일': _LATEST_INFLATION,
    '프랑스': _LATEST_INFLATION,
    '호주': _LATEST_INFLATION,
    '중국': _LATEST_INFLATION,
    '캐나다': _LATEST_INFLATION,
}

OUTPUT_PATH = r'C:\Users\USER\OneDrive\문서\QAE-dashboard\Consensus Builder\cpi_consensus_dashboard.html'

COUNTRY_NAMES = {
    '미국': 'US', '영국': 'UK', '일본': 'JP', '독일': 'DE',
    '프랑스': 'FR', '호주': 'AU', '중국': 'CN', '캐나다': 'CA'
}
# ============================================================


HEADER_ROW_OFFSET_DEFAULT = 13
BIWEEKLY_MIN_GAP_DAYS = 13
MAX_BIWEEKLY_POINTS = 12
RECENT_BUSINESS_DAYS = 10
READ_RETRY_COUNT = 3
READ_RETRY_DELAY_SEC = 2
DASHBOARD_TITLE = '2026 CPI consensus'
LOG_TITLE = '2026 CPI Consensus Dashboard Generator'


def detect_header_offset(df: pd.DataFrame) -> int:
    """
    데이터가 시작하는 행 번호를 자동 감지.
    조건: 티커 행(다수 셀이 'INDEX' 포함) → 그 다음 다음 행이 실제 날짜로 파싱되어야 함.
    오탐 방지를 위해 두 조건을 모두 만족하는 첫 행을 채택.
    """
    max_scan = min(30, len(df))

    def looks_like_data_row(row_idx: int) -> bool:
        """주어진 행의 첫 컬럼이 진짜 날짜로 파싱되는지 확인."""
        if row_idx >= len(df):
            return False
        cell = df.iloc[row_idx, 0]
        # pd 날짜 직접 파싱
        try:
            parsed = pd.to_datetime(cell, errors='coerce')
            if pd.notna(parsed) and 2000 <= parsed.year <= 2100:
                return True
        except Exception:
            pass
        # 엑셀 시리얼 넘버
        try:
            num = float(cell)
            if 20000 <= num <= 90000:
                return True
        except (TypeError, ValueError):
            pass
        return False

    for r in range(max_scan):
        row_vals = df.iloc[r].dropna().astype(str).tolist()
        if not row_vals:
            continue
        # 티커 비율: 'INDEX'가 들어간 셀이 전체 비-NaN 셀의 30% 이상
        index_count = sum(1 for v in row_vals if 'INDEX' in v.upper())
        if index_count < 3:  # 우연히 들어간 단어 1-2개는 무시
            continue
        ratio = index_count / len(row_vals)
        if ratio < 0.3:
            continue
        # 티커 행 발견 → r+2 행이 실제 날짜인지 검증
        if looks_like_data_row(r + 2):
            return r + 2

    # 못 찾으면 기본값
    return HEADER_ROW_OFFSET_DEFAULT


def parse_dates(df: pd.DataFrame, header_offset: int) -> pd.Series:
    """첫 번째 열의 날짜를 최대한 견고하게 파싱한다."""
    raw = df.iloc[header_offset:, 0].copy()

    if raw.empty:
        return pd.Series(dtype='datetime64[ns]')

    # 1) 일반 문자열/날짜형 파싱
    normal = pd.to_datetime(raw, errors='coerce')

    # 2) 엑셀 serial date 파싱
    numeric = pd.to_numeric(raw, errors='coerce')
    excel_serial = pd.Series(pd.NaT, index=raw.index, dtype='datetime64[ns]')
    excel_mask = numeric.between(20000, 90000, inclusive='both')
    if excel_mask.any():
        excel_serial.loc[excel_mask] = (
            pd.Timestamp('1899-12-30') + pd.to_timedelta(numeric.loc[excel_mask], unit='D')
        )

    # 3) 더 그럴듯한 결과 선택: 2000년 이후 유효 날짜가 더 많은 쪽
    normal_modern = normal[(normal.notna()) & (normal.dt.year >= 2000)]
    excel_modern = excel_serial[(excel_serial.notna()) & (excel_serial.dt.year >= 2000)]

    if len(excel_modern) > len(normal_modern):
        chosen = excel_serial
    else:
        chosen = normal
        chosen = chosen.where(chosen.notna(), excel_serial)

    return pd.to_datetime(chosen, errors='coerce')



def clean_numeric_values(row: pd.Series) -> np.ndarray:
    """%, comma, 공백 등이 섞인 값을 안전하게 float 배열로 변환."""
    s = row.copy()
    if not isinstance(s, pd.Series):
        s = pd.Series(s)

    s = s.astype(str).str.strip()
    s = s.replace({'': np.nan, 'nan': np.nan, 'None': np.nan, 'N/A': np.nan, '#N/A': np.nan})
    s = s.str.replace(',', '', regex=False)
    s = s.str.replace('%', '', regex=False)

    vals = pd.to_numeric(s, errors='coerce').dropna()
    if vals.empty:
        return np.array([], dtype=float)
    return vals.to_numpy(dtype=float)



def summarize_values(d: pd.Timestamp, values: np.ndarray) -> dict | None:
    if values.size == 0:
        return None
    return {
        'date': d.strftime('%Y-%m-%d'),
        'values': values.tolist(),
    }



def calc_bandwidth(values_list: list[np.ndarray]) -> float:
    """분포 특성에 맞춘 좀 더 안정적인 bandwidth 계산."""
    flattened = [np.asarray(v, dtype=float) for v in values_list if len(v) > 0]
    if not flattened:
        return 0.08

    values = np.concatenate(flattened)
    if values.size < 2:
        return 0.08

    std = float(np.std(values, ddof=1)) if values.size > 1 else 0.0
    iqr = float(np.percentile(values, 75) - np.percentile(values, 25))
    sigma = min(std, iqr / 1.34) if iqr > 0 and std > 0 else max(std, iqr / 1.34 if iqr > 0 else 0.0)
    if sigma <= 0:
        sigma = max((values.max() - values.min()) / 6 if values.max() > values.min() else 0.0, 0.05)

    bw_s = 0.9 * sigma * (values.size ** (-1 / 5))
    rng = float(values.max() - values.min())
    floor = max(rng * 0.08, 0.08)
    return round(float(max(bw_s, floor)), 4)



def select_biweekly_points(obs_dates: pd.Series) -> list[int]:
    """가장 가까운 날짜 매칭 대신 실제 관측일 기준으로 2주 간격 샘플을 고른다."""
    if obs_dates.empty:
        return []

    chosen = []
    last_kept_date = None

    for idx, d in reversed(list(obs_dates.items())):
        if d.weekday() >= 5:
            continue
        if last_kept_date is None or (last_kept_date - d).days >= BIWEEKLY_MIN_GAP_DAYS:
            chosen.append(idx)
            last_kept_date = d
        if len(chosen) >= MAX_BIWEEKLY_POINTS:
            break

    return sorted(chosen)


def select_biweekly_points_v2(rows):
    """rows = [(원본행번호, 날짜), ...] 받는 버전. 명시적 행번호 페어를 반환."""
    if not rows:
        return []

    chosen = []
    last_kept_date = None

    for idx, d in reversed(rows):
        if d.weekday() >= 5:
            continue
        if last_kept_date is None or (last_kept_date - d).days >= BIWEEKLY_MIN_GAP_DAYS:
            chosen.append((idx, d))
            last_kept_date = d
        if len(chosen) >= MAX_BIWEEKLY_POINTS:
            break

    return sorted(chosen, key=lambda x: x[1])



def extract_country(df: pd.DataFrame):
    if df.shape[0] == 0:
        return None

    header_offset = detect_header_offset(df)
    dates = parse_dates(df, header_offset)
    valid_mask = dates.notna()
    dates = dates[valid_mask]
    if len(dates) == 0:
        return None

    # 정렬 후 (원본 df 행번호, 날짜) 페어로 명시적 관리
    # → reset_index 같은 게 끼어들어도 안전
    rows = sorted(
        [(int(idx), d) for idx, d in dates.items()],
        key=lambda x: x[1]
    )
    last_date = rows[-1][1]

    # 2W: 영업일 기준 최근 N일 (RECENT_BUSINESS_DAYS)
    weekday_rows = [(idx, d) for idx, d in rows if d.weekday() < 5]
    rows_2w = weekday_rows[-RECENT_BUSINESS_DAYS:]

    cutoff_6m = last_date - pd.DateOffset(months=6)
    rows_6m = [(idx, d) for idx, d in rows if d >= cutoff_6m]

    items_2w = []
    vals_2w = []
    for idx, d in rows_2w:
        v = clean_numeric_values(df.iloc[idx, 1:])
        item = summarize_values(d, v)
        if item:
            items_2w.append(item)
            vals_2w.append(v)

    biweekly = []
    vals_6m = []
    for idx, d in select_biweekly_points_v2(rows_6m):
        v = clean_numeric_values(df.iloc[idx, 1:])
        item = summarize_values(d, v)
        if item:
            biweekly.append(item)
            vals_6m.append(v)

    median_line = []
    for idx, d in rows_6m:
        if d.weekday() >= 5:
            continue
        v = clean_numeric_values(df.iloc[idx, 1:])
        if v.size > 0:
            median_line.append({
                'd': d.strftime('%Y-%m-%d'),
                'med': round(float(np.median(v)), 3),
                'q1': round(float(np.percentile(v, 25)), 3),
                'q3': round(float(np.percentile(v, 75)), 3),
            })

    if not items_2w and not biweekly and not median_line:
        return None

    bw = calc_bandwidth(vals_2w + vals_6m)

    return {
        '2w': items_2w,
        '6m': biweekly,
        'ml': median_line,
        'bw': bw,
    }



def generate_html(all_data, updated_date):
    data_json = json.dumps(all_data, separators=(',', ':'))
    nm_json = json.dumps(COUNTRY_NAMES, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2026 CPI Consensus Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{
  --page-bg:#f7f6f3;--card-bg:#ffffff;--text-main:#1a1c1f;--text-muted:#5a5f66;
  --border:#e8e8e6;--header-bg:#f4f3f1;--accent:#6e1f1f;--pos:#1a7a4c;--neg:#c0392b;
  --font-base:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",Arial,sans-serif;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:var(--font-base);background:var(--page-bg);color:var(--text-main);padding:24px 32px}}
h1{{font-size:22px;font-weight:600;color:var(--text-main);margin-bottom:4px;font-family:Georgia,serif}}
.sub{{font-size:13px;color:var(--text-muted);margin-bottom:24px}}
.header-row{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px}}
.header-left{{flex:1}}
.country-select{{background:var(--card-bg);border:1px solid var(--border);color:var(--text-main);font-family:var(--font-base);font-size:14px;font-weight:500;padding:10px 16px;border-radius:8px;cursor:pointer;outline:none;min-width:180px}}
.country-select:hover{{border-color:var(--text-muted)}}
.country-select:focus{{border-color:var(--accent)}}
.country{{margin-bottom:28px}}
.country.hidden{{display:none}}
.ctitle{{font-size:16px;font-weight:600;color:var(--text-main);margin-bottom:8px;font-family:Georgia,serif}}
.row{{display:flex;gap:12px;flex-wrap:wrap}}
.panel{{flex:1;min-width:500px;background:var(--card-bg);border:1px solid var(--border);border-radius:10px;padding:16px 14px 10px}}
.plabel{{font-size:16px;font-weight:600;color:var(--text-main);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px}}
canvas{{width:100%;height:auto}}
</style>
</head>
<body>
<div class="header-row">
<div class="header-left">
<h1>2026 CPI consensus</h1>
<p class="sub">Distribution of broker forecasts · updated {updated_date}</p>
</div>
<select class="country-select" id="country-filter" onchange="filterCountry(this.value)">
<option value="ALL">All countries</option>
</select>
</div>
<div id="root"></div>
<script>
const D={data_json};
const NM={nm_json};
const CL=[[46,139,87],[60,160,100],[80,180,115],[110,195,130],[145,210,150],[185,220,160],[215,225,140],[240,210,100],[245,180,60],[240,145,40],[230,110,30],[220,90,20],[210,75,15],[200,60,10]];
const MO={{'01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'May','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Oct','11':'Nov','12':'Dec'}};

function kde(data,lo,hi,n,bw){{
  const r=[];
  const safeBw=Math.max(bw||0, 0.01);
  const s=(hi-lo)/(n-1||1);
  for(let i=0;i<n;i++){{
    const x=lo+i*s;
    let v=0;
    for(const d of data){{
      const z=(x-d)/safeBw;
      v+=Math.exp(-0.5*z*z);
    }}
    r.push({{x,y:v/(data.length*safeBw*Math.sqrt(2*Math.PI))}});
  }}
  return r;
}}

function fky(c,x){{
  let b=c[0];
  for(const p of c) if(Math.abs(p.x-x)<Math.abs(b.x-x)) b=p;
  return b.y;
}}

function gc(i,N){{
  const t=N>1?i/(N-1):0;
  const idx=t*(CL.length-1);
  const lo=Math.floor(idx),hi=Math.min(lo+1,CL.length-1),f=idx-lo;
  return [
    Math.round(CL[lo][0]+(CL[hi][0]-CL[lo][0])*f),
    Math.round(CL[lo][1]+(CL[hi][1]-CL[lo][1])*f),
    Math.round(CL[lo][2]+(CL[hi][2]-CL[lo][2])*f)
  ];
}}

function percentile(arr,p){{
  if(!arr.length) return null;
  const a=[...arr].sort((x,y)=>x-y);
  const pos=(a.length-1)*p;
  const lo=Math.floor(pos), hi=Math.ceil(pos);
  if(lo===hi) return a[lo];
  return a[lo] + (a[hi]-a[lo])*(pos-lo);
}}

function buildRidgeState(items,bw){{
  const N=items.length;
  if(!N) return null;

  const trimmedItems=items.map(it=>{{
    const sv=[...it.values].sort((a,b)=>a-b);
    const tv=sv.length>2?sv.slice(1,-1):sv;
    return {{date:it.date, values:it.values, trimmed:tv}};
  }});

  const allTrimmed=trimmedItems.flatMap(it=>it.trimmed).filter(v=>Number.isFinite(v));
  if(!allTrimmed.length) return null;
  const tMin=Math.min(...allTrimmed), tMax=Math.max(...allTrimmed);
  const spread=Math.max(tMax-tMin, 0.2);
  const pad=spread*0.25;
  const xL=tMin-pad;
  const xH=tMax+pad;

  let maxY=0;
  const curves=trimmedItems.map(it=>{{
    const c=kde(it.trimmed,xL,xH,250,bw);
    for(const p of c) if(p.y>maxY) maxY=p.y;
    return c;
  }});

  return {{items:trimmedItems,bw,xL,xH,maxY,curves}};
}}

function drawRidge(cv,state,lp,sharedMaxY){{
  if(!state || !state.items || !state.items.length) return;
  const items=state.items, cs=state.curves, xL=state.xL, xH=state.xH;
  const mY=Math.max(sharedMaxY || state.maxY || 0, 1e-6);
  const N=items.length;
  const range=xH-xL;

  const dpr=window.devicePixelRatio||1;
  const W=640,pH=120,rS=N<=8?36:N<=12?30:24;
  const tP=14,bP=30,rP=14;
  const H=tP+pH+(N-1)*rS+bP;
  cv.width=W*dpr;cv.height=H*dpr;
  cv.style.width='100%';cv.style.height='auto';cv.style.maxWidth=W+'px';
  const x=cv.getContext('2d');x.scale(dpr,dpr);
  const pL=lp,pR=W-rP;
  function xP(v){{return pL+((v-xL)/(xH-xL||1))*(pR-pL);}}

  x.strokeStyle='rgba(0,0,0,.07)';x.lineWidth=0.5;x.setLineDash([2,4]);
  const st=range>2?1:range>0.8?0.5:0.2;
  for(let v=Math.ceil(xL/st)*st;v<=xH+1e-9;v+=st){{
    const px=xP(v);x.beginPath();x.moveTo(px,tP-3);x.lineTo(px,H-bP+6);x.stroke();
  }}
  x.setLineDash([]);
  x.font='10px DM Sans,sans-serif';x.fillStyle='rgba(90,95,102,0.8)';x.textAlign='center';
  for(let v=Math.ceil(xL/st)*st;v<=xH+1e-9;v+=st) x.fillText(v.toFixed(st<1?1:0)+'%',xP(v),H-bP+18);

  for(let i=N-1;i>=0;i--){{
    const c=cs[i];const bl=tP+pH+i*rS;const[r,g,b]=gc(i,N);
    x.beginPath();x.moveTo(xP(c[0].x),bl);
    for(const pt of c) x.lineTo(xP(pt.x),bl-(pt.y/mY)*pH);
    x.lineTo(xP(c[c.length-1].x),bl);x.closePath();
    const gd=x.createLinearGradient(0,bl-pH,0,bl);
    gd.addColorStop(0,`rgba(${{r}},${{g}},${{b}},0.8)`);
    gd.addColorStop(0.5,`rgba(${{r}},${{g}},${{b}},0.6)`);
    gd.addColorStop(1,'rgba(255,255,255,0.4)');
    x.fillStyle=gd;x.fill();
  }}

  for(let i=N-1;i>=0;i--){{
    const c=cs[i];const bl=tP+pH+i*rS;const[r,g,b]=gc(i,N);
    x.beginPath();let s=false;
    for(const pt of c){{
      if(pt.y>0.01){{
        const px=xP(pt.x),py=bl-(pt.y/mY)*pH;
        if(!s){{x.moveTo(px,py);s=true;}} else x.lineTo(px,py);
      }}
    }}
    x.strokeStyle=`rgb(${{Math.min(r+40,255)}},${{Math.min(g+40,255)}},${{Math.min(b+30,255)}})`;
    x.lineWidth=1.8;x.stroke();
  }}

  for(let i=N-1;i>=0;i--){{
    const c=cs[i];const bl=tP+pH+i*rS;const[r,g,b]=gc(i,N);
    const tm=items[i].trimmed;
    const mn=Math.min(...tm), mx=Math.max(...tm);
    const av=tm.reduce((a,b)=>a+b,0)/tm.length;
    const dc=`rgb(${{Math.min(r+50,255)}},${{Math.min(g+50,255)}},${{Math.min(b+40,255)}})`;
    const lc=`rgba(${{Math.min(r+70,255)}},${{Math.min(g+70,255)}},${{Math.min(b+50,255)}},0.8)`;
    function dot(xV,sz,lb,side){{
      const ky=fky(c,xV);const px=xP(xV),py=bl-(ky/mY)*pH;
      x.beginPath();x.arc(px,py,sz,0,Math.PI*2);x.fillStyle=dc;x.fill();x.strokeStyle='rgba(0,0,0,0.35)';x.lineWidth=1.2;x.stroke();
      if(lb){{
        x.fillStyle=lc;x.font='600 11px DM Sans,sans-serif';x.textAlign=side==='center'?'center':side;
        const o=side==='left'?6:side==='right'?-6:0;x.fillText(lb,px+o,py-6);
      }}
    }}
    dot(av,3.5,av.toFixed(2)+'%','center');dot(mn,2,mn.toFixed(2)+'%','right');dot(mx,2,mx.toFixed(2)+'%','left');
    const d=items[i].date;const ds=MO[d.slice(5,7)]+' '+parseInt(d.slice(8));
    x.textAlign='right';x.fillStyle='rgba(26,28,31,0.85)';x.font='600 12px DM Sans,sans-serif';
    x.fillText(ds,lp-70,bl+4);
    x.fillText('avg '+av.toFixed(2)+'%',lp-6,bl+4);
  }}
}}

function drawMedian(cv,ml){{
  if(!ml||!ml.length) return;
  const dpr=window.devicePixelRatio||1;
  const W=640,H=300;
  cv.width=W*dpr;cv.height=H*dpr;
  cv.style.width='100%';cv.style.height='auto';cv.style.maxWidth=W+'px';
  const x=cv.getContext('2d');x.scale(dpr,dpr);
  const tP=20,bP=40,lP=45,rP=60;
  const pW=W-lP-rP,pH_=H-tP-bP;
  const allQ1=ml.map(d=>d.q1),allQ3=ml.map(d=>d.q3);
  const yMin=Math.min(...allQ1)-0.1,yMax=Math.max(...allQ3)+0.1;
  const N=ml.length;
  function xP(i){{return lP+(N===1?0:(i/(N-1))*pW);}}
  function yP(v){{return tP+pH_-(v-yMin)/(yMax-yMin||1)*pH_;}}
  x.strokeStyle='rgba(0,0,0,.07)';x.lineWidth=0.5;x.setLineDash([2,4]);
  const st=(yMax-yMin)>1?0.5:0.2;
  for(let v=Math.ceil(yMin/st)*st;v<=yMax+1e-9;v+=st){{const py=yP(v);x.beginPath();x.moveTo(lP,py);x.lineTo(W-rP,py);x.stroke();}}
  x.setLineDash([]);
  x.font='11px DM Sans,sans-serif';x.fillStyle='rgba(90,95,102,0.9)';x.textAlign='right';
  for(let v=Math.ceil(yMin/st)*st;v<=yMax+1e-9;v+=st) x.fillText(v.toFixed(1)+'%',lP-6,yP(v)+3);
  const months=[0];
  for(let i=1;i<N;i++) if(ml[i].d.slice(5,7)!==ml[i-1].d.slice(5,7)) months.push(i);
  const skip=months.length>5?2:1;
  x.textAlign='center';x.fillStyle='rgba(26,28,31,0.7)';x.font='600 11px DM Sans,sans-serif';
  months.forEach((idx,j)=>{{if(j%skip===0||j===months.length-1){{const yr=ml[idx].d.slice(2,4);const mo=parseInt(ml[idx].d.slice(5,7));x.fillText("'"+yr+'.'+mo,xP(idx),H-bP+20);}}
  }});
  x.beginPath();
  for(let i=0;i<N;i++){{const px=xP(i);if(i===0)x.moveTo(px,yP(ml[i].q3));else x.lineTo(px,yP(ml[i].q3));}}
  for(let i=N-1;i>=0;i--) x.lineTo(xP(i),yP(ml[i].q1));
  x.closePath();x.fillStyle='rgba(26,122,76,0.12)';x.fill();
  x.beginPath();
  for(let i=0;i<N;i++){{const px=xP(i);if(i===0)x.moveTo(px,yP(ml[i].q3));else x.lineTo(px,yP(ml[i].q3));}}
  x.strokeStyle='rgba(26,122,76,0.3)';x.lineWidth=0.8;x.stroke();
  x.beginPath();
  for(let i=0;i<N;i++){{const px=xP(i);if(i===0)x.moveTo(px,yP(ml[i].q1));else x.lineTo(px,yP(ml[i].q1));}}
  x.strokeStyle='rgba(26,122,76,0.3)';x.lineWidth=0.8;x.stroke();
  x.beginPath();
  for(let i=0;i<N;i++){{const px=xP(i);if(i===0)x.moveTo(px,yP(ml[i].med));else x.lineTo(px,yP(ml[i].med));}}
  x.strokeStyle='#1a7a4c';x.lineWidth=2;x.stroke();
  const last=ml[N-1];
  x.beginPath();x.arc(xP(N-1),yP(last.med),4,0,Math.PI*2);x.fillStyle='#1a7a4c';x.fill();
  x.strokeStyle='rgba(255,255,255,0.6)';x.lineWidth=1.5;x.stroke();
  x.fillStyle='#1a7a4c';x.font='bold 10px DM Sans,sans-serif';x.textAlign='left';
  x.fillText(last.med.toFixed(2)+'%',xP(N-1)+8,yP(last.med)+3);
  x.fillStyle='rgba(90,95,102,0.9)';x.font='9px DM Sans,sans-serif';
  x.textAlign='left';x.fillText('Q1-Q3 band',lP+4,tP+10);
  x.fillStyle='#1a7a4c';x.fillText('Median',lP+70,tP+10);
}}

const root=document.getElementById('root');
const filterSel=document.getElementById('country-filter');
Object.keys(D).forEach(c=>{{
  const d=D[c];const nm=NM[c]||c;
  const opt=document.createElement('option');opt.value=c;opt.textContent=nm+' ('+c+')';
  filterSel.appendChild(opt);
  const div=document.createElement('div');div.className='country';div.dataset.country=c;
  const lastN=d['2w']&&d['2w'].length?d['2w'][d['2w'].length-1].values.length:0;
  div.innerHTML=`<div class="ctitle">${{nm}} (${{c}})</div><div class="row"><div class="panel"><div class="plabel">2W chg (daily, weekdays)</div><div style="font-size:13px;color:var(--text-muted);margin-bottom:8px">#${{lastN}}</div><canvas id="a_${{nm}}"></canvas></div><div class="panel"><div class="plabel">6M chg (bi-weekly)</div><canvas id="b_${{nm}}"></canvas></div><div class="panel"><div class="plabel">6M median + IQR (daily)</div><canvas id="m_${{nm}}"></canvas></div></div>`;
  root.appendChild(div);
  setTimeout(()=>{{
    const state2w=buildRidgeState(d['2w']||[], d.bw);
    const state6m=buildRidgeState(d['6m']||[], d.bw);
    const sharedMaxY=Math.max(state2w?.maxY||0, state6m?.maxY||0, 1e-6);
    drawRidge(document.getElementById('a_'+nm), state2w, 185, sharedMaxY);
    drawRidge(document.getElementById('b_'+nm), state6m, 185, sharedMaxY);
    drawMedian(document.getElementById('m_'+nm), d.ml);
  }},10);
}});

function filterCountry(val){{
  document.querySelectorAll('.country').forEach(div=>{{
    if(val==='ALL'||div.dataset.country===val){{
      div.classList.remove('hidden');
    }}else{{
      div.classList.add('hidden');
    }}
  }});
}}
</script>
</body>
</html>'''



def open_excel_with_retry(filepath):
    """Windows 파일 락(엑셀 사용중 등) 대비 retry 로직."""
    last_err = None
    for attempt in range(READ_RETRY_COUNT):
        try:
            return pd.ExcelFile(filepath)
        except (PermissionError, OSError) as e:
            last_err = e
            if attempt < READ_RETRY_COUNT - 1:
                import time
                time.sleep(READ_RETRY_DELAY_SEC)
    raise last_err


def main():
    print("=" * 50)
    print(LOG_TITLE)
    print("=" * 50)

    # 1) 파일별로 한 번만 열어서 캐싱 (1000+컬럼이라 read_excel 비용이 큼)
    file_cache = {}
    unique_files = set(EXCEL_FILES.values())
    for filepath in unique_files:
        if not os.path.exists(filepath):
            print(f"[SKIP] 파일 없음: {filepath}")
            continue
        try:
            file_cache[filepath] = open_excel_with_retry(filepath)
        except Exception as e:
            print(f"[ERR]  파일 열기 실패: {filepath} -> {e}")

    if not file_cache:
        print("\n읽을 수 있는 엑셀 파일이 없습니다.")
        return

    # 2) 시트별로 데이터 추출
    all_data = {}
    for sheet_name, filepath in EXCEL_FILES.items():
        if filepath not in file_cache:
            print(f"[SKIP] {sheet_name}: 파일 없음")
            continue

        xl = file_cache[filepath]

        # 시트 존재 검증
        if sheet_name not in xl.sheet_names:
            print(
                f"[ERR]  {sheet_name}: 시트가 파일에 없습니다. "
                f"사용 가능한 시트: {xl.sheet_names}"
            )
            continue

        try:
            df = xl.parse(sheet_name, header=None)
            result = extract_country(df)
            if not result:
                print(f"[WARN] {sheet_name}: 데이터 추출 실패 (빈 시트?)")
                continue

            all_data[sheet_name] = result
            latest_avg = None
            if result['2w']:
                latest_avg = float(np.mean(result['2w'][-1]['values']))
            elif result['6m']:
                latest_avg = float(np.mean(result['6m'][-1]['values']))

            latest_avg_txt = f", latest avg={latest_avg:.2f}%" if latest_avg is not None else ""
            print(
                f"[OK]   {sheet_name}: 2w={len(result['2w'])}d, 6m={len(result['6m'])}d, "
                f"median={len(result['ml'])}pts, bw={result['bw']}"
                f"{latest_avg_txt}"
            )
        except Exception as e:
            print(f"[ERR]  {sheet_name}: {type(e).__name__}: {e}")

    if not all_data:
        print("\n데이터가 없습니다. 엑셀 경로/시트명을 확인하세요.")
        return

    updated = datetime.now().strftime('%Y-%m-%d %H:%M')
    html = generate_html(all_data, updated)

    os.makedirs(os.path.dirname(OUTPUT_PATH) or '.', exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n생성 완료: {OUTPUT_PATH}")
    print("브라우저에서 열어보세요!")


if __name__ == '__main__':
    main()
