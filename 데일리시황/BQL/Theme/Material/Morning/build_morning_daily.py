"""Latest-session morning quant tables. Prose is attached separately."""
import argparse, contextlib, json, math, sys
from datetime import date
from pathlib import Path
import numpy as np
import openpyxl

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--qae',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--cutoff',type=date.fromisoformat,required=True)
    a=p.parse_args()
    mat=a.qae/'데일리시황/BQL/Theme/Material'
    sys.path.insert(0,str(mat/'Morning'))
    from build_morning_bql import load,sha,save,table,kpis,bars,CSS
    s=load(mat/'Sector_Industry/Reports/build_sector_rotation_html.py','daily_sector')
    ai=load(mat/'AI/build_ai_value_chain_html.py','daily_ai')
    master=a.qae/'데일리시황/BQL/Rawfile/BQuant_Master.xlsx'
    hashes={'master':sha(master),'source':sha(a.source)}
    markets=[]; audit=[]
    with contextlib.closing(openpyxl.load_workbook(master,read_only=True,data_only=True)) as wb:
        for key in s.MARKETS:
            raw=s.load_market(wb,key)
            m=s.build_market(raw,'1D',3,a.cutoff)
            end,starts,sessions=s.resolve_windows(raw,a.cutoff)
            ix=starts['1D']; v=np.array(m['stock']['returns']['1D'],dtype=float)
            cap=raw.market_caps[:,ix]; valid=np.isfinite(v); good=valid & np.isfinite(cap) & (cap>0)
            assert abs(np.average(v[good],weights=cap[good])-m['benchmark']['constituentReturns']['1D'])<1e-12
            m['positiveCount']=int(np.sum(v[valid]>0));m['validCount']=int(valid.sum())
            assert abs(m['positiveCount']/m['validCount']-m['benchmark']['breadth']['1D'])<1e-12
            for group in m['sectors']:
                group['bottom']=[i for i in group['bottom'] if i not in group['top']]
            audit.append({'market':key,'start':m['periodStart']['1D'],'end':m['asOf'],'positive':m['positiveCount'],'valid':m['validCount']})
            markets.append(m)
    asof=max(m['asOf'] for m in markets);tag=asof.replace('-','')
    def num(v):return f'<span class="{s.value_class(v)}">{s.pct(v,2)}</span>'
    original=s.render_market_panel
    def panel(m,descriptions,active=False):
        out=original(m,descriptions,active).replace('기준 상위·하위 종목 각 5개','기준 상위·하위 종목 각 3개 (중복 제외)')
        top=kpis([('시장 BM · Index Level',num(m['benchmark']['returns']['1D']),m['periodStart']['1D']+' → '+m['asOf']),('1D 상승 종목 비율',s.breadth_pct(m['benchmark']['breadth']['1D']),f'{m["positiveCount"]} / {m["validCount"]} 유효 종목'),('선두 섹터',s.esc(m['sectors'][0]['sector']),num(m['sectors'][0]['returns']['1D'])),('후행 섹터',s.esc(m['sectors'][-1]['sector']),num(m['sectors'][-1]['returns']['1D']))])
        return out.replace('<h2>1. 전체 섹터',top+'<h2>1. 전체 섹터')
    s.render_market_panel=panel
    universe={r['industry']:r['sector'] for r in markets[0]['industries']}
    for m in markets:
        missing=set(universe)-{r['industry'] for r in m['industries']}
        for name in sorted(missing):
            m['industries'].append({'industry':name+' · 구성종목 없음','sector':universe[name],'n':0,'indices':[],'returns':{p:None for p in s.PERIODS},'breadth':{p:None for p in s.PERIODS}})
    page=s.render_combined_html(markets,'1D',s.load_descriptions(s.DEFAULT_DESCRIPTION_BOOK))
    rows=[]
    for name in sorted({r['sector'] for m in markets for r in m['sectors']}):
        row=[s.esc(name)]
        for m in markets:
            item=next((r for r in m['sectors'] if r['sector']==name),None)
            val=item['returns']['1D'] if item else None
            row.extend([num(val),num(val-m['benchmark']['returns']['1D']) if val is not None else '—'])
        rows.append(row)
    rows.append(['BM 수익률']+[x for m in markets for x in [num(m['benchmark']['returns']['1D']),'—']])
    rows.append(['1D 상승 종목 비율']+[x for m in markets for x in [s.breadth_pct(m['benchmark']['breadth']['1D']),f'{m["positiveCount"]}/{m["validCount"]}']])
    comp=table(['섹터']+[x for m in markets for x in [m['title']+' 1D','BM 대비']],rows,'market-comparison')
    page=page.replace('<nav class="market-tabs"','<h2>유럽·미국·일본·항생 — 섹터 1D 비교</h2>'+comp+'<nav class="market-tabs"').replace('</style>',CSS+'</style>')
    sd=a.output/'Sector_Industry';sd.mkdir(parents=True,exist_ok=True)
    (sd/'sector_1D.html').write_text(page,encoding='utf-8')
    save(sd/'sector_1D.json',s.sanitize_for_json({'asOf':asof,'primary':'1D','markets':markets}))
    print('SECTOR_DONE='+asof,flush=True)
    raw=ai.ai.load_spx([master]);keep=[i for i,d in enumerate(raw.dates) if d<=a.cutoff]
    raw.dates=[raw.dates[i] for i in keep];raw.metrics={k:v[:,keep] for k,v in raw.metrics.items()}
    data=ai.ai.build_data(raw)
    assert data['meta']['asOf']==next(m['asOf'] for m in markets if m['key']=='SP500') and len(data['stages'])==12
    page=ai.render(data,'1D')
    for mode in ['Core','Expanded']:
        allowed={'Core'} if mode=='Core' else {'Core','Adjacent'}
        stocks=[r for r in data['stocks'] if r['confidence'] in allowed and r['returns']['1D'] is not None]
        ranked=sorted(data['stages'],key=lambda r:data['modes'][mode][r['key']]['performance']['1D']['return'] if data['modes'][mode][r['key']]['performance']['1D']['return'] is not None else -math.inf,reverse=True)
        vals=[(r['short'],data['modes'][mode][r['key']]['performance']['1D']['return']) for r in ranked]
        assert all(v is None or math.isfinite(v) for _,v in vals)
        top=kpis([('S&P 500 · Index Level BM',num(data['benchmark']['returns']['1D']),data['periodStarts']['1D']+' → '+asof),('상승 AI 종목',f'{sum(r["returns"]["1D"]>0 for r in stocks)} / {len(stocks)}','중복 없는 유효 종목'),('선두 밸류체인',s.esc(vals[0][0]),num(vals[0][1])),('후행 밸류체인',s.esc(vals[-1][0]),num(vals[-1][1]))])+bars(vals,s.esc,lambda v:s.pct(v,2))
        page=page.replace(f'data-mode="{mode}"><h2>',f'data-mode="{mode}">{top}<h2>')
    page=page.replace('class="mode-panel active" data-mode="Core"','class="mode-panel" data-mode="Core"').replace('class="mode-panel" data-mode="Expanded"','class="mode-panel active" data-mode="Expanded"')
    page=page.replace('class="mode-button active" onclick="showMode(\'Core\',this)"','class="mode-button" onclick="showMode(\'Core\',this)"').replace('class="mode-button" onclick="showMode(\'Expanded\',this)"','class="mode-button active" onclick="showMode(\'Expanded\',this)"')
    page=page.replace('</style>',CSS+'</style>')
    ad=a.output/'AI';ad.mkdir(exist_ok=True)
    (ad/'ai_1D.html').write_text(page,encoding='utf-8');save(ad/'ai_data.json',data)
    assert hashes=={'master':sha(master),'source':sha(a.source)}
    save(a.output/'manifest.json',{'asOf':asof,'primary':'1D','markets':audit,'hashes':hashes,'scope':'Sector and AI only; no theme, macro or IB','status':'success'})
    print('QUANT_DONE='+str(a.output),flush=True)

if __name__=='__main__':main()
