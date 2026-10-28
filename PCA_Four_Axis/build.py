"""Four directly fitted activity blocks; frozen January GDP weights per year."""
import sys,json,hashlib,shutil
from pathlib import Path
import pandas as pd
import numpy as np
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(ROOT))
from PCA_Common.fixed_pca import standardize,fit as fixed_pca,POLICY as ESTIMATION,DESCRIPTION
sys.path.insert(0,str(ROOT/'PCA_GDP_Weighted'))
import build_model as core
from derive_momentum import difference
from annual_weights import POLICY,OLD_POLICY,read_ledger,save_ledger,weight_panel,migrate_export_weights
from blackrock_union import extend
from period_alignment import align_uk_period_ends,ALIGNMENTS
AXES={'Consumer':'소비·고용·소득·소비심리','Capex':'기업활동·제조업·설비투자','Housing':'주택투자','Export':'수출'}
MAPPING={'C_actual':'Consumer','C_labor':'Consumer','C_sentiment':'Consumer','I_business':'Capex','I_housing':'Housing','X':'Export'}
HOUSING={'US':(['usecon:fr'],[], 'usecon:gdp'),'UK':(['uk:l62tq','uk:l62rq'],[],None),'FR':(['france:frsnfih'],[],None),'DE':(['germany:desnfir'],['germany:desnfgr'],None),'CA':(['g10:s156nprr'],[],None),'JP':(['japan:n9dfd'],[],None),'AU':(['anz:ausnfr'],[],None)}

def weight_candidates(raw,review,cc):
    cfg=core.INVESTMENT_SCOPE['countries'][cc]
    anchors={r['group']:r['pk'] for r in review['anchors'] if r['country']==cc}
    plus,minus,denom=HOUSING[cc];denom=denom or cfg['gdp']
    codes=set([cfg['total'],cfg['gdp'],*cfg['government'],anchors['C_actual'],anchors['X'],*plus,*minus,denom])
    q=raw[raw.pk.isin(codes)].copy();q['quarter']=pd.PeriodIndex(q.date,freq='Q')
    q=q.pivot(index='quarter',columns='pk',values='value').sort_index()
    q=q.reindex(pd.period_range(q.index.min(),q.index.max(),freq='Q')).rolling(4,min_periods=4).sum()
    r=q[list(codes)].dropna()
    housing=(r[plus].sum(axis=1)-r[minus].sum(axis=1))/r[denom]
    private=(r[cfg['total']]-r[cfg['government']].sum(axis=1))/r[cfg['gdp']]
    w=pd.DataFrame({'Consumer':r[anchors['C_actual']]/r[cfg['gdp']], 'Capex':private-housing,'Housing':housing,'Export':0.5*r[anchors['X']]/r[cfg['gdp']]})
    assert ((w['Capex']+w['Housing']-private).abs()<1e-12).all()
    return w,sorted(codes)

def main(output_base=None,reference_only=False):
    output=Path(output_base) if output_base is not None else BASE
    output.mkdir(exist_ok=True)
    protected=[ROOT/p for p in core.READ(ROOT/'PCA_GDP_Weighted/blackrock_baseline_hashes.json')]
    if reference_only:
        protected += [p for p in [BASE/'dashboard_data.json',BASE/'index.html',BASE/'indices.csv',BASE/'classification_signs.csv',BASE/'annual_weights.json',BASE/'blackrock_coverage.csv'] if p.exists()]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    meta=core.READ(BASE/'source/metadata.json');meta.update(core.READ(BASE/'metadata.json'))
    meta.update(core.READ(BASE/'blackrock_source/metadata.json'))
    raw=pd.concat([pd.read_csv(BASE/'source/raw_haver.csv'),pd.read_csv(BASE/'values.csv'),pd.read_csv(BASE/'blackrock_source/values.csv')]).drop_duplicates(['pk','date'],keep='last')
    review=core.READ(ROOT/'outputs/gdp_expenditure_review/report_data.json')
    wide,specs,audit=core.prepare(review,meta,raw)
    wide,specs=align_uk_period_ends(wide,specs)
    # France previously had no monthly business-investment proxy. Add the
    # verified investment-goods production series, explicitly marked as a proxy.
    pk='france:frsdk';m=meta[pk];kind,direction,ambiguous,seasonal=core.classify(m,'I_business')
    specs['FR|'+pk]=dict(id='FR|'+pk,country='FR',pk=pk,group='I_business',label=m['descriptor'],kind=kind,direction=direction,ambiguous=ambiguous,seasonal=seasonal,substitution=True,note='자본재 생산 대리변수. 국내 기업의 실제 투자지출과 같지 않음.',last=str(wide[pk].last_valid_index())[:10])
    blackrock_audit=extend(wide,specs,meta,core,write_audit=output==BASE)
    if reference_only:
        selected={(r['country'],r['pk']) for r in blackrock_audit if r['action'] in ['existing','added','duplicate']}
        specs={k:s for k,s in specs.items() if (s['country'],s['pk']) in selected}
        assert {(s['country'],s['pk']) for s in specs.values()}==selected
        pd.DataFrame(blackrock_audit).to_csv(output/'blackrock_coverage.csv',index=False,encoding='utf-8-sig')
    names={cc:n for cc,n in review['names'].items() if any(s['country']==cc for s in specs.values())}
    ledger_path=output/'annual_weights.json';records=read_ledger(ledger_path)
    if reference_only:
        # Use the very same frozen snapshots for overlapping country-years.
        for key,record in read_ledger(BASE/'annual_weights.json').items():
            if key in records:assert records[key]['weights']==record['weights'],('PCA II/III weight mismatch',key)
            else:records[key]=record
    legacy_backup=output/'annual_weights_gross_export_v1.json'
    if any(r['policy']==OLD_POLICY for r in records.values()) and not legacy_backup.exists():shutil.copy2(ledger_path,legacy_backup)
    payload={'names':names,'axes':AXES,'countries':{},'method':'Four direct block PCAs; '+DESCRIPTION+'; frozen January GDP shares; Export = 0.5 * gross exports/GDP','estimation':ESTIMATION,'weight_policy':POLICY,'generated_kst':pd.Timestamp.now(tz='Asia/Seoul').isoformat()}
    if reference_only:payload.update(model='PCA III',universe='blackrock_reference_only',excluded_countries={cc:n for cc,n in review['names'].items() if cc not in names})
    classifications=[];timeseries=[];weights_rows=[];loads=[]
    input_series={}
    def vals(s):return [None if pd.isna(v) else float(v) for v in s]
    for cc in names:
        sp={k:s for k,s in specs.items() if s['country']==cc and s['group'] in MAPPING}
        z=standardize(pd.DataFrame({k:core.transform(wide[s['pk']],s,'YoY') for k,s in sp.items()}))
        input_series[cc]={'dates':[str(t)[:7] for t in wide.index], 'latest_raw':str(wide[[s['pk'] for s in sp.values()]].notna().any(axis=1).loc[lambda s:s].index[-1])[:7], 'series':{
            s['pk']:{'raw':vals(wide[s['pk']].round(6)), 'zscore':vals(z[k].round(6))}
            for k,s in sp.items()}}
        blocks={};diagnostics={};block_loads={}
        for axis in AXES:
            keys=[k for k,s in sp.items() if MAPPING[s['group']]==axis]
            if not keys:
                if not reference_only:raise ValueError((cc,axis,'No inputs'))
                blocks[axis]=pd.Series(np.nan,index=z.index)
                diagnostics[axis]={'count':0,'single':False,'available_latest':0}
                continue
            score,loading,explained,n,fit_detail=fixed_pca(z[keys])
            blocks[axis]=score;block_loads[axis]=loading
            diagnostics[axis]={'count':len(keys),'single':len(keys)==1,'fit':fit_detail}
            for t in loading.index:
                if t.year>=2005:
                    loads.extend(dict(country=cc,date=str(t)[:10],axis=axis,indicator=k,loading=float(v)) for k,v in loading.loc[t].dropna().items())
        candidates,sources=weight_candidates(raw,review,cc)
        migrate_export_weights(candidates,cc,records,sources)
        panel=pd.DataFrame(blocks)
        lag=core.INVESTMENT_SCOPE['countries'][cc].get('weight_lag_months',3)
        wp,weight_quarters,annual=weight_panel(candidates,cc,panel.index,lag,records,sources)
        active=[a for a in AXES if diagnostics[a]['count']>0]
        contrib=panel*wp;headline=contrib[active].sum(axis=1,min_count=len(active))
        # Consumer requires at least one consumption-actual observation.
        actual=[k for k,s in sp.items() if s['group']=='C_actual']
        headline=headline.where(z[actual].notna().any(axis=1))
        # Export surveys now extend further than the trade release. A new
        # survey-only month must not represent the full Export activity block.
        export_actual=[k for k,s in sp.items() if s['group']=='X' and s['kind'] in ['level','growth_yoy','growth_mom']]
        if not export_actual:raise ValueError((cc,'No actual export inputs'))
        headline=headline.where(z[export_actual].notna().any(axis=1))
        contrib=contrib.where(headline.notna(),axis=0)
        versions={}
        for mode in ['YoY','Momentum']:
            bp=panel if mode=='YoY' else difference(panel)
            cp=contrib if mode=='YoY' else difference(contrib)
            hp=headline if mode=='YoY' else difference(headline)
            idx=hp.index[hp.index>=pd.Timestamp('2005-01-01')];last=hp.last_valid_index()
            # Published block charts/cards/contributions must share the headline
            # cutoff. Late partial releases (e.g. surveys only) can otherwise
            # masquerade as a collapse of the full Consumer block.
            bp=bp.copy();bp.loc[bp.index>last,:]=np.nan
            assert (cp[active].sum(axis=1,min_count=len(active))-hp).abs().max()<1e-10
            versions[mode]={'dates':[str(t)[:7] for t in idx],'headline':vals(hp.loc[idx]),'blocks':{a:vals(bp.loc[idx,a]) for a in AXES},'contributions':{a:vals(cp.loc[idx,a]) for a in AXES},'latest':str(last)[:7],'latest_value':float(hp[last]),'negative_loadings':sum(diagnostics[a]['fit']['negative_loadings'] for a in active)}
            for t in idx:timeseries.append(dict(country=cc,version=mode,date=str(t)[:10],headline=hp[t],weight_year=t.year,weight_quarter=weight_quarters[t],**{'weight_'+a:wp.at[t,a] for a in AXES},**{a:bp.at[t,a] for a in AXES},**{'contrib_'+a:cp.at[t,a] for a in AXES}))
        last=headline.last_valid_index()
        for axis in AXES:
            keys=[k for k,s in sp.items() if MAPPING[s['group']]==axis]
            diagnostics[axis]['available_latest']=int(z.loc[last,keys].notna().sum())
        w=wp.loc[last].to_dict();quarter=weight_quarters[last]
        for k,s in sp.items():
            axis=MAPPING[s['group']];loading=block_loads[axis].at[last,k]
            classifications.append(dict(country=cc,axis=axis,previous_group=s['group'],pk=s['pk'],label=s['label'],kind=s['kind'],direction=s['direction'],loading=None if pd.isna(loading) else float(loading),signed_loading=None if pd.isna(loading) else float(loading*s['direction']),date=str(last)[:7],proxy=bool(s['substitution']),origin=s.get('origin','Existing'),reference_matches='; '.join(s.get('reference_matches',[])),note=s.get('note','')))
        payload['countries'][cc]={'weights':w,'weight_year':last.year,'weight_quarter':quarter,'annual_weights':annual,'weight_sources':sources,'diagnostics':diagnostics,'versions':versions}
        if reference_only:payload['countries'][cc].update(active_axes=active,missing_axes=[a for a in AXES if a not in active])
        weights_rows.extend(dict(country=cc,year=r['year'],cutoff=r['cutoff'],quarter=r['quarter'],assumed_available=r['assumed_available'],**r['weights']) for r in annual)
        print(cc,{a:d['count'] for a,d in diagnostics.items()},quarter,{a:round(v*100,2) for a,v in w.items()},flush=True)
    payload['indicators']=classifications
    payload['period_alignment']=ALIGNMENTS
    payload['input_series']=input_series
    payload['blackrock_review']={'targets':len(blackrock_audit),'actions':pd.Series([r['action'] for r in blackrock_audit]).value_counts().to_dict(),'excluded_region':'EA','scope':('확인된 BlackRock 참조 지표만 사용. 프랑스 자체 참조 패널 없음. 독일·일본 Housing 미편입.' if reference_only else '기존 7개국 유지.')+' 사용자 제공 BlackRock 패널 텍스트 기준 개념 매핑; 원본 티커 동일성 미검증.'}
    pd.DataFrame(classifications).to_csv(output/'classification_signs.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(classifications).to_csv(output/'inputs.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(timeseries).to_csv(output/'indices.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(weights_rows).to_csv(output/'weights.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(loads).to_csv(output/'loadings.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame([dict(country=s['country'],pk=s['pk'],previous_group=s['group'],axis=MAPPING.get(s['group'],'Excluded reference'),included=s['group'] in MAPPING) for s in specs.values()]).to_csv(output/'selection_audit.csv',index=False,encoding='utf-8-sig')
    (output/'dashboard_data.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf8')
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    save_ledger(ledger_path,records)
    (output/'validation.json').write_text(json.dumps({'pca_i_unchanged_during_this_build':True,'pca_ii_unchanged':reference_only,'countries':len(names),'inputs':len(classifications),'momentum':'post-PCA 3m/3m difference','estimation':ESTIMATION,'weights':POLICY},indent=2),encoding='utf8')

if __name__=='__main__':main()
