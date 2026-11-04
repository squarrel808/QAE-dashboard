"""Render the statistical loading audit; does not publish or alter models."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent.parent.parent;O=R/'outputs/pca_loading_audit'
D=json.loads((O/'audit.json').read_text(encoding='utf8'))
plt.rcParams['font.family']=font_manager.FontProperties(fname='C:/Windows/Fonts/malgun.ttf').get_name()
plt.rcParams['axes.unicode_minus']=False
plt.rcParams['font.size']=9
axes=['Consumer','Capex','Housing','Export'];names={'US':'미국','UK':'영국','FR':'프랑스','DE':'독일','CA':'캐나다','JP':'일본','AU':'호주'}
fig,axs=plt.subplots(3,2,figsize=(13,12),layout='constrained')
for j,model in enumerate(['II','III']):
    countries=['US','UK']+(['FR'] if model=='II' else [])+['DE','CA','JP','AU']
    for k,(measure,title,lo,hi) in enumerate([
        ('cosine_old_new_common','기존 vs 현재 로딩 방향 유사도',.85,1),
        ('new_explained','현재 PC1 설명분산 (%)',0,100),
        ('bootstrap24','재표본화 방향 유사도 · 하위 5%',.3,1)]):
        values=np.full((len(countries),4),np.nan);texts={}
        for row in D['panels']:
            if row['model']!=model:continue
            i=countries.index(row['country']);a=axes.index(row['axis'])
            if row['status']!='pca':texts[(i,a)]='단일' if row['status']=='single' else '—';continue
            value=row[measure]['cosine_p05'] if measure=='bootstrap24' else row[measure]*(100 if measure=='new_explained' else 1)
            values[i,a]=value;texts[(i,a)]=f'{value:.1f}' if measure=='new_explained' else f'{value:.3f}'
        ax=axs[k,j];im=ax.imshow(values,cmap='YlGnBu',vmin=lo,vmax=hi,aspect='auto')
        ax.set_facecolor('#edf0f3');ax.set_xticks(range(4),axes);ax.set_yticks(range(len(countries)),[names[c] for c in countries])
        ax.set_title('PCA '+model+' · '+title,pad=12,fontweight='bold')
        for (i,a),txt in texts.items():ax.text(a,i,txt,ha='center',va='center',color='white' if np.isfinite(values[i,a]) and (values[i,a]-lo)/(hi-lo)>.65 else '#172e43')
        fig.colorbar(im,ax=ax,shrink=.8)
fig.suptitle('카테고리별 로딩 변화와 표본 안정성 · 2026-10-29\n유사도는 1에 가까울수록 방향이 같음 · 설명분산은 GDP 설명력이 아님',fontsize=15,fontweight='bold')
fig.savefig(O/'statistical_overview.png',dpi=160);plt.close(fig)
I=pd.DataFrame(D['indicators'])
for axis in axes:
    fig,axs=plt.subplots(2,2,figsize=(15,11),layout='constrained')
    for j,model in enumerate(['II','III']):
        for k,cc in enumerate(['US','UK']):
            t=I[(I.model==model)&(I.country==cc)&(I.axis==axis)].copy()
            t['importance']=t.change.abs().fillna(-1)
            t=t.sort_values('importance',ascending=False).head(10)
            key='derived:uk_mgsx_endmonth'
            if axis=='Consumer' and model=='II' and cc=='UK' and key not in set(t.pk):
                t=pd.concat([t.iloc[:9],I[(I.model==model)&(I.country==cc)&I.pk.eq(key)]])
            t=t.sort_values('new_loading');ax=axs[k,j];ys=np.arange(len(t))
            ax.hlines(ys,t.bootstrap24_p05,t.bootstrap24_p95,color='#bed5e5',lw=5,alpha=.8,label='현재 계수 재표본화 5~95%')
            ax.scatter(t.old_loading,ys+.15,s=32,color='#8a96a3',label='기존 제약 EWM',zorder=3)
            ax.scatter(t.constraint_only_loading,ys,s=40,color='#d68b2e',marker='x',label='기존 행렬 · 제약만 해제',zorder=4)
            ax.scatter(t.new_loading,ys-.15,s=30,color='#176b97',label='현재 전체 표본',zorder=3)
            ax.axvline(0,color='#b0bac4',lw=.8,linestyle='--');ax.set_yticks(ys,t.pk);ax.grid(axis='x',alpha=.15)
            ax.set_title(f'PCA {model} · {names[cc]} · {axis}',fontweight='bold')
            ax.set_xlabel('경제적 방향을 적용한 입력의 계수 · 단위 벡터')
    handles,labels=axs[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=2,frameon=False)
    fig.suptitle(axis+' · 로딩 변화가 큰 지표 (미국·영국)\n재표본화 범위는 민감도 진단이며 정식 유의성 검정이 아닙니다.',fontsize=15,fontweight='bold')
    fig.savefig(O/(axis.lower()+'_loadings.png'),dpi=155);plt.close(fig)

groups=[]
for (m,c,a,g),x in I.groupby(['model','country','axis','group']):
    if a!='Consumer':continue
    groups.append(dict(model=m,country=c,group=g,old_squared_share=float((x.old_loading.fillna(0)**2).sum()),new_squared_share=float((x.new_loading**2).sum()),score_term=float(x.current_score_term.sum())))
D['consumer_groups']=groups
pd.DataFrame(groups).to_csv(O/'consumer_groups.csv',index=False,encoding='utf-8-sig')
template=(R/'PCA/PCA_Common/loading_report_template.html').read_text(encoding='utf8')
(O/'index.html').write_text(template.replace('__DATA__',json.dumps(D,ensure_ascii=False,allow_nan=False).replace('</','<\\/')),encoding='utf8')
print('Audit report and 5 research figures saved:',O/'index.html')
