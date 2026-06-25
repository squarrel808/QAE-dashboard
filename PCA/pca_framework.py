import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================
HALF_LIFE = 12  # EWM half-life (months)
MA_WINDOW = 3   # Moving average window for smoothing (MoM version)

# 그룹 정의 — 여기에 실제 컬럼명을 매핑
# key = 그룹명, value = 해당 그룹에 속하는 컬럼명 리스트
GROUPS = {
    'Consumer':      [],  # e.g. ['retail_sales', 'consumer_sentiment', 'pce_services', ...]
    'Investment':    [],  # e.g. ['building_permits', 'capex_orders', ...]
    'Export':        [],  # e.g. ['exports', 'trade_balance', ...]
    'Employment':    [],  # e.g. ['employment_change', 'unemployment_rate', 'hours_worked', ...]
    'Production':    [],  # e.g. ['mfg_pmi', 'services_pmi', 'industrial_production', ...]
    'Housing':       [],  # e.g. ['housing_starts', 'home_prices', ...]
    'Financial':     [],  # e.g. ['yield_spread', 'credit_growth', 'm2', ...]
}

# 지표별 변환 방식 정의 (MoM 버전용)
# 'growth' = log-difference (mom 성장률), 'level' = 그대로 (PMI 같은 서베이 지표)
TRANSFORM = {
    # 예시:
    # 'retail_sales': 'growth',
    # 'mfg_pmi': 'level',
    # 'unemployment_rate': 'growth',  # 또는 'diff' (차분)
}

# 부호 조정용 — 경기 좋을 때 올라가는 대표 지표 (그룹별 1개)
# PC1 부호가 이 지표와 양의 상관이 되도록 조정
SIGN_REFERENCE = {
    # 예시:
    # 'Consumer': 'retail_sales',
    # 'Employment': 'employment_change',
}


# ============================================================
# STEP 1: 데이터 전처리
# ============================================================
def load_data(filepath):
    """CSV 로드. 첫 컬럼 = 날짜, 나머지 = 지표"""
    df = pd.read_csv(filepath, parse_dates=[0], index_col=0)
    df = df.sort_index()
    df = df.apply(pd.to_numeric, errors='coerce')
    return df


def transform_mom(df, transform_map):
    """지표별 MoM 변환. growth=log차분, level=그대로, diff=단순차분"""
    result = pd.DataFrame(index=df.index)
    for col in df.columns:
        t = transform_map.get(col, 'growth')  # default = growth
        if t == 'growth':
            result[col] = np.log(df[col]).diff() * 100  # % 단위
        elif t == 'diff':
            result[col] = df[col].diff()
        elif t == 'level':
            result[col] = df[col]
    return result.dropna(how='all')


def standardize(df):
    """z-score 표준화 (전체 기간 mean=0, std=1)"""
    return (df - df.mean()) / df.std()


# ============================================================
# STEP 2: Time-Varying PCA (EWM Correlation)
# ============================================================
def tv_pca(std_df, half_life, sign_ref_col=None):
    """
    Time-Varying PCA (BlackRock 방식)
    
    Parameters:
        std_df: 표준화된 DataFrame (행=시점, 열=지표)
        half_life: EWM 반감기
        sign_ref_col: 부호 조정용 기준 컬럼명
    
    Returns:
        pc1_ts: PC1 시계열 (Series)
        loadings_df: 시점별 loading (DataFrame)
        contrib_df: 시점별 contribution (DataFrame)
    """
    n_col = len(std_df.columns)
    pc1_list = []
    loadings_list = []
    
    for i in range(n_col, len(std_df)):  # 최소 n_col 시점부터 시작
        # EWM Correlation Matrix
        corr_block = std_df.iloc[:i+1].ewm(halflife=half_life, adjust=False).corr()
        corr_matrix = corr_block.iloc[-n_col:, :].values.reshape(n_col, n_col)
        
        if np.isnan(corr_matrix).any():
            pc1_list.append(np.nan)
            loadings_list.append(np.full(n_col, np.nan))
            continue
        
        # PCA (1 component)
        pca = PCA(n_components=1)
        pca.fit(corr_matrix)
        
        loading = pca.components_[0]
        pc1_value = std_df.iloc[i].values.dot(loading)
        
        loadings_list.append(loading)
        pc1_list.append(pc1_value)
    
    # DataFrame으로 변환
    idx = std_df.index[n_col:]
    pc1_ts = pd.Series(pc1_list, index=idx, name='PC1')
    loadings_df = pd.DataFrame(loadings_list, index=idx, columns=std_df.columns)
    
    # 부호 조정
    if sign_ref_col and sign_ref_col in std_df.columns:
        ref = std_df[sign_ref_col].loc[idx]
        if ref.corr(pc1_ts) < 0:
            pc1_ts *= -1
            loadings_df *= -1
    
    # Contribution = z-score × loading
    contrib_df = std_df.loc[idx] * loadings_df
    
    return pc1_ts, loadings_df, contrib_df


# ============================================================
# STEP 3: 2단계 PCA
# ============================================================
def run_two_stage_pca(df_raw, groups, transform_map, half_life, sign_refs, mode='mom'):
    """
    2단계 PCA 실행
    
    Parameters:
        df_raw: 원본 데이터 DataFrame
        groups: 그룹 딕셔너리
        transform_map: 변환 방식 딕셔너리
        half_life: EWM 반감기
        sign_refs: 부호 조정 기준 딕셔너리
        mode: 'mom' = MoM 성장률 버전, 'level' = 레벨 z-score 버전
    
    Returns:
        results: 딕셔너리 (그룹별 + 전체 결과)
    """
    results = {'stage1': {}, 'stage2': {}}
    
    # --- 전처리 ---
    if mode == 'mom':
        df_transformed = transform_mom(df_raw, transform_map)
    else:  # level
        df_transformed = df_raw.copy()
    
    df_std = standardize(df_transformed.dropna())
    
    # --- Stage 1: 그룹별 PCA ---
    group_pc1s = {}
    
    for group_name, cols in groups.items():
        valid_cols = [c for c in cols if c in df_std.columns]
        if len(valid_cols) < 2:
            print(f"[WARN] {group_name}: 지표 {len(valid_cols)}개 — PCA 불가, skip")
            continue
        
        group_df = df_std[valid_cols].dropna()
        sign_ref = sign_refs.get(group_name, None)
        
        pc1, loadings, contrib = tv_pca(group_df, half_life, sign_ref)
        
        results['stage1'][group_name] = {
            'pc1': pc1,
            'loadings': loadings,
            'contrib': contrib,
            'indicators': valid_cols,
        }
        group_pc1s[group_name] = pc1
    
    # --- Stage 2: 전체 PCA ---
    if len(group_pc1s) < 2:
        print("[ERROR] Stage 2 PCA 불가 — 유효 그룹이 2개 미만")
        return results
    
    pc1_combined = pd.DataFrame(group_pc1s).dropna()
    pc1_combined_std = standardize(pc1_combined)
    
    # 전체 PCA에서 부호 기준: 첫 번째 그룹
    first_group = list(group_pc1s.keys())[0]
    total_pc1, total_loadings, total_contrib = tv_pca(
        pc1_combined_std, half_life, sign_ref_col=first_group
    )
    
    results['stage2'] = {
        'pc1': total_pc1,
        'loadings': total_loadings,
        'contrib': total_contrib,
        'group_names': list(group_pc1s.keys()),
    }
    
    return results


# ============================================================
# STEP 4: MA3 적용 (MoM 버전용)
# ============================================================
def apply_ma3(results):
    """MoM 버전 결과에 MA3 smoothing 적용"""
    smoothed = {'stage1': {}, 'stage2': {}}
    
    # Stage 1
    for group_name, data in results['stage1'].items():
        smoothed['stage1'][group_name] = {
            'pc1': data['pc1'].rolling(MA_WINDOW).mean(),
            'contrib': data['contrib'].rolling(MA_WINDOW).mean(),
            'loadings': data['loadings'],  # loading은 smoothing 안 함
            'indicators': data['indicators'],
        }
    
    # Stage 2
    if results['stage2']:
        smoothed['stage2'] = {
            'pc1': results['stage2']['pc1'].rolling(MA_WINDOW).mean(),
            'contrib': results['stage2']['contrib'].rolling(MA_WINDOW).mean(),
            'loadings': results['stage2']['loadings'],
            'group_names': results['stage2']['group_names'],
        }
    
    return smoothed


# ============================================================
# STEP 5: 시각화
# ============================================================
COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
          '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
          '#aec7e8', '#ffbb78', '#98df8a', '#ff9896']


def plot_contribution(pc1, contrib_df, title, col_labels=None, ax=None):
    """Contribution 스택 차트 + PC1 라인"""
    if ax is None:
        fig, ax = plt.subplots(figsize=(14, 5))
    
    idx = contrib_df.index
    cols = col_labels if col_labels else contrib_df.columns
    
    # 양수/음수 분리하여 스택
    pos_bottom = np.zeros(len(idx))
    neg_bottom = np.zeros(len(idx))
    
    for i, col in enumerate(contrib_df.columns):
        vals = contrib_df[col].values
        color = COLORS[i % len(COLORS)]
        label = cols[i] if col_labels else col
        
        pos_vals = np.where(vals > 0, vals, 0)
        neg_vals = np.where(vals < 0, vals, 0)
        
        ax.bar(idx, pos_vals, bottom=pos_bottom, width=25, color=color, label=label, alpha=0.7)
        ax.bar(idx, neg_vals, bottom=neg_bottom, width=25, color=color, alpha=0.7)
        
        pos_bottom += pos_vals
        neg_bottom += neg_vals
    
    # PC1 라인
    ax.plot(idx, pc1.loc[idx], color='black', linewidth=2, label='PC1')
    ax.axhline(y=0, color='gray', linewidth=0.5, linestyle='--')
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.set_ylabel('Level')
    ax.legend(loc='upper left', fontsize=7, ncol=min(len(contrib_df.columns), 4))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    return ax


def plot_all_results(results, mode_label=''):
    """전체 결과 시각화"""
    stage1 = results['stage1']
    stage2 = results['stage2']
    n_groups = len(stage1)
    
    if n_groups == 0:
        print("시각화할 그룹 없음")
        return
    
    # --- Stage 1: 그룹별 차트 ---
    ncols = 2
    nrows = (n_groups + 1) // 2
    fig1, axes1 = plt.subplots(nrows, ncols, figsize=(18, 5 * nrows))
    fig1.suptitle(f'Canada Activity Indicators — Stage 1 ({mode_label})', 
                  fontsize=16, fontweight='bold', y=1.02)
    axes1 = axes1.flatten()
    
    for i, (group_name, data) in enumerate(stage1.items()):
        plot_contribution(
            data['pc1'], data['contrib'],
            f'Canada {group_name} Indicator',
            ax=axes1[i]
        )
    
    # 빈 axes 숨기기
    for j in range(i + 1, len(axes1)):
        axes1[j].set_visible(False)
    
    fig1.tight_layout()
    fig1.savefig(f'/home/claude/stage1_{mode_label}.png', dpi=150, bbox_inches='tight')
    plt.close(fig1)
    
    # --- Stage 2: 전체 경기 차트 ---
    if stage2:
        fig2, ax2 = plt.subplots(figsize=(16, 6))
        plot_contribution(
            stage2['pc1'], stage2['contrib'],
            f'Canada Overall Activity Index ({mode_label})',
            col_labels=stage2.get('group_names'),
            ax=ax2
        )
        fig2.tight_layout()
        fig2.savefig(f'/home/claude/stage2_{mode_label}.png', dpi=150, bbox_inches='tight')
        plt.close(fig2)


def plot_loadings(results, mode_label=''):
    """Stage 2 loading 시계열"""
    stage2 = results['stage2']
    if not stage2:
        return
    
    fig, ax = plt.subplots(figsize=(16, 6))
    loadings = stage2['loadings']
    group_names = stage2.get('group_names', loadings.columns)
    
    for i, col in enumerate(loadings.columns):
        label = group_names[i] if i < len(group_names) else col
        ax.plot(loadings.index, loadings[col], label=label, 
                color=COLORS[i % len(COLORS)], linewidth=1.5)
    
    ax.axhline(y=0, color='gray', linewidth=0.5, linestyle='--')
    ax.set_title(f'Stage 2 Loadings Over Time ({mode_label})', fontsize=13, fontweight='bold')
    ax.set_ylabel('Loading')
    ax.legend(loc='best', fontsize=9)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.tight_layout()
    fig.savefig(f'/home/claude/loadings_{mode_label}.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


# ============================================================
# STEP 6: 검증
# ============================================================
def validate(results, gdp_growth=None):
    """PC1 검증 — explained variance, GDP 상관"""
    stage2 = results['stage2']
    if not stage2:
        return
    
    pc1 = stage2['pc1']
    print(f"  PC1 시계열 기간: {pc1.index[0].strftime('%Y-%m')} ~ {pc1.index[-1].strftime('%Y-%m')}")
    print(f"  PC1 mean: {pc1.mean():.3f}, std: {pc1.std():.3f}")
    
    if gdp_growth is not None:
        # 분기 GDP와 월간 PC1 매칭 (분기 마지막 월 기준)
        quarterly_pc1 = pc1.resample('QE').mean()
        merged = pd.concat([quarterly_pc1, gdp_growth], axis=1).dropna()
        if len(merged) > 4:
            corr = merged.iloc[:, 0].corr(merged.iloc[:, 1])
            print(f"  PC1 vs GDP 성장률 상관: {corr:.3f}")


# ============================================================
# MAIN
# ============================================================
def main(data_path, gdp_path=None):
    """
    메인 실행
    
    Parameters:
        data_path: 지표 데이터 CSV 경로
        gdp_path: (선택) 분기 GDP 성장률 CSV 경로 (검증용)
    """
    print("=" * 60)
    print("Canada Economic Activity PCA Framework")
    print("=" * 60)
    
    # 데이터 로드
    df_raw = load_data(data_path)
    print(f"\n데이터: {df_raw.shape[0]}행 × {df_raw.shape[1]}열")
    print(f"기간: {df_raw.index[0].strftime('%Y-%m')} ~ {df_raw.index[-1].strftime('%Y-%m')}")
    print(f"컬럼: {list(df_raw.columns)}")
    
    gdp = None
    if gdp_path:
        gdp = load_data(gdp_path).iloc[:, 0]
    
    # === Version 1: MoM + MA3 ===
    print("\n" + "=" * 60)
    print("Version 1: MoM Growth Rate + MA3")
    print("=" * 60)
    
    results_mom = run_two_stage_pca(
        df_raw, GROUPS, TRANSFORM, HALF_LIFE, SIGN_REFERENCE, mode='mom'
    )
    results_mom_ma3 = apply_ma3(results_mom)
    
    print("\n[검증 — MoM MA3]")
    validate(results_mom_ma3, gdp)
    plot_all_results(results_mom_ma3, mode_label='MoM_MA3')
    plot_loadings(results_mom_ma3, mode_label='MoM_MA3')
    
    # === Version 2: Level z-score ===
    print("\n" + "=" * 60)
    print("Version 2: Level Z-Score")
    print("=" * 60)
    
    results_level = run_two_stage_pca(
        df_raw, GROUPS, TRANSFORM, HALF_LIFE, SIGN_REFERENCE, mode='level'
    )
    
    print("\n[검증 — Level]")
    validate(results_level, gdp)
    plot_all_results(results_level, mode_label='Level')
    plot_loadings(results_level, mode_label='Level')
    
    print("\n" + "=" * 60)
    print("완료. 결과 파일:")
    print("  stage1_MoM_MA3.png / stage2_MoM_MA3.png / loadings_MoM_MA3.png")
    print("  stage1_Level.png / stage2_Level.png / loadings_Level.png")
    print("=" * 60)
    
    return results_mom_ma3, results_level


# ============================================================
# 사용법
# ============================================================
"""
1. 위의 GROUPS 딕셔너리에 실제 컬럼명 매핑
2. TRANSFORM 딕셔너리에 지표별 변환 방식 지정
3. SIGN_REFERENCE에 그룹별 부호 기준 지표 지정
4. CSV 데이터 준비 (첫 컬럼=날짜, 나머지=지표)
5. 실행:

    results_mom, results_level = main('canada_indicators.csv', 'canada_gdp.csv')

CSV 예시:
    date,retail_sales,consumer_sentiment,mfg_pmi,employment_change,...
    2010-01-01,45000,98.5,52.3,15000,...
    2010-02-01,45200,97.8,51.9,12000,...
    ...
"""

if __name__ == '__main__':
    # 데이터 경로를 지정하고 실행
    # results_mom, results_level = main('/path/to/data.csv')
    print("GROUPS, TRANSFORM, SIGN_REFERENCE 설정 후 main() 호출하세요.")
