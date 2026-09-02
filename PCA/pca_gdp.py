# -*- coding: utf-8 -*-
"""
pca_gdp.py — 국가별 카테고리 Time-Varying PCA → GDP 프록시 + LEI + HTML 대시보드

입력: haver/haver-api_PCA/Meta data_Raw data.xlsx
  - Wide     : 날짜 x 지표 (헤더 = CODE@DATABASE)
  - Metadata : ticker_pk / code / descriptor / datatype / frequency / category / country
               (country: AU/CA/DE/JP/UK/US — tickers.xlsx Country 열에서 fetch 스크립트가 병기.
                한 지표를 여러 국가에서 쓰면 "US,CA" 처럼 콤마로 들어오고 양쪽 모두에 포함된다.
                country 컬럼이 없거나 비어 있으면 US 로 간주 → 구버전 파일과 호환)
  - 전처리   : ticker_pk / code / (level | diffusion)

버전 2개 (국가마다 각각):
  - YoY      : level은 12개월 로그차분, diffusion은 그대로. 반감기 24개월
  - Momentum : 3m/3m — 3개월평균의 3개월 전 대비 (level=로그차분, diffusion=차분). 반감기 12개월

구조:
  국가별로 지표를 나눈 뒤 →
  카테고리별 TV-PCA(EWM 상관행렬 + eigh) → 카테고리 지수(EWM z-score)
  → lei 제외 카테고리 동일가중 평균 = GDP 프록시 / lei는 별도 LEI 지수

출력:
  - pca_result.xlsx    (국가_버전별 지수·기여도·지표 z-score 시트)
  - pca_dashboard.html (국가 드롭다운 + 탭: 경기지수 / LEI)
    payload 형식: {"default": "US", "countries": {"US": {"label","label_kr","versions"}, ...}}
"""
import json
import re
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

LEI_CAT    = "lei"          # 합산에서 제외하고 별도 산출할 카테고리
MIN_EWM_OBS = 12            # EWM 평균/표준편차 최소 관측치
# GDP 프록시 한 달을 만드는 데 필요한 최소 카테고리 비중.
# 카테고리 지수는 지표가 하나만 갱신돼도 산출되지만(그게 원래 요구),
# 헤드라인 지수까지 카테고리 1개로 그리면 최신월이 그 카테고리 그 자체가 된다.
# 0.5 = 카테고리 절반 이상(5개면 3개)이 있는 달만 GDP 프록시를 낸다.
GDP_MIN_CAT_RATIO = 0.5

# 국가 코드 → 표기 (드롭다운 순서 = 이 순서)
COUNTRIES = {
    "US": {"en": "United States",  "kr": "미국"},
    "AU": {"en": "Australia",      "kr": "호주"},
    "CA": {"en": "Canada",         "kr": "캐나다"},
    "DE": {"en": "Germany",        "kr": "독일"},
    "JP": {"en": "Japan",          "kr": "일본"},
    "UK": {"en": "United Kingdom", "kr": "영국"},
}
DEFAULT_COUNTRY = "US"      # country 컬럼이 없는 구버전 데이터의 폴백

VERSIONS = {
    "YoY":      {"halflife": 24, "mode": "yoy"},
    "Momentum": {"halflife": 12, "mode": "m3m3"},
}

CAT_LABEL = {"consumer": "Consumer", "capex": "Capex", "export": "Export",
             "housing": "Housing", "labor": "Labor", "lei": "LEI",
             "employment": "Employment", "production": "Production",
             "financial": "Financial"}


def cat_label(cat):
    return CAT_LABEL.get(cat, str(cat).capitalize())


def country_label(cc, kind="en"):
    info = COUNTRIES.get(cc)
    return info[kind] if info else cc


# ============================================================
# 1. 로드 + 검증
# ============================================================
def ticker_to_pk(h):
    h = str(h).strip()
    if "@" in h:
        code, db = h.split("@", 1)
        return f"{db.strip().lower()}:{code.strip().lower()}"
    return h.lower()


def rule_column(pre):
    """전처리 시트의 level/diffusion 열 이름.
       'rule' 열이 있으면 그걸 쓰고, 없으면 옛 구조(3번째 열 = 라벨)로 폴백."""
    for c in pre.columns:
        if str(c).strip().lower() == "rule":
            return c
    return pre.columns[2] if len(pre.columns) >= 3 else pre.columns[-1]


# 수식에 허용할 문자 — ticker_pk(db:code), 숫자, 사칙연산, 괄호, 공백만
_FORMULA_OK = re.compile(r"^[A-Za-z0-9_:.+\-*/() ]+$")
_PK_TOKEN   = re.compile(r"[A-Za-z0-9_]+:[A-Za-z0-9_]+")


def add_derived(wide, pre, cat_map, ctry_map, desc_map):
    """전처리 시트의 formula 열로 파생 지표 컬럼을 만든다.

    예) canada:x_nonenergy = g10:s156ix - canada:v6911351  (비에너지 수출)
    원료 티커는 tickers.xlsx 에 두되 카테고리를 비워두면 데이터만 들어오고
    PCA 지표로는 잡히지 않는다(아래 검증 게이트에서 제외됨).

    파생 지표는 Metadata 에 없으므로 category/country/descriptor 도 이 시트에서 읽는다.
    """
    if "formula" not in pre.columns:
        return wide
    for _, r in pre.iterrows():
        expr = str(r.get("formula", "")).strip()
        if not expr or expr.lower() == "nan":
            continue
        pk = str(r["ticker_pk"]).strip()
        if not _FORMULA_OK.match(expr):
            raise SystemExit(f"[중단] 허용되지 않는 문자가 수식에 있습니다: {pk} = {expr}")
        toks = sorted(set(_PK_TOKEN.findall(expr)), key=len, reverse=True)
        missing = [t for t in toks if t not in wide.columns]
        if missing:
            print(f"[WARN] 파생 {pk}: 원료 없음 {missing} — 건너뜀")
            continue
        py = expr
        for t in toks:                      # 긴 것부터 치환해야 부분일치가 안 생긴다
            py = py.replace(t, f'W["{t}"]')
        wide[pk] = eval(py, {"__builtins__": {}}, {"W": wide})
        cat_map[pk]  = str(r.get("category", "")).strip().lower()
        v = str(r.get("country", "")).strip().upper()
        ctry_map[pk] = [x.strip() for x in v.split(",") if x.strip()] or [DEFAULT_COUNTRY]
        desc_map[pk] = str(r.get("descriptor", "")).strip() or pk
        print(f"[INFO] 파생 생성: {pk} = {expr}  (n={wide[pk].notna().sum()})")
    return wide


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
    rule_map = dict(zip(pre["ticker_pk"].astype(str), pre[rule_column(pre)].astype(str).str.strip().str.lower()))
    desc_map = dict(zip(meta["ticker_pk"].astype(str), meta["descriptor"].astype(str)))

    # --- 국가 매핑: Metadata의 country 컬럼. 없거나 빈 값이면 DEFAULT_COUNTRY ---
    # 값은 "US" 또는 "US,CA" (한 지표를 여러 국가에서 쓰는 경우 — 예: US ISM의 캐나다 스필오버).
    # ctry_map[pk] 는 항상 국가코드 리스트.
    if "country" in meta.columns:
        raw_ctry = dict(zip(meta["ticker_pk"].astype(str), meta["country"].astype(str).str.strip().str.upper()))
    else:
        print(f"[INFO] Metadata에 country 컬럼 없음 → 전체를 {DEFAULT_COUNTRY} 로 간주 (구버전 호환)")
        raw_ctry = {}
    ctry_map = {}
    for c in wide.columns:
        v = raw_ctry.get(c, "")
        ccs = [] if v in ("", "NAN", "NONE") else [x.strip() for x in v.split(",") if x.strip()]
        ctry_map[c] = ccs or [DEFAULT_COUNTRY]

    # --- 파생 지표 생성 (검증 게이트 전에 — 원료는 게이트에서 빠져도 파생은 남는다) ---
    wide = add_derived(wide, pre, cat_map, ctry_map, desc_map)

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

    return wide, cat_map, rule_map, desc_map, ctry_map


def short_label(pk, desc_map):
    """descriptor를 차트용 짧은 이름으로."""
    d = str(desc_map.get(pk, pk))
    d = d.split("(")[0].strip()
    return d if len(d) <= 42 else d[:40] + "…"


# ============================================================
# 2. 변환 (버전별) + EWM z-score
# ============================================================
def transform(wide, rule_map, mode):
    """level 은 성장률로, diffusion 은 그대로(또는 차분).

    YoY 의 level 은 3개월 이동평균을 먼저 걸고 12개월 로그차분한다.
    원계열을 바로 로그차분하면 하드데이터가 매달 방향이 뒤집힐 만큼 노이지했다
    (level 80개 중앙: Δz 자기상관 -0.223 → 3mma 적용 시 +0.436,
     월간 변동폭 |Δz| 0.296 → 0.162). 대가는 GDP 프록시 기준 0~1개월 시차.
    """
    cols = {}
    for col in wide.columns:
        x = wide[col]
        if mode == "yoy":
            if rule_map[col] == "level":
                cols[col] = np.log(x.rolling(3).mean()).diff(12) * 100   # 3mma 기준 YoY %
            else:
                cols[col] = x                                 # diffusion 그대로
        elif mode == "m3m3":
            ma3 = x.rolling(3).mean()
            if rule_map[col] == "level":
                cols[col] = np.log(ma3).diff(3) * 100          # 3m/3m %
            else:
                cols[col] = ma3.diff(3)                        # diffusion: 3mma 차분
    return pd.concat(cols, axis=1).dropna(how="all")


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
    z: 카테고리 내 지표들의 z-score DataFrame. **결측 허용** — 지표마다 시작·종료가 달라도 된다.
       그 시점에 값이 **하나라도** 있으면 계산한다(예전엔 2개 이상이어야 했다).

    각 시점 t 에서 그 시점에 값이 있는 지표만 골라 상관행렬 부분행렬을 떼어내 PC1 을 뽑는다.
    (예전에는 dropna 로 균형패널을 만들었는데, 늦게 시작하는 지표 하나가
     카테고리 전체 기간을 그 지표 시작일까지 잘라먹었다 — 2021년 시작 PMI 등)

    지표 수 n 이 시점마다 달라지면 PC1 = z·loading 의 스케일이 대략 sqrt(n) 에 비례해
    합류 시점에 계단이 생기므로 sqrt(n) 으로 나눠 맞춘다.

    반환: pc1(Series), loadings(DataFrame, 미가용 지표는 NaN), contrib(DataFrame)
    """
    cols = list(z.columns)
    # 쌍별 EWM 상관. min_periods 를 넘기지 못한 쌍은 NaN 이라 그 시점엔 자동 제외된다.
    # 상관은 '지표 2개 이상인 달'만으로 추정한다 — 1개짜리 달(발표가 몰리기 전 최신월)을
    # 섞으면 EWM 감쇠 위치가 밀려 과거 값까지 미세하게 달라진다.
    z2 = z[z.notna().sum(axis=1) >= 2]
    corr_panel = z2.ewm(halflife=halflife,
                        min_periods=max(len(cols), MIN_EWM_OBS)).corr()

    pc1_vals, load_rows, idx_used = [], [], []
    prev_load = None                    # 직전 시점 로딩 (부호 연속성용)
    last_load = None                    # 지표별 '마지막으로 본' 로딩 (단일 지표 달의 부호 기준)
    for t in z.index:
        row = z.loc[t]
        avail = [c for c in cols if pd.notna(row[c])]
        if not avail:
            continue

        cmdf = None
        if len(avail) >= 2:
            try:
                cmdf = corr_panel.loc[t]
            except KeyError:
                cmdf = None

        if cmdf is not None:
            # 새로 합류한 지표는 값은 있어도 다른 지표와의 EWM 상관이 아직 min_periods 를
            # 못 채워 NaN 이다. 이때 그 시점을 통째로 버리면 지수에 구멍이 생기고
            # 상관이 추정되는 순간 계단이 난다 → 상관을 못 구한 지표만 빼고 나머지로 진행한다.
            while len(avail) >= 2:
                na = cmdf.loc[avail, avail].isna().sum(axis=1)
                if na.max() == 0:
                    break
                avail = [c for c in avail if c != na.idxmax()]

        if cmdf is not None and len(avail) >= 2:
            cm = cmdf.loc[avail, avail].values
            w, v = np.linalg.eigh(cm)       # 고유분해 (w 오름차순)
            lser = pd.Series(v[:, -1], index=avail)   # 최대 고유값의 고유벡터 = PC1 방향

            # 고유벡터의 부호는 임의로 정해진다. 예전에는 loading.sum()<0 이면 뒤집었는데,
            # 로딩 부호가 섞여 합이 0 근처면 달마다 제멋대로 뒤집혀 지수에 가짜 스파이크가 났다.
            # → 직전 시점 로딩과 내적이 음수면 뒤집어 방향을 이어붙인다.
            if prev_load is not None:
                shared = [c for c in avail if c in prev_load.index]
                if shared and float((lser[shared] * prev_load[shared]).sum()) < 0:
                    lser = -lser
            elif lser.sum() < 0:            # 첫 시점만 경기순응 가정으로 방향 결정
                lser = -lser
            prev_load = lser
        else:
            # 그 달에 갱신된 지표가 1개뿐(또는 쌍 상관을 못 구함) — 그 지표의 z 를 그대로
            # PC1 로 쓴다. 로딩은 ±1 이고 부호는 그 지표의 마지막 정식 로딩을 따른다.
            # (지표 n개일 때 PC1 = Σz·l/√n ≈ 평균 z 라 단일 지표 z 와 스케일이 맞는다)
            # 카테고리가 아직 자리를 못 잡은 초반(로딩 이력 없음)에는 그대로 건너뛴다.
            if last_load is None:
                continue
            pick = next((c for c in avail
                         if c in last_load.index and pd.notna(last_load[c])), None)
            if pick is None:
                continue
            avail = [pick]
            lser = pd.Series([1.0 if last_load[pick] >= 0 else -1.0], index=[pick])
            # prev_load 는 갱신하지 않는다 — 다음 달 부호 기준은 마지막 정식 PCA 로딩이다.

        last_load = lser if last_load is None else lser.combine_first(last_load)
        pc1_vals.append(float(row[avail].values @ lser.values) / np.sqrt(len(avail)))
        load_rows.append(lser)
        idx_used.append(t)

    if not idx_used:
        return pd.Series(dtype=float), pd.DataFrame(columns=cols), pd.DataFrame(columns=cols)

    pc1 = pd.Series(pc1_vals, index=idx_used, name="PC1")
    loadings = pd.DataFrame(load_rows, index=idx_used).reindex(columns=cols)

    # 전체 부호 확정: 카테고리 평균 z와 양의 상관이 되도록
    anchor = z.mean(axis=1).reindex(idx_used)
    if pc1.corr(anchor) < 0:
        pc1, loadings = -pc1, -loadings

    contrib = z.reindex(idx_used) * loadings
    return pc1, loadings, contrib


# ============================================================
# 4. (국가 하나의) 버전 하나 전체 실행
# ============================================================
def run_version(wide, cat_map, rule_map, halflife, mode, tag=""):
    z_all = ewm_zscore(transform(wide, rule_map, mode), halflife)

    cats = sorted(set(cat_map.get(c) for c in z_all.columns))
    res = {"z": z_all, "cat_index": {}, "cat_loadings": {}, "cat_contrib": {}}

    for cat in cats:
        cols = [c for c in z_all.columns if cat_map[c] == cat]
        # 결측을 남긴 채 넘긴다 — 그 시점에 지표가 하나라도 있으면 계산한다.
        # (dropna 로 균형패널을 만들면 늦게 시작하는 지표 하나가 카테고리 전체를 잘라먹는다.
        #  2개 이상을 요구하면 발표가 이른 지표 하나만 나온 최신월이 통째로 사라졌다)
        sub = z_all[cols]
        sub = sub[sub.notna().sum(axis=1) >= 1]
        if len(cols) < 2 or len(sub) <= len(cols):
            print(f"  [WARN] {tag}{cat}: 지표 {len(cols)}개/표본 {len(sub)} — 스킵")
            continue
        pc1, loadings, contrib = tv_pca(sub, halflife)
        # 카테고리 지수도 EWM z-score로 스케일 통일
        pc1_z = ewm_zscore(pc1.to_frame(), halflife).iloc[:, 0]
        res["cat_index"][cat] = pc1_z
        res["cat_loadings"][cat] = loadings
        res["cat_contrib"][cat] = contrib

    # GDP 프록시 = lei 제외 카테고리 동일가중 평균
    gdp_cats = [c for c in res["cat_index"] if c != LEI_CAT]
    if gdp_cats:
        panel = pd.DataFrame({c: res["cat_index"][c] for c in gdp_cats})
        full = panel.dropna()
        # 시작은 모든 카테고리가 갖춰진 첫 달(초반이 카테고리 1~2개로 만들어지지 않게).
        # 그 뒤로는 '있는 카테고리만' 동일가중 평균 — 발표가 늦는 카테고리 하나 때문에
        # 최신월 전체가 사라지지 않는다. 기여도도 그 달의 유효 카테고리 수로 나눠
        # 막대 합 = 지수가 그대로 유지된다.
        if len(full):
            panel = panel.loc[full.index[0]:]
        need = max(2, int(np.ceil(len(gdp_cats) * GDP_MIN_CAT_RATIO)))
        panel = panel[panel.notna().sum(axis=1) >= need]
        n_avail = panel.notna().sum(axis=1)
        res["gdp"] = panel.mean(axis=1)
        res["gdp_contrib"] = panel.div(n_avail, axis=0)   # 합 = GDP 프록시
        res["gdp_navail"] = n_avail                       # 그 달에 쓴 카테고리 수
        res["gdp_ncats"] = len(gdp_cats)
    else:
        res["gdp"] = pd.Series(dtype=float)
        res["gdp_contrib"] = pd.DataFrame()
        res["gdp_navail"] = pd.Series(dtype=int)
        res["gdp_ncats"] = 0
    res["lei"] = res["cat_index"].get(LEI_CAT, pd.Series(dtype=float))
    return res


# ============================================================
# 5. 엑셀 저장 (국가별 시트 프리픽스)
# ============================================================
def save_excel(all_results, cat_map, desc_map):
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as wr:
        readme = pd.DataFrame({
            "항목": ["국가", "버전", "전처리", "z-score", "PCA", "합산", "LEI", "시트명"],
            "내용": [
                " / ".join(f"{cc}={country_label(cc)}" for cc in all_results),
                "YoY(반감기24) / Momentum 3m3m(반감기12)",
                "level→로그차분(YoY=12개월, Mom=3mma 3개월), diffusion→그대로(Mom은 3mma 차분)",
                f"EWM 평균·표준편차 (min_periods={MIN_EWM_OBS}, 룩어헤드 없음)",
                "국가·카테고리별 EWM 상관행렬 고유분해, 시점별 PC1",
                "lei 제외 카테고리 지수(z) 동일가중 평균 = GDP 프록시",
                "별도 산출 (합산 미포함)",
                "국가코드_버전_내용 (예: US_YoY_indices)",
            ],
        })
        readme.to_excel(wr, sheet_name="README", index=False)

        for cc, results in all_results.items():
            for ver, r in results.items():
                idx_df = pd.DataFrame({"GDP_proxy": r["gdp"], "LEI": r["lei"]})
                for cat, s in r["cat_index"].items():
                    if cat != LEI_CAT:
                        idx_df[cat_label(cat)] = s
                idx_df.to_excel(wr, sheet_name=f"{cc}_{ver}_indices")
                r["gdp_contrib"].rename(columns=cat_label).to_excel(
                    wr, sheet_name=f"{cc}_{ver}_gdp_contrib")
                r["z"].rename(columns=lambda c: short_label(c, desc_map)).to_excel(
                    wr, sheet_name=f"{cc}_{ver}_indicator_z")
    print(f"엑셀 저장: {OUT_XLSX}")


# ============================================================
# 6. 대시보드 데이터(JSON) 빌드
# ============================================================
def fmt_series(s, index):
    s = s.reindex(index)
    return [None if pd.isna(v) else round(float(v), 3) for v in s]


def build_country_versions(results, cat_map, desc_map):
    versions = {}
    for ver, r in results.items():
        idx = r["z"].index
        dates = [d.strftime("%Y-%m") for d in idx]
        # 최신 관측월 = 지표가 2개 이상 들어온 마지막 달.
        # (한 달 먼저 나오는 서베이 1개가 기준월을 끌고 가면 나머지가 전부 미갱신으로 보인다)
        cnt = r["z"].notna().sum(axis=1)
        ref = cnt[cnt >= 2].index[-1] if (cnt >= 2).any() else (idx[-1] if len(idx) else None)
        gdp_cats = [c for c in r["cat_index"] if c != LEI_CAT]

        cat_block = {}
        for cat in r["cat_index"]:
            cols = [c for c in r["z"].columns if cat_map[c] == cat]
            cat_block[cat_label(cat)] = {
                "index": fmt_series(r["cat_index"][cat], idx),
                "indicators": {short_label(c, desc_map): fmt_series(r["z"][c], idx) for c in cols},
            }

        versions[ver] = {
            "dates": dates,
            "latest": ref.strftime("%Y-%m") if ref is not None else None,
            "gdp": {
                "index": fmt_series(r["gdp"], idx),
                "contrib": {cat_label(c): fmt_series(r["gdp_contrib"][c], idx) for c in gdp_cats},
            },
            "lei": {"index": fmt_series(r["lei"], idx)},
            "categories": cat_block,
        }
    return versions


def build_payload(all_results, cat_map, desc_map):
    countries = {}
    for cc, results in all_results.items():
        countries[cc] = {
            "label": country_label(cc, "en"),
            "label_kr": country_label(cc, "kr"),
            "versions": build_country_versions(results, cat_map, desc_map),
        }
    default = DEFAULT_COUNTRY if DEFAULT_COUNTRY in countries else next(iter(countries))
    return {"default": default, "countries": countries}


# ============================================================
# 7. HTML 대시보드 (국가 드롭다운 활성)
# ============================================================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Activity Index Dashboard</title>
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
.panel .upd{font-size:11px;font-weight:600;color:var(--up);height:15px;line-height:15px;margin:-5px 0 3px}
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
    <h1 id="page-title">Activity Index</h1>
    <p class="sub">Category PCA · Equal-Weight GDP Proxy · YoY half-life 24m / Momentum 3m3m half-life 12m · EWM z-score · generated __NOW__</p>
  </div>
  <select class="country-select" id="country-filter"></select>
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
      <span id="drill-ref" style="color:var(--muted2);font-size:12px"></span>
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
const CC_ORDER = ['US','AU','CA','DE','JP','UK'];

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

// ---------- 국가 선택 ----------
const ccSel=document.getElementById('country-filter');
const codes=Object.keys(DATA.countries);
const ordered=CC_ORDER.filter(c=>codes.includes(c)).concat(codes.filter(c=>!CC_ORDER.includes(c)));
ordered.forEach(cc=>{const o=document.createElement('option');o.value=cc;
o.textContent=(DATA.countries[cc].label_kr||cc)+' ('+cc+')';ccSel.appendChild(o);});
let CC=(DATA.default&&codes.includes(DATA.default))?DATA.default:ordered[0];
ccSel.value=CC;

let VY=null,VM=null;   // 현재 국가의 YoY / Momentum
const EMPTY={dates:[],gdp:{index:[],contrib:{}},lei:{index:[]},categories:{}};
function setCountry(cc){CC=cc;
const vs=DATA.countries[CC].versions;
VY=vs['YoY']||EMPTY;
VM=vs['Momentum']||EMPTY;
document.getElementById('page-title').textContent=(DATA.countries[CC].label||CC)+' — Activity Index';}

// ---- 기간 선택 ----
const rangeSel=document.getElementById('range-select');
const leiRangeSel=document.getElementById('lei-range-select');
const RANGE_OPTS=[[1,'1M'],[3,'3M'],[6,'6M'],[12,'12M'],[24,'2Y'],[36,'3Y'],[48,'4Y'],[60,'5Y'],[120,'10Y'],[240,'20Y']];
function buildRange(sel,total){const prev=sel.value;sel.innerHTML='';
const avail=RANGE_OPTS.filter(([m])=>m<=total);
const list=avail.length?avail:[[total,'전체']];
list.forEach(([m,lab])=>{const o=document.createElement('option');o.value=m;o.textContent=lab;sel.appendChild(o);});
const oa=document.createElement('option');oa.value='all';oa.textContent='전체';sel.appendChild(oa);
const vals=[...sel.options].map(o=>o.value);
if(prev&&vals.includes(prev)){sel.value=prev;}
else{sel.value=list.some(([m])=>m===36)?'36':String(list[list.length-1][0]);}}
function sliceLast(a,n){return n==='all'?a:a.slice(-n);}
function sliceObj(o,n){const r={};Object.keys(o).forEach(k=>r[k]=sliceLast(o[k],n));return r;}

function renderMain(){const n=rangeSel.value==='all'?'all':parseInt(rangeSel.value);
contribChart('gdp-yoy',sliceLast(VY.dates,n),sliceObj(VY.gdp.contrib,n),sliceLast(VY.gdp.index,n),'lg-yoy');
contribChart('gdp-mom',sliceLast(VM.dates,n),sliceObj(VM.gdp.contrib,n),sliceLast(VM.gdp.index,n),'lg-mom');}
rangeSel.onchange=renderMain;

function renderLeiMain(){const n=leiRangeSel.value==='all'?'all':parseInt(leiRangeSel.value);
lineChart(document.getElementById('lei-yoy'),sliceLast(VY.dates,n),[sliceLast(VY.lei.index,n)],['#1a7a4c']);
lineChart(document.getElementById('lei-mom'),sliceLast(VM.dates,n),[sliceLast(VM.lei.index,n)],['#1a7a4c']);}
leiRangeSel.onchange=renderLeiMain;

// 카테고리 패널 (YoY 검정 / Momentum 주황)
function renderCatGrid(){const catGrid=document.getElementById('cat-grid');catGrid.innerHTML='';
Object.keys(VY.categories).filter(c=>c!=='LEI').forEach(cat=>{
const p=document.createElement('div');p.className='panel';
p.innerHTML=`<div class="t">${cat} <span style="color:var(--muted2);font-weight:400">— YoY(검정) / Momentum(주황)</span></div><canvas height="170"></canvas>`;
catGrid.appendChild(p);
lineChart(p.querySelector('canvas'),VY.dates,
[VY.categories[cat].index, VM.categories[cat]?VM.categories[cat].index:[]],['#1a1c1f','#f28e2b']);});}

// 드릴다운
const sel=document.getElementById('cat-select');
let drillVer='YoY';
function buildDrillSelect(){const prev=sel.value;sel.innerHTML='';
const cats=Object.keys(VY.categories).filter(c=>c!=='LEI');
cats.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o);});
if(prev&&cats.includes(prev))sel.value=prev;}
function renderDrill(){const V=drillVer==='YoY'?VY:VM;const cat=sel.value;
const g=document.getElementById('drill-grid');g.innerHTML='';
// 최신 관측월 위치 — 그 달에 값이 있는 지표만 'updated'
const li=V.latest?V.dates.indexOf(V.latest):V.dates.length-1;
const rf=document.getElementById('drill-ref');
if(rf)rf.textContent=V.latest?`기준 ${V.latest}`:'';
if(!cat||!V.categories[cat])return;
const ind=V.categories[cat].indicators;
Object.keys(ind).forEach((name,i)=>{
const upd=(li>=0&&ind[name][li]!=null)?'updated':'';
const p=document.createElement('div');p.className='panel';
p.innerHTML=`<div class="t">${name}</div><div class="upd">${upd}</div><canvas height="130"></canvas>`;
g.appendChild(p);
lineChart(p.querySelector('canvas'),V.dates,[ind[name]],[COLORS[i%COLORS.length]]);});}
sel.onchange=renderDrill;
document.querySelectorAll('.vbtn:not(.lei-vbtn)').forEach(b=>{b.onclick=()=>{
document.querySelectorAll('.vbtn:not(.lei-vbtn)').forEach(x=>x.classList.remove('active'));
b.classList.add('active');drillVer=b.dataset.ver;renderDrill();};});

// LEI 지표 그리드
let leiVer='YoY';
function renderLei(){const V=leiVer==='YoY'?VY:VM;
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

// ---------- 전체 렌더 (국가 변경 시 재실행) ----------
function renderAll(){
buildRange(rangeSel,Math.max(VY.dates.length,VM.dates.length));
buildRange(leiRangeSel,Math.max(VY.dates.length,VM.dates.length));
buildDrillSelect();
renderMain();renderCatGrid();renderDrill();
renderLeiMain();renderLei();}

ccSel.onchange=()=>{setCountry(ccSel.value);renderAll();};
setCountry(CC);
renderAll();

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
            .replace("__NOW__", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False)))
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"대시보드 저장: {OUT_HTML}")


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("Country PCA / GDP Proxy (AU CA DE JP UK US)")
    print("=" * 60)
    wide, cat_map, rule_map, desc_map, ctry_map = load_data()
    print(f"데이터: {wide.shape[0]}행 x {wide.shape[1]}지표 "
          f"({wide.index[0]:%Y-%m} ~ {wide.index[-1]:%Y-%m})")

    # 국가별 컬럼 분리 (드롭다운 순서 = COUNTRIES 순서, 그 외 코드는 뒤에)
    present = sorted({cc for c in wide.columns for cc in ctry_map[c]})
    ordered = [cc for cc in COUNTRIES if cc in present] + [cc for cc in present if cc not in COUNTRIES]
    unknown = [cc for cc in present if cc not in COUNTRIES]
    if unknown:
        print(f"[WARN] COUNTRIES에 정의 안 된 국가코드 발견(코드 그대로 표기): {unknown}")

    all_results = {}
    for cc in ordered:
        cols = [c for c in wide.columns if cc in ctry_map[c]]
        print(f"\n### {cc} ({country_label(cc)}) — 지표 {len(cols)}개")
        if len(cols) < 2:
            print(f"  [WARN] {cc}: 지표 부족 — 국가 스킵")
            continue
        sub = wide[cols].dropna(how="all")
        results = {}
        for ver, cfg in VERSIONS.items():
            print(f"[{cc}·{ver}] halflife={cfg['halflife']}, mode={cfg['mode']}")
            r = run_version(sub, cat_map, rule_map, cfg["halflife"], cfg["mode"], tag=f"{cc}·")
            g = r["gdp"].dropna()
            if len(g):
                nv = r["gdp_navail"].get(g.index[-1], r["gdp_ncats"])
                print(f"  GDP proxy: {g.index[0]:%Y-%m} ~ {g.index[-1]:%Y-%m} "
                      f"(mean {g.mean():.2f}, std {g.std():.2f}, "
                      f"마지막달 카테고리 {int(nv)}/{r['gdp_ncats']})")
            if len(r["lei"].dropna()):
                l = r["lei"].dropna()
                print(f"  LEI      : {l.index[0]:%Y-%m} ~ {l.index[-1]:%Y-%m}")
            results[ver] = r
        # GDP·LEI 둘 다 빈 국가는 대시보드에서 제외
        if all(len(r["gdp"].dropna()) == 0 and len(r["lei"].dropna()) == 0 for r in results.values()):
            print(f"  [WARN] {cc}: 산출된 지수 없음 — 국가 스킵")
            continue
        all_results[cc] = results

    if not all_results:
        raise SystemExit("[중단] 산출된 국가가 하나도 없습니다.")

    save_excel(all_results, cat_map, desc_map)
    save_dashboard(build_payload(all_results, cat_map, desc_map))
    print(f"\n완료. 국가: {list(all_results.keys())}")
    return all_results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        DATA_FILE = Path(sys.argv[1])
    main()
