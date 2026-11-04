"""Behavioral checks for constraints, causality, weights and conservation."""
import json,hashlib
import numpy as np
import pandas as pd
from build_model import BASE,ROOT,pca,positive_loading,weights,transform,classify,ALIAS

def main():
    # A diffusion index describes current conditions; a trending total does not.
    def kind(label,datatype='INDEX',group='COMMON'):
        return classify({'descriptor':label,'datatype':datatype},group)[0]
    assert kind('Manufacturing PMI (SA, 50=no change)')=='rate'
    assert kind('Economic Conditions Next 12 Months (SA, 100+=Favorable)',group='C_sentiment')=='rate'
    assert kind('Aggregate Weekly Hours Index: Total Private Industries (SA, 2007=100)')=='level'
    assert kind('Average Weekly Hours: Total Private Industries (SA, Hrs)')=='rate'
    assert kind('All Employees: Total Nonfarm (SA, Thous)','NUM')=='level'
    assert ALIAS['anz:ausvcpfl']=='anz:ausvcfl' and ALIAS['anz:ausvcpfn']=='anz:ausvcfn'
    # Adding a fixed neutral threshold before z-scoring cannot preserve that
    # threshold as zero; centering removes constants. Preserve raw PMI separately.
    from build_model import zscore
    test_idx=pd.date_range('2000-01-31',periods=50,freq='ME')
    diffusion=pd.Series(48+np.sin(np.arange(50)),index=test_idx)
    np.testing.assert_allclose(zscore(diffusion,24),zscore(diffusion-50,24),atol=1e-10,equal_nan=True)
    rng=np.random.default_rng(71027);idx=pd.date_range('2000-01-31',periods=80,freq='ME')
    x=pd.DataFrame(rng.normal(size=(80,4)),index=idx,columns=list('abcd'));x['b']=x.a*.8+x.b*.2;x.loc[idx[40:45],'c']=np.nan
    full,loading,_,_=pca(x,12);prefix,_,_,_=pca(x.iloc[:65],12)
    np.testing.assert_allclose(full.iloc[:65],prefix,equal_nan=True,atol=1e-12)
    assert (loading.stack().dropna()>=0).all()
    a=np.array([[1,.7,-.3],[.7,1,-.2],[-.3,-.2,1]])
    vals,vec=np.linalg.eigh(a);v,obj=positive_loading(a,vec[:,-1])
    assert min(v)>=0 and abs(v@v-1)<1e-10 and obj>=np.ones(3)@a@np.ones(3)/3
    s=pd.Series(np.linspace(4,8,80),index=idx)
    negative=transform(s,{'kind':'rate','direction':-1,'seasonal':'adjusted'},'YoY')
    assert negative.iloc[-1]<negative.iloc[0]
    g=pd.Series(np.linspace(-3,4,80),index=idx)
    actual=transform(g,{'kind':'growth_yoy','direction':1,'seasonal':'adjusted'},'YoY')
    np.testing.assert_allclose(actual,g.rolling(3).mean(),equal_nan=True)
    records=[];anchors=[]
    for group,val in [('GDP_REF',100),('C_actual',60),('I_TOTAL',20),('G',20),('X',30),('M',30),('INVENTORY',0)]:
        pk='test:'+group;anchors.append({'country':'T','group':group,'pk':pk})
        records.extend({'pk':pk,'date':str(q.end_time.date()),'value':val} for q in pd.period_range('2020Q1','2021Q4',freq='Q'))
    midx=pd.date_range('2020-01-31','2022-03-31',freq='ME');w,q=weights(pd.DataFrame(records),anchors,'T',midx)
    assert w.loc['2021-02-28'].isna().all() and q['2021-03-31']=='2020Q4'
    assert w.loc['2021-03-31','C']==.6 and w.loc['2021-03-31','M']==-.3
    # Use a real country configuration to verify government investment is
    # subtracted with nominal units preserved, including late missing quarters.
    from build_model import INVESTMENT_SCOPE
    cfg=INVESTMENT_SCOPE['countries']['US'];test_anchors=[];test_records=[]
    us_groups=[('GDP_REF',cfg['gdp'],100),('I_TOTAL',cfg['total'],25),('G','test:G',20),('C_actual','test:C',60),('X','test:X',20),('M','test:M',25),('INVENTORY','test:INV',0)]
    for g,pk,val in us_groups:
        test_anchors.append({'country':'US','group':g,'pk':pk})
        test_records.extend({'pk':pk,'date':str(q.end_time.date()),'value':val} for q in pd.period_range('2020Q1','2021Q4',freq='Q'))
    test_records.extend({'pk':cfg['government'][0],'date':str(q.end_time.date()),'value':5} for q in pd.period_range('2020Q1','2021Q3',freq='Q'))
    iw,iq=weights(pd.DataFrame(test_records),test_anchors,'US',midx)
    assert iw.loc['2021-03-31','I']==.20 and iw.loc['2021-03-31','I_GOV']==.05
    assert iq['2022-03-31']=='2021Q3', 'Hold last complete weights; never silently set government to zero'
    result=json.loads((BASE/'dashboard_data.json').read_text(encoding='utf-8'))
    checked=0
    for cc,c in result['countries'].items():
        for mode,m in c['versions'].items():
            score=np.array([np.nan if v is None else v for v in m['headline']]);con=np.array([[np.nan if v is None else v for v in s] for s in m['contributions'].values()])
            mask=np.isfinite(score);np.testing.assert_allclose(np.nansum(con[:,mask],axis=0),score[mask],atol=4e-6)
            assert m['negative_loadings']==0 and 'G' not in m['included_components'] and 'I_GOV' not in m['included_components']
            assert 'I_GOV' in m['latest_weights'] and m['latest_weights']['I_GOV']>=0
            for r in m['indicators']:
                if r['loading'] is not None:assert r['loading']>=0
                if r['direction']==-1 and r['raw_direction_loading'] is not None:assert r['raw_direction_loading']<=0
            checked+=1
    # Momentum must be a filter of completed scores, including weighted contributions.
    from derive_momentum import difference
    saved=pd.read_csv(BASE/'indices.csv',parse_dates=['date'])
    for cc in saved.country.unique():
        y=saved[(saved.country==cc)&(saved.version=='YoY')].set_index('date').sort_index()
        mom=saved[(saved.country==cc)&(saved.version=='Momentum')].set_index('date').sort_index()
        for col in ['headline']+[k for k in y if k.startswith(('pca_','contrib_'))]:
            np.testing.assert_allclose(mom[col],difference(y[col]),equal_nan=True,atol=1e-10)
    toy=pd.Series([1.,2.,3.,4.,5.,6.,7.]);assert difference(toy).iloc[5]==3
    toy.iloc[2]=np.nan;assert difference(toy).iloc[5:].isna().all()
    historic=pd.read_csv(BASE/'loadings.csv');assert (historic.loading>=-1e-12).all()
    baseline=BASE/'blackrock_last_run_hashes.json'
    if not baseline.exists():baseline=BASE/'blackrock_baseline_hashes.json'
    for path,digest in json.loads(baseline.read_text()).items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    print(f'PASS: {checked} models; nonnegative loadings across {len(historic):,} observations; prefix invariance; lagged weights; contributions; BlackRock files unchanged.')
if __name__=='__main__':main()
