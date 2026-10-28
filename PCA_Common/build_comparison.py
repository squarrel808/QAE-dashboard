"""Frozen-data audit of the 2026-10-29 PCA methodology migration."""
import hashlib,json,pickle,sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from PCA_Common.fixed_pca import POLICY
B=ROOT/'outputs/pca_cfna_comparison';OLD=B/'before'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
snapshot=read(OLD/'snapshot.json')
for name,digest in snapshot['raw_hashes'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,('Raw vintage changed',name)

old_i=pickle.loads((OLD/'pca_i_results.pkl').read_bytes())
new_i=pickle.loads((ROOT/'PCA/model_results.pkl').read_bytes())
labels=pd.read_csv(ROOT/'PCA/fixed_loadings.csv').set_index(['country','axis','pk']).label.to_dict()
data={'asof':'2026-10-29','methodology':POLICY,'raw_unchanged':True,'models':{},'summary':[]}
series_rows=[];loading_rows=[];sector_rows=[]

def serial(s):
    return {str(t)[:7]:None if pd.isna(v) else float(v) for t,v in s.items()}
def post(s):
    return s.reindex(pd.date_range(s.index.min(),s.index.max(),freq='ME')).rolling(3).mean().diff(3)
def metric(a,b):
    x=pd.concat([a.rename('old'),b.rename('new')],axis=1,sort=True).dropna().loc['2016-01-01':]
    return dict(n=len(x),correlation=float(x.old.corr(x.new)),mean_abs_change=float((x.new-x.old).abs().mean()))
def indicator(cc,model,axis,pk,label,old_loading,new_loading,direction,old_signed=None):
    row=dict(country=cc,model=model,axis=axis,pk=pk,label=label,old_loading=old_loading,new_loading=new_loading,
             economic_direction=direction,old_signed=old_loading*direction if old_signed is None and old_loading is not None else old_signed,
             new_signed=new_loading*direction)
    loading_rows.append(row);return row

for model,path in [('I',None),('II','PCA_Four_Axis'),('III','PCA_BlackRock_Only')]:
    panels={};data['models'][model]=panels
    if path:
        old=read(OLD/path/'dashboard_data.json');new=read(ROOT/path/'dashboard_data.json')
        assert old['names']==new['names']
        assert {(r['country'],r['axis'],r['pk'],r['kind'],r['direction']) for r in old['indicators']}=={(r['country'],r['axis'],r['pk'],r['kind'],r['direction']) for r in new['indicators']}
        assert read(OLD/path/'annual_weights.json')==read(ROOT/path/'annual_weights.json')
        frames=[pd.read_csv(p/'indices.csv',parse_dates=['date']) for p in [OLD/path,ROOT/path]]
    for cc in ['US','UK']:
        if path:
            a,b=[x[x.country.eq(cc)&x.version.eq('YoY')].set_index('date') for x in frames]
            am,bm=[x[x.country.eq(cc)&x.version.eq('Momentum')].set_index('date') for x in frames]
            latest=min(a.headline.last_valid_index(),b.headline.last_valid_index())
            old_level,new_level=a.headline,b.headline;old_mom,new_mom=am.headline,bm.headline
            axes=list(new['axes']);load=[]
            prior={(r['country'],r['pk']):r for r in old['indicators']}
            for r in new['indicators']:
                if r['country']!=cc:continue
                prev=prior[(cc,r['pk'])]
                load.append(indicator(cc,model,r['axis'],r['pk'],r['label'],prev['loading'],r['loading'],r['direction']))
            sector=[]
            for axis in axes:
                sector.append(dict(axis=axis,old_level=a.at[latest,axis],new_level=b.at[latest,axis],
                    old_momentum=am.at[latest,axis],new_momentum=bm.at[latest,axis],
                    old_contribution=a.at[latest,'contrib_'+axis],new_contribution=b.at[latest,'contrib_'+axis]))
            fit={k:v.get('fit',{}) for k,v in new['countries'][cc]['diagnostics'].items()}
        else:
            a,b=old_i[cc]['YoY'],new_i[cc]['YoY'];am,bm=old_i[cc]['Momentum'],new_i[cc]['Momentum']
            old_level,new_level=a['gdp'],b['gdp'];old_mom,new_mom=am['gdp'],bm['gdp']
            assert set(a['z'])==set(b['z']) and set(a['cat_index'])==set(b['cat_index'])
            latest=min(old_level.last_valid_index(),new_level.last_valid_index())
            load=[];sector=[];fit=b['fit_details']
            for axis,loading in b['cat_loadings'].items():
                if axis=='lei':continue
                for pk in loading:
                    before=a['cat_loadings'][axis].reindex([latest])[pk].iloc[0]
                    after=loading.iloc[-1][pk]
                    load.append(indicator(cc,model,axis.title(),pk,labels[(cc,axis,pk)],None if pd.isna(before) else float(before),float(after),1))
                val=lambda obj,key:float(obj[key][axis].get(latest,np.nan))
                sector.append(dict(axis=axis.title(),old_level=val(a,'cat_index'),new_level=val(b,'cat_index'),
                    old_momentum=val(am,'cat_index'),new_momentum=val(bm,'cat_index'),
                    old_contribution=val(a,'gdp_contrib'),new_contribution=val(b,'gdp_contrib')))
        month=str(latest)[:7]
        panel={'country':cc,'latest':month,'old_level':serial(old_level),'new_level':serial(new_level),
               'old_momentum':serial(old_mom),'new_momentum':serial(new_mom),
               'old_level_post_momentum':serial(post(old_level)),
               'sectors':sector,'loadings':load,'fit':fit,
               'comparison':{'Level':metric(old_level,new_level),'Momentum':metric(old_mom,new_mom)}}
        panels[cc]=panel
        row=dict(country=cc,model=model,month=month,old_level=float(old_level[latest]),new_level=float(new_level[latest]),
                 old_momentum=float(old_mom[latest]),new_momentum=float(new_mom[latest]),old_level_post_momentum=float(post(old_level)[latest]))
        data['summary'].append(row)
        for s in sector:sector_rows.append(dict(country=cc,model=model,month=month,**s))
        for key in ['old_level','new_level','old_momentum','new_momentum','old_level_post_momentum']:
            series_rows.extend(dict(country=cc,model=model,series=key,month=t,value=v) for t,v in panel[key].items())

def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list):return [clean(v) for v in x]
    if isinstance(x,(float,np.floating)):return None if not np.isfinite(x) else float(x)
    if isinstance(x,np.integer):return int(x)
    return x
data=clean(data)
B.mkdir(exist_ok=True)
(B/'comparison.json').write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding='utf8')
pd.DataFrame(data['summary']).to_csv(B/'summary.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(sector_rows).to_csv(B/'sectors.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(loading_rows).to_csv(B/'loadings.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(series_rows).to_csv(B/'series.csv',index=False,encoding='utf-8-sig')
html=(Path(__file__).parent/'comparison_template.html').read_text(encoding='utf8').replace('__DATA__',json.dumps(data,ensure_ascii=False,allow_nan=False).replace('</','<\\/'))
(B/'index.html').write_text(html,encoding='utf8')
dest=ROOT/'macro_hub/public/embeds/pca-comparison';dest.mkdir(exist_ok=True,parents=True)
for name in ['index.html','comparison.json','summary.csv','sectors.csv','loadings.csv','series.csv']:
    (dest/name).write_bytes((B/name).read_bytes())
print(pd.DataFrame(data['summary']).round(4).to_string(index=False))
print('PASS: raw-data hashes, country/input/transformation membership and frozen GDP weights unchanged')
