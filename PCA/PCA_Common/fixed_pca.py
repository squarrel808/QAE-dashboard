"""CFNAI-style full-sample normalization and one unrestricted PC1 per release.

This is an adaptation, not a replica of the Chicago Fed index. Input universes,
transformations and aggregation belong to each QAE model. Unbalanced histories
retain the existing pairwise-correlation/PSD repair and available-input sqrt(n)
score adjustment. Raw missing observations are never interpolated or zero-filled.
The entire historical index is revised when a new release is fitted; this is NOT
a sequence of historical real-time vintages or a look-ahead-free backtest.
"""
import numpy as np
import pandas as pd

METHOD_ID='cfna_style_fixed_full_sample_v1'
DESCRIPTION='CFNAI-style unrestricted PCA; full-sample normalization and fixed loadings per release'
POLICY={
    'id':METHOD_ID,'normalization':'full_sample_mean_std','halflife':None,
    'loadings':'fixed_per_release','constraint':'unrestricted',
    'correlation':'pairwise_complete_full_sample_psd_repair',
    'missing':'observed-input sum divided by sqrt(observed count); no raw imputation',
    'history':'current-vintage revised history; not a real-time backtest',
    'source':'https://www.chicagofed.org/-/media/publications/cfnai/background/cfnai-background-pdf.pdf',
}

def standardize(x,min_observations=12):
    mean=x.mean();std=x.std(ddof=1);count=x.count()
    if isinstance(x,pd.Series):
        return (x-mean)/std if count>=min_observations and pd.notna(std) and std>1e-10 else x*np.nan
    std=std.where((count>=min_observations)&(std>1e-10))
    return ((x-mean)/std).replace([np.inf,-np.inf],np.nan)

def fit(z,orientation=None,min_available=2):
    original=list(z);cols=[c for c in original if z[c].notna().sum()>=12 and z[c].std()>1e-10]
    if not cols:raise ValueError('No nonconstant series with 12 observations for PCA')
    sample=z[cols];corr=sample.corr(min_periods=12)
    if corr.isna().any().any():raise ValueError('Insufficient pairwise overlap: '+str(corr.columns[corr.isna().any()].tolist()))
    a=corr.to_numpy();a=(a+a.T)/2
    eigen,vec=np.linalg.eigh(a)
    # Pairwise-complete correlation may not be PSD. Repair once per release,
    # never refit a different eigenvector for each historical observation.
    repaired=(vec*np.maximum(eigen,1e-8))@vec.T
    scale=np.sqrt(np.diag(repaired));repaired/=np.outer(scale,scale)
    values,vectors=np.linalg.eigh(repaired)
    loading=pd.Series(vectors[:,-1],index=cols)
    n=sample.notna().sum(axis=1)
    minimum=min(min_available,len(cols))
    raw=sample.mul(loading).sum(axis=1,min_count=minimum)/np.sqrt(n.where(n>=minimum))
    directions=pd.Series(1.,index=cols) if orientation is None else pd.Series(orientation).reindex(cols).fillna(1.)
    anchor=sample.mul(directions).mean(axis=1)
    association=raw.corr(anchor)
    if pd.notna(association) and association<0:loading=-loading;raw=-raw
    elif pd.isna(association) and loading.dot(directions)<0:loading=-loading;raw=-raw
    score=standardize(raw)
    loads=pd.DataFrame(np.tile(loading.reindex(original).to_numpy(),(len(z),1)),index=z.index,columns=original)
    explained=pd.Series(float(values[-1]/values.sum()),index=z.index).where(score.notna())
    detail={**POLICY,'fit_start':str(sample.dropna(how='all').index.min())[:10],
        'fit_end':str(sample.dropna(how='all').index.max())[:10],
        'fit_months':int(sample.notna().any(axis=1).sum()),'complete_months':int(sample.notna().all(axis=1).sum()),
        'features':len(cols),'excluded_constant_or_short':[c for c in original if c not in cols],
        'explained':float(values[-1]/values.sum()),'negative_loadings':int((loading<0).sum()),
        'psd_adjustment_norm':float(np.linalg.norm(repaired-a)),
        'score_mean':float(raw.mean()),'score_std':float(raw.std(ddof=1)),
        'orientation_correlation':None if pd.isna(association) else abs(float(association))}
    return score,loads,explained,n,detail
