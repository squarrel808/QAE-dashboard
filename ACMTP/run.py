import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from scipy.interpolate import CubicSpline
import warnings
import re

warnings.filterwarnings("ignore")


# ============================================================
# CONFIG
# ============================================================

DATA_FILE = r"C:\Users\USER\OneDrive\문서\QAE-dashboard\ACMTP\zero coupon.xlsx"
OUTPUT_DIR = r"C:\Users\USER\OneDrive\문서\QAE-dashboard\ACMTP\outputs_daily_tp"

N_PCS = 5
MAX_MAT_MONTHS = 120
TP_MATURITIES = [24, 60, 120]      # 2Y, 5Y, 10Y
ROLLING_WINDOW_MONTHS = 240        # 20년 rolling
MIN_MONTHLY_OBS = 120              # 최소 10년 이상은 있어야 추정
TP_ABS_CAP_BP = 1000               # 비정상 TP 제거 기준


# ============================================================
# 1. 데이터 로딩
# ============================================================

def parse_maturity_months(col_name):
    """
    컬럼명을 월 단위 만기로 변환.
    Bloomberg 티커 지원: 'G0025Z 3M BLC2 Curncy' -> 3, '... 1Y ...' -> 12, '... 10Y ...' -> 120
    구형 형식도 지원: '3 M' -> 3, '10 Y' -> 120
    헤더 어디든 '숫자+(공백)+M/Y' 토큰을 찾아 만기로 사용.
    """
    s = str(col_name).strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*([MmYy])\b", s)

    if not m:
        return None

    num = float(m.group(1))
    unit = m.group(2).upper()

    if unit == "M":
        return int(round(num))

    if unit == "Y":
        return int(round(num * 12))

    return None


def load_country(filepath, sheet_name):
    """
    국가별 시트 로드.
    반환:
        index   = 날짜
        columns = 만기 월수, 예: 1, 3, 6, 12, 24, ...
        values  = 연율 %, 예: 4.25
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name, header=9)

    date_col = df.columns[0]
    raw_dates = df[date_col]
    # 일부 구간은 날짜 서식이 안 먹어 엑셀 일련번호(정수, 예: 46160)로 저장됨.
    # to_datetime은 이를 1970년+나노초로 오해하므로, 숫자형 셀만 골라 엑셀 기준일로 변환.
    is_serial = raw_dates.map(
        lambda x: isinstance(x, (int, float, np.integer, np.floating))
        and not isinstance(x, bool)
        and pd.notna(x)
    )
    dt_direct = pd.to_datetime(raw_dates, errors="coerce")
    serial_num = pd.to_numeric(raw_dates.where(is_serial), errors="coerce")
    # 정상 엑셀 일련번호 범위만 (1900~2100년 ≈ 1~73000) 변환, 그 외엔 NaT
    serial_num = serial_num.where((serial_num > 0) & (serial_num < 100000))
    is_serial = serial_num.notna()
    dt_serial = pd.to_datetime(serial_num, unit="D", origin="1899-12-30")
    df[date_col] = dt_direct.where(~is_serial, dt_serial)
    df = df.dropna(subset=[date_col])
    df = df.sort_values(date_col)

    mat_map = {}

    for col in df.columns[1:]:
        m = parse_maturity_months(col)

        if m is not None and m > 0:
            mat_map[col] = m

    yield_cols = list(mat_map.keys())

    y = df[yield_cols].apply(pd.to_numeric, errors="coerce")
    y.columns = [mat_map[c] for c in yield_cols]
    y.index = df[date_col]

    y = y.loc[:, ~y.columns.duplicated()]
    y = y[sorted(y.columns)]
    y = y.dropna(how="all")

    return y


# ============================================================
# 2. 일간 금리곡선 보간
# ============================================================

def interpolate_to_monthly_grid(yields_raw, max_mat_months=MAX_MAT_MONTHS):
    """
    원본 만기들을 1M~120M 월별 grid로 보간.
    일간 데이터든 월간 데이터든, 만기 단위는 무조건 '월'로 유지.

    Input:
        columns = 관측 만기 월수, 예: 3, 6, 12, 24, 60, 120
        values  = annual %
    Output:
        columns = 1, 2, 3, ..., 120
        values  = annual %
    """
    mats_sparse = np.array(yields_raw.columns, dtype=float)

    actual_max = min(int(np.nanmax(mats_sparse)), max_mat_months)
    mats_full = np.arange(1, actual_max + 1, dtype=float)

    result = np.full((len(yields_raw), len(mats_full)), np.nan)

    for i in range(len(yields_raw)):
        y_row = yields_raw.iloc[i].values.astype(float)
        mask = np.isfinite(y_row)

        if mask.sum() < 4:
            continue

        cs = CubicSpline(
            mats_sparse[mask],
            y_row[mask],
            extrapolate=True
        )

        result[i, :] = cs(mats_full)

    out = pd.DataFrame(
        result,
        index=yields_raw.index,
        columns=mats_full.astype(int)
    )

    out = out.dropna(how="any")

    return out


def make_monthly_yields(yields_daily_grid):
    """
    일간 금리곡선에서 월말값 추출.
    """
    return yields_daily_grid.resample("ME").last().dropna(how="any")


# ============================================================
# 3. ACM 핵심 함수
# ============================================================

def compute_monthly_excess_returns(Y_monthly):
    """
    월간 초과수익률 계산.

    Y_monthly:
        shape = (T, N)
        values = monthly decimal yield
        columns implied = 1M, 2M, ..., N개월

    초과수익률 직관:
        n개월 채권을 한 달 들고 있으면 n-1개월 채권이 됨.
        그 보유수익률에서 1개월 단기금리를 뺀 값.
    """
    T, N = Y_monthly.shape
    mats = np.arange(1, N + 1)

    # log price: p_t(n) = -n * y_t(n)
    log_price = -Y_monthly * mats[None, :]

    rx_list = []
    rx_mats = []

    for n in range(2, N + 1):
        j_n = n - 1
        j_nm1 = n - 2

        # rx_{t+1}^{n} = p_{t+1}(n-1) - p_t(n) - r_t
        rx = (
            log_price[1:, j_nm1]
            - log_price[:-1, j_n]
            - Y_monthly[:-1, 0]
        )

        rx_list.append(rx)
        rx_mats.append(n)

    RX = np.column_stack(rx_list)

    return RX, np.array(rx_mats)


def estimate_lambda_acm(RX, X, v, Sigma):
    """
    ACM risk price 추정.

    RX:
        shape = (T-1, N_rx)
        월간 초과수익률

    X:
        shape = (T, K)
        PCA factor

    v:
        shape = (T-1, K)
        VAR residual, factor shock

    Sigma:
        shape = (K, K)
        factor shock covariance

    반환:
        lambda0: (K,)
        lambda1: (K, K)
    """
    K = X.shape[1]

    # RX 시점은 t=1..T-1에 해당
    X_lag = X[:-1]

    # 설명변수 = factor shock + lagged factor
    Z = np.hstack([v, X_lag])

    reg_rx = LinearRegression()
    reg_rx.fit(Z, RX)

    residual = RX - reg_rx.predict(Z)

    # beta: 초과수익률의 factor shock exposure
    beta = reg_rx.coef_[:, :K].T        # (K, N_rx)

    # c: 초과수익률의 state dependence
    c = reg_rx.coef_[:, K:].T           # (K, N_rx)

    # alpha/intercept
    alpha = reg_rx.intercept_           # (N_rx,)

    # 초과수익률 잔차분산 평균
    sigma2_rx = np.trace(residual.T @ residual) / residual.size

    # 0.5 * beta' Sigma beta
    beta_sigma_beta = np.array([
        beta[:, i].T @ Sigma @ beta[:, i]
        for i in range(beta.shape[1])
    ])

    # lambda0 추정 대상
    a = alpha + 0.5 * (beta_sigma_beta + sigma2_rx)

    # pinv로 안정성 확보
    BtB_inv = np.linalg.pinv(beta @ beta.T)

    lambda0 = BtB_inv @ beta @ a
    lambda1 = BtB_inv @ beta @ c.T

    return lambda0, lambda1


def bond_recursion(Phi_star, mu_star, Sigma, delta0, delta1, n_max):
    """
    월간 단위 채권가격 재귀.
    n_max=120이면 10Y까지.

    p_t(n) = A_n + B_n' X_t
    """
    K = len(delta1)

    A = np.zeros(n_max)
    B = np.zeros((K, n_max))

    A[0] = -delta0
    B[:, 0] = -delta1

    for n in range(n_max - 1):
        Bn = B[:, n]

        B[:, n + 1] = Phi_star.T @ Bn - delta1

        A[n + 1] = (
            A[n]
            + mu_star @ Bn
            + 0.5 * Bn @ Sigma @ Bn
            - delta0
        )

        # 폭발 방어
        if not np.isfinite(A[n + 1]) or not np.all(np.isfinite(B[:, n + 1])):
            A[n + 1:] = np.nan
            B[:, n + 1:] = np.nan
            break

    return A, B


def max_abs_eig(M):
    vals = np.linalg.eigvals(M)
    return float(np.max(np.abs(vals)))


# ============================================================
# 4. 월간 ACM 추정
# ============================================================

def fit_monthly_acm_window(yields_monthly_window):
    """
    월간 window 하나에 대해 ACM 파라미터 추정.

    yields_monthly_window:
        index   = month-end
        columns = 1, 2, ..., 120
        values  = annual %
    """
    if len(yields_monthly_window) < MIN_MONTHLY_OBS:
        return None

    # annual % -> monthly decimal
    Y = yields_monthly_window.values / 1200.0

    T, N = Y.shape

    if N < MAX_MAT_MONTHS:
        return None

    # 1) PCA
    scaler = StandardScaler()
    Y_scaled = scaler.fit_transform(Y)

    pca = PCA(n_components=N_PCS)
    X = pca.fit_transform(Y_scaled)

    # 2) VAR(1)
    X_t = X[1:]
    X_lag = X[:-1]

    reg_var = LinearRegression()
    reg_var.fit(X_lag, X_t)

    Phi = reg_var.coef_
    mu = reg_var.intercept_

    v = X_t - reg_var.predict(X_lag)
    Sigma = v.T @ v / len(v)

    # 3) short rate equation
    r_1m = Y[:, 0]

    reg_delta = LinearRegression()
    reg_delta.fit(X, r_1m)

    delta0 = float(reg_delta.intercept_)
    delta1 = reg_delta.coef_.astype(float)

    # 4) excess return
    RX, rx_mats = compute_monthly_excess_returns(Y)

    # 5) lambda
    lambda0, lambda1 = estimate_lambda_acm(RX, X, v, Sigma)

    # 6) recursion
    Phi_q = Phi - lambda1
    mu_q = mu - lambda0

    eig_P = max_abs_eig(Phi)
    eig_Q = max_abs_eig(Phi_q)

    A_q, B_q = bond_recursion(
        Phi_star=Phi_q,
        mu_star=mu_q,
        Sigma=Sigma,
        delta0=delta0,
        delta1=delta1,
        n_max=MAX_MAT_MONTHS,
    )

    A_rf, B_rf = bond_recursion(
        Phi_star=Phi,
        mu_star=mu,
        Sigma=Sigma,
        delta0=delta0,
        delta1=delta1,
        n_max=MAX_MAT_MONTHS,
    )

    params = {
        "scaler": scaler,
        "pca": pca,
        "Phi": Phi,
        "mu": mu,
        "Sigma": Sigma,
        "lambda0": lambda0,
        "lambda1": lambda1,
        "delta0": delta0,
        "delta1": delta1,
        "A_q": A_q,
        "B_q": B_q,
        "A_rf": A_rf,
        "B_rf": B_rf,
        "eig_Phi": eig_P,
        "eig_Phi_star": eig_Q,
        "window_start": yields_monthly_window.index[0],
        "window_end": yields_monthly_window.index[-1],
    }

    return params


# ============================================================
# 5. Daily projection
# ============================================================

def project_daily_to_monthly_pca(yields_daily_slice, params):
    """
    daily yield curve를 월간 PCA 좌표계에 projection.

    중요:
        scaler.fit_transform 아님.
        pca.fit_transform 아님.
        월간 window에서 fit된 scaler/pca로 transform만 해야 함.
    """
    scaler = params["scaler"]
    pca = params["pca"]

    # annual % -> monthly decimal
    Y_daily = yields_daily_slice.values / 1200.0

    Y_daily_scaled = scaler.transform(Y_daily)
    X_daily = pca.transform(Y_daily_scaled)

    X_daily = pd.DataFrame(
        X_daily,
        index=yields_daily_slice.index,
        columns=[f"PC{i+1}" for i in range(X_daily.shape[1])]
    )

    return X_daily


def compute_daily_tp_from_params(X_daily, params, maturities=TP_MATURITIES):
    """
    daily X_t를 월간 A/B에 넣어 daily TP 계산.
    """
    A_q = params["A_q"]
    B_q = params["B_q"]

    A_rf = params["A_rf"]
    B_rf = params["B_rf"]

    X = X_daily.values

    out = pd.DataFrame(index=X_daily.index)

    for n in maturities:
        idx = n - 1

        if idx >= len(A_q):
            continue

        y_q = -(
            A_q[idx] + X @ B_q[:, idx]
        ) / n * 1200.0

        y_rf = -(
            A_rf[idx] + X @ B_rf[:, idx]
        ) / n * 1200.0

        tp_pct = y_q - y_rf
        tp_bp = tp_pct * 100.0

        # 비정상값 제거
        tp_bp = np.where(
            np.isfinite(tp_bp) & (np.abs(tp_bp) <= TP_ABS_CAP_BP),
            tp_bp,
            np.nan
        )

        out[f"Yield_{n}M_pct"] = y_q
        out[f"RFR_{n}M_pct"] = y_rf
        out[f"TP_{n}M_pct"] = tp_pct
        out[f"TP_{n}M_bp"] = tp_bp

    out["eig_Phi"] = params["eig_Phi"]
    out["eig_Phi_star"] = params["eig_Phi_star"]
    out["param_date"] = params["window_end"]

    return out


# ============================================================
# 6. 전체 실행: 월간 추정 + 다음 달 daily 평가
# ============================================================

def run_monthly_estimation_daily_evaluation(yields_daily_grid):
    """
    전체 실행 함수.

    구조:
        1. 일간 금리곡선에서 월말 금리곡선 생성
        2. 월간 240개월 rolling window로 ACM 추정
        3. 해당 월말 파라미터를 다음 월 daily 데이터에 적용
        4. daily TP 산출
    """
    yields_monthly = make_monthly_yields(yields_daily_grid)

    month_ends = yields_monthly.index

    all_results = []
    diagnostics = []

    if len(month_ends) < ROLLING_WINDOW_MONTHS + 2:
        print("    데이터 부족: rolling window를 만들 수 없음")
        return None, None

    for i in range(ROLLING_WINDOW_MONTHS, len(month_ends) - 1):

        estimation_end = month_ends[i]
        estimation_start = month_ends[i - ROLLING_WINDOW_MONTHS + 1]

        monthly_window = yields_monthly.loc[
            estimation_start:estimation_end
        ]

        print(f"    추정 window: {estimation_start.date()} ~ {estimation_end.date()}")

        params = fit_monthly_acm_window(monthly_window)

        if params is None:
            print("      스킵: 파라미터 추정 실패")
            continue

        # 다음 월 daily 구간
        next_month_start = estimation_end + pd.offsets.BDay(1)
        next_month_end = month_ends[i + 1]

        daily_slice = yields_daily_grid.loc[
            next_month_start:next_month_end
        ]

        if daily_slice.empty:
            continue

        try:
            X_daily = project_daily_to_monthly_pca(daily_slice, params)
            daily_tp = compute_daily_tp_from_params(X_daily, params)

            all_results.append(daily_tp)

            diagnostics.append({
                "param_date": estimation_end,
                "window_start": params["window_start"],
                "window_end": params["window_end"],
                "eig_Phi": params["eig_Phi"],
                "eig_Phi_star": params["eig_Phi_star"],
                "n_daily_obs": len(daily_tp),
            })

            print(
                f"      적용 daily: {daily_slice.index[0].date()} ~ "
                f"{daily_slice.index[-1].date()}, "
                f"eigQ={params['eig_Phi_star']:.4f}"
            )

        except Exception as e:
            print(f"      daily 평가 실패: {e}")
            continue

    if not all_results:
        return None, None

    result = pd.concat(all_results).sort_index()
    diag = pd.DataFrame(diagnostics)

    return result, diag


# ============================================================
# 7. 국가별 실행
# ============================================================

def run_country(sheet_name):
    print("\n" + "=" * 70)
    print(f"국가/시트: {sheet_name}")
    print("=" * 70)

    # 1. 원본 로드
    y_raw = load_country(DATA_FILE, sheet_name)

    print(f"  원본 데이터: {len(y_raw)}개 일자, 만기={list(y_raw.columns)}")

    # 2. 1M~120M 월 단위 grid로 보간
    y_daily_grid = interpolate_to_monthly_grid(y_raw, MAX_MAT_MONTHS)

    print(
        f"  보간 후: {len(y_daily_grid)}개 일자, "
        f"{y_daily_grid.shape[1]}개 만기 "
        f"({y_daily_grid.columns.min()}M~{y_daily_grid.columns.max()}M)"
    )

    # 3. 월간 추정 + daily 평가
    result, diag = run_monthly_estimation_daily_evaluation(y_daily_grid)

    if result is None:
        print("  결과 없음")
        return None, None

    # 4. 저장
    out_path = Path(OUTPUT_DIR)
    out_path.mkdir(parents=True, exist_ok=True)

    result_file = out_path / f"daily_tp_{sheet_name}.csv"
    diag_file = out_path / f"diagnostics_{sheet_name}.csv"

    result.to_csv(result_file, encoding="utf-8-sig")
    diag.to_csv(diag_file, index=False, encoding="utf-8-sig")

    print(f"  저장 완료: {result_file}")
    print(f"  진단 저장: {diag_file}")

    # 5. 간단 진단 출력
    for col in result.columns:
        if col.endswith("_bp"):
            vals = result[col].dropna()

            if len(vals) == 0:
                continue

            print(
                f"  {col}: "
                f"mean={vals.mean():.1f}bp, "
                f"std={vals.std():.1f}bp, "
                f"last={vals.iloc[-1]:.1f}bp, "
                f"min={vals.min():.1f}bp, "
                f"max={vals.max():.1f}bp"
            )

    return result, diag


# ============================================================
# 8. main
# ============================================================

def main():
    print("=" * 70)
    print("월간 ACM 추정 + 일간 TP 평가")
    print("=" * 70)

    xls = pd.ExcelFile(DATA_FILE)
    sheets = xls.sheet_names

    print(f"시트 목록: {sheets}")

    all_10y = {}
    all_diag = {}

    for sheet in sheets:
        try:
            result, diag = run_country(sheet)

            if result is not None:
                tp_col = "TP_120M_bp"

                if tp_col in result.columns:
                    all_10y[sheet] = result[tp_col]

                all_diag[sheet] = diag

        except Exception as e:
            print(f"{sheet}: 오류 발생 - {e}")
            import traceback
            traceback.print_exc()

    # 전체 국가 10Y 합산 저장
    out_path = Path(OUTPUT_DIR)
    out_path.mkdir(parents=True, exist_ok=True)

    if all_10y:
        combined = pd.DataFrame(all_10y)
        combined_file = out_path / "daily_tp_all_countries_10Y_bp.csv"
        combined.to_csv(combined_file, encoding="utf-8-sig")

        print("\n" + "=" * 70)
        print("전체 국가 10Y TP 저장")
        print("=" * 70)
        print(combined_file)

        print("\n최근값:")
        for col in combined.columns:
            vals = combined[col].dropna()

            if len(vals) > 0:
                print(f"  {col}: {vals.iloc[-1]:.1f}bp")

    print("\n완료")


if __name__ == "__main__":
    main()