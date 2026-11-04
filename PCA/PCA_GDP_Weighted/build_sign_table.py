"""Country classification and sign audit from the fitted model, never refits PCA."""
import json,re
from collections import Counter
from pathlib import Path
import pandas as pd
BASE=Path(__file__).resolve().parent
TOL=1e-8
PARENT={'C_actual':'C','C_labor':'C','C_sentiment':'C','I_business':'I','I_housing':'I','INVENTORY':'INVENTORY','X':'X','M':'M'}
ORDER=['C_actual','C_labor','C_sentiment','I_business','I_housing','INVENTORY','G','X','M','COMMON','TRADE_REF','GDP_REF']
def sign(x):
    if x is None or pd.isna(x):return '미산출'
    return '+' if x>TOL else '−' if x < -TOL else '0'
def main():
    d=json.loads((BASE/'dashboard_data.json').read_text(encoding='utf-8'))
    loads=pd.read_csv(BASE/'loadings.csv');lookup={(r.country,r.version,r.date[:7],r.group,r.indicator):r.loading for r in loads.itertuples()}
    rows=[];components=[]
    for cc,c in d['countries'].items():
        versions=c['versions'];by={v:{r['id']:r for r in x['indicators']} for v,x in versions.items()}
        for spec in [s for s in d['specs'] if s['country']==cc]:
            row={k:spec[k] for k in ['id','country','pk','group','label','direction','kind','ambiguous','substitution','review_status','origins','last']}
            row['parent']=PARENT.get(spec['group'],'');row['input_sign']=sign(spec['direction'])
            row['short']=re.sub(r'^(U\.S\.|U\.K\.|UK|CA|AU|US|Great Britain|United States|Australia|Canada|France|Germany|Japan):\s*','',spec['label']).split('(')[0].strip()
            for ver,v in versions.items():
                r=by[ver][spec['id']];leaf=r['loading'];stage=1.;parent=row['parent'];weight=v['latest_weights'].get(parent)
                if parent and parent!=spec['group']:
                    stage=lookup.get((cc,ver,v['latest'],parent,spec['group']))
                signed=leaf*spec['direction'] if leaf is not None else None
                if not parent:net='참고';reason='종합지수 합산 제외'
                elif leaf is None or stage is None or weight is None:net='미산출';reason='Momentum은 완성된 주 PCA 차분으로 별도 로딩 없음' if v.get('derivation') else '기준월 로딩 또는 가중치 없음'
                elif abs(leaf)<=TOL:net='0';reason='항목 내부 로딩이 0에 가까움'
                elif abs(stage)<=TOL:net='0';reason='상위 소비/투자 PCA의 하위블록 로딩이 0에 가까움'
                elif abs(weight)<=TOL:net='0';reason='GDP 비중이 0에 가까움'
                else:net=sign(spec['direction']*leaf*stage*weight);reason='입력 부호 × 항목 로딩 × 상위 로딩 × GDP 비중의 부호'
                row[ver]={'date':v['latest'],'loading':leaf,'signed_loading':signed,'loading_sign':sign(signed),
                          'parent_loading':stage if parent else None,'gdp_weight':weight,'net_sign':net,'net_reason':reason,'z':r['z']}
            rows.append(row)
        for group in ['C','I','INVENTORY','G','X','M','COMMON','TRADE_REF','GDP_REF','HEADLINE']:
            row={'country':cc,'group':group,'label':d['groups'].get(group,'GDP 가중 종합지수')}
            for ver,v in versions.items():
                if group=='HEADLINE':score=v['latest_value']
                else:
                    values=v['blocks'].get(group);score=values[v['dates'].index(v['latest'])] if values is not None else None
                row[ver]={'score':score,'score_sign':sign(score),'date':v['latest'],
                          'weight':v['latest_weights'].get(group),'weight_sign':sign(v['latest_weights'].get(group)),
                          'included':group in v['included_components'] or group=='HEADLINE'}
            components.append(row)
    assert len(rows)==260 and len({r['id'] for r in rows})==260
    for row in rows:
        for ver in ['YoY','Momentum']:
            r=row[ver]
            if r['signed_loading'] is not None:assert r['signed_loading']*row['direction']>=-TOL
            if row['direction']<0 and row['parent']=='C':assert r['net_sign'] in ['−','0','미산출']
            if row['parent']=='M':assert r['net_sign'] in ['−','0','미산출']
    payload={'generated':d['generated_kst'],'names':d['names'],'groups':d['groups'],'order':ORDER,'rows':rows,'components':components,
             'counts':{cc:dict(Counter(r['group'] for r in rows if r['country']==cc)) for cc in d['names']},
             'sign_counts':dict(Counter(r['input_sign'] for r in rows))}
    flat=[]
    for r in rows:
        out={'국가':d['names'][r['country']],'국가코드':r['country'],'분류':d['groups'][r['group']],'지출항목':d['groups'].get(r['parent'],'합산 제외·참고'),
             '지표':r['label'],'Haver':r['pk'],'입력부호':r['input_sign'],'대체지표':r['substitution'],'최신원자료':r['last'],'모형방향가정주의':r['ambiguous']}
        for ver in ['YoY','Momentum']:
            for k,v in r[ver].items():out[ver+'_'+k]=v
        flat.append(out)
    pd.DataFrame(flat).to_csv(BASE/'classification_signs.csv',index=False,encoding='utf-8-sig')
    flat=[]
    for r in components:
        out={'국가':d['names'][r['country']],'항목':r['label']}
        for ver in ['YoY','Momentum']:
            for k,v in r[ver].items():out[ver+'_'+k]=v
        flat.append(out)
    pd.DataFrame(flat).to_csv(BASE/'component_signs.csv',index=False,encoding='utf-8-sig')
    (BASE/'classification_signs.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    (BASE/'classification_signs.html').write_text(TEMPLATE.replace('__DATA__',json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('</','<\\/')),encoding='utf-8')
    print('Classification/sign audit:',len(rows),'indicators;',payload['sign_counts'])

TEMPLATE=r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>국가별 지표 분류·PCA 부호표</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6f7;color:#20394b;font:14px/1.65 'Segoe UI','Malgun Gothic',sans-serif}header{background:#142e44;color:white;padding:28px 4vw}header small{color:#88d1c3;letter-spacing:1.4px}h1{font-size:28px;margin:7px 0}header p{color:#d1dee7;margin:5px 0}main{max-width:1700px;margin:auto;padding:22px 4vw 50px}h2{font-size:21px;margin:0 0 10px}h3{font-size:18px;margin:0 0 12px}.panel{background:white;border:1px solid #dce5ea;border-radius:12px;padding:20px;margin:17px 0}.muted,small{color:#708492}.explain{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.explain>div{padding:15px;background:#eaf1f5;border-radius:9px}.explain strong{display:block}.toolbar,.links,.nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:12px 0}button,select,input{font:inherit;padding:8px 12px;border:1px solid #cad8df;border-radius:7px;background:white;color:#20394b}button{cursor:pointer}button.active{background:#20394b;color:white}.toolbar input{flex:1;min-width:240px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th{background:#edf3f6;color:#5d7383;white-space:nowrap}td,th{padding:10px;border-bottom:1px solid #e0e7eb;text-align:left;vertical-align:top}.sign{display:inline-block;min-width:22px;font-weight:750;text-align:center;border-radius:4px;padding:1px 5px;font-size:14px}.positive{color:#147b66;background:#e6f3ec}.negative{color:#b34e42;background:#fae9e6}.zero{color:#71818b;background:#edf0f2}.reference{color:#58749a;background:#edf2fb}.signcell{white-space:nowrap}.chip{display:inline-flex;gap:6px;align-items:center;padding:4px 8px;margin:3px 4px 3px 0;border:1px solid #dce7eb;border-radius:6px;background:#fafcfd;font-size:12px}.chips{max-width:1150px}.groupcell{min-width:145px;max-width:180px;font-weight:600}.notice{padding:12px 15px;border-left:4px solid #bd9145;background:#fff6e6}.links a{background:#e9eff6;color:#355d93;padding:6px 11px;border-radius:6px;text-decoration:none}code{font:11px Consolas,monospace;color:#3b6192;overflow-wrap:anywhere}.detail{min-width:1300px}.detail th:nth-child(1){min-width:70px}.num{font-variant-numeric:tabular-nums}.zeroNote{font-size:11px;color:#8b744d}.empty{color:#9a8053}footer{font-size:12px;color:#708492}.scores td{white-space:nowrap}.scores small{font-size:11px}.matrix td{text-align:center}.matrix td:first-child{text-align:left}.pill{font-size:11px;border-radius:4px;background:#eaf0fa;color:#4d6f9e;padding:2px 5px}@media(max-width:850px){.explain{grid-template-columns:1fr}main{padding:15px}h1{font-size:23px}}@media print{.toolbar,.nav,.links{display:none}.panel{break-inside:avoid}}
</style></head><body><p style="padding:16px;background:#eaf2f7">Momentum은 완성된 YoY PCA의 최근 3개월 평균 − 직전 3개월 평균입니다. 별도 로딩을 추정하지 않으므로 Momentum 로딩·단일 반영 방향은 표시하지 않습니다.</p><header><small>QAE / CATEGORY & SIGN AUDIT</small><h1>국가별 지표 분류 · PCA 부호표</h1><p>7개국 260개 전체 지표 · 소비/투자 하위분류 · 입력 부호 · 실제 로딩 · GDP 합산 방향</p><p id="stamp"></p></header><main>
<div class="links"><a href="index.html">← GDP 가중 PCA</a><a href="classification_signs.csv" download>260개 분류·부호 CSV</a><a href="component_signs.csv" download>국가·항목별 PCA 값 CSV</a></div>
<div class="explain"><div><strong>① 입력 부호 + / −</strong>변환한 지표가 상승할 때 해당 블록을 어느 방향으로 읽는지입니다. 예: 실업률 −, 소비·생산 +. 국가별 분류표에 표시합니다.</div><div><strong>② 실제 PCA 로딩 부호</strong>경제적 방향 × 비음수 PCA 로딩입니다. 입력 부호가 −여도 해당 시점 로딩이 0이면 0으로 표시합니다. YoY·Momentum을 나란히 비교합니다.</div><div><strong>③ 현재 PCA 값의 + / −</strong>이번 기준월에 산출된 지수가 0선 위인지 아래인지입니다. 지표의 고정 입력 부호와 다릅니다. 아래 국가별 점수표에서 확인합니다.</div></div>
<p class="notice"><b>GDP 합산 방향은 한 번 더 구분합니다.</b> 수입은 지표 블록 안에서 +지만 GDP 가중치가 −라 종합지수에는 반대로 들어갑니다. 재고는 GDP 비중의 부호에 따라 달라집니다. 공통 경기·무역수지·GDP 검증용은 참고용으로만 표시합니다. 부호는 표준화된 변환 입력 기준이며 GDP 성장률의 인과효과가 아닙니다.</p>
<section class="panel"><h2>국가별 분류 현황</h2><p class="muted">숫자는 중복 정리 후 원계열 개수입니다. C 안의 고용·소득/소비심리는 민간소비 설명 블록입니다.</p><div class="scroll" id="matrix"></div></section>
<section class="panel"><h2>현재 국가별 PCA 값은 +인가, −인가?</h2><p class="muted">각 칸의 위 = YoY, 아래 = Momentum. 부호는 실제 계산값 기준입니다. 정부소비는 범위에서 제외하고, 미확보 재고는 미산출로 표시합니다.</p><div class="scroll" id="scores"></div></section>
<h2>국가별 지표 분류표</h2><p class="muted">각 지표 앞의 +/−는 <b>고정한 입력 부호</b>입니다. 이름 위에 마우스를 올리면 전체 Haver 정의와 코드를 볼 수 있습니다.</p><div id="countries" class="nav"></div><div class="toolbar"><select id="group"><option value="all">모든 분류</option></select><input id="search" placeholder="지표명 · Haver 코드 검색" aria-label="지표 검색"><select id="sign"><option value="all">모든 입력 부호</option><option value="−">음의 부호만</option><option value="+">양의 부호만</option></select></div><div id="count" class="muted"></div><div id="categorized"></div>
<section class="panel"><h2>지표별 실제 로딩과 GDP 합산 부호</h2><p class="muted">위 국가·분류·검색 필터와 연결됩니다. <b>부호 있는 로딩 = 입력 부호 × 항목 내부 로딩</b>이며, 계층 표준화 때문에 최종 지수의 회귀계수나 민감도는 아닙니다. GDP 합산 방향은 소비/투자 상위 로딩과 GDP 비중 부호까지 확인했습니다. 절댓값 ≤ 10⁻⁸은 표시상 0으로 취급합니다.</p><div class="scroll" id="detail"></div></section>
<section class="panel"><h2>분류·부호에 포함한 예외</h2><ul><li>저축률·저축의향·총이직률은 단기 소비 관점에서 −라는 모형 가정을 적용했습니다.</li><li>수입 증가 자체를 경기 악화로 보지는 않습니다. GDP 지출식의 차감 부호를 별도 열에 표시했습니다.</li><li>재고 블록은 재고 잔액 자체가 아니라 증감·비율 변화입니다. 미국·일본의 이번 GDP 재고증감 비중은 음수이므로 합산 방향이 음수가 될 수 있습니다.</li><li>하위 지표 로딩이 양수여도 상위 소비/투자 PCA의 해당 블록 로딩이 0이면 종합지수 반영은 0입니다.</li><li>정부소비·일반정부 투자는 사용자 지정 범위에 따라 합산에서 제외합니다. 원본 4개(호주 임금 2개·산업생산, 캐나다 단위노동비용)는 미확보로 제외했습니다.</li></ul></section>
<footer>이 표는 저장된 모델 결과에서 생성했습니다. 기존 BlackRock PCA와 새 PCA의 계산값은 바꾸지 않았습니다.</footer></main><script id="payload" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('payload').textContent),$=s=>document.querySelector(s);let cc='all';const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const fmt=x=>x==null?'—':Math.abs(x)<1e-8?'0.000':(x>=0?'+':'')+Number(x).toFixed(3);const badge=x=>`<span class="sign ${x==='+'?'positive':x==='−'?'negative':x==='참고'?'reference':'zero'}">${esc(x)}</span>`;
$('#stamp').textContent='계산 '+D.generated.slice(0,10)+' · 점수·로딩 기준월 '+[...new Set(D.rows.flatMap(r=>[r.YoY.date,r.Momentum.date]))].join(' / ')+' · 입력 + '+D.sign_counts['+']+'개 / − '+D.sign_counts['−']+'개';
let cols=['C_actual','C_labor','C_sentiment','I_business','I_housing','INVENTORY','G','X','M','COMMON','TRADE_REF','GDP_REF'];let short={'C_actual':'C 소비실적','C_labor':'C 고용·소득','C_sentiment':'C 심리','I_business':'I 설비·비주거','I_housing':'I 주택','INVENTORY':'재고','G':'정부소비','X':'수출','M':'수입','COMMON':'공통 경기','TRADE_REF':'무역수지','GDP_REF':'GDP 참고'};
$('#matrix').innerHTML='<table class="matrix"><thead><tr><th>국가</th>'+cols.map(g=>'<th>'+short[g]+'</th>').join('')+'<th>합계</th></tr></thead><tbody>'+Object.entries(D.names).map(([c,n])=>'<tr><td><b>'+n+'</b></td>'+cols.map(g=>'<td>'+(D.counts[c][g]||'—')+'</td>').join('')+'<td><b>'+D.rows.filter(r=>r.country===c).length+'</b></td></tr>').join('')+'</tbody></table>';
let cats=['C','I','INVENTORY','G','X','M','HEADLINE'];$('#scores').innerHTML='<table class="scores"><thead><tr><th>국가</th>'+cats.map(g=>'<th>'+(D.groups[g]||'종합지수')+'</th>').join('')+'</tr></thead><tbody>'+Object.entries(D.names).map(([c,n])=>'<tr><td><b>'+n+'</b><br><small>YoY / Mom.</small></td>'+cats.map(g=>{let r=D.components.find(x=>x.country===c&&x.group===g);return '<td>'+['YoY','Momentum'].map(v=>r[v].score==null?'<small>미산출</small>':badge(r[v].score_sign)+' <span class="num">'+fmt(r[v].score)+'</span>').join('<br>')+'</td>'}).join('')+'</tr>').join('')+'</tbody></table>';
D.order.forEach(g=>$('#group').insertAdjacentHTML('beforeend',`<option value="${g}">${D.groups[g]}</option>`));
function render(){let q=$('#search').value.toLowerCase(),g=$('#group').value,s=$('#sign').value;let rows=D.rows.filter(r=>(cc==='all'||r.country===cc)&&(g==='all'||r.group===g)&&(s==='all'||r.input_sign===s)&&[r.label,r.pk,...r.origins].join(' ').toLowerCase().includes(q));$('#countries').innerHTML=[['all','7개국 전체'],...Object.entries(D.names)].map(([c,n])=>`<button data-c="${c}" class="${c===cc?'active':''}">${n}</button>`).join('');$('#countries').querySelectorAll('button').forEach(b=>b.onclick=()=>{cc=b.dataset.c;render()});$('#count').textContent=rows.length+'개 지표 표시';
$('#categorized').innerHTML=(cc==='all'?Object.keys(D.names):[cc]).map(c=>`<section class="panel"><h3>${D.names[c]}</h3><div class="scroll"><table><thead><tr><th>지출항목 / 하위분류</th><th>편입 지표 · 입력 부호</th></tr></thead><tbody>`+D.order.filter(k=>g==='all'||g===k).map(k=>{let r=rows.filter(x=>x.country===c&&x.group===k);if(!r.length&&(q||s!=='all'))return '';return `<tr><td class="groupcell">${D.groups[k]}<br><small>${r.length}개${['COMMON','TRADE_REF','GDP_REF'].includes(k)?' · 합산 제외':''}</small></td><td class="chips">${r.length?r.map(x=>`<span class="chip" title="${esc(x.label+' | '+x.pk)}">${badge(x.input_sign)}${esc(x.short)}${x.substitution?'<span class="pill">대체</span>':''}</span>`).join(''):(k==='G'?'<span class="empty">사용자 지정 범위 · 제외</span>':'<span class="empty">월별 지표 미확보 · 제외</span>')}</td></tr>`}).join('')+'</tbody></table></div></section>').join('');
$('#detail').innerHTML='<table class="detail"><thead><tr><th>국가</th><th>분류</th><th>지표 / Haver</th><th>입력</th><th>YoY 부호 있는 로딩</th><th>Mom. 부호 있는 로딩</th><th>YoY 종합 반영 방향</th><th>Mom. 종합 반영 방향</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${D.names[r.country]}</td><td>${D.groups[r.group]}</td><td>${esc(r.label)}<br><code>${esc(r.pk)}</code></td><td>${badge(r.input_sign)}</td>${['YoY','Momentum'].map(v=>`<td class="signcell">${badge(r[v].loading_sign)} ${fmt(r[v].signed_loading)}</td>`).join('')}${['YoY','Momentum'].map(v=>`<td>${badge(r[v].net_sign)}${r[v].net_sign==='0'?'<div class="zeroNote">'+esc(r[v].net_reason)+'</div>':''}${r.parent==='M'?'<small> 수입 차감</small>':''}${r.parent==='INVENTORY'?'<small> GDP 재고비중 '+(r[v].gdp_weight*100).toFixed(3)+'%</small>':''}</td>`).join('')}</tr>`).join('')+'</tbody></table>';
}['group','sign','search'].forEach(id=>$('#'+id).addEventListener(id==='search'?'input':'change',render));render();
</script></body></html>'''
if __name__=='__main__':main()
