"""Cross-model integration: fixed coefficients, aggregation, Momentum and vintage."""
import hashlib,json,pickle,sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from PCA.pca_gdp import difference_3m3m

results=pickle.loads((ROOT/'PCA/model_results.pkl').read_bytes())
for cc,versions in results.items():
    y,m=versions['YoY'],versions['Momentum']
    np.testing.assert_allclose(m['gdp'],difference_3m3m(y['gdp']),equal_nan=True,atol=1e-12)
    for v in [y,m]:
        np.testing.assert_allclose(v['gdp_contrib'].sum(axis=1,min_count=1),v['gdp'],equal_nan=True,atol=1e-12)
    for axis,z in y['cat_index'].items():
        assert np.isclose(z.mean(),0,atol=1e-12) and np.isclose(z.std(),1,atol=1e-12)
        assert (y['cat_loadings'][axis].nunique()<=1).all()
        assert np.isclose((y['cat_loadings'][axis].iloc[-1]**2).sum(),1,atol=1e-12)
        np.testing.assert_allclose(m['cat_index'][axis],difference_3m3m(z),equal_nan=True,atol=1e-12)
for name in ['PCA_Four_Axis','PCA_BlackRock_Only']:
    d=json.loads((ROOT/name/'dashboard_data.json').read_text(encoding='utf8'))
    assert d['estimation']['constraint']=='unrestricted' and d['estimation']['loadings']=='fixed_per_release'
    for cc,c in d['countries'].items():
        for axis,item in c['diagnostics'].items():
            if 'fit' in item:
                assert item['fit']['excluded_constant_or_short']==[]
                assert item['fit']['orientation_correlation']>0
snapshot=json.loads((ROOT/'outputs/pca_cfna_comparison/before/snapshot.json').read_text(encoding='utf8'))
for path,digest in snapshot['raw_hashes'].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
print('PASS: all PCA I contributions reconcile, all Momentum is post-Level 3M/3M, full-sample normalization, fixed unit vectors, shared II/III estimation, frozen raw data')
