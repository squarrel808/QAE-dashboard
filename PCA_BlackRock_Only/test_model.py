"""Verify only the intended universe changes relative to PCA II."""
import json,sys
from pathlib import Path
import pandas as pd,numpy as np

B=Path(__file__).resolve().parent;S=B.parent/'PCA_Four_Axis'
sys.path.insert(0,str(S));from build import core,AXES,MAPPING,align_uk_period_ends,standardize,fixed_pca
d=json.loads((B/'dashboard_data.json').read_text(encoding='utf8'))
assert d['universe']=='blackrock_reference_only'
assert set(d['countries'])=={'US','UK','DE','CA','JP','AU'}
coverage=pd.read_csv(B/'blackrock_coverage.csv')
accepted=coverage[coverage.action.isin(['existing','added','duplicate'])]
expected=set(zip(accepted.country,accepted.pk))
actual={(r['country'],r['pk']) for r in d['indicators']}
assert actual==expected and len(actual)==len(d['indicators'])
assert not any(r['previous_group']=='C_labor' for r in d['indicators'])
assert {r['pk'] for r in d['indicators'] if r['country']=='UK' and r['axis']=='Consumer'}==set(accepted[(accepted.country=='UK')&(accepted.included_axis=='Consumer')].pk)
assert d['estimation']['constraint']=='unrestricted' and d['estimation']['halflife'] is None
loads=pd.read_csv(B/'loadings.csv')
assert (loads.groupby(['country','axis','indicator']).loading.nunique()==1).all()
x=pd.read_csv(B/'indices.csv',parse_dates=['date'])
ledger=json.loads((S/'annual_weights.json').read_text(encoding='utf8'))['records']
for cc,c in d['countries'].items():
    assert c['missing_axes']==(['Housing'] if cc in ['DE','JP'] else [])
    y=x[(x.country==cc)&(x.version=='YoY')].set_index('date')
    m=x[(x.country==cc)&(x.version=='Momentum')].set_index('date')
    active=c['active_axes'];cols=['headline',*AXES,*['contrib_'+a for a in AXES]]
    # Published exports start in 2005; the first five Momentum observations use
    # valid 2004 history that is intentionally outside this CSV's display range.
    np.testing.assert_allclose(m[cols].iloc[5:],y[cols].rolling(3,min_periods=3).mean().diff(3).iloc[5:],atol=1e-10,equal_nan=True)
    np.testing.assert_allclose(y.headline,y[['contrib_'+a for a in active]].sum(axis=1,min_count=len(active)),atol=1e-10,equal_nan=True)
    for a in AXES:
        if a not in active:assert y[a].isna().all() and y['contrib_'+a].isna().all()
        valid=y.headline.notna()
        np.testing.assert_allclose(y.loc[valid,'contrib_'+a],y.loc[valid,a]*y.loc[valid,'weight_'+a],equal_nan=True,atol=1e-10)
    for r in c['annual_weights']:
        if (key:=f"{cc}:{r['year']}") in ledger:assert r['weights']==ledger[key]['weights']
    assert all(v['latest'] for v in c['versions'].values())

# Reproduce UK's Consumer directly from raw data, outside the variant builder.
meta={}
for path in [S/'source/metadata.json',S/'metadata.json',S/'blackrock_source/metadata.json']:meta.update(json.loads(path.read_text(encoding='utf8')))
raw=pd.concat([pd.read_csv(S/'source/raw_haver.csv'),pd.read_csv(S/'values.csv'),pd.read_csv(S/'blackrock_source/values.csv')]).drop_duplicates(['pk','date'],keep='last')
review=json.loads((B.parent/'outputs/gdp_expenditure_review/report_data.json').read_text(encoding='utf8'))
wide,specs,_=core.prepare(review,meta,raw);wide,_=align_uk_period_ends(wide,specs)
sp=[r for r in d['indicators'] if r['country']=='UK' and r['axis']=='Consumer']
z=standardize(pd.DataFrame({r['pk']:core.transform(wide[r['pk']],r,'YoY') for r in sp}))
score,loading,_,_,_=fixed_pca(z)
v=d['countries']['UK']['versions']['YoY'];last=pd.Timestamp(v['latest'])+pd.offsets.MonthEnd(0)
assert abs(score[last]-v['blocks']['Consumer'][v['dates'].index(v['latest'])])<1e-10
for r in sp:
    expected=z[r['pk']].reindex(pd.PeriodIndex(d['input_series']['UK']['dates'],freq='M').to_timestamp('M'))
    np.testing.assert_allclose(expected,np.array(d['input_series']['UK']['series'][r['pk']]['zscore'],dtype=float),atol=5.1e-7,equal_nan=True)
    assert abs(loading.at[last,r['pk']]-r['loading'])<1e-10
print('PASS: reference-only membership; no labor additions; same transformations, full-sample standardization, fixed unrestricted PCA, January weights and post-PCA momentum; missing sectors not redistributed')
