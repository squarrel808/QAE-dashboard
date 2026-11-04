"""Quantitative presentation completion; never called by prose attachment."""
import argparse,contextlib,json,sys
from pathlib import Path
import numpy as np
import openpyxl
from bs4 import BeautifulSoup

def serialize(dom):
    import re
    text=str(dom);m=dom.main
    text=re.sub(r'<main\b[^>]*>',f'<main data-report="{m["data-report"]}" data-as-of="{m["data-as-of"]}" data-primary="{m["data-primary"]}">',text,count=1)
    for node in dom.select('.commentary-slot'):
        token=f'<div class="commentary-slot" data-commentary-slot="{node["data-commentary-slot"]}" data-commentary-id="{node["data-commentary-id"]}"></div>'
        text=text.replace(str(node),token)
    return text

def main():
    p=argparse.ArgumentParser();p.add_argument('--qae',type=Path,required=True);p.add_argument('--quant',type=Path,required=True);p.add_argument('--normalize-only',action='store_true');a=p.parse_args()
    if a.normalize_only:
        for name in ('Sector_Industry/sector_1D.html','AI/ai_1D.html'):
            path=a.quant/name;path.write_text(serialize(BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser')),encoding='utf-8')
        return
    mat=a.qae/'데일리시황/BQL/Theme/Material';sys.path.insert(0,str(mat/'Morning'))
    from build_morning_bql import load,save,table,sha
    s=load(mat/'Sector_Industry/Reports/build_sector_rotation_html.py','complete_sector')
    ai=load(mat/'AI/build_ai_value_chain_html.py','complete_ai')
    payload=json.loads((a.quant/'Sector_Industry/sector_1D.json').read_text(encoding='utf-8'))
    master=a.qae/'데일리시황/BQL/Rawfile/BQuant_Master.xlsx';before=sha(master)
    dom=BeautifulSoup((a.quant/'Sector_Industry/sector_1D.html').read_text(encoding='utf-8'),'html.parser')
    def num(v):return f'<span class="{s.value_class(v)}">{s.pct(v,2)}</span>'
    with contextlib.closing(openpyxl.load_workbook(master,read_only=True,data_only=True)) as wb:
        for m in payload['markets']:
            raw=s.load_market(wb,m['key']);start=raw.dates.index(__import__('datetime').date.fromisoformat(m['periodStart']['1D']))
            caps=raw.market_caps[:,start];valid=np.isfinite(caps)&(caps>0);total=float(caps[valid].sum())
            rows=[]
            for rank,g in enumerate(m['industries'],1):
                ix=[i for i,n in enumerate(m['stock']['industry']) if n==g['industry']]
                weight=float(sum(caps[i] for i in ix if valid[i])/total)
                g['weight']=weight
                val=g['returns']['1D']
                rows.append([rank if g['n'] else '—',s.esc(g['industry']),s.esc(g['sector']),g['n'],f'{weight:.2%}',num(val),num(val-m['benchmark']['returns']['1D']) if val is not None else '—',s.breadth_pct(g['breadth']['1D'])])
            panel=dom.select_one('#panel-'+m['key']);heading=next(h for h in panel.find_all('h2') if h.text.startswith('5. 전체 산업그룹'))
            heading.find_next_sibling('div').replace_with(BeautifulSoup(table(['순위','산업그룹','소속 섹터','N','시작일 시총 비중','1D','BM 대비','1D 상승 비율'],rows,m['key']+'-industry-ranking'),'html.parser'))
            assert len(rows)>=25
    (a.quant/'Sector_Industry/sector_1D.html').write_text(serialize(dom),encoding='utf-8')
    save(a.quant/'Sector_Industry/sector_1D.json',payload)
    data=json.loads((a.quant/'AI/ai_data.json').read_text(encoding='utf-8'))
    dom=BeautifulSoup((a.quant/'AI/ai_1D.html').read_text(encoding='utf-8'),'html.parser')
    checked=[]
    for mode in ('Core','Expanded'):
        allowed={'Core'} if mode=='Core' else {'Core','Adjacent'}
        panel=dom.select_one('[data-mode="'+mode+'"]')
        for section,stage in zip(panel.select('section.chain'),data['stages']):
            allstocks=[r for r in data['stocks'] if r['stage']==stage['key'] and r['confidence'] in allowed]
            ranked=sorted([r for r in allstocks if r['returns']['1D'] is not None],key=lambda r:r['returns']['1D'],reverse=True)
            n=len(ranked);nt=min(3,n//2) if n>1 else n
            top=ranked[:nt];bottom=list(reversed(ranked[max(nt,n-3):]))
            assert not {r['ticker'] for r in top}&{r['ticker'] for r in bottom}
            selected={r['ticker']:label for label,group in [('상위',top),('하위',bottom)] for r in group}
            # Keep all constituent rows and descriptions, marking disjoint leaders/laggards.
            tbody=section.select_one('tbody');stocks=sorted(allstocks,key=lambda r:r['returns']['1D'] if r['returns']['1D'] is not None else -999,reverse=True)
            assert len(tbody.find_all('tr',recursive=False))==len(stocks)
            for tr,r in zip(tbody.find_all('tr',recursive=False),stocks):
                name=tr.select_one('.stock-name');label=selected.get(r['ticker'])
                if label:name.insert(0,'['+label+'] ')
            summary=dom.new_tag('p',attrs={'class':'desc'});summary.string=f'1D 상위 {len(top)}개 / 하위 {len(bottom)}개 표시 · 중복 제외 · 전체 구성종목 성과도 함께 유지'
            section.select_one('.table-wrap').insert_before(summary)
            checked.append({'mode':mode,'stage':stage['key'],'top':[r['ticker'] for r in top],'bottom':[r['ticker'] for r in bottom]})
    (a.quant/'AI/ai_1D.html').write_text(serialize(dom),encoding='utf-8')
    assert sha(master)==before
    save(a.quant/'presentation_checks.json',{'industryGroups':{m['key']:len(m['industries']) for m in payload['markets']},'disjointMovers':checked,'masterUnchanged':True})
    print('PRESENTATION_CHECKS_OK',flush=True)

if __name__=='__main__':main()
