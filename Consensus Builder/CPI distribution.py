"""
CPI YoY Distribution Dashboard Generator (Haver Edition)
=========================================================
haver-api 의 dashboard_data.xlsx 에서 직접 읽어 국가별 CPI 분포 대시보드 생성.

데이터 흐름:
  dashboard_data.xlsx (Wide=원자료, Metadata=설명) → YoY% 계산
  → descriptor 콜론 앞부분으로 국가 분류 → 4-panel 시각화

4패널 구성:
  1. Ridge Plot (YoY 분포, KDE)
  2. Median & Trimmed Mean (시계열)
  3. YoY Distribution (100% 적층 영역)
  4. 3M Moving Avg (전월대비 상승폭 확대 비중)

사용법:
  python "CPI distribution.py"
"""

from pathlib import Path
import json
import datetime
import pandas as pd

# ============================================================
# CONFIG - 여기만 수정하세요
# ============================================================
DASHBOARD_XLSX = Path(r'C:\Users\USER\OneDrive\문서\QAE-dashboard\haver\haver-api_CPI\dashboard_data_CPI Distribution.xlsx')
OUTPUT_PATH    = Path(r'C:\Users\USER\OneDrive\문서\QAE-dashboard\Consensus Builder\cpi_dashboard.html')

# descriptor 콜론 앞부분(소문자) → 화면 표시명
COUNTRY_MAP = {
    'united states':  'US',
    'u.s.':           'US',
    'us':             'US',
    'usa':            'US',
    'cpi-u':          'US',           # 미국 CPI 표준 표기
    'united kingdom': 'UK',
    'u.k.':           'UK',
    'uk':             'UK',
    'great britain':  'UK',
    'britain':        'UK',
    'euro area':      'Eurozone',
    'eurozone':       'Eurozone',
    'euro':           'Eurozone',
    'ea21':           'Eurozone',     # EUDATA 21개국 prefix
    'ea':             'Eurozone',
    'france':         'France',
    'germany':        'Germany',
    'canada':         'Canada',
    'australia':      'Australia',
    'au':             'Australia',    # Australia 약어
    'japan':          'Japan',
    'jp':             'Japan',
    'korea':          'Korea',
    'south korea':    'Korea',
    'china':          'China',
}

# Ridge Plot: 상하위 10% 절단
TRIM_RATIO = 0.10
# Trimmed Mean #1: 상하위 8%씩 (총 16% trim) — Cleveland Fed 16% 트림 비율
TRIMMED_MEAN_CUT = 0.08
# Trimmed Mean #2: Dallas Fed 방식 — 하위 24%, 상위 31% 제거 (가운데 45% 유지)
DALLAS_LO = 0.24
DALLAS_HI = 0.69
# 데이터 포함 기준: 전체 항목의 10% 이상
MIN_DATA_RATIO = 0.10
# KDE bandwidth: Silverman's rule with IQR correction
KDE_POINTS = 250

# HTML 드롭다운에서 슬라이스할 수 있도록 미리 보내는 최대 히스토리
RIDGE_MAX_HISTORY    = 240   # 4패널 (ridge/stats) 최대 240개월(20Y)
MOMENTUM_MAX_HISTORY = 240   # 5번째 패널 최대 240개월(20Y)

# ============================================================
# 헤더 / 국가 / 서브카테고리 파싱
# ============================================================
def normalize_to_pk(s):
    """원본 ticker → metadata ticker_pk 형식으로 정규화.
       'AUWPC861@ANZ'  → 'anz:auwpc861'
       'usecon:gdp'    → 'usecon:gdp'  (이미 형식 맞음)
    """
    s = str(s).strip().lower()
    if '@' in s:
        code, db = s.split('@', 1)
        return f"{db}:{code}"
    return s


def resolve_descriptor(header, pk_to_desc):
    """Wide 시트 컬럼 헤더 → descriptor 문자열.
    헤더 형식이 다음 중 무엇이든 처리:
      - 'United States: CPI: ...'                 (이미 descriptor)
      - 'United States: CPI: ... (usecon:gdp)'    (descriptor + ticker_pk 병기)
      - 'AUWPC861@ANZ'                             (원본 ticker, 변환 필요)
      - 'anz:auwpc861'                             (이미 ticker_pk 형식)
    """
    h = str(header).strip()

    # 1) '... (ticker_pk)' 꼬리가 있으면 그 안의 ticker_pk 추출
    if h.endswith(')') and ' (' in h:
        pk_part = h.rsplit(' (', 1)[1][:-1]
        norm = normalize_to_pk(pk_part)
        if norm in pk_to_desc:
            return pk_to_desc[norm]
        return h.rsplit(' (', 1)[0]

    # 2) 헤더 자체를 ticker_pk로 정규화해서 lookup
    norm = normalize_to_pk(h)
    if norm in pk_to_desc:
        return pk_to_desc[norm]

    # 3) 헤더가 이미 descriptor면 그대로 (콜론 있으면 descriptor일 가능성)
    return h


def parse_country(descriptor):
    """descriptor 콜론 앞부분으로 국가명 식별. 별칭 정규화 + fallback 첫 단어."""
    if not descriptor or not isinstance(descriptor, str):
        return None
    head = descriptor.split(':', 1)[0].strip().lower()
    if head in COUNTRY_MAP:
        return COUNTRY_MAP[head]
    first = head.split()[0] if head else ''
    return COUNTRY_MAP.get(first)


def parse_subcategory(descriptor):
    """descriptor에서 국가명 앞부분을 떼고 서브카테고리만 남김."""
    if ':' in descriptor:
        return descriptor.split(':', 1)[1].strip()
    return descriptor


# ============================================================
# YoY 계산 + 빈도 자동 감지 + 변화율 시리즈 필터
# ============================================================
def is_change_series(descriptor):
    """descriptor에 변화율 표시가 있는지."""
    return detect_change_type(descriptor) is not None


def detect_change_type(descriptor):
    """변화율 시리즈 종류 판별. 'yoy' / 'mom' / 'qoq' / None.
       - 'yoy'  : 이미 YoY 그 자체. 추가 계산 없이 그대로 사용.
       - 'mom'  : 월간 변화율. 12개월 누적환산으로 YoY 도출.
       - 'qoq'  : 분기 변화율. 누적환산.
       - None   : 레벨(INDEX) 시리즈. compute_yoy_smart로 계산.
    """
    if not descriptor or not isinstance(descriptor, str):
        return None
    d = descriptor.lower()
    if 'y/y' in d or 'yoy' in d or 'yr/yr' in d or 'year over year' in d:
        return 'yoy'
    if 'm/m' in d or 'mom' in d or 'month over month' in d:
        return 'mom'
    if 'q/q' in d or 'qoq' in d or 'quarter over quarter' in d:
        return 'qoq'
    # 그 외에 %Chg만 있고 단위 불명이면 보수적으로 'mom' 취급
    if '%chg' in d or '% chg' in d or '%change' in d or '% change' in d:
        return 'mom'
    return None


def compute_yoy_smart(series):
    """시계열 빈도를 자동 감지해 1년 전 대비 YoY% 계산.
       월간 → shift(12), 분기 → shift(4), 연간 → shift(1) 등.
    """
    s = series.dropna()
    if len(s) < 2:
        return pd.Series(index=series.index, dtype=float)

    avg_gap = (s.index[-1] - s.index[0]).days / (len(s) - 1)
    if avg_gap < 10:
        lag = 252         # 영업일 기준 1년 (드물게 daily CPI가 있다면)
    elif avg_gap < 45:
        lag = 12          # monthly
    elif avg_gap < 120:
        lag = 4           # quarterly
    elif avg_gap < 240:
        lag = 2           # semi-annual
    else:
        lag = 1           # annual

    return (series / series.shift(lag) - 1.0) * 100.0


def compute_yoy_monthly(df):
    """[deprecated] 월간 가정 일괄 계산. compute_yoy_smart로 대체됨."""
    return (df / df.shift(12) - 1.0) * 100.0


def derive_yoy_from_mom_pct(series_mom_pct):
    """월간 %Chg 시리즈 → 12개월 누적 YoY% 환산.
       YoY ≈ (1+m1/100)(1+m2/100)...(1+m12/100) - 1
       미국 USECON 티커처럼 raw가 이미 M/M %Chg일 때 사용.
    """
    one_plus = (series_mom_pct / 100.0) + 1.0
    cumprod  = one_plus.rolling(12).apply(lambda x: x.prod(), raw=True)
    return (cumprod - 1.0) * 100.0


# 국가 표시 순서 (앞부터 우선, 나머지는 원래 순서 유지)
COUNTRY_DISPLAY_ORDER = ['US', 'UK', 'Eurozone', 'France', 'Germany',
                         'Canada', 'Japan', 'Australia']


# ============================================================
# G10 Core CPI 모멘텀 (12M YoY / 3M/3M ann. / 6M/6M ann.)
# ============================================================
def compute_momentum_metrics(series, max_months=MOMENTUM_MAX_HISTORY):
    """월간 시리즈 → 세 가지 모멘텀 지표.
       12M YoY        : 단순 (current/12mo전 - 1)*100
       3M/3M ann.     : 3개월 평균 vs 직전 3개월 평균, 4승 환산 (분기→연환산)
       6M/6M ann.     : 6개월 평균 vs 직전 6개월 평균, 2승 환산
    """
    s = series.dropna().sort_index()
    if len(s) < 13:
        return None

    yoy_12m  = (s / s.shift(12) - 1.0) * 100.0
    avg3     = s.rolling(3).mean()
    mom_3m3m = ((avg3 / avg3.shift(3)) ** 4 - 1.0) * 100.0
    avg6     = s.rolling(6).mean()
    mom_6m6m = ((avg6 / avg6.shift(6)) ** 2 - 1.0) * 100.0

    # 최근 max_months 만 잘라서 보내기
    idx = s.index[-max_months:] if len(s) > max_months else s.index

    def pick(ser):
        out = []
        for d in idx:
            v = ser.get(d)
            out.append(round(float(v), 3) if pd.notna(v) else None)
        return out

    return {
        'dates':    [pd.Timestamp(d).strftime('%Y-%m') for d in idx],
        'yoy_12m':  pick(yoy_12m),
        'mom_3m3m': pick(mom_3m3m),
        'mom_6m6m': pick(mom_6m6m),
    }


# 국가 → G10 Core CPI ticker_pk 하드코딩 매핑
# (사용자가 직접 확인한 7개 — 점수제 추측 안 함)
G10_CORE_CPI_MAP = {
    'Eurozone': 'g10:h023pcx',   # EA 11-21: HICP: All Items Excluding Food and Energy (SA, 2025=100)
    'UK':       'g10:h112pcx',   # UK: CPI excluding Energy and Unprocessed Food (SA, 2015=100)
    'France':   'g10:h132pcx',   # France: HICP: All Items Excluding Food and Energy (SA, 2025=100)
    'Germany':  'g10:h134pcx',   # Germany: HICP: All Items Excluding Food and Energy (SA, 2025=100)
    'US':       'g10:s111pcx',   # U.S.: CPI-U: All Items Less Food and Energy (SA, 1982-84=100)
    'Canada':   'g10:s156pcx',   # Canada: CPI: All Items Less Food and Energy (SA, 2002=100)
    'Japan':    'g10:s158pcx',   # Japan: General CPI Excluding Food & Energy (SA, 2020=100)
}


def extract_g10_core_cpi(wide, pk_to_desc):
    """하드코딩된 매핑으로 국가별 Core CPI 시리즈 추출."""
    # Wide 컬럼명을 ticker_pk 형식으로 정규화해서 빠른 lookup
    pk_to_col = {}
    for col in wide.columns:
        pk_to_col[normalize_to_pk(col)] = col

    by_country = {}
    for country, target_pk in G10_CORE_CPI_MAP.items():
        col = pk_to_col.get(target_pk)
        if col is None:
            print(f"  [G10] {country:10s}: ticker_pk '{target_pk}' Wide에 없음 — skip")
            continue
        descriptor = pk_to_desc.get(target_pk, str(col))
        metrics = compute_momentum_metrics(wide[col])
        if metrics is None:
            print(f"  [G10] {country:10s}: 데이터 부족 — skip")
            continue
        by_country[country] = {
            'ticker': str(col),
            'descriptor': descriptor,
            **metrics,
        }
    return by_country


def build_country_data(country_yoy_df):
    """기존 extract_cpi_data와 동일한 형식의 dict 반환.
       입력: index=date, columns=서브카테고리명, value=YoY%
    """
    # 월별 dict로 정리
    month_data = {}
    for ts, row in country_yoy_df.iterrows():
        month_str = pd.Timestamp(ts).strftime('%b %Y')
        valid = {k: float(v) for k, v in row.items() if pd.notna(v)}
        if valid:
            month_data[month_str] = valid

    if not month_data:
        return None

    total_items = country_yoy_df.shape[1]

    # 월 정렬 (시간 순)
    month_order_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
    }

    def parse_month_key(s):
        parts = s.split()
        if len(parts) == 2:
            m = month_order_map.get(parts[0][:3], 0)
            try:
                y = int(parts[1])
            except ValueError:
                y = 0
            return y * 100 + m
        return 0

    sorted_months = sorted(month_data.keys(), key=parse_month_key)

    # 데이터 부족 월 필터링
    filtered = [m for m in sorted_months if len(month_data[m]) >= total_items * MIN_DATA_RATIO]
    # 충분한 히스토리 보내기 (HTML 드롭다운에서 슬라이스)
    filtered = filtered[-RIDGE_MAX_HISTORY:] if len(filtered) > RIDGE_MAX_HISTORY else filtered
    if not filtered:
        return None

    # Ridge
    ridge = [{'date': m, 'values': list(month_data[m].values())} for m in filtered]

    # Stats timeline
    stats_timeline = []
    prev_dict = None
    for m in filtered:
        curr = month_data[m]
        vals = sorted(curr.values())
        n = len(vals)

        # Median
        median = vals[n // 2] if n % 2 == 1 else (vals[n // 2 - 1] + vals[n // 2]) / 2

        # Trimmed Mean #1 (16% — 상하위 8%씩 대칭 절단, Cleveland Fed 방식)
        cut = max(1, int(n * TRIMMED_MEAN_CUT))
        trimmed = vals[cut:n - cut] if n > cut * 2 else vals
        trimmed_mean = sum(trimmed) / len(trimmed) if trimmed else median

        # Trimmed Mean #2 (Dallas Fed 비대칭: 하위 24% / 상위 31% 제외, 24~69th percentile 유지)
        d_lo = int(n * DALLAS_LO)
        d_hi = int(n * DALLAS_HI)
        if d_hi > d_lo:
            d_slice = vals[d_lo:d_hi]
            trimmed_mean_32 = sum(d_slice) / len(d_slice)
        else:
            trimmed_mean_32 = trimmed_mean

        # Distribution
        dist = {'lt0': 0, '0to1': 0, '1to2': 0, '2to3': 0, '3to4': 0, 'gte4': 0}
        for v in curr.values():
            if v < 0: dist['lt0'] += 1
            elif v < 1: dist['0to1'] += 1
            elif v < 2: dist['1to2'] += 1
            elif v < 3: dist['2to3'] += 1
            elif v < 4: dist['3to4'] += 1
            else: dist['gte4'] += 1
        total = sum(dist.values())
        if total > 0:
            for k in dist:
                dist[k] = dist[k] / total * 100

        # Expanding %
        expanding_pct = 0
        if prev_dict is not None:
            common = set(prev_dict.keys()) & set(curr.keys())
            if common:
                expanding = sum(1 for item in common if curr[item] > prev_dict[item])
                expanding_pct = expanding / len(common) * 100

        stats_timeline.append({
            'month': m,
            'trimmed_mean': round(trimmed_mean, 4),
            'trimmed_mean_32': round(trimmed_mean_32, 4),
            'median': round(median, 2),
            'dist': {k: round(v, 2) for k, v in dist.items()},
            'expanding_pct': round(expanding_pct, 2),
        })
        prev_dict = curr

    # Bandwidth (Silverman's rule with IQR) — outlier 영향 차단 위해 trim 적용
    all_vals_trimmed = []
    for m in filtered:
        vals = sorted(month_data[m].values())
        n = len(vals)
        cut = int(n * TRIM_RATIO)
        clipped = vals[cut:n - cut] if n > cut * 2 else vals
        all_vals_trimmed.extend(clipped)

    if all_vals_trimmed:
        avt_sorted = sorted(all_vals_trimmed)
        n_all = len(avt_sorted)
        mean = sum(all_vals_trimmed) / n_all
        std = (sum((v - mean) ** 2 for v in all_vals_trimmed) / n_all) ** 0.5
        q1 = avt_sorted[int(n_all * 0.25)]
        q3 = avt_sorted[int(n_all * 0.75)]
        iqr = q3 - q1
        h = min(std, iqr / 1.34) if iqr > 0 else std
        bw = 0.9 * h * n_all ** (-0.2)
        # spread 비례 floor만 살림(매우 좁은 분포에서 KDE 발산 방지)
        spread = max(all_vals_trimmed) - min(all_vals_trimmed)
        bw = max(bw, spread * 0.01)   # 트림 범위의 1%만 floor
    else:
        bw = 0.5

    return {
        'ridge': ridge,
        'stats_timeline': stats_timeline,
        'bw': round(bw, 6),
        'item_count': total_items,
    }


def extract_all_from_haver():
    """dashboard_data.xlsx → {country: country_data} 전체 추출."""
    if not DASHBOARD_XLSX.exists():
        print(f"[ERROR] {DASHBOARD_XLSX} not found")
        return {}

    # 1) Wide 시트
    wide = pd.read_excel(DASHBOARD_XLSX, sheet_name='Wide')
    date_col = wide.columns[0]
    wide[date_col] = pd.to_datetime(wide[date_col], errors='coerce')
    wide = wide.dropna(subset=[date_col]).set_index(date_col).sort_index()

    # 2) Metadata 시트 (ticker_pk → descriptor)
    try:
        meta = pd.read_excel(DASHBOARD_XLSX, sheet_name='Metadata')
        pk_to_desc = dict(zip(meta['ticker_pk'].astype(str),
                              meta['descriptor'].astype(str)))
    except Exception:
        print("[WARN] Metadata 시트가 없습니다. Wide 헤더만으로 진행합니다.")
        pk_to_desc = {}

    # 3) 컬럼별 분류 + @G10 헤드라인 제외 (시리즈 종류는 chg_type으로 기억)
    country_cols = {}  # country -> [(col, descriptor, chg_type)]  chg_type: None/'yoy'/'mom'/'qoq'
    skipped_no_country = 0
    skipped_g10 = 0
    n_chg_yoy = 0
    n_chg_mom = 0
    for col in wide.columns:
        norm_pk = normalize_to_pk(col)
        if norm_pk.startswith('g10:'):
            skipped_g10 += 1
            continue
        descriptor = resolve_descriptor(col, pk_to_desc)
        country = parse_country(descriptor)
        if country is None:
            skipped_no_country += 1
            continue
        chg_type = detect_change_type(descriptor)
        if chg_type == 'yoy':
            n_chg_yoy += 1
        elif chg_type in ('mom', 'qoq'):
            n_chg_mom += 1
        country_cols.setdefault(country, []).append((col, descriptor, chg_type))

    print(f"[INFO] 분류된 국가: {len(country_cols)}개")
    print(f"[INFO] @G10 헤드라인 제외(5번째 패널 전용): {skipped_g10}개")
    print(f"[INFO] Y/Y %Chg 시리즈: {n_chg_yoy}개 (값 그대로 YoY 사용)")
    print(f"[INFO] M/M·Q/Q %Chg 시리즈: {n_chg_mom}개 (12개월 누적환산으로 YoY 도출)")
    print(f"[INFO] 국가 매핑 안 된 티커: {skipped_no_country}개")

    # 4) 국가별 데이터 빌드 — chg_type별 분기
    result = {}
    for country, items in country_cols.items():
        yoy_per_col = {}
        for col, desc, chg_type in items:
            s = wide[col]
            if chg_type == 'yoy':
                yoy_per_col[col] = s              # 이미 YoY → 그대로
            elif chg_type in ('mom', 'qoq'):
                yoy_per_col[col] = derive_yoy_from_mom_pct(s)
            else:
                yoy_per_col[col] = compute_yoy_smart(s)
        sub_df = pd.DataFrame(yoy_per_col)
        sub_df.columns = [parse_subcategory(d) for _, d, _ in items]
        sub_df = sub_df.loc[:, ~sub_df.columns.duplicated()]

        data = build_country_data(sub_df)
        if data:
            result[country] = data
            print(f"  [OK] {country}: {data['item_count']} items, "
                  f"{len(data['ridge'])} months, bw={data['bw']}")
        else:
            print(f"  [SKIP] {country}: insufficient data")

    # 5) G10 Core CPI 모멘텀 — 기존 국가 리스트에 매핑되는 것만 attach
    g10_data = extract_g10_core_cpi(wide, pk_to_desc)
    print(f"[INFO] G10 Core CPI 잡힌 국가: {sorted(g10_data.keys())}")
    for country in result:
        if country in g10_data:
            result[country]['core_momentum'] = g10_data[country]
            sel = g10_data[country]
            print(f"  [G10] {country:10s} ← {sel['ticker']}")
            print(f"         desc: {sel['descriptor'][:100]}")
        else:
            result[country]['core_momentum'] = None

    # 6) 표시 순서 정렬 (US 먼저)
    ordered = {}
    for c in COUNTRY_DISPLAY_ORDER:
        if c in result:
            ordered[c] = result[c]
    for c in result:
        if c not in ordered:
            ordered[c] = result[c]
    return ordered


# ============================================================
# HTML 생성 (시각화 부분은 기존 그대로 유지)
# ============================================================
def generate_html(all_data):
    """데이터를 받아서 HTML 대시보드를 생성합니다."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    data_json = json.dumps(all_data, ensure_ascii=False)

    js_code = r"""
const CL=[[46,139,87],[60,160,100],[80,180,115],[110,195,130],[145,210,150],[185,220,160],[215,225,140],[240,210,100],[245,180,60],[240,145,40],[230,110,30],[220,90,20],[210,75,15],[200,60,10]];
const MO={'01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'May','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Oct','11':'Nov','12':'Dec'};

function kde(data,lo,hi,n,bw){
  const r=[];const safeBw=Math.max(bw||0,0.01);const s=(hi-lo)/(n-1||1);
  for(let i=0;i<n;i++){
    const x=lo+i*s;let v=0;
    for(const d of data){const z=(x-d)/safeBw;v+=Math.exp(-0.5*z*z);}
    r.push({x,y:v/(data.length*safeBw*Math.sqrt(2*Math.PI))});
  }
  return r;
}

function fky(c,x){let b=c[0];for(const p of c)if(Math.abs(p.x-x)<Math.abs(b.x-x))b=p;return b.y;}

function gc(i,N){
  const t=N>1?i/(N-1):0;const idx=t*(CL.length-1);
  const lo=Math.floor(idx),hi=Math.min(lo+1,CL.length-1),f=idx-lo;
  return [Math.round(CL[lo][0]+(CL[hi][0]-CL[lo][0])*f),Math.round(CL[lo][1]+(CL[hi][1]-CL[lo][1])*f),Math.round(CL[lo][2]+(CL[hi][2]-CL[lo][2])*f)];
}

function buildRidgeState(items,bw){
  const N=items.length;if(!N)return null;
  const trimmedItems=items.map(it=>{
    const sv=[...it.values].sort((a,b)=>a-b);
    const tc=Math.ceil(sv.length*0.1);
    const tv=sv.length>tc*2?sv.slice(tc,sv.length-tc):sv;
    return {date:it.date,values:it.values,trimmed:tv};
  });
  const allTrimmed=trimmedItems.flatMap(it=>it.trimmed).filter(v=>Number.isFinite(v));
  if(!allTrimmed.length)return null;
  const tMin=Math.min(...allTrimmed),tMax=Math.max(...allTrimmed);
  const spread=Math.max(tMax-tMin,0.2);const pad=spread*0.25;
  const xL=tMin-pad,xH=tMax+pad;
  let maxY=0;
  const curves=trimmedItems.map(it=>{
    const c=kde(it.trimmed,xL,xH,250,bw);
    for(const p of c)if(p.y>maxY)maxY=p.y;
    return c;
  });
  return {items:trimmedItems,bw,xL,xH,maxY,curves};
}

function drawRidge(cv,state,sharedMaxY){
  if(!state||!state.items||!state.items.length)return;
  const items=state.items,cs=state.curves,xL=state.xL,xH=state.xH;
  const mY=Math.max(sharedMaxY||state.maxY||0,1e-6);
  const N=items.length;const range=xH-xL;

  const dpr=window.devicePixelRatio||1;
  const W=640,pH=120,rS=N<=8?36:N<=12?30:24;
  const tP=14,bP=30,lP=120,rP=14;
  const H=tP+pH+(N-1)*rS+bP;
  cv.width=W*dpr;cv.height=H*dpr;
  cv.style.width='100%';cv.style.height='auto';cv.style.maxWidth=W+'px';
  const x=cv.getContext('2d');x.scale(dpr,dpr);
  const pL=lP,pR=W-rP;
  function xP(v){return pL+((v-xL)/(xH-xL||1))*(pR-pL);}

  x.strokeStyle='rgba(0,0,0,.07)';x.lineWidth=0.5;x.setLineDash([2,4]);
  const st=range>10?5:range>4?2:range>2?1:range>0.8?0.5:0.2;
  for(let v=Math.ceil(xL/st)*st;v<=xH+1e-9;v+=st){
    const px=xP(v);x.beginPath();x.moveTo(px,tP-3);x.lineTo(px,H-bP+6);x.stroke();
  }
  x.setLineDash([]);
  x.font='10px DM Sans,sans-serif';x.fillStyle='rgba(90,95,102,0.85)';x.textAlign='center';
  for(let v=Math.ceil(xL/st)*st;v<=xH+1e-9;v+=st)x.fillText(v.toFixed(st<1?1:0)+'%',xP(v),H-bP+18);

  // 우상단에 KDE bandwidth 값 표시 (국가간 비교 시 참고용)
  x.textAlign='right';x.fillStyle='rgba(255,200,120,0.55)';x.font='600 10px DM Sans,sans-serif';
  x.fillText('bw='+(state.bw||0).toFixed(2),W-rP,tP-2);

  for(let i=N-1;i>=0;i--){
    const c=cs[i];const bl=tP+pH+i*rS;const[r,g,b]=gc(i,N);
    x.beginPath();x.moveTo(xP(c[0].x),bl);
    for(const pt of c)x.lineTo(xP(pt.x),bl-(pt.y/mY)*pH);
    x.lineTo(xP(c[c.length-1].x),bl);x.closePath();
    const gd=x.createLinearGradient(0,bl-pH,0,bl);
    gd.addColorStop(0,`rgba(${r},${g},${b},0.8)`);
    gd.addColorStop(0.5,`rgba(${r},${g},${b},0.6)`);
    gd.addColorStop(1,'rgba(255,255,255,0.4)');
    x.fillStyle=gd;x.fill();
  }

  for(let i=N-1;i>=0;i--){
    const c=cs[i];const bl=tP+pH+i*rS;const[r,g,b]=gc(i,N);
    x.beginPath();let s=false;
    for(const pt of c){if(pt.y>0.01){const px=xP(pt.x),py=bl-(pt.y/mY)*pH;if(!s){x.moveTo(px,py);s=true;}else x.lineTo(px,py);}}
    x.strokeStyle=`rgb(${Math.min(r+40,255)},${Math.min(g+40,255)},${Math.min(b+30,255)})`;x.lineWidth=1.8;x.stroke();
  }

  for(let i=N-1;i>=0;i--){
    const c=cs[i];const bl=tP+pH+i*rS;const[r,g,b]=gc(i,N);
    const tm=items[i].trimmed;
    const mn=Math.min(...tm),mx=Math.max(...tm);
    const av=tm.reduce((a,b)=>a+b,0)/tm.length;
    const dc=`rgb(${Math.min(r+50,255)},${Math.min(g+50,255)},${Math.min(b+40,255)})`;
    const lc=`rgba(${Math.min(r+70,255)},${Math.min(g+70,255)},${Math.min(b+50,255)},0.8)`;
    function dot(xV,sz,lb,side){
      const ky=fky(c,xV);const px=xP(xV),py=bl-(ky/mY)*pH;
      x.beginPath();x.arc(px,py,sz,0,Math.PI*2);x.fillStyle=dc;x.fill();x.strokeStyle='rgba(0,0,0,0.35)';x.lineWidth=1.2;x.stroke();
      if(lb){x.fillStyle=lc;x.font='600 11px DM Sans,sans-serif';x.textAlign=side==='center'?'center':side;
        const o=side==='left'?6:side==='right'?-6:0;x.fillText(lb,px+o,py-6);}
    }
    dot(av,3.5,av.toFixed(1)+'%','center');dot(mn,2,mn.toFixed(1)+'%','right');dot(mx,2,mx.toFixed(1)+'%','left');
    x.textAlign='right';x.fillStyle='rgba(26,28,31,0.85)';x.font='600 12px DM Sans,sans-serif';
    x.fillText(items[i].date,lP-6,bl+4);
  }
}

function drawDualLine(cv,stats){
  if(!stats||!stats.length)return;
  const dpr=window.devicePixelRatio||1;
  const W=640,H=520;
  cv.width=W*dpr;cv.height=H*dpr;
  cv.style.width='100%';cv.style.height='auto';cv.style.maxWidth=W+'px';
  const x=cv.getContext('2d');x.scale(dpr,dpr);
  const tP=20,bP=40,lP=50,rP=60;
  const pW=W-lP-rP,pH_=H-tP-bP;
  const N=stats.length;
  const medians=stats.map(s=>s.median);
  const trimmeds=stats.map(s=>s.trimmed_mean);
  const trimmeds32=stats.map(s=>s.trimmed_mean_32);
  const all=[...medians,...trimmeds,...trimmeds32].filter(v=>Number.isFinite(v));
  const yMin=Math.min(...all)-0.3,yMax=Math.max(...all)+0.3;
  function xP(i){return lP+(N===1?0:(i/(N-1))*pW);}
  function yP(v){return tP+pH_-(v-yMin)/(yMax-yMin||1)*pH_;}
  x.strokeStyle='rgba(0,0,0,.07)';x.lineWidth=0.5;x.setLineDash([2,4]);
  const st=(yMax-yMin)>3?1:(yMax-yMin)>1?0.5:0.2;
  for(let v=Math.ceil(yMin/st)*st;v<=yMax+1e-9;v+=st){const py=yP(v);x.beginPath();x.moveTo(lP,py);x.lineTo(W-rP,py);x.stroke();}
  x.setLineDash([]);
  x.font='12px DM Sans,sans-serif';x.fillStyle='rgba(90,95,102,0.9)';x.textAlign='right';
  for(let v=Math.ceil(yMin/st)*st;v<=yMax+1e-9;v+=st)x.fillText(v.toFixed(1)+'%',lP-6,yP(v)+4);
  x.textAlign='center';x.fillStyle='rgba(26,28,31,0.85)';x.font='600 12px DM Sans,sans-serif';
  const skip=Math.max(1,Math.ceil(N/6));
  for(let i=0;i<N;i+=skip){x.fillText(stats[i].month,xP(i),H-bP+20);}
  // 3개 라인
  function drawLine(arr,color,w){
    x.beginPath();let s=false;
    for(let i=0;i<N;i++){
      const v=arr[i];if(!Number.isFinite(v)){s=false;continue;}
      const px=xP(i),py=yP(v);
      if(!s){x.moveTo(px,py);s=true;}else x.lineTo(px,py);
    }
    x.strokeStyle=color;x.lineWidth=w;x.stroke();
  }
  drawLine(medians,'#5DCAA5',2.5);   // Median = green
  drawLine(trimmeds,'#42a5f5',2.5);   // Trimmed 16% = blue
  drawLine(trimmeds32,'#ab47bc',2.5); // Trimmed 32% = purple
  // 마지막 점·라벨
  const last=stats[N-1];
  function dotLabel(v,color,offset){
    if(!Number.isFinite(v))return;
    const px=xP(N-1),py=yP(v);
    x.beginPath();x.arc(px,py,4,0,Math.PI*2);x.fillStyle=color;x.fill();
    x.strokeStyle='rgba(0,0,0,0.4)';x.lineWidth=1.5;x.stroke();
    x.fillStyle=color;x.font='bold 12px DM Sans,sans-serif';x.textAlign='left';
    x.fillText(v.toFixed(2)+'%',px+8,py+offset);
  }
  dotLabel(last.median,'#5DCAA5',-6);
  dotLabel(last.trimmed_mean,'#42a5f5',4);
  dotLabel(last.trimmed_mean_32,'#ab47bc',14);
  // 범례
  x.textAlign='left';x.font='600 12px DM Sans,sans-serif';
  x.fillStyle='#5DCAA5';x.fillRect(lP+4,tP+2,12,3);x.fillText('Median',lP+22,tP+10);
  x.fillStyle='#42a5f5';x.fillRect(lP+90,tP+2,12,3);x.fillText('Trimmed Mean(16%)',lP+108,tP+10);
  x.fillStyle='#ab47bc';x.fillRect(lP+250,tP+2,12,3);x.fillText('Trimmed Mean(24%/31%)',lP+268,tP+10);
}

function drawDistChart(cv,stats){
  if(!stats||!stats.length)return;
  const dpr=window.devicePixelRatio||1;
  const W=640,H=520;
  cv.width=W*dpr;cv.height=H*dpr;
  cv.style.width='100%';cv.style.height='auto';cv.style.maxWidth=W+'px';
  const x=cv.getContext('2d');x.scale(dpr,dpr);
  const tP=20,bP=40,lP=50,rP=20;
  const pW=W-lP-rP,pH_=H-tP-bP;
  const N=stats.length;
  const colors=['#d32f2f','#ff6f00','#fbc02d','#7cb342','#689f38','#1976d2'];
  const labels=['<0%','0-1%','1-2%','2-3%','3-4%','4%+'];
  const keys=['lt0','0to1','1to2','2to3','3to4','gte4'];
  function xP(i){return lP+(i/(N-1||1))*pW;}
  function yP(pct){return tP+pH_-(pct/100)*pH_;}
  x.strokeStyle='rgba(0,0,0,.07)';x.lineWidth=0.5;x.setLineDash([2,4]);
  for(let p=0;p<=100;p+=20){x.beginPath();x.moveTo(lP,yP(p));x.lineTo(W-rP,yP(p));x.stroke();}
  x.setLineDash([]);
  x.font='12px DM Sans,sans-serif';x.fillStyle='rgba(90,95,102,0.9)';x.textAlign='right';
  for(let p=0;p<=100;p+=20)x.fillText(p+'%',lP-6,yP(p)+4);
  const stackH=[];
  for(let i=0;i<N;i++){const s=[0];for(let ki=0;ki<keys.length;ki++){s.push(s[s.length-1]+(stats[i].dist[keys[ki]]||0));}stackH.push(s);}
  for(let ki=0;ki<keys.length;ki++){
    x.beginPath();
    for(let i=0;i<N;i++)x.lineTo(xP(i),yP(stackH[i][ki+1]));
    for(let i=N-1;i>=0;i--)x.lineTo(xP(i),yP(stackH[i][ki]));
    x.closePath();x.fillStyle=colors[ki];x.globalAlpha=0.8;x.fill();x.globalAlpha=1;
  }
  x.textAlign='center';x.fillStyle='rgba(26,28,31,0.85)';x.font='600 12px DM Sans,sans-serif';
  const skip=Math.max(1,Math.ceil(N/6));
  for(let i=0;i<N;i+=skip){x.fillText(stats[i].month,xP(i),H-bP+22);}
  x.font='600 12px DM Sans,sans-serif';x.textAlign='left';
  for(let ki=0;ki<labels.length;ki++){
    const lx=lP+ki*78;
    x.fillStyle=colors[ki];x.fillRect(lx,tP+2,10,10);
    x.fillStyle='rgba(26,28,31,0.7)';x.fillText(labels[ki],lx+13,tP+11);
  }
}

function drawMovingAvg(cv,stats){
  if(!stats||!stats.length)return;
  const dpr=window.devicePixelRatio||1;
  const W=640,H=520;
  cv.width=W*dpr;cv.height=H*dpr;
  cv.style.width='100%';cv.style.height='auto';cv.style.maxWidth=W+'px';
  const x=cv.getContext('2d');x.scale(dpr,dpr);
  const tP=20,bP=40,lP=50,rP=60;
  const pW=W-lP-rP,pH_=H-tP-bP;
  const N=stats.length;

  const ma3=[];
  for(let i=0;i<N;i++){
    const start=Math.max(0,i-2),end=i+1;
    const subset=stats.slice(start,end).map(s=>s.expanding_pct);
    ma3.push(subset.reduce((a,b)=>a+b)/subset.length);
  }

  const dataMin=Math.min(...ma3),dataMax=Math.max(...ma3);
  const pad=Math.max((dataMax-dataMin)*0.25,3);
  const yMin=Math.max(0,Math.floor((dataMin-pad)/5)*5),yMax=Math.min(100,Math.ceil((dataMax+pad)/5)*5);
  function xP(i){return lP+(i/(N-1||1))*pW;}
  function yP(v){return tP+pH_-((v-yMin)/(yMax-yMin))*pH_;}

  const gStep=(yMax-yMin)>40?10:5;
  x.strokeStyle='rgba(0,0,0,.07)';x.lineWidth=0.5;x.setLineDash([2,4]);
  for(let p=Math.ceil(yMin/gStep)*gStep;p<=yMax;p+=gStep){x.beginPath();x.moveTo(lP,yP(p));x.lineTo(W-rP,yP(p));x.stroke();}
  x.setLineDash([]);
  x.font='12px DM Sans,sans-serif';x.fillStyle='rgba(90,95,102,0.9)';x.textAlign='right';
  for(let p=Math.ceil(yMin/gStep)*gStep;p<=yMax;p+=gStep)x.fillText(p+'%',lP-6,yP(p)+4);

  if(yMin<=50&&yMax>=50){x.strokeStyle='rgba(0,0,0,0.18)';x.lineWidth=1;x.setLineDash([4,4]);
  x.beginPath();x.moveTo(lP,yP(50));x.lineTo(W-rP,yP(50));x.stroke();
  x.setLineDash([]);}

  x.beginPath();x.moveTo(xP(0),yP(yMin));
  for(let i=0;i<N;i++)x.lineTo(xP(i),yP(ma3[i]));
  x.lineTo(xP(N-1),yP(yMin));x.closePath();
  x.fillStyle='rgba(255,152,0,0.15)';x.fill();

  x.beginPath();
  for(let i=0;i<N;i++){if(i===0)x.moveTo(xP(i),yP(ma3[i]));else x.lineTo(xP(i),yP(ma3[i]));}
  x.strokeStyle='#ff9800';x.lineWidth=2.5;x.stroke();

  const lastV=ma3[N-1];
  x.beginPath();x.arc(xP(N-1),yP(lastV),4,0,Math.PI*2);x.fillStyle='#ff9800';x.fill();x.strokeStyle='rgba(0,0,0,0.4)';x.lineWidth=1.5;x.stroke();
  x.fillStyle='#ffb74d';x.font='bold 12px DM Sans,sans-serif';x.textAlign='left';
  x.fillText(lastV.toFixed(1)+'%',xP(N-1)+8,yP(lastV)+4);

  x.textAlign='center';x.fillStyle='rgba(26,28,31,0.85)';x.font='600 12px DM Sans,sans-serif';
  const skip=Math.max(1,Math.ceil(N/6));
  for(let i=0;i<N;i+=skip){x.fillText(stats[i].month,xP(i),H-bP+22);}

  x.fillStyle='rgba(90,95,102,0.9)';x.font='600 12px DM Sans,sans-serif';x.textAlign='left';
  x.fillStyle='#ff9800';x.fillText('3M MA (Expanding %)',lP+4,tP+10);
}

function drawCoreMomentum(cv,mom){
  if(!cv||!mom)return;
  const dpr=window.devicePixelRatio||1;
  const W=1300,H=420;
  cv.width=W*dpr;cv.height=H*dpr;
  cv.style.width='100%';cv.style.height='auto';cv.style.maxWidth=W+'px';
  const x=cv.getContext('2d');x.scale(dpr,dpr);
  const tP=24,bP=44,lP=58,rP=110;
  const pW=W-lP-rP,pH_=H-tP-bP;
  const dates=mom.dates,yoy=mom.yoy_12m,m3=mom.mom_3m3m,m6=mom.mom_6m6m;
  const N=dates.length;
  const allVals=[...yoy,...m3,...m6].filter(v=>v!==null&&Number.isFinite(v));
  if(!allVals.length)return;
  const yMin=Math.min(...allVals)-0.5,yMax=Math.max(...allVals)+0.5;
  function xP(i){return lP+(N===1?0:(i/(N-1))*pW);}
  function yP(v){return tP+pH_-(v-yMin)/(yMax-yMin||1)*pH_;}

  // 가로 그리드
  x.strokeStyle='rgba(0,0,0,.07)';x.lineWidth=0.5;x.setLineDash([2,4]);
  const rng=yMax-yMin;const st=rng>10?2:rng>4?1:rng>2?0.5:0.2;
  for(let v=Math.ceil(yMin/st)*st;v<=yMax+1e-9;v+=st){
    const py=yP(v);x.beginPath();x.moveTo(lP,py);x.lineTo(W-rP,py);x.stroke();
  }
  x.setLineDash([]);
  // 2% 타겟 라인
  if(yMin<=2&&yMax>=2){
    x.strokeStyle='rgba(180,180,180,0.30)';x.lineWidth=1;x.setLineDash([6,4]);
    x.beginPath();x.moveTo(lP,yP(2));x.lineTo(W-rP,yP(2));x.stroke();x.setLineDash([]);
    x.fillStyle='rgba(180,180,180,0.6)';x.font='10px DM Sans,sans-serif';x.textAlign='left';
    x.fillText('2%',W-rP+4,yP(2)+3);
  }
  // 0% 라인
  if(yMin<=0&&yMax>=0){
    x.strokeStyle='rgba(0,0,0,0.18)';x.lineWidth=1;
    x.beginPath();x.moveTo(lP,yP(0));x.lineTo(W-rP,yP(0));x.stroke();
  }

  x.font='12px DM Sans,sans-serif';x.fillStyle='rgba(90,95,102,0.9)';x.textAlign='right';
  for(let v=Math.ceil(yMin/st)*st;v<=yMax+1e-9;v+=st)x.fillText(v.toFixed(st<1?1:0)+'%',lP-6,yP(v)+4);

  // 시리즈 그리기 (3개 라인: 12M YoY, 3M/3M ann, 6M/6M ann)
  function drawLine(arr,color,width){
    x.strokeStyle=color;x.lineWidth=width;x.beginPath();
    let s=false;
    for(let i=0;i<N;i++){
      const v=arr[i];
      if(v===null||!Number.isFinite(v)){s=false;continue;}
      const px=xP(i),py=yP(v);
      if(!s){x.moveTo(px,py);s=true;}else x.lineTo(px,py);
    }
    x.stroke();
  }
  drawLine(m6,'#42a5f5',2.2);  // 6M/6M = blue
  drawLine(m3,'#ff9800',2.2);  // 3M/3M = orange
  drawLine(yoy,'#5DCAA5',2.6); // 12M YoY = green (가장 굵게)

  // 마지막 값 점·라벨
  function lastIdx(arr){for(let i=arr.length-1;i>=0;i--)if(arr[i]!==null&&Number.isFinite(arr[i]))return i;return -1;}
  function dotLabel(arr,color,offset){
    const i=lastIdx(arr);if(i<0)return;
    const v=arr[i];const px=xP(i),py=yP(v);
    x.beginPath();x.arc(px,py,4,0,Math.PI*2);x.fillStyle=color;x.fill();
    x.strokeStyle='rgba(0,0,0,0.4)';x.lineWidth=1.2;x.stroke();
    x.fillStyle=color;x.font='bold 12px DM Sans,sans-serif';x.textAlign='left';
    x.fillText(v.toFixed(2)+'%',px+8,py+offset);
  }
  dotLabel(yoy,'#5DCAA5',-6);
  dotLabel(m3,'#ff9800',4);
  dotLabel(m6,'#42a5f5',14);

  // X축 라벨
  x.textAlign='center';x.fillStyle='rgba(26,28,31,0.7)';x.font='600 11px DM Sans,sans-serif';
  const skip=Math.max(1,Math.ceil(N/10));
  for(let i=0;i<N;i+=skip){x.fillText(dates[i],xP(i),H-bP+22);}

  // 범례 (좌상단)
  x.textAlign='left';x.font='600 12px DM Sans,sans-serif';
  x.fillStyle='#5DCAA5';x.fillRect(lP+4,tP+2,12,3);x.fillText('12M YoY',lP+22,tP+10);
  x.fillStyle='#ff9800';x.fillRect(lP+110,tP+2,12,3);x.fillText('3M/3M ann.',lP+128,tP+10);
  x.fillStyle='#42a5f5';x.fillRect(lP+230,tP+2,12,3);x.fillText('6M/6M ann.',lP+248,tP+10);

  // 티커명 (우상단)
  x.textAlign='right';x.fillStyle='rgba(90,95,102,0.7)';x.font='10px DM Sans,sans-serif';
  x.fillText(mom.ticker||'',W-rP,tP+10);
}

const root=document.getElementById('root');
const filterSel=document.getElementById('country-filter');
let CURRENT_WINDOW=36;  // 디폴트: 3Y (36개월)

function sliceMomentum(mom,win){
  if(!mom||win>=9999)return mom;
  return {
    ticker:mom.ticker,descriptor:mom.descriptor,
    dates:mom.dates.slice(-win),
    yoy_12m:mom.yoy_12m.slice(-win),
    mom_3m3m:mom.mom_3m3m.slice(-win),
    mom_6m6m:mom.mom_6m6m.slice(-win),
  };
}

function drawCountry(c,win){
  const d=D[c];const hasMom=d.core_momentum?true:false;
  // Ridge는 항상 최근 12개월 고정 (드롭다운 영향 안 받음)
  const RIDGE_FIXED=12;
  const ridge=(d.ridge||[]).slice(-RIDGE_FIXED);
  const state=buildRidgeState(ridge,d.bw);
  drawRidge(document.getElementById('r_'+c),state,state?.maxY||0);

  // 나머지 3개 (Median/Trimmed, Distribution, 3M MA)는 드롭다운 윈도우만큼
  const winStats=(d.stats_timeline||[]).slice(-win);
  drawDualLine(document.getElementById('d_'+c),winStats);
  drawDistChart(document.getElementById('s_'+c),winStats);
  drawMovingAvg(document.getElementById('m_'+c),winStats.slice(1));

  // 5번째 패널: momentum도 드롭다운 윈도우 (최소 13개월은 있어야 12M YoY 의미)
  if(hasMom){
    const momWin=Math.max(win,13);
    drawCoreMomentum(document.getElementById('cm_'+c),sliceMomentum(d.core_momentum,momWin));
  }
  // 헤더의 #items 카운트 갱신
  const titleEl=document.querySelector(`.country[data-country="${c}"] .ctitle .items-count`);
  if(titleEl){
    const lastN=ridge.length?ridge[ridge.length-1].values.length:0;
    titleEl.textContent=`#${lastN} items · ridge fixed 12M · others ${win>=9999?'ALL':win+'M'}`;
  }
}

Object.keys(D).forEach(c=>{
  const d=D[c];
  const opt=document.createElement('option');opt.value=c;opt.textContent=c;
  filterSel.appendChild(opt);
  const div=document.createElement('div');div.className='country';div.dataset.country=c;
  const hasMom=d.core_momentum?true:false;
  const momRow=hasMom?`<div class="row" style="margin-top:12px"><div class="panel" style="flex:1 1 100%"><div class="plabel">Core CPI Momentum — 12M YoY · 3M/3M annualized · 6M/6M annualized</div><canvas id="cm_${c}"></canvas></div></div>`:'';
  div.innerHTML=`<div class="ctitle">${c} <span class="items-count" style="font-size:13px;color:var(--text-muted);font-weight:400"></span></div><div class="row"><div class="panel"><div class="plabel">CPI 분포(%YoY)</div><div class="psub">최근 12개월 품목별 YoY 분포 · 상하위 10% 트림 (Ridge KDE)</div><canvas id="r_${c}"></canvas></div><div class="panel"><div class="plabel">Median & Trimmed Mean(% YoY)</div><div class="psub">Trimmed Mean(16%): 상하위 8%씩 제외 (Cleveland Fed 방식) · Trimmed Mean(24%/31%): 하위 24% / 상위 31% 제외 (Dallas Fed 비대칭 방식) · 모두 개수 기준 근사</div><canvas id="d_${c}"></canvas></div></div><div class="row" style="margin-top:12px"><div class="panel"><div class="plabel">CPI 분포(% YoY)</div><div class="psub">품목 갯수 기준</div><canvas id="s_${c}"></canvas></div><div class="panel"><div class="plabel">물가 상승폭 확대 품목(% YoY)</div><div class="psub">전월 대비 상승폭 확대 품목 수 비중(3MMA)</div><canvas id="m_${c}"></canvas></div></div>${momRow}`;
  root.appendChild(div);
});

// 초기 렌더
setTimeout(()=>{Object.keys(D).forEach(c=>drawCountry(c,CURRENT_WINDOW));},10);

function applyWindow(val){
  CURRENT_WINDOW=val;
  Object.keys(D).forEach(c=>drawCountry(c,val));
}

function filterCountry(val){
  document.querySelectorAll('.country').forEach(div=>{
    if(val==='ALL'||div.dataset.country===val){
      div.classList.remove('hidden');
    }else{
      div.classList.add('hidden');
    }
  });
}
"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CPI YoY Distribution Dashboard</title>
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
.panel{{flex:1;min-width:380px;background:var(--card-bg);border:1px solid var(--border);border-radius:10px;padding:16px 14px 10px}}
.plabel{{font-size:16px;font-weight:600;color:var(--text-main);margin-bottom:2px;text-transform:uppercase;letter-spacing:0.5px}}
.psub{{font-size:11px;font-weight:400;color:var(--text-muted);margin-bottom:10px;letter-spacing:0.2px}}
canvas{{width:100%;height:auto}}
</style>
</head>
<body>
<div class="header-row">
<div class="header-left">
<h1>CPI YoY distribution</h1>
<p class="sub">All items · 4-panel layout · updated {now} · source: dashboard_data.xlsx</p>
</div>
<select class="country-select" id="window-filter" onchange="applyWindow(parseInt(this.value))" style="margin-right:10px">
<option value="1">1M</option>
<option value="3">3M</option>
<option value="6">6M</option>
<option value="12">12M</option>
<option value="24">2Y</option>
<option value="36" selected>3Y</option>
<option value="48">4Y</option>
<option value="60">5Y</option>
<option value="120">10Y</option>
<option value="240">20Y</option>
</select>
<select class="country-select" id="country-filter" onchange="filterCountry(this.value)">
<option value="ALL">All countries</option>
</select>
</div>
<div id="root"></div>
<script>
const D = {data_json};
{js_code}
</script>
</body>
</html>"""

    return html


# ============================================================
# MAIN
# ============================================================
def main():
    all_data = extract_all_from_haver()

    if not all_data:
        print("[ERROR] No data extracted from dashboard_data.xlsx")
        return

    html = generate_html(all_data)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n✅ Dashboard saved to {OUTPUT_PATH}")
    print(f"   File size: {len(html):,} bytes")
    print(f"   Countries rendered: {list(all_data.keys())}")


if __name__ == '__main__':
    main()
