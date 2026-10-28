import json
from pathlib import Path
import pandas as pd,numpy as np
BASE=Path(__file__).resolve().parent
def main():
    from annual_weights import resolve_year,weight_panel,POLICY,OLD_POLICY,migrate_export_weights
    import copy
    # Jan 1 selection excludes quarters whose assumed publication is later.
    candidate=pd.DataFrame({'Consumer':[.60,.61,.62,.63,.64,.65], 'Capex':[.15]*6,
                            'Housing':[.04]*6,'Export':[.2]*6},
                           index=pd.period_range('2024Q3',periods=6,freq='Q'))
    store={};r=resolve_year(candidate,'T',2026,3,store,[],now='2026-10-28')
    assert r['quarter']=='2025Q3' and r['cutoff']=='2026-01-01'
    frozen=copy.deepcopy(r)
    revised=candidate*1.1
    assert resolve_year(revised,'T',2026,3,store,[],now='2026-12-31')==frozen
    assert resolve_year(candidate,'T',2027,3,store,[],now='2026-12-31') is None
    r27=resolve_year(candidate,'T',2027,3,store,[],now='2027-01-02')
    assert r27['quarter']=='2025Q4' and store['T:2026']==frozen
    assert resolve_year(candidate,'J',2026,9,store,[],now='2026-10-28')['quarter']=='2025Q1'
    assert resolve_year(candidate,'EARLY',2024,3,store,[],now='2026-10-28') is None
    wi,_,_=weight_panel(candidate,'T',pd.date_range('2025-01-31','2026-12-31',freq='ME'),3,store,[],now='2026-10-28')
    assert (wi.groupby(wi.index.year).nunique()==1).all().all()
    # Policy migration halves the frozen gross share once, never the net share.
    from annual_weights import NET_POLICY
    legacy=copy.deepcopy(store);legacy['T:2026']['policy']=NET_POLICY
    legacy['T:2026']['weights']['Export']=-.04
    legacy['T:2026']['previous_gross_export_weight']=.2
    migrate_export_weights(candidate,'T',legacy,[])
    assert legacy['T:2026']['quarter']==frozen['quarter']
    for a in ['Consumer','Capex','Housing']:assert legacy['T:2026']['weights'][a]==frozen['weights'][a]
    assert legacy['T:2026']['weights']['Export']==.1
    migrate_export_weights(candidate,'T',legacy,[])
    assert legacy['T:2026']['weights']['Export']==.1
    d=json.loads((BASE/'dashboard_data.json').read_text(encoding='utf8'))
    assert d['weight_policy']==POLICY
    x=pd.read_csv(BASE/'indices.csv',parse_dates=['date']);load=pd.read_csv(BASE/'loadings.csv')
    assert len(d['countries'])==7 and (load.loading>=0).all()
    for cc,c in d['countries'].items():
        assert set(c['weights'])==set(d['axes']) and all(c['weights'][a]>0 for a in ['Consumer','Capex','Housing'])
        assert np.isfinite(c['weights']['Export']) and c['weights']['Export']>=0
        y=x[(x.country==cc)&(x.version=='YoY')].set_index('date')
        mom=x[(x.country==cc)&(x.version=='Momentum')].set_index('date')
        # First five months may depend on pre-2005 observations retained in builder.
        for col in ['headline',*d['axes'],*['contrib_'+a for a in d['axes']]]:
            expected=y[col].rolling(3).mean().diff(3)
            if col in d['axes']:expected=expected.where(expected.index<=pd.Period(c['versions']['Momentum']['latest'],freq='M').end_time)
            np.testing.assert_allclose(mom[col].iloc[5:],expected.iloc[5:],equal_nan=True,atol=1e-10)
        for mode in ['YoY','Momentum']:
            f=x[(x.country==cc)&(x.version==mode)]
            np.testing.assert_allclose(f[["contrib_"+a for a in d['axes']]].sum(axis=1,min_count=4),f.headline,equal_nan=True,atol=1e-10)
            version=c['versions'][mode]
            after=[i for i,t in enumerate(version['dates']) if t>version['latest']]
            for axis in d['axes']:
                assert all(version['blocks'][axis][i] is None for i in after)
            assert f.loc[f.date>pd.Period(version['latest'],freq='M').end_time,list(d['axes'])].isna().all().all()
        for a in d['axes']:
            mask=y.headline.notna()
            np.testing.assert_allclose(y.loc[mask,'contrib_'+a],y.loc[mask,a]*y.loc[mask,'weight_'+a],atol=1e-10)
            assert (y.groupby(y.index.year)['weight_'+a].nunique()<=1).all()
            n=sum(r['country']==cc and r['axis']==a for r in d['indicators']);assert n==c['diagnostics'][a]['count']
        for r in c['annual_weights']:
            assert pd.Timestamp(r['assumed_available'])<=pd.Timestamp(r['cutoff'])
    # Check the saved signed weights against the actual GDP source formula.
    from build import weight_candidates,core,ROOT
    raw=pd.concat([pd.read_csv(BASE/'source/raw_haver.csv'),pd.read_csv(BASE/'values.csv')]).drop_duplicates(['pk','date'],keep='last')
    review=core.READ(ROOT/'outputs/gdp_expenditure_review/report_data.json')
    old_path=BASE/'annual_weights_gross_export_v1.json'
    if old_path.exists():
        old=json.loads(old_path.read_text(encoding='utf8'))['records']
        for cc,c in d['countries'].items():
            candidates,_=weight_candidates(raw,review,cc)
            for r in c['annual_weights']:
                key=f"{cc}:{r['year']}"
                if key not in old:continue
                assert r['quarter']==old[key]['quarter']
                for axis in ['Consumer','Capex','Housing']:assert r['weights'][axis]==old[key]['weights'][axis]
                assert np.isclose(r['weights']['Export'],old[key]['weights']['Export']*.5)
    assert all(r['axis']=='Consumer' for r in d['indicators'] if r['previous_group'].startswith('C_'))
    # Expansion must retain every original country/series/axis and frozen GDP share.
    baseline=json.loads((BASE/'pre_blackrock_union.json').read_text(encoding='utf8'))
    original={(r['country'],r['pk'],r['axis']) for r in baseline['indicators']}
    current={(r['country'],r['pk'],r['axis']) for r in d['indicators']}
    assert original<=current and len(current)==len(d['indicators'])
    assert set(d['countries'])=={'US','UK','FR','DE','CA','JP','AU'}
    frozen_before=json.loads((BASE/'pre_blackrock_union_weights.json').read_text(encoding='utf8'))['records']
    frozen_after=json.loads((BASE/'annual_weights.json').read_text(encoding='utf8'))['records']
    assert all(frozen_after[k]==v for k,v in frozen_before.items())
    metadata=json.loads((BASE/'blackrock_source/metadata.json').read_text(encoding='utf8'))
    review=pd.read_csv(BASE/'blackrock_coverage.csv').fillna('')
    added=review[review.action.eq('added')]
    assert len(added)==len(current-original)
    for r in added.to_dict('records'):
        assert metadata[r['pk']]['frequency']=='M'
        assert 'DISC' not in metadata[r['pk']]['descriptor'].upper()
        assert pd.Timestamp(r['last'])>=pd.Timestamp.now()-pd.DateOffset(months=6)
        assert (r['country'],r['pk'],r['included_axis']) in current
    assert 'usecon:napmc' not in {r['pk'] for r in d['indicators'] if r['country']=='CA'}
    # Trade surveys alone cannot move the published cutoff beyond actual exports.
    merged=pd.concat([pd.read_csv(BASE/'source/raw_haver.csv'),pd.read_csv(BASE/'values.csv'),pd.read_csv(BASE/'blackrock_source/values.csv')]).drop_duplicates(['pk','date'],keep='last')
    merged['month']=pd.PeriodIndex(merged.date,freq='M').to_timestamp('M')
    for cc,c in d['countries'].items():
        actual_codes=[r['pk'] for r in d['indicators'] if r['country']==cc and r['axis']=='Export' and r['kind'] in ['level','growth_yoy','growth_mom']]
        last_raw=merged.loc[merged.pk.isin(actual_codes),'month'].max()
        assert pd.Period(c['versions']['YoY']['latest'],freq='M').to_timestamp('M')<=last_raw
    print('PASS: original inputs, seven-region geography, no duplicate inputs, monthly-only additions, unchanged annual weights, no US ISM in Canada')
    print('PASS: 7 countries, January cutoffs, frozen revisions, automatic year rollover, annual fixed weights, contributions, post-PCA Momentum, nonnegative loadings')
if __name__=='__main__':main()
