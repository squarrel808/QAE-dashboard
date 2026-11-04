"""BQL-only morning quantitative builder. Reuses maintained calculation modules."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import openpyxl

KST = timezone(timedelta(hours=9))
QAE = Path(r'C:\Users\infomax\Documents\python\QAE')
CSS = '''.morning-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}.morning-kpis>div{border:1px solid #d9e2f3;border-radius:8px;padding:12px;background:#f5f8fc}.morning-kpis small{display:block;color:#667085}.morning-kpis b{font-size:20px;display:block;margin:5px 0}.rank-bars{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px 24px;margin:15px 0}.rank-bar{display:grid;grid-template-columns:160px 1fr 65px;gap:8px;align-items:center;font-size:12px}.rank-bar i{display:block;height:12px;background:#0070c0}.rank-bar i.negative{background:#c00000}.rank-bar>span:last-child{text-align:right}.table-wrap{max-width:100%}.stock-desc{max-width:380px}.prose-table{white-space:normal;width:100%;table-layout:fixed;min-width:800px}.prose-table td{vertical-align:top;line-height:1.6}.morning-headlines{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.morning-timeline{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.source-context{margin:10px 0;border:1px solid #d9e2f3;border-radius:7px;padding:10px}.source-context summary{cursor:pointer;color:#17365d;font-weight:700}.morning-nav{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 18px;font-size:13px}.morning-nav a{color:#17365d}.commentary-block{max-width:100%;overflow-wrap:anywhere}@media(max-width:800px){.morning-kpis,.morning-headlines,.morning-timeline,.rank-bars{grid-template-columns:1fr}.rank-bar{grid-template-columns:135px 1fr 60px}}'''

def load(path, name):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def table(head, rows, ident=''):
    return f'<div class="table-wrap"><table data-quant="{ident}"><thead><tr>'+''.join(f'<th>{x}</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{v}</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def kpis(items):
    return '<div class="morning-kpis">'+''.join(f'<div><small>{a}</small><b>{b}</b><small>{c}</small></div>' for a,b,c in items)+'</div>'

def bars(rows, esc, pct):
    scale=max([abs(v) for _,v in rows if v is not None]+[.01])
    return '<div class="rank-bars">'+''.join(f'<div class="rank-bar"><span>{esc(n)}</span><span><i class="{"negative" if v<0 else "positive"}" style="width:{abs(v)/scale*100:.4f}%"></i></span><span>{pct(v)}</span></div>' for n,v in rows if v is not None)+'</div>'

def navigation(tag, kind):
    # Quantitative output names are stable; dated commentary/set pages are separate.
    return '<nav class="morning-nav"><a href="../Sector_Industry/sector_5D.html">섹터·산업</a><a href="../AI/ai_5D.html">AI 밸류체인</a></nav>'


def render_market_comparison(markets):
    from html import escape
    names=sorted({s['sector'] for m in markets for s in m['sectors']})
    def cell(v):
        if v is None:return '—'
        cls='pos' if v>0 else 'neg' if v<0 else 'zero'
        return f'<span class="{cls}">{v*100:+.2f}</span>'
    returns=[]; relatives=[]
    for name in names:
        left=[escape(name)];right=[escape(name)]
        for m in markets:
            group=next((s for s in m['sectors'] if s['sector']==name),None)
            value=group['returns']['5D'] if group else None
            bm=m['benchmark']['returns']['5D']
            left.append(cell(value));right.append(cell(value-bm) if value is not None and bm is not None else '—')
        returns.append(left);relatives.append(right)
    headers=['섹터']+[escape(m['title']) for m in markets]
    absolute=table(headers,returns,'market-comparison-returns')
    breadth='<tr class="benchmark" data-breadth="5D"><td>5D 상승 종목 비율</td>'+''.join(f'<td data-market="{m["key"]}" data-positive="{m["positiveCount"]}" data-valid="{m["validCount"]}">{m["positiveCount"]/m["validCount"]*100:.1f}%</td>' for m in markets)+'</tr>'
    absolute=absolute.replace('</tbody>',breadth+'</tbody>')
    relative=table(headers,relatives,'market-comparison-relative')
    return '<h2>글로벌 시장 섹터 수익률 — 5D (%)</h2>'+absolute+'<h2>글로벌 시장 섹터 BM 대비 — 5D (%p)</h2>'+relative


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--qae', type=Path, default=QAE)
    p.add_argument('--cutoff', type=date.fromisoformat, default=datetime.now(KST).date())
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    a=p.parse_args()
    bql=a.qae/'데일리시황/BQL'
    material=bql/'Theme/Material'
    sector=load(material/'Sector_Industry/Reports/build_sector_rotation_html.py','morning_sector')
    ai=load(material/'AI/build_ai_value_chain_html.py','morning_ai')
    week={'mode':'rolling_5_sessions','policyVersion':'rolling_5_sessions_v1_20261103','definition':'시장별 최신 유효 종가 / 5거래일 전 유효 종가 - 1; 6개 종가, 휴장·이월 열 제외'}
    master=bql/'Rawfile/BQuant_Master.xlsx'
    input_sha=sha(a.source)
    master_sha=sha(master)
    with contextlib.closing(openpyxl.load_workbook(master,read_only=True,data_only=True)) as wb:
        raws=[sector.load_market(wb,key) for key in sector.MARKETS]
    markets=[]
    audit=[]
    for raw in raws:
        m=sector.build_market(raw,'5D',3,a.cutoff)
        end, starts, sessions=sector.resolve_windows(raw,a.cutoff)
        start=starts['5D']
        if start is None:raise ValueError(f'{raw.key}: fewer than six valid closes')
        actual=[i for i in sessions if start<=i<=end]
        assert start is not None and len(actual)==6,(raw.key,'5D requires six valid closes')
        assert raw.dates[end]<=a.cutoff
        caps=raw.market_caps[:,start]
        cap_valid=np.isfinite(caps)&(caps>0)
        total=float(caps[cap_valid].sum())
        vec=np.array(m['stock']['returns']['5D'])
        eligible=np.isfinite(vec)&cap_valid
        check=float(np.sum(vec[eligible]*caps[eligible])/caps[eligible].sum())
        assert abs(check-m['benchmark']['constituentReturns']['5D'])<1e-12
        m['validCount']=int(np.isfinite(vec).sum())
        m['positiveCount']=int((vec[np.isfinite(vec)]>0).sum())
        m['fiveSessions']=[raw.dates[i].isoformat() for i in actual]
        m['periodWindow']={**week,'priceStart':raw.dates[start].isoformat(),'priceEnd':raw.dates[end].isoformat(),'actualReturnIntervals':len(actual)-1}
        m['calendarWindow']=m['periodWindow']  # Backward-compatible alias; mode is rolling_5_sessions.
        m['startCap']=caps.tolist()
        m['startCapTotal']=total
        for item in m['sectors']+m['industries']:
            ix=np.array(item['indices'])
            good=ix[eligible[ix]]
            expected=float(np.sum(vec[good]*caps[good])/caps[good].sum()) if len(good) else None
            got=item['returns']['5D']
            assert expected==got or (expected is not None and got is not None and abs(expected-got)<1e-12)
            item['weight']=float(caps[ix][cap_valid[ix]].sum()/total)
        for item in m['sectors']:
            item['bottom']=[i for i in item['bottom'] if i not in item['top']]
            assert not set(item['top'])&set(item['bottom'])
        assert abs(m['positiveCount']/m['validCount']-m['benchmark']['breadth']['5D'])<1e-12
        audit.append({k:m[k] for k in ['key','asOf','periodStart','fiveSessions','calendarWindow','coverage','capCoverage','memberCount','validCount','positiveCount']})
        markets.append(m)
    asof=max(m['asOf'] for m in markets)
    # Keep the 25-group comparison universe visible even when a market has no
    # current constituent in a group. Missing groups have no invented returns.
    universe={r['industry']:r['sector'] for r in markets[0]['industries']}
    for m in markets:
        present={r['industry'] for r in m['industries']}
        m['missingIndustryGroups']=sorted(set(universe)-present)
        for name in m['missingIndustryGroups']:
            m['industries'].append({'industry':name,'sector':universe[name],'n':0,'indices':[],'weight':0.0,'returns':{p:None for p in sector.PERIODS},'breadth':{p:None for p in sector.PERIODS},'status':'현재 구성종목 없음'})
    assert all(date.fromisoformat(m['asOf'])<=a.cutoff for m in markets)
    tag=asof.replace('-','')
    esc,pct=sector.esc,sector.pct
    def numeric(v):
        return f'<span class="{sector.value_class(v)}">{pct(v,2)}</span>'
    def group_table(m, groups, label):
        bm=m['benchmark']['returns']['5D']
        rows=[]
        for rank,r in enumerate(groups,1):
            v=r['returns']['5D']
            rows.append([str(rank) if r['n'] else '—',esc(r.get('industry',r.get('sector')))+(' · 구성종목 없음' if not r['n'] else ''),esc(r['sector']) if label=='산업그룹' else '',str(r['n']),f'{r["weight"]*100:.2f}%',numeric(v) if r['n'] else '—',numeric(v-bm) if v is not None else '—',sector.breadth_pct(r['breadth']['5D']) if r['n'] else '—'])
        return table(['순위',label,'소속 섹터' if label=='산업그룹' else '', 'N','시작일 시총 비중','5D','BM 대비','5D 상승 종목 비율'],rows,f'{m["key"]}-{label}')
    original_panel=sector.render_market_panel
    def panel(m,descriptions,active=False):
        page=original_panel(m,descriptions,active)
        page=page.replace('기준 상위·하위 종목 각 5개','기준 상위·하위 종목 각 3개')
        page=page.replace(sector.overall_table(m),group_table(m,m['sectors'],'섹터'))
        old=sector.multi_period_table(m['industries'],[('industry','산업그룹'),('sector','섹터')])
        page=page.replace(old,group_table(m,m['industries'],'산업그룹'))
        positive=sum((x['returns']['5D'] or 0)>0 for x in m['sectors'])
        dashboard=kpis([('시장 BM · Index Level',numeric(m['benchmark']['returns']['5D']),m['periodStart']['5D']+' → '+m['asOf']),('5D 상승 종목 비율',sector.breadth_pct(m['benchmark']['breadth']['5D']),f'{m["positiveCount"]} / {m["validCount"]} 유효 종목'),('상승 섹터',f'{positive} / {len(m["sectors"])}','절대 가격수익률 > 0'),('선두 섹터',esc(m['sectors'][0]['sector']),pct(m['sectors'][0]['returns']['5D']))])
        dashboard+=bars([(r['sector'],r['returns']['5D']) for r in m['sectors']],esc,lambda v:pct(v,2))
        page=page.replace('<h2>1. 전체 섹터',dashboard+'<h2>1. 전체 섹터')
        page=page.replace('계산 기준:','계산 기준: 현재 구성종목을 과거 시작일에 적용하여 생존편향 가능성이 있습니다. ')
        detail=f'<p class="note">5D = 최근 5거래일 · 비교 종가 {m["periodStart"]["5D"]} → {m["asOf"]} · 실제 거래구간 5개(6개 종가).</p>'
        page=page.replace('<h2>1. 전체 섹터',detail+'<h2>1. 전체 섹터')
        return page
    sector.render_market_panel=panel
    desc=sector.load_descriptions(sector.DEFAULT_DESCRIPTION_BOOK)
    page=sector.render_combined_html(markets,'5D',desc)
    page=page.replace('<nav class="market-tabs"',render_market_comparison(markets)+'<nav class="market-tabs"')
    page=page.replace('</style>',CSS+'</style>').replace('<header class="report-header">',navigation(tag,'sector')+'<header class="report-header">')
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'Sector_Industry').mkdir(exist_ok=True)
    (a.output/'Sector_Industry/sector_5D.html').write_text(page,encoding='utf-8')
    save(a.output/'Sector_Industry/sector_5D.json',sector.sanitize_for_json({'asOf':asof,'primary':'5D','markets':markets}))
    raw=ai.ai.load_spx([master])
    keep=[i for i,d in enumerate(raw.dates) if d<=a.cutoff]
    raw.dates=[raw.dates[i] for i in keep]
    raw.metrics={key:value[:,keep] for key,value in raw.metrics.items()}
    data=ai.ai.build_data(raw)
    assert date.fromisoformat(data['meta']['asOf'])<=a.cutoff
    assert len(data['stages'])==12
    ai_dates=data['dates']
    start_i=ai_dates.index(data['periodStarts']['5D'])
    assert len(ai_dates[start_i:])==6
    data['calendarWindow']={**week,'priceStart':ai_dates[start_i],'priceEnd':ai_dates[-1],'actualReturnIntervals':len(ai_dates[start_i:])-1}
    for period in ai.PERIODS:
        enough=(len(ai_dates)>=2 if period=='1D' else len(ai_dates[start_i:])==6) if period in ('1D','5D') else ai_dates[0]<=ai.ai.shift_months(date.fromisoformat(ai_dates[-1]),-int(period[:-1])).isoformat()
        if not enough:
            data['periodStarts'][period]=None
            data['benchmark']['returns'][period]=None
            for mode in data['modes'].values():
                for st in mode.values():
                    for key in ('return','relative','breadth','median','dispersion'):
                        st['performance'][period][key]=None
                    st['performance'][period]['weightedMembers']=0
                    st['performance'][period]['startMarketCap']=None
                    st['periodSeries'][period]=[]
            for stock in data['stocks']:stock['returns'][period]=None
    def movers(d,st,mode,primary):
        allowed={'Core'} if mode=='Core' else {'Core','Adjacent'}
        stocks=sorted([s for s in d['stocks'] if s['stage']==st['key'] and s['confidence'] in allowed and s['returns'][primary] is not None],key=lambda s:s['returns'][primary],reverse=True)
        n=len(stocks); nt=min(3,n//2) if n>1 else n
        top=stocks[:nt]; bottom=list(reversed(stocks[max(nt,n-3):]))
        assert not {s['ticker'] for s in top}&{s['ticker'] for s in bottom}
        rows=[]
        for label, group in [('상위',top),('하위',bottom)]:
            for s in group:
                name=f'<div class="stock-name">{esc(s["company"])}</div><div class="stock-desc">{esc(s["rationale"])}</div>'+ai.commentary_slot('stock',s['ticker'])
                rows.append([label,name,'핵심' if s['confidence']=='Core' else '인접']+[numeric(s['returns'].get(p)) for p in ai.PERIODS])
        return table(['순위 구분','종목 및 사업 설명','분류',*ai.PERIODS],rows,f'{mode}-{st["key"]}')
    ai.stock_table=movers
    ai_page=ai.render(data,'5D')
    for mode in ['Core','Expanded']:
        allowed={'Core'} if mode=='Core' else {'Core','Adjacent'}
        stocks=[s for s in data['stocks'] if s['confidence'] in allowed and s['returns']['5D'] is not None]
        ranked=sorted(data['stages'],key=lambda s:data['modes'][mode][s['key']]['performance']['5D']['return'] if data['modes'][mode][s['key']]['performance']['5D']['return'] is not None else -math.inf,reverse=True)
        positive=sum(s['returns']['5D']>0 for s in stocks)
        pos_stages=sum((data['modes'][mode][s['key']]['performance']['5D']['return'] or 0)>0 for s in ranked)
        for s in ranked:
            value=data['modes'][mode][s['key']]['performance']['5D']['return']
            assert value is None or math.isfinite(value)
        fragment=kpis([('S&P 500 · Index Level BM',numeric(data['benchmark']['returns']['5D']),data['periodStarts']['5D']+' → '+data['meta']['asOf']),('상승 AI 종목',f'{positive} / {len(stocks)}','중복 없는 유효 종목'),('상승 밸류체인',f'{pos_stages} / 12','선두: '+esc(ranked[0]['short'])),('후행 밸류체인',esc(ranked[-1]['short']),numeric(data['modes'][mode][ranked[-1]['key']]['performance']['5D']['return']))])
        fragment+=bars([(s['short'],data['modes'][mode][s['key']]['performance']['5D']['return']) for s in ranked],esc,lambda v:pct(v,2))
        ai_page=ai_page.replace(f'data-mode="{mode}"><h2>',f'data-mode="{mode}">{fragment}<h2>')
    ai_page=ai_page.replace('class="mode-panel active" data-mode="Core"','class="mode-panel" data-mode="Core"').replace('class="mode-panel" data-mode="Expanded"','class="mode-panel active" data-mode="Expanded"')
    ai_page=ai_page.replace('class="mode-button active" onclick="showMode(\'Core\',this)"','class="mode-button" onclick="showMode(\'Core\',this)"').replace('class="mode-button" onclick="showMode(\'Expanded\',this)"','class="mode-button active" onclick="showMode(\'Expanded\',this)"')
    ai_page=ai_page.replace('</style>',CSS+'</style>').replace('<h1>',navigation(tag,'ai')+'<h1>',1)
    ai_page=ai_page.replace('</h1>','</h1><p class="note">5D = 최근 5거래일 · '+data['periodStarts']['5D']+' → '+data['meta']['asOf']+' · 실제 거래구간 5개.</p>',1)
    (a.output/'AI').mkdir(exist_ok=True)
    (a.output/'AI/ai_5D.html').write_text(ai_page,encoding='utf-8')
    save(a.output/'AI/ai_data.json',data)
    assert sha(a.source)==input_sha,'Raw input changed'
    assert sha(master)==master_sha,'Master changed during build'
    manifest={'status':'success','scope':'BQL only; no Consensus, WECO, IB writes','requested_at':datetime.now(KST).isoformat(),'cutoff':a.cutoff.isoformat(),'asOf':asof,'calendarWindow':week,'source':str(a.source),'sourceSHA256':input_sha,'masterSHA256':master_sha,'markets':audit,'AI':{'asOf':data['meta']['asOf'],'periodStarts':data['periodStarts'],'calendarWindow':data['calendarWindow'],'stages':len(data['stages']),'stocks':len(data['stocks'])},'quantitative_checks':'Rolling five-session boundaries; six observed closes required; start-cap recomputation; valid-stock breadth; disjoint movers; unchanged raw/master hashes'}
    save(a.output/'manifest.json',manifest)
    print(json.dumps(manifest,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
