"""Numerical estimator contracts, including unrestricted negative coefficients."""
import numpy as np,pandas as pd
from fixed_pca import fit,standardize
rng=np.random.default_rng(741)
idx=pd.date_range('2000-01-31',periods=180,freq='ME')
f=rng.normal(size=180)
x=pd.DataFrame({'activity':f+.1*rng.normal(size=180),'jobs':.7*f+.1*rng.normal(size=180),'unemployment':-f+.1*rng.normal(size=180)},index=idx)
z=standardize(x);orientation={'activity':1,'jobs':1,'unemployment':-1}
score,loads,expl,n,detail=fit(z,orientation)
val,vec=np.linalg.eigh(z.corr());v=vec[:,-1]
if v[0]<0:v=-v
np.testing.assert_allclose(loads.iloc[0],v,atol=1e-10)
np.testing.assert_allclose(score,standardize(pd.Series(z.to_numpy()@v/np.sqrt(3),index=idx)),atol=1e-10)
assert loads.unemployment.max()<0 and (loads.nunique()==1).all()
assert abs(score.mean())<1e-12 and abs(score.std()-1)<1e-12
# Economic input sign flips cannot change an unrestricted component's score.
flipped=z.copy();flipped.unemployment*=-1
score2,load2,_,_,_=fit(flipped)
np.testing.assert_allclose(score2,score,atol=1e-10)
np.testing.assert_allclose(load2.unemployment,-loads.unemployment,atol=1e-10)
# Missing observations retain a single fitted vector; no value appears in input.
partial=z.copy();partial.iloc[-1,1]=np.nan;partial.iloc[-2,:2]=np.nan
snap=partial.copy();s,l,_,n,_=fit(partial,orientation)
pd.testing.assert_frame_equal(partial,snap)
assert pd.isna(s.iloc[-2]) and pd.notna(s.iloc[-1]) and (l.nunique()==1).all()
print('PASS: standard PCA eigenvector, fixed history loadings, negative unemployment coefficient, full-sample moments, input sign invariance and missing-data policy')
