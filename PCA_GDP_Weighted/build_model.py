"""Independent expenditure TV-PCA. Current vintage research index, not a GDP forecast."""
import json,re,hashlib,math
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
READ=lambda p:json.loads(p.read_text(encoding='utf-8'))
GROUPS={'C_actual':'소비 실적','C_labor':'고용·소득','C_sentiment':'소비심리','I_business':'설비·비주거 투자','I_housing':'주택 투자','C':'민간소비','I':'고정투자','INVENTORY':'재고','G':'정부소비','X':'수출','M':'수입','COMMON':'공통 생산·경기','TRADE_REF':'무역수지 참고','GDP_REF':'GDP 검증용'}
GROUPS.update(I='민간·기업 고정투자',I_GOV='일반정부 투자 · 제외')
INVESTMENT_SCOPE=READ(BASE/'investment_scope.json')
ALIAS={
 'usecon:ipy':'usecon:ip','usecon:ipp':'usecon:ip','usecon:nmodgn':'usecon:nmodg',
 'g10:s111eh':'usecon:lepriva','g10:s111elen':'usecon:lanagra','g10:s111elur':'usecon:kr','g10:s111tod':'usecon:nmodg',
 'uk:k2dg':'uk:k222','uk:s222':'uk:s2ku','uk:j45w':'uk:j45u','intsrvys:n112vgi':'uk:ugfci','g10:s112elur':'derived:uk_mgsx_endmonth',
 'g10:s132rsic':'france:frstu47','g10:s132eurh':'france:frselrm',
 'germany:dewdy':'germany:desdy','germany:dewtoc':'germany:destoc','germany:dentuy47':'germany:destu47',
 'eudata:w134d4yk':'eudata:s134d4yk','g10:s134elur':'germany:deseur',
 'g10:s156ele':'canada:v2062811','g10:s156elur':'canada:v2062815','g10:s156hs':'g10:z156hs',
 'canada:v6911338':'g10:s156ix','canada:v1558664':'canada:v7e11153','g10:s156trsc':'canada:v1q40181',
 'japan:jpniip':'japan:jpsiip','japan:omnpeen':'japan:omnpeen2','japan:corsv':'japan:jpsir2',
 'japan:costn':'japan:costny2','g10:s158elur':'japan:fluedr2',
 'anz:aunvcc':'anz:ausvcc','intsrvys:s193vcc':'anz:ausvcc','intsrvys:s193vct':'anz:ausvct',
 'g10:s193ele':'anz:ausele','g10:s193elur':'anz:auselur','g10:s193hp':'anz:aushah','g10:h193ix':'anz:ausbmgc',
 # Survey state must use the diffusion level, not its published monthly change.
 'anz:ausvcpfl':'anz:ausvcfl','anz:ausvcpfn':'anz:ausvcfn',
}
# Exact expenditure classification corrections from actual Haver definitions.
REGROUP={'usecon:tvsar':'C_actual','germany:desibt':'TRADE_REF','germany:desdk':'I_business','japan:wrs':'COMMON'}
NEGATIVE=['unemployment','unemployed','unempl+','claimant','job cuts','initial claims','jobs hard to get','bankrupt','beneficiaries','saving rate','current savings','total separations']
AMBIGUOUS=['saving rate','current savings','total separations','filled vacancies']

def zscore(x,hl):
    mean=x.ewm(halflife=hl,min_periods=12).mean();std=x.ewm(halflife=hl,min_periods=12).std()
    return ((x-mean)/std.where(std>1e-10)).replace([np.inf,-np.inf],np.nan)

def classify(m,group):
    d=m['descriptor'].lower();datatype=m.get('datatype','')
    if re.search(r'(yr/yr|y/y|year.over.year|yr ago|3m growth|3mo.*ago|yoy)',d):kind='growth_yoy'
    elif re.search(r'(mo/mo|m/m|%change|% change)',d) and datatype=='%':kind='growth_mom'
    elif 'aggregate' in d and 'hours' in d:kind='level'
    elif datatype in ['%','RATIO'] or group=='C_sentiment' or any(x in d for x in ['confidence','sentiment','barometer','hours','ratio:','purchasing managers','diffusion','pmi','100+=favorable','50+=better']):kind='rate'
    elif 'change (' in d or 'contribution to' in d:kind='change'
    else:kind='level'
    if group=='INVENTORY':kind='inventory_ratio' if 'ratio' in d else 'inventory_stock'
    if group=='TRADE_REF':kind='change'
    direction=-1 if any(t in d for t in NEGATIVE) else 1
    ambiguous=any(t in d for t in AMBIGUOUS)
    if group=='INVENTORY':direction=1;ambiguous=False
    seasonal='NSA' if ('NSA' in m['descriptor'] or not re.search(r'\b(SA|SWDA|WDA|SAAR|Trend)\b',m['descriptor'])) else 'adjusted'
    return kind,direction,ambiguous,seasonal

def prepare(review,meta,raw):
    monthly=raw[raw.pk.map(lambda p:meta[p]['frequency']=='M')].copy();monthly['month']=pd.PeriodIndex(monthly.date,freq='M').to_timestamp('M')
    wide=monthly.pivot(index='month',columns='pk',values='value').reindex(pd.date_range(monthly.month.min(),monthly.month.max(),freq='ME'))
    wide['derived:uk_mgsx_endmonth']=wide['uk:mgsx'].shift(1)
    wide['derived:fr_car_light']=wide['france:frnopcr']+wide['france:frnolcvr']
    specs={};audit=[]
    for row in review['rows']:
        a={k:row.get(k,'') for k in ['country','bbg','label','pk','group','status','note']}
        if not row['monthly_available']:a.update(action='exclude',reason='적합한 현행 월별 대체 없음');audit.append(a);continue
        for original in row['pk'].split(';'):
            p=ALIAS.get(original,original);group=REGROUP.get(p,row['group']);key=row['country']+'|'+p
            a1=dict(a,selected=p,group=group)
            deps=['uk:mgsx'] if p=='derived:uk_mgsx_endmonth' else ['france:frnopcr','france:frnolcvr'] if p=='derived:fr_car_light' else [p]
            if any(t not in meta or 'DISC' in meta[t]['descriptor'].upper() or meta[t]['frequency']!='M' for t in deps):
                a1.update(action='exclude',reason='최신 메타데이터에서 중단/비월별/조회 실패');audit.append(a1);continue
            if p not in wide or wide[p].notna().sum()<36:
                a1.update(action='exclude',reason='PCA 추정에 필요한 원자료 36개월 미만');audit.append(a1);continue
            if key in specs:
                specs[key]['origins'].append(row['bbg'] or row['label']);a1.update(action='duplicate',reason='같은 원계열/계절조정/단위·변환 중복 제거');audit.append(a1);continue
            m=meta[deps[0]];kind,direction,ambiguous,seasonal=classify(m,group)
            label='France: New Passenger Cars + Light Commercial Vehicles' if p=='derived:fr_car_light' else m['descriptor']
            s=wide[p]
            specs[key]=dict(id=key,country=row['country'],pk=p,group=group,label=label,kind=kind,direction=direction,ambiguous=ambiguous,seasonal=seasonal,
                dependencies=deps,origins=[row['bbg'] or row['label']],substitution=row['verdict'] in ['proxy','extra_proxy'],review_status=row['status'],note=row['note'],
                first=str(s.first_valid_index())[:10],last=str(s.last_valid_index())[:10],n=int(s.notna().sum()))
            if original in ['anz:ausvcpfl','anz:ausvcpfn']:
                specs[key]['note']+=' | 2026-10-28 검토: 전월비 코드 대신 같은 소비심리의 SA 수준 코드를 사용.'
            a1.update(action='include',reason='월별 원자료를 한 번만 편입');audit.append(a1)
    return wide,specs,audit

def transform(x,spec,mode):
    kind=spec['kind'];ma=x.rolling(3,min_periods=3).mean();log=np.log(x.where(x>0));logma=np.log(ma.where(ma>0))
    if kind=='inventory_stock':
        # Flow proxy from stock changes, not the stock level itself.
        y=x.diff().rolling(3).mean()
        y=y if mode=='YoY' else y.diff(3)
    elif kind=='inventory_ratio':
        y=ma.diff(12 if mode=='YoY' else 3)
    elif kind=='level':
        if mode=='YoY':y=logma.diff(12)*100
        elif spec['seasonal']=='NSA':y=(log.diff(12)*100).rolling(3).mean().diff(3)
        else:y=logma.diff(3)*100
    elif kind=='growth_yoy':y=ma if mode=='YoY' else ma.diff(3)
    elif kind=='growth_mom':
        # Reported % change is already transformed; never log-difference it again.
        y=x.rolling(12,min_periods=12).mean() if mode=='YoY' else ma
    else:y=x if mode=='YoY' else ma.diff(3)
    return y*spec['direction']

def positive_loading(a,leading,previous=None):
    """Nonnegative variance-maximizing component, projected power multi-start.

    Solves the constrained Rayleigh problem approximately, not ordinary PCA.
    PSD projection ensures stable ascent; no post-hoc abs() of the eigenvector.
    """
    starts=[np.ones(len(a)),np.maximum(leading,0),np.maximum(-leading,0)]
    if previous is not None:starts.append(previous)
    best=None;objective=-np.inf
    for v in starts:
        v=np.maximum(v,0)
        if np.linalg.norm(v)<1e-12:continue
        v=v/np.linalg.norm(v)
        for _ in range(300):
            candidate=np.maximum(a@v+v,0);candidate/=np.linalg.norm(candidate)
            if np.linalg.norm(candidate-v)<1e-9:v=candidate;break
            v=candidate
        value=float(v@a@v)
        if value>objective:best=v;objective=value
    return best,objective

def pca(z,hl,anchor=None):
    """EWM correlation PC1, pairwise complete data, causal sign and PSD repair.

    Empty observations remain NaN. Nonnegative loadings preserve the explicitly
    configured economic direction. Single-column blocks are labeled as such.
    """
    z=z.dropna(axis=1,how='all');cols=list(z);idx=z.index
    raw=pd.Series(np.nan,index=idx);expl=pd.Series(np.nan,index=idx);loads=pd.DataFrame(np.nan,index=idx,columns=cols);ns=pd.Series(0,index=idx)
    if not cols:return raw,loads,expl,ns
    if len(cols)==1:
        raw=z.iloc[:,0];loads.iloc[:,0]=np.where(raw.notna(),1,np.nan);expl.loc[raw.notna()]=1;ns.loc[raw.notna()]=1
        return zscore(raw,hl),loads,expl,ns
    corr=z.ewm(halflife=hl,min_periods=12).corr();prev=None
    for t in idx:
        avail=[c for c in cols if pd.notna(z.at[t,c])]
        if len(avail)<2:continue
        cm=corr.loc[t]
        while len(avail)>1:
            counts=cm.loc[avail,avail].isna().sum(axis=1)
            if counts.max()==0:break
            avail.remove(counts.idxmax())
        if len(avail)<2:continue
        a=cm.loc[avail,avail].to_numpy();a=(a+a.T)/2
        val,vec=np.linalg.eigh(a)
        # Pairwise missingness can yield a non-PSD correlation matrix.
        a=(vec*np.maximum(val,1e-8))@vec.T;scale=np.sqrt(np.diag(a));a=a/np.outer(scale,scale)
        val,vec=np.linalg.eigh(a)
        v,objective=positive_loading(a,vec[:,-1],prev.reindex(avail,fill_value=0).values if prev is not None else None)
        v=pd.Series(v,index=avail)
        prev=v;loads.loc[t,avail]=v;raw[t]=z.loc[t,avail].dot(v)/np.sqrt(len(avail));expl[t]=objective/val.sum();ns[t]=len(avail)
    return zscore(raw,hl),loads,expl,ns

def weights(raw,anchors,cc,idx):
    a=[x for x in anchors if x['country']==cc];gmap={r['pk']:r['group'] for r in a}
    q=raw[raw.pk.isin(gmap)].copy();q['quarter']=pd.PeriodIndex(q.date,freq='Q');q['group']=q.pk.map(gmap)
    q=q.pivot(index='quarter',columns='group',values='value').sort_index()
    q=q.reindex(pd.period_range(q.index.min(),q.index.max(),freq='Q'))
    # TTM nominal flow shares. GDP, components within each country have common annualization.
    trailing=q.rolling(4,min_periods=4).sum();shares=trailing.div(trailing['GDP_REF'],axis=0)
    shares=shares.rename(columns={'C_actual':'C','I_TOTAL':'I'}).drop(columns='GDP_REF')
    shares['M']=-shares['M']
    if cc in INVESTMENT_SCOPE['countries']:
        rule=INVESTMENT_SCOPE['countries'][cc]
        wanted=[rule['total'],rule['gdp'],*rule['government']]
        records=raw[raw.pk.isin(wanted)].copy()
        records['quarter']=pd.PeriodIndex(records.date,freq='Q')
        panel=records.pivot(index='quarter',columns='pk',values='value').reindex(q.index)
        missing=set(wanted)-set(panel)
        if missing:raise ValueError(f'{cc}: general-government investment sources missing: {missing}')
        # Exact same-country nominal units/frequency within each ratio; no
        # mixing of quarterly amounts and SAAR. Japan uses all-NSA inputs.
        gov=panel[rule['government']].sum(axis=1,min_count=len(rule['government']))
        nongov=panel[rule['total']]-gov
        denom=panel[rule['gdp']].rolling(4,min_periods=4).sum()
        shares['I']=nongov.rolling(4,min_periods=4).sum()/denom
        shares['I_GOV']=gov.rolling(4,min_periods=4).sum()/denom
        assert (shares['I'].dropna()>=0).all(),(cc,'negative nongovernment investment share')
    lag=INVESTMENT_SCOPE['countries'].get(cc,{}).get('weight_lag_months',3)
    # Carry a previously available GDP composition until the next complete one;
    # this is a weight policy, never an interpolation of monthly PCA inputs.
    complete=shares.notna().all(axis=1)
    availability=pd.DataFrame({'quarter':[str(x) for x in shares.index], 'available':[x.asfreq('M').to_timestamp('M')+pd.offsets.MonthEnd(lag) for x in shares.index]})
    availability=availability.loc[complete.to_numpy()]
    w=pd.DataFrame(index=idx,columns=shares.columns,dtype=float);quarter=pd.Series(index=idx,dtype=object)
    for t in idx:
        valid=availability[availability.available<=t]
        if not len(valid):continue
        qkey=pd.Period(valid.iloc[-1]['quarter'],freq='Q');w.loc[t]=shares.loc[qkey];quarter[t]=str(qkey)
    return w,quarter

def list_values(s,idx):return [None if pd.isna(v) else round(float(v),6) for v in s.reindex(idx)]
def json_safe(v):
    if isinstance(v,dict):return {str(k):json_safe(x) for k,x in v.items()}
    if isinstance(v,list):return [json_safe(x) for x in v]
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.floating,float)):return None if not np.isfinite(v) else float(v)
    return v

def main():
    # A future normal BlackRock refresh is allowed; guarantee no mutation during
    # this independent calculation, while retaining the original audit baseline.
    baseline={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in READ(BASE/'blackrock_baseline_hashes.json')}
    (BASE/'blackrock_last_run_hashes.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8')
    review=READ(ROOT/'outputs/gdp_expenditure_review/report_data.json');meta=READ(BASE/'metadata.json');raw=pd.read_csv(BASE/'raw_haver.csv')
    wide,specs,audit=prepare(review,meta,raw)
    (BASE/'indicator_config.json').write_text(json.dumps(list(specs.values()),ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame(audit).to_csv(BASE/'selection_audit.csv',index=False,encoding='utf-8-sig')
    payload={'generated_kst':pd.Timestamp.now(tz='Asia/Seoul').isoformat(),'method':'Economic-direction-constrained EWM PCA; nonnegative loadings','names':review['names'],'groups':GROUPS,'countries':{},'input_count':len(specs),'specs':list(specs.values()),'audit_counts':dict(Counter(a['action'] for a in audit))}
    payload['investment_scope']=INVESTMENT_SCOPE
    timeseries=[];load_export=[];checks=[]
    for cc,name in review['names'].items():
        sp={k:s for k,s in specs.items() if s['country']==cc};country={'label':name,'versions':{}}
        for mode,hl in [('YoY',24)]:  # Momentum is derived from this completed PCA below.
            transformed=pd.DataFrame({k:transform(wide[s['pk']],s,mode) for k,s in sp.items()})
            z=zscore(transformed,hl);block={};diagnostics={}
            for group in sorted(set(s['group'] for s in sp.values())):
                keys=[k for k,s in sp.items() if s['group']==group]
                anchors=[k for k in keys if not sp[k]['ambiguous']]
                score,loads,ev,n=pca(z[keys],hl,anchors)
                block[group]=score
                diagnostics[group]={'features':keys,'explained':ev,'n':n,'loads':loads}
            # Balanced subblocks prevent the number of labor/soft indicators from
            # mechanically overwhelming the small number of consumption actuals.
            for parent,children in [('C',['C_actual','C_labor','C_sentiment']),('I',['I_business','I_housing'])]:
                kids=[g for g in children if g in block];panel=pd.DataFrame({g:block[g] for g in kids})
                score,loads,ev,n=pca(panel,hl,[kids[0]] if kids else None)
                # Do not call labor/sentiment alone a consumption observation.
                if parent=='C':score=score.where(panel.get('C_actual',pd.Series(np.nan,index=score.index)).notna())
                if len(kids)>1:score=score.where(panel.notna().sum(axis=1)==len(kids))
                block[parent]=score;diagnostics[parent]={'features':kids,'explained':ev,'n':n,'loads':loads}
            idx=wide.index;w,quarters=weights(raw,review['anchors'],cc,idx)
            comps=[g for g in ['C','I','INVENTORY','G','X','M'] if g in block and block[g].notna().any()]
            panel=pd.DataFrame({g:block[g] for g in comps}).reindex(idx)
            contrib=panel*w[comps];score=contrib.sum(axis=1,min_count=1)
            # No weight redistribution: retain the actual nominal-GDP shares.
            active=w[comps].abs().where(panel.notna()).sum(axis=1);total=w.abs().sum(axis=1)
            coverage=active/total;potential=w[comps].abs().sum(axis=1)/total
            required=[g for g in ['C','I','X','M'] if g in comps]
            valid=(panel[required].notna().all(axis=1))&(active>=w[comps].abs().sum(axis=1)*0.8)&w[comps].notna().all(axis=1)
            score=score.where(valid);contrib=contrib.where(valid)
            outidx=idx[idx>=pd.Timestamp('2005-01-01')]
            last=score.loc[outidx].last_valid_index();assert last is not None,(cc,mode,'No headline')
            # Verify the user's requested direction constraint in every block.
            detail=[]
            for k,s in sp.items():
                dg=diagnostics[s['group']];l=dg['loads'].at[last,k] if k in dg['loads'] else np.nan
                detail.append(dict(s,z=None if pd.isna(z.at[last,k]) else float(z.at[last,k]),loading=None if pd.isna(l) else float(l),
                    raw_direction_loading=None if pd.isna(l) else float(l*s['direction']),direction_conflict=bool(pd.notna(l) and l<0 and not s['ambiguous'])))
            version={'dates':[str(t)[:7] for t in outidx],'headline':list_values(score,outidx),
                'blocks':{g:list_values(s,outidx) for g,s in block.items()},'contributions':{g:list_values(contrib[g],outidx) for g in comps},
                'weights':{g:list_values(w[g],outidx) for g in w},'coverage':list_values(coverage,outidx),'potential_coverage':list_values(potential,outidx),
                'weight_quarters':[quarters.get(t) if pd.notna(quarters.get(t)) else None for t in outidx],
                'latest':str(last)[:7],'latest_value':float(score.at[last]),'latest_weights':w.loc[last].to_dict(),
                'latest_contributions':contrib.loc[last].to_dict(),'latest_coverage':float(coverage.at[last]),'latest_quarter':quarters[last],
                'included_components':comps,'missing_components':[g for g in ['C','I','INVENTORY','G','X','M'] if g not in comps],
                'diagnostics':{g:{'features':v['features'],'n':int(v['n'].get(last,0)),'explained':v['explained'].get(last),'single':len(v['features'])==1} for g,v in diagnostics.items()},
                'indicators':detail,'negative_loadings':sum(r['direction_conflict'] for r in detail)}
            country['versions'][mode]=version
            assert version['negative_loadings']==0,(cc,mode)
            for t in outidx:
                timeseries.append(dict(country=cc,version=mode,date=str(t)[:10],headline=score.get(t),coverage=coverage.get(t),weight_quarter=quarters.get(t),
                    **{'pca_'+g:s.get(t) for g,s in block.items()},**{'contrib_'+g:contrib[g].get(t) for g in comps},**{'weight_'+g:w[g].get(t) for g in w}))
            for g,dg in diagnostics.items():
                for t in dg['loads'].index.intersection(outidx):
                    for k,l in dg['loads'].loc[t].dropna().items():load_export.append(dict(country=cc,version=mode,date=str(t)[:10],group=g,indicator=k,loading=float(l)))
            err=(contrib.sum(axis=1,min_count=1)-score).abs().max();assert err<1e-10
            checks.append(dict(country=cc,version=mode,latest=str(last)[:7],first=str(score.loc[outidx].first_valid_index())[:7],contribution_error=float(err),inputs=len(sp),negative_loadings=version['negative_loadings']))
            print(cc,mode,'inputs',len(sp),'latest',last.date(),'score',round(score[last],3),'coverage',round(coverage[last],3),'negative-loadings',version['negative_loadings'],flush=True)
        payload['countries'][cc]=country
    pd.DataFrame(timeseries).to_csv(BASE/'indices.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(load_export).to_csv(BASE/'loadings.csv',index=False,encoding='utf-8-sig')
    (BASE/'dashboard_data.json').write_text(json.dumps(json_safe(payload),ensure_ascii=False,allow_nan=False),encoding='utf-8')
    unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in baseline.items());assert unchanged
    (BASE/'validation.json').write_text(json.dumps({'models':checks,'blackrock_unchanged':unchanged,'selection':payload['audit_counts'],'inputs':len(specs)},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
    main()
    from derive_momentum import main as derive_momentum
    derive_momentum()
