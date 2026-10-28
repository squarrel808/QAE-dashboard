"""Momentum is a six-month linear filter of the completed YoY index.

No second PCA fit or restandardization. Contributions are filtered AFTER
GDP weighting so that they sum exactly even when GDP weights change.
"""
import copy,json
from pathlib import Path
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent

def difference(s):
    return s.rolling(3,min_periods=3).mean().diff(3)

def main():
    payload=json.loads((BASE/'dashboard_data.json').read_text(encoding='utf8'))
    data=pd.read_csv(BASE/'indices.csv',parse_dates=['date'])
    outputs=[data[data.version=='YoY'].copy()];checks=[]
    def values(s):return [None if pd.isna(v) else round(float(v),6) for v in s]
    for cc,country in payload['countries'].items():
        base=country['versions']['YoY']
        frame=data[(data.country==cc)&(data.version=='YoY')].set_index('date').sort_index()
        frame=frame.reindex(pd.date_range(frame.index.min(),frame.index.max(),freq='ME'))
        out=frame.copy();out['version']='Momentum';out['country']=cc
        for col in ['headline']+[c for c in frame if c.startswith(('pca_','contrib_'))]:
            out[col]=difference(frame[col])
        out['coverage']=frame.coverage.rolling(6,min_periods=6).min()
        last=out.headline.last_valid_index()
        if last is None:raise ValueError(f'{cc}: no six-month window')
        version=copy.deepcopy(base);idx=out.index
        version.update(derivation='post_pca_3m3m_difference',source_version='YoY',
            formula='mean(PCA[t:t-2]) - mean(PCA[t-3:t-5])',
            dates=[str(t)[:7] for t in idx],headline=values(out.headline),
            blocks={g:values(out['pca_'+g]) for g in base['blocks']},
            contributions={g:values(out['contrib_'+g]) for g in base['included_components']},
            coverage=values(out.coverage),latest=str(last)[:7],latest_value=float(out.at[last,'headline']),
            latest_contributions={g:float(out.at[last,'contrib_'+g]) for g in base['included_components']},
            latest_weights={g:float(out.at[last,'weight_'+g]) for g in base['weights']},
            latest_coverage=float(out.at[last,'coverage']),latest_quarter=out.at[last,'weight_quarter'])
        # A filter of six historical scores has no newly estimated single-month loading.
        for r in version['indicators']:
            r.update(z=None,loading=None,raw_direction_loading=None,direction_conflict=False)
        for diagnostic in version['diagnostics'].values():diagnostic['explained']=None
        country['versions']['Momentum']=version
        valid=out.headline.notna()
        err=(out.loc[valid,['contrib_'+g for g in base['included_components']]].sum(axis=1)-out.loc[valid,'headline']).abs().max()
        assert err<1e-10,(cc,err)
        outputs.append(out.rename_axis('date').reset_index())
        checks.append(dict(country=cc,latest=str(last)[:7],contribution_error=float(err)))
    payload['momentum_method']='Completed YoY PCA: trailing 3-month mean minus preceding 3-month mean; no refit or restandardization'
    payload['generated_kst']=pd.Timestamp.now(tz='Asia/Seoul').isoformat()
    pd.concat(outputs,ignore_index=True).to_csv(BASE/'indices.csv',index=False,encoding='utf-8-sig')
    (BASE/'dashboard_data.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf8')
    loads=pd.read_csv(BASE/'loadings.csv')
    loads[loads.version=='YoY'].to_csv(BASE/'loadings.csv',index=False,encoding='utf-8-sig')
    (BASE/'momentum_validation.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
    validation_path=BASE/'validation.json'
    if validation_path.exists():
        validation=json.loads(validation_path.read_text(encoding='utf8'))
        validation['momentum_method']=payload['momentum_method']
        validation['momentum_checks']=checks
        for row in validation.get('models',[]):
            if row.get('version')=='Momentum':
                current=country_value=payload['countries'][row['country']]['versions']['Momentum']
                row.update(latest=current['latest'],first=next(d for d,v in zip(current['dates'],current['headline']) if v is not None),derivation=current['derivation'])
        validation_path.write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf8')
    print('Derived Momentum from completed YoY PCA for',len(checks),'countries; contributions conserved.')

if __name__=='__main__':main()
