"""Reaggregate saved, full precision PCA block scores after a scope/weight change.

Does not refit PCA. Refuses to change latest observation month, so saved latest
loadings/diagnostics remain valid. For a changed input set use build_model.py.
"""
import hashlib,json
import numpy as np
import pandas as pd
from build_model import BASE,ROOT,READ,INVESTMENT_SCOPE,GROUPS,weights,json_safe,list_values

def main():
    payload=READ(BASE/'dashboard_data.json');raw=pd.read_csv(BASE/'raw_haver.csv')
    review=READ(ROOT/'outputs/gdp_expenditure_review/report_data.json')
    original=pd.read_csv(BASE/'indices.csv');original['date']=pd.to_datetime(original.date)
    expected_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in READ(BASE/'blackrock_baseline_hashes.json')}
    load_hash=hashlib.sha256((BASE/'loadings.csv').read_bytes()).hexdigest()
    changes=[];outputs=[];checks=[]
    for cc,c in payload['countries'].items():
        for mode,v in c['versions'].items():
            if mode != 'YoY':continue
            out=original[(original.country==cc)&(original.version==mode)].set_index('date').copy()
            idx=out.index;w,quarters=weights(raw,review['anchors'],cc,idx)
            comps=v['included_components'];assert 'G' not in comps and 'I_GOV' not in comps
            panel=pd.DataFrame({g:out['pca_'+g] for g in comps},index=idx)
            contrib=panel*w[comps];score=contrib.sum(axis=1,min_count=1)
            active=w[comps].abs().where(panel.notna()).sum(axis=1);total=w.abs().sum(axis=1)
            coverage=active/total;potential=w[comps].abs().sum(axis=1)/total
            required=[g for g in ['C','I','X','M'] if g in comps]
            valid=panel[required].notna().all(axis=1)&(active>=w[comps].abs().sum(axis=1)*.8)&w[comps].notna().all(axis=1)
            score=score.where(valid);contrib=contrib.where(valid)
            last=score.last_valid_index();assert str(last)[:7]==v['latest'],(cc,mode,'Latest date changed; run full model')
            changes.append(dict(country=cc,version=mode,date=v['latest'],old_investment_weight=v['latest_weights']['I'],new_investment_weight=w.at[last,'I'],excluded_government_investment=w.at[last,'I_GOV'],old_headline=v['latest_value'],new_headline=score.at[last]))
            v.update(headline=list_values(score,idx),contributions={g:list_values(contrib[g],idx) for g in comps},weights={g:list_values(w[g],idx) for g in w},coverage=list_values(coverage,idx),potential_coverage=list_values(potential,idx),weight_quarters=[quarters.get(t) if pd.notna(quarters.get(t)) else None for t in idx],latest_value=float(score.at[last]),latest_weights=w.loc[last].to_dict(),latest_contributions=contrib.loc[last].to_dict(),latest_coverage=float(coverage.at[last]),latest_quarter=quarters[last])
            out['headline']=score;out['coverage']=coverage;out['weight_quarter']=quarters
            for g in comps:out['contrib_'+g]=contrib[g]
            for g in w:out['weight_'+g]=w[g]
            outputs.append(out.reset_index())
            err=float((contrib.sum(axis=1,min_count=1)-score).abs().max());assert err<1e-10
            checks.append(dict(country=cc,version=mode,latest=str(last)[:7],first=str(score.first_valid_index())[:7],contribution_error=err,inputs=len(v['indicators']),negative_loadings=v['negative_loadings']))
    payload.update(generated_kst=pd.Timestamp.now(tz='Asia/Seoul').isoformat(),investment_scope=INVESTMENT_SCOPE,groups=GROUPS)
    assert hashlib.sha256((BASE/'loadings.csv').read_bytes()).hexdigest()==load_hash
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in expected_hashes.items())
    pd.concat(outputs,ignore_index=True).to_csv(BASE/'indices.csv',index=False,encoding='utf-8-sig')
    (BASE/'dashboard_data.json').write_text(json.dumps(json_safe(payload),ensure_ascii=False,allow_nan=False),encoding='utf8')
    (BASE/'blackrock_last_run_hashes.json').write_text(json.dumps(expected_hashes,indent=2),encoding='utf8')
    (BASE/'validation.json').write_text(json.dumps({'models':checks,'blackrock_unchanged':True,'pca_loadings_unchanged':True,'selection':payload['audit_counts'],'inputs':payload['input_count'],'investment_scope':INVESTMENT_SCOPE},ensure_ascii=False,indent=2),encoding='utf8')
    pd.DataFrame(changes).to_csv(ROOT/'outputs/pca_private_scope/weight_changes.csv',index=False,encoding='utf-8-sig')
    print('Reweighted',len(checks),'models; block PCA/loadings unchanged; BlackRock unchanged.')
if __name__=='__main__':
    main()
    from derive_momentum import main as derive_momentum
    derive_momentum()
