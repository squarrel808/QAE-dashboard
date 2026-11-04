"""Read-only loading audit: old constrained EWM, constraint-only, current PCA.

Block resampling describes sensitivity; bands are not formal significance tests.
No production input, estimate, weight, or published page is overwritten.
"""
import sys,json,hashlib,math
from pathlib import Path
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent.parent.parent
sys.path.insert(0,str(R));sys.path.insert(0,str(R/'PCA/PCA_Four_Axis'))
from build import core,AXES,align_uk_period_ends
from PCA.PCA_Common.fixed_pca import standardize,fit
def migrated_path(p):
    p=Path(p)
    return R/'PCA'/p if p.parts[0].startswith('PCA_') else R/p


B=R/'PCA/PCA_Four_Axis';O=R/'outputs/pca_loading_audit';O.mkdir(exist_ok=True)
BEFORE=R/'outputs/pca_cfna_comparison/before'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
snap=read(BEFORE/'snapshot.json')
for p,h in snap['raw_hashes'].items():assert hashlib.sha256(migrated_path(p).read_bytes()).hexdigest()==h,p
meta={}
for p in [B/'source/metadata.json',B/'metadata.json',B/'blackrock_source/metadata.json']:meta.update(read(p))
raw=pd.concat([pd.read_csv(B/'source/raw_haver.csv'),pd.read_csv(B/'values.csv'),pd.read_csv(B/'blackrock_source/values.csv')]).drop_duplicates(['pk','date'],keep='last')
wide,specs,_=core.prepare(read(R/'outputs/gdp_expenditure_review/report_data.json'),meta,raw)
wide,specs=align_uk_period_ends(wide,specs)

def repair(a):
    a=np.asarray(a,dtype=float);a=(a+a.T)/2
    if not np.isfinite(a).all():raise ValueError('insufficient pair overlap')
    val,vec=np.linalg.eigh(a)
    q=(vec*np.maximum(val,1e-8))@vec.T;scale=np.sqrt(np.diag(q));q=q/np.outer(scale,scale)
    vals,vecs=np.linalg.eigh(q)
    return q,vals,vecs,dict(min_raw_eigen=float(val.min()),negative_raw_eigen=int((val < -1e-8).sum()),
        repair_relative=float(np.linalg.norm(q-a)/np.linalg.norm(a)),max_correlation_repair=float(np.max(np.abs(q-a))))
def principal(x,reference=None):
    q,e,v,diag=repair(x.corr(min_periods=12).to_numpy())
    coef=v[:,-1]
    if reference is not None:
        if coef@reference<0:coef=-coef
    else:
        s=(x*coef).sum(axis=1,min_count=min(2,x.shape[1]))/np.sqrt(x.notna().sum(axis=1))
        if s.corr(x.mean(axis=1))<0:coef=-coef
    return coef,e,q,diag
def cosine(a,b):
    a=np.asarray(a);b=np.asarray(b)
    return float(a@b/np.linalg.norm(a)/np.linalg.norm(b))
def band_bootstrap(x,v,block,reps=300):
    # Circular moving blocks preserve local monthly serial and cross dependence.
    # The panel and its missingness pattern are resampled together.
    rng=np.random.default_rng(20261029+block+len(v));rows=[];fail=0;n=len(x)
    for _ in range(reps):
        starts=rng.integers(0,n,size=math.ceil(n/block))
        ix=np.concatenate([(s+np.arange(block))%n for s in starts])[:n]
        try:rows.append(principal(x.iloc[ix],v)[0])
        except (ValueError,np.linalg.LinAlgError):fail+=1
    a=np.array(rows)
    if len(a)<reps*.8:return {'success':len(a),'failed':fail,'insufficient':True},None
    cos=a@v
    return dict(success=len(a),failed=fail,cosine_p05=float(np.quantile(cos,.05)),cosine_median=float(np.median(cos))),a
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(float,np.floating)):return None if not np.isfinite(x) else float(x)
    if isinstance(x,np.integer):return int(x)
    return x

panels=[];indicator_rows=[];pair_rows=[];cache={};old_fits={};attributions=[]
for model,folder in [('II','PCA/PCA_Four_Axis'),('III','PCA/PCA_BlackRock_Only')]:
    d=read(R/folder/'dashboard_data.json');old=read(BEFORE/Path(folder).name/'dashboard_data.json')
    assert {(s['country'],s['axis'],s['pk'],s['kind'],s['direction']) for s in d['indicators']}=={(s['country'],s['axis'],s['pk'],s['kind'],s['direction']) for s in old['indicators']}
    assert read(R/folder/'annual_weights.json')==read(BEFORE/Path(folder).name/'annual_weights.json')
    for cc,country in d['countries'].items():
        last=pd.Period(country['versions']['YoY']['latest'],freq='M').to_timestamp('M')
        prior={(s['country'],s['pk']):s for s in old['indicators']}
        for axis in AXES:
            sp=[dict(s) for s in d['indicators'] if s['country']==cc and s['axis']==axis]
            if not sp:
                panels.append(dict(model=model,country=cc,axis=axis,status='missing',n=0));continue
            for s in sp:
                pk=s['pk'];dependency='uk:mgsx' if pk=='derived:uk_mgsx_endmonth' else 'france:frnopcr' if pk=='derived:fr_car_light' else pk
                s['seasonal']=core.classify(meta[dependency],s['previous_group'])[3]
            pks=[s['pk'] for s in sp]
            x=pd.DataFrame({s['pk']:core.transform(wide[s['pk']],s,'YoY') for s in sp})
            z=standardize(x);ze=core.zscore(x,24)
            score,loads,_,_,detail=fit(z);v=loads.iloc[-1].to_numpy()
            np.testing.assert_allclose(v,[s['loading'] for s in sp],atol=1e-10)
            at=country['versions']['YoY']['dates'].index(str(last)[:7])
            assert abs(score[last]-country['versions']['YoY']['blocks'][axis][at])<1e-10
            current_saved=d['input_series'][cc]
            for s in sp:
                arr=np.array(current_saved['series'][s['pk']]['zscore'],dtype=float)
                np.testing.assert_allclose(z[s['pk']],arr,atol=5.1e-7,equal_nan=True)
            old_v=np.array([prior[(cc,p)]['loading'] if prior[(cc,p)]['loading'] is not None else np.nan for p in pks])
            present=np.isfinite(old_v);available=[p for i,p in enumerate(pks) if present[i]]
            # This is exactly the old month's correlation matrix, including its
            # causal EWM z-scores and available-variable subset; only the sign
            # constraint is removed for the controlled comparison.
            ae=ze[available].ewm(halflife=24,min_periods=12).corr().loc[last].to_numpy()
            old_r,eold,veold,old_diag=repair(ae)
            u=veold[:,-1]
            if u@old_v[present]<0:u=-u
            uncon=np.full(len(pks),np.nan);uncon[present]=u
            old_objective=float(old_v[present]@old_r@old_v[present])
            q,e,vec,diag=repair(z.corr(min_periods=12))
            np.testing.assert_allclose(q@v,e[-1]*v,atol=1e-9)
            assert abs(np.linalg.norm(v)-1)<1e-10
            observed=z.notna().astype(int);overlap=observed.T@observed
            pair_min=int(overlap.to_numpy()[np.triu_indices(len(pks),1)].min()) if len(pks)>1 else int(z.iloc[:,0].count())
            counts=z.notna().sum(axis=1);valid=z.dropna(how='all')
            key=hashlib.sha256(x.to_csv().encode()).hexdigest()
            if key not in cache:
                sensitivity={}
                for name,sub in [('last10y',x.loc[x.index>x.index.max()-pd.DateOffset(years=10)]),
                    ('without_2020_2022',x.loc[~x.index.year.isin([2020,2021,2022])]),
                    ('through_published_month',x.loc[:last]),('leave_last12m',x.iloc[:-12]),
                    ('complete_cases',x.dropna())]:
                    try:
                        vv,ee,_,_=principal(sub,v)
                        sensitivity[name]=dict(cosine=cosine(v,vv),rows=len(sub),coefficients=vv.tolist(),
                            material_sign_flips=int(((v*vv<0)&(np.abs(v)>.05)&(np.abs(vv)>.05)).sum()))
                    except (ValueError,np.linalg.LinAlgError):sensitivity[name]=dict(rows=len(sub),unavailable=True)
                boot24,boot=band_bootstrap(valid,v,24)
                boot12,_=band_bootstrap(valid,v,12,150)
                cache[key]=(sensitivity,boot24,boot12,boot)
            sensitivity,boot24,boot12,boot=cache[key]
            pairs=[]
            for i in range(len(pks)):
                for j in range(i+1,len(pks)):
                    r=float(z[pks[i]].corr(z[pks[j]]));n=int(overlap.iloc[i,j])
                    if abs(r)>=.98 and n>=60:
                        item=dict(model=model,country=cc,axis=axis,pk1=pks[i],pk2=pks[j],label1=sp[i]['label'],label2=sp[j]['label'],correlation=r,n=n)
                        pair_rows.append(item);pairs.append(item)
            indices=np.argsort(np.abs(v))[-3:][::-1]
            row=dict(model=model,country=cc,axis=axis,status='single' if len(pks)==1 else 'pca',month=str(last)[:7],n=len(pks),
                old_available=int(present.sum()),new_available=int(z.loc[last].notna().sum()),
                old_zeros=int((np.abs(old_v[present])<1e-8).sum()),new_negative=int((v < -1e-8).sum()),
                constraint_only_negative=int((u < -1e-8).sum()),
                cosine_old_new_common=cosine(old_v[present],v[present]),cosine_old_new_full=cosine(np.nan_to_num(old_v),v),
                cosine_constraint_only=cosine(old_v[present],u),
                old_explained=old_objective/np.trace(old_r),old_unrestricted_explained=float(eold[-1]/eold.sum()),
                    constraint_variance_gain_pp=float(max(0,100*(eold[-1]-old_objective)/eold.sum())),
                new_explained=float(e[-1]/e.sum()),lambda1=float(e[-1]),lambda2=None if len(e)<2 else float(e[-2]),
                eigengap_ratio=None if len(e)<2 else float((e[-1]-e[-2])/e[-1]),
                top3_squared_share=float(np.sum(v[indices]**2)),effective_loading_count=float(1/np.sum(v**4)),
                fit_start=str(valid.index.min())[:7],fit_end=str(valid.index.max())[:7],fit_months=len(valid),
                complete_months=int(z.notna().all(axis=1).sum()),min_pair_overlap=pair_min,
                score=float(score[last]),old_score=old['countries'][cc]['versions']['YoY']['blocks'][axis][at],
                top3=[dict(pk=pks[i],label=sp[i]['label'],old=old_v[i],new=v[i]) for i in indices],
                near_duplicate_pairs=len(pairs),sensitivity=sensitivity,bootstrap24=boot24,bootstrap12=boot12,**diag)
            panels.append(row)
            for i,s in enumerate(sp):
                low,high=(np.quantile(boot[:,i],[.05,.95]) if boot is not None else [np.nan,np.nan])
                same=float(np.mean(boot[:,i]*v[i]>0)) if boot is not None else np.nan
                # Contribution is to standardized category score BEFORE the
                # output-centering intercept and GDP aggregation weight.
                term=z.loc[last,pks[i]]*v[i]/np.sqrt(counts[last])/detail['score_std']
                indicator_rows.append(dict(model=model,country=cc,axis=axis,pk=pks[i],label=s['label'],group=s['previous_group'],
                    kind=s['kind'],direction=s['direction'],old_loading=old_v[i],constraint_only_loading=uncon[i],new_loading=v[i],
                    old_signed=old_v[i]*s['direction'],constraint_only_signed=uncon[i]*s['direction'],new_signed=v[i]*s['direction'],
                    change=v[i]-old_v[i],new_squared_share=v[i]**2,current_z=z.loc[last,pks[i]],current_score_term=term,
                    output_centering_intercept=-detail['score_mean']/detail['score_std'],
                    actual_input_score_correlation=z[pks[i]].corr(score),bootstrap24_p05=low,bootstrap24_p95=high,
                    bootstrap24_signed_p05=min(low*s['direction'],high*s['direction']),
                    bootstrap24_signed_p95=max(low*s['direction'],high*s['direction']),
                    bootstrap24_same_sign=same,latest_available=bool(pd.notna(z.loc[last,pks[i]]))))
            if cc in ['US','UK']:
                if key not in old_fits:old_fits[key]=core.pca(ze,24)
                old_score,old_load,_,old_ns=old_fits[key]
                assert abs(old_score[last]-row['old_score'])<1e-10,(model,cc,axis,'old score mismatch')
                np.testing.assert_allclose(old_load.loc[last],old_v,atol=1e-10,equal_nan=True)
                old_raw=(ze*old_load).sum(axis=1,min_count=1)/np.sqrt(old_load.notna().sum(axis=1))
                old_mean=old_raw.ewm(halflife=24,min_periods=12).mean()[last]
                old_std=old_raw.ewm(halflife=24,min_periods=12).std()[last]
                start=float(old_score[last])
                # Ordered algebraic bridge, not independent causal effects.
                after_loading=float(((ze.loc[last]*v).sum()/np.sqrt(present.sum())-old_mean)/old_std)
                after_input=float(((z.loc[last]*v).sum()/np.sqrt(counts[last])-old_mean)/old_std)
                after_output=float(score[last])
                steps=dict(model=model,country=cc,axis=axis,old_score=start,new_score=after_output,
                    loading_step=after_loading-start,input_standardization_and_coverage_step=after_input-after_loading,
                    output_standardization_step=after_output-after_input)
                assert abs(sum(steps[k] for k in ['loading_step','input_standardization_and_coverage_step','output_standardization_step'])-(after_output-start))<1e-10
                attributions.append(steps)
            print(model,cc,axis,'cos',round(row['cosine_old_new_common'],3),'EV',round(row['new_explained'],3),'boot05',round(boot24.get('cosine_p05',np.nan),3),flush=True)

data=clean(dict(asof='2026-10-29',raw_unchanged=True,panels=panels,indicators=indicator_rows,correlated_pairs=pair_rows,score_bridge=attributions,
    methods=dict(bootstrap_main='300 circular moving-block resamples of 24 contiguous months; eigenvector signs aligned to full-sample vector',
        bootstrap_sensitivity='150 resamples of 12 months',bands='5th/95th percentiles are sensitivity bands, not formal significance tests',
        comparison='old latest published month versus current-vintage fixed vector; constraint-only uses old exact matrix and observed-variable subset')))
(O/'audit.json').write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf8')
pd.DataFrame([{k:v for k,v in row.items() if not isinstance(v,(dict,list))} for row in data['panels']]).to_csv(O/'category_summary.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(data['indicators']).to_csv(O/'indicator_loadings.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(data['correlated_pairs']).to_csv(O/'high_correlations.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(data['score_bridge']).to_csv(O/'score_bridge.csv',index=False,encoding='utf-8-sig')
for p,h in snap['raw_hashes'].items():assert hashlib.sha256(migrated_path(p).read_bytes()).hexdigest()==h,p
print('Audit saved:',len(panels),'country/category entries;',len(indicator_rows),'coefficient rows; all production data untouched',flush=True)
