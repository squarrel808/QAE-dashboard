"""Attach authored prose to validated 1D tables, then update BQL entry links only."""
import argparse,json,sys,re,shutil
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

def main():
    p=argparse.ArgumentParser();p.add_argument('--qae',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--content',type=Path,required=True);p.add_argument('--observations',type=Path,required=True);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    mat=a.qae/'데일리시황/BQL/Theme/Material';sys.path.insert(0,str(mat/'Morning'))
    from build_morning_bql import load,save,sha
    helper=load(mat/'Morning/runs/20260928_20260925_calendar/finalize_morning_bql.py','prose_helpers')
    common=load(mat/'attach_commentary.py','daily_attach');helper.install_prose_renderer(common)
    n=json.loads(a.content.read_text(encoding='utf-8'));obs=helper.observations(a.observations)
    quant=a.run/'quant';sector=json.loads((quant/'Sector_Industry/sector_1D.json').read_text(encoding='utf-8'));ai=json.loads((quant/'AI/ai_data.json').read_text(encoding='utf-8'))
    assert n['date']==sector['asOf']==ai['meta']['asOf']
    tag=n['date'].replace('-','');out=a.qae/'데일리시황/BQL/Theme/output'/tag
    endlabel=n['date'][5:].replace('-','/');startlabel=sector['markets'][0]['periodStart']['1D']
    written=datetime.strptime(a.source.stem,'%Y%m%d').date().isoformat() if re.fullmatch(r'\d{8}',a.source.stem) else datetime.now().date().isoformat()
    def item(title,body):return {'title':title,'body':body,'date':n['date'],'source':n['source']}
    sp={'global':[item(*r) for r in n['sector_global']],'markets':{},'sectors':{},'stocks':{}}
    for market,rows in n['contexts'].items():
        sp['markets'][market]=[item('섹터 원문 해설: '+title,body) for title,body in rows]
        sp['markets'][market].append(item('섹터 원문 해설: 원문 검토·계산 구분',n['quality']))
        for r in obs:
            if r['market']==market:sp['markets'][market].append(item('종목 해석: '+r['company'],'\n'.join(r[k] for k in ('observation','catalyst','readthrough'))))
    maps={
      'STOXX600':{'Financials':1,'Real Estate':1,'Industrials':1,'Energy':2,'Materials':3,'Utilities':3,'Consumer Staples':4,'Consumer Discretionary':4,'Health Care':4,'Information Technology':5,'Communication Services':5},
      'TOPIX':{'Communication Services':1,'Industrials':1,'Materials':2,'Information Technology':2,'Financials':3,'Consumer Staples':4,'Consumer Discretionary':4,'Health Care':4,'Utilities':4,'Real Estate':4,'Energy':4}}
    def stockprose(name,marketobs):
        r=helper.match_company(name,marketobs)
        if not r:return item('개별 촉매','제공 원문에서 확인된 개별 기업 촉매 없음. 아래 순위는 BQL 1D 가격 관측이다.')
        return item('원문 종목 코멘트',r['catalyst']+' '+r['readthrough']+' ['+r['observation']+']')
    for m in sector['markets']:
        key=m['key'];sp['sectors'][key]={};sp['stocks'][key]={}
        records=[r for r in obs if r['market']==key]
        for g in m['sectors']:
            name=g['sector']
            if key=='SP500':body=next((b for t,b in n['contexts'][key] if t.startswith(name+' —')),'제공 원문의 독립적인 섹터 촉매는 제한적이다.')
            elif key in maps:body=n['contexts'][key][maps[key][name]][1]
            else:body=n['contexts'][key][0][1] if name in ('Health Care','Information Technology','Consumer Discretionary','Financials') else '제공 원문에서 독립적인 섹터 촉매는 확인되지 않았다. 아래 BQL 가격 성과와 원문 홍콩·중국 참고 해설을 구분한다.'
            sp['sectors'][key][name]=item('섹터 움직임',body)
            for idx in g['top']+g['bottom']:
                ticker=m['stock']['ticker'][idx];name=m['stock']['name'][idx]
                sp['stocks'][key][ticker]=stockprose(name,records)
    ap={'global':[item(*r) for r in n['ai_global']],'stages':{k:item('밸류체인 해석',v) for k,v in n['stages'].items()},'stocks':{}}
    # Retain source-only discussion in a collapsed review block rather than presenting it as a KPI.
    ap['global'].append(item('섹터 원문 해설: 원문 검토·계산 구분',n['quality']))
    us=[r for r in obs if r['market']=='SP500']
    for stock in ai['stocks']:
        if helper.match_company(stock['company'],us):ap['stocks'][stock['ticker']]=stockprose(stock['company'],us)
    ai_names=[r['company'] for r in ai['stocks']]
    for r in us:
        if any(helper.match_company(name,[r]) for name in ai_names):
            ap['global'].append(item('종목 해석: '+r['company'],'\n'.join(r[k] for k in ('observation','catalyst','readthrough'))))
    paths={'sector':out/f'Sector_Industry/유럽_미국_일본_섹터_산업_1D_코멘터리_{tag}.html','ai':out/f'AI/SP500_AI_밸류체인_1D_코멘터리_{tag}.html'}
    checks={}
    for kind,base,payload in [('sector',quant/'Sector_Industry/sector_1D.html',sp),('ai',quant/'AI/ai_1D.html',ap)]:
        checks[kind]=helper.attach(common,base,payload,paths[kind],a.run/(kind+'_commentary.json'))
        doc=BeautifulSoup(paths[kind].read_text(encoding='utf-8'),'html.parser')
        assert doc.main['data-primary']=='1D' and doc.main['data-as-of']==n['date']
        assert '\ufffd' not in doc.get_text() and 'undefined' not in doc.get_text() and 'NaN' not in doc.get_text()
        if kind=='sector':
            for market in sp['markets']:
                expected=sum(r['market']==market for r in obs)
                assert len(doc.select('#panel-'+market+' tr[data-source-observation]'))==expected,(market,expected)
        else:
            assert len(doc.select('.mode-panel[data-mode="Expanded"] section.chain'))==12
            assert doc.select_one('.mode-panel.active')['data-mode']=='Expanded'
    # A link page contains no regenerated quantitative table.
    body='<h1>아침시황 — 1D</h1><p>주가 기준 '+n['date']+' · 비교 종가 '+startlabel+' → '+n['date']+' · Bloomberg '+written+' 작성 원문</p>'
    body+='<div class="morning-headlines">'+''.join('<article class="card headline"><h3>'+helper.E(t.split(': ',1)[-1])+'</h3><p>'+helper.E(b)+'</p></article>' for t,b in n['sector_global'][:2])+'</div><div class="cards">'
    for kind,title,desc in [('sector','유럽·미국·일본 섹터·산업','1D 전체 성과·산업그룹·상하위 3개 + 원문 종목 해석. 홍콩·중국 참고 포함.'),('ai','S&P 500 AI 밸류체인','12단계 1D 성과·상하위 표시·전 종목표 + Core/인접 토글·코멘트.')]:
        body+='<a class="card report-link" href="'+paths[kind].relative_to(out).as_posix()+'"><h3>'+title+'</h3><p>'+desc+'</p></a>'
    body+='</div><p class="muted">Theme Rotation은 요청에 따라 제외했습니다. 5D 주간 보고서·경제지표·Consensus·IB는 이번 실행에서 갱신하지 않았습니다. 일본 장기 구간은 가격 이력 부족으로 비워 두었습니다.</p>'
    setpath=out/f'아침시황_1D_세트_{tag}.html';setpath.write_text(helper.shell('아침시황 1D — '+n['date'],body),encoding='utf-8')
    entry=a.qae/'데일리시황/표_업데이트/index.html';old=entry.read_text(encoding='utf-8');dom=BeautifulSoup(old,'html.parser')
    preserved=[(x.get('href'),x.text) for x in dom.select('a[href]') if any(y in x.get('href','') for y in ('Consensus/','WECO/'))]
    status=dom.select_one('#bql-current-status')
    status.string='BQL 1D 갱신: '+datetime.now().date().isoformat()+' · 비교 종가 '+startlabel+' → '+n['date']+' · 섹터·산업 + AI 밸류체인. 5D·팩터/테마·컨센서스·WECO·IB는 이전 자료를 유지합니다.'
    for link in dom.select('a[href]'):
        href=link['href']
        if 'Sector_Industry/sector_1D.html' in href or ('Sector_Industry/' in href and '_1D_' in href):
            link['href']='../BQL/Theme/output/'+tag+'/'+paths['sector'].relative_to(out).as_posix();link.string='글로벌 섹터·산업 1D · 최신 '+endlabel+' · 코멘터리 포함'
        elif 'AI/ai_1D.html' in href or ('/AI/' in href and '_1D_' in href):
            link['href']='../BQL/Theme/output/'+tag+'/'+paths['ai'].relative_to(out).as_posix();link.string='AI 밸류체인 1D · 최신 '+endlabel+' · 코멘터리 포함'
        elif '팩터·테마' in link.text and '미갱신' not in link.text:link.string=link.text+' (이번 미갱신)'
        elif '5D' in link.text and '이전' not in link.text:link.string=link.text+' · 이전 주간'
    first=dom.new_tag('li');link=dom.new_tag('a',href='../BQL/Theme/output/'+tag+'/'+setpath.name);link.string='최신 아침시황 1D 보고서 세트 · '+endlabel+' 기준';first.append(link)
    # Idempotent replacement of this specific dated entry only.
    for previous in list(dom.select('a[href]')):
        if previous.get('href')==link['href']:previous.parent.decompose()
    dom.select_one('.box ul').insert(0,first)
    assert preserved==[(x.get('href'),x.text) for x in dom.select('a[href]') if any(y in x.get('href','') for y in ('Consensus/','WECO/'))]
    if not (a.run/'entry_before.html').exists():(a.run/'entry_before.html').write_text(old,encoding='utf-8')
    entry.write_text(str(dom),encoding='utf-8')
    for file in [entry,setpath,*paths.values()]:
        for link in BeautifulSoup(file.read_text(encoding='utf-8'),'html.parser').select('a[href]'):
            href=link['href']
            if not re.match(r'^(https?:|#|mailto:)',href):assert (file.parent/href).resolve().exists(),(file,href)
    save(a.run/'delivery_manifest.json',{'asOf':n['date'],'primary':'1D','source':str(a.source),'sourceSHA256':sha(a.source),'sourceStockObservations':len(obs),'counts':{k:sum(r['market']==k for r in obs) for k in sp['markets']},'checks':checks,'reports':{k:str(v) for k,v in paths.items()},'entry':str(entry),'set':str(setpath),'scope':'two reports; theme excluded; no macro/IB updates','completed':datetime.now().isoformat()})
    print('DELIVERED='+str(setpath),flush=True)

if __name__=='__main__':main()
