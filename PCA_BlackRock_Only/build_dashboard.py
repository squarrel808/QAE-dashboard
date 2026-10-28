"""Reuse PCA II's chart language, with simultaneous vertical Level/Momentum."""
import json,re,html
from pathlib import Path
import pandas as pd

BASE=Path(__file__).resolve().parent
SOURCE=BASE.parent/'PCA_Four_Axis'

def replace_once(text,old,new):
    assert text.count(old)==1,('Dashboard template changed',old[:80])
    return text.replace(old,new,1)

def main():
    d=json.loads((BASE/'dashboard_data.json').read_text(encoding='utf8'))
    page=(SOURCE/'template.html').read_text(encoding='utf8').replace('PCA II','PCA III')
    page=replace_once(page,'<h1>Consumer · Capex · Housing · Export</h1>','<h1>BlackRock 지표 · PCA III</h1>')
    page=replace_once(page,'<p>네 부문의 지표 전체를 각각 PCA → 매년 연초 GDP 대비 비중으로 연중 고정 합산</p>','<p>BlackRock 참조 지표만 선택 · PCA II와 같은 전처리·CFNAI형 일반 PCA·GDP 가중치</p>')
    page=page.replace('<button id="yoy" class="active">','<button id="yoy" hidden class="active">').replace('<button id="momentum">','<button id="momentum" hidden>')
    page=page.replace('BlackRock 추가·제외 확인표','BlackRock 편입·제외 확인표')
    page=re.sub(r'<div class="note">.*?</div>', '<div class="note"><b>BlackRock 참조 목록의 Haver 대응 지표만 사용합니다.</b> 원본 BlackRock의 정확한 티커·산식 재현은 아니며, 확인된 월별 대리지표는 표시 후 포함합니다. 제조업은 Capex(기업활동)에 묶습니다. 프랑스 자체 패널은 목록에 없어 제외하고 유로존도 제외합니다. 독일·일본은 Housing 지표가 없어 세 부문만 합산하며 해당 비중은 재배분하지 않습니다. Export 비중은 명목 총수출/GDP의 50%입니다. 이 지수는 GDP 성장률이 아닙니다.</div>',page,count=1)
    page=replace_once(page,'<p id="latest" class="sub"></p></section>','<p id="latest" class="sub"></p></section><section class="panel" id="momentumPanel"><h2 id="momentumTitle"></h2><div id="momentumChart"></div><p id="momentumLatest" class="sub"></p></section>')
    page=page.replace('상단 Level / Momentum 선택 · Swirlogram 기준월 적용','Level 위 · Momentum 아래 · Swirlogram 기준월 적용')
    page=re.sub(r'<p class="sub" id="dmDefinition">.*?</p>','<p class="sub" id="dmDefinition">주요DM = 미국·영국·독일·캐나다·일본·호주 6개국 동일가중 평균(각 1/6). Housing은 자료가 있는 미국·영국·캐나다·호주 4개국을 고정 구성으로 사용합니다. 각 구성국의 같은 월 자료가 모두 있어야 계산하며, 범례에서 국가를 숨겨도 구성은 바뀌지 않습니다.</p>',page,count=1)
    page=page.replace('<th>합계</th><th>기준 분기</th>','<th>편입 비중 합계</th><th>기준 분기</th>')
    page=page.replace('100%로 재배분하지 않습니다.','100%로 재배분하지 않습니다. 독일·일본의 Housing은 비중을 표시하되 합계와 Growth에서 제외합니다.')
    page=page.replace(' 프랑스 Housing은 자영업자를 제외한 가계 고정투자의 대리값으로, 기업 보유 주택까지 완전히 분리한 값은 아닙니다.','')
    page=page.replace('매월 네 축이 모두 있고','매월 해당 국가에 편입된 축이 모두 있고')
    page=re.sub(r'<p>⑤ .*?</p>','<p>⑤ 사용자 제공 BlackRock 패널 목록에서 Haver 대응이 확인된 지표만 선택합니다. 기존 PCA II의 추가 지표는 편입하지 않습니다. 같은 원계열은 한 번만 사용하고 분류·전처리는 PCA II와 같습니다. 제조업·생산·수주는 기업활동 Capex에 포함되지만 실제 투자지출과 같지 않습니다. 참조 목록에 없는 프랑스, 독일·일본 Housing은 추가하지 않습니다. <a href="blackrock_coverage.html">198개 참조 항목의 편입·제외 내역</a>.</p>',page,count=1)
    page=page.replace('기존 BlackRock PCA와 이전 세부 분류 GDP 가중 PCA 파일은 보존합니다.','기존 PCA와 PCA II는 보존합니다.')
    page=replace_once(page,'</style>',(BASE/'style.css').read_text(encoding='utf8')+'\n</style>')
    stack=(SOURCE/'stacked_chart.js').read_text(encoding='utf8')
    stack=stack.replace('function contributionChart(version) {','function contributionChart(version) {\n  const axes=D.countries[cc].active_axes;')
    stack=stack.replace('W=1200,H=340,L=52,R=18,T=18,B=35','W=1200,H=235,L=52,R=100,T=18,B=35')
    stack=replace_once(stack,"  svg+='</svg>';", "  const last=headline.findLastIndex(v=>v!=null);\n  if(last>=0)svg+=`<circle cx=\"${x(last)}\" cy=\"${y(headline[last])}\" r=\"3.5\" fill=\"#101820\"/><text class=\"endpoint\" data-value=\"${headline[last]}\" x=\"${x(last)+12}\" y=\"${y(headline[last])+4}\">${fmt(headline[last],3)}</text>`;\n  svg+='</svg>';")
    explorer=(SOURCE/'explorer.js').read_text(encoding='utf8')
    explorer=explorer.replace("const dmMembers=['US','UK','FR','DE','CA','JP','AU'];","const dmMembers=Object.keys(D.countries);")
    explorer=explorer.replace('const members=dmMembers.map(member=>atMonth(member,version,month,measure));','const fixedMembers=measure===\'headline\'?dmMembers:dmMembers.filter(c=>D.countries[c].active_axes.includes(measure));\n        const members=fixedMembers.map(member=>atMonth(member,version,month,measure));')
    explorer=explorer.replace('members.every(finite)?members.reduce((a,b)=>a+b,0)/dmMembers.length:null','members.length&&members.every(finite)?members.reduce((a,b)=>a+b,0)/members.length:null')
    page=page.replace('__DATA__',json.dumps(d,ensure_ascii=False,allow_nan=False).replace('</','<\\/'))
    page=page.replace('__STACKED_CHART__',stack).replace('__EXPLORER__',explorer+'\n'+(BASE/'view.js').read_text(encoding='utf8'))
    (BASE/'index.html').write_text(page,encoding='utf8')
    common='<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{font:13px/1.7 Malgun Gothic;padding:24px;color:#234}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #ddd;text-align:left}th{background:#eef4f8}.scroll{overflow:auto}a{color:#236a96}</style><a href="index.html">PCA III로 돌아가기</a>'
    table=pd.DataFrame(d['indicators'])
    (BASE/'classification_signs.html').write_text(common+'<h1>PCA III · 국가별 지표·전처리·부호</h1><p>경제적 방향을 적용한 입력에 일반 PCA를 추정합니다. 개별 로딩은 양수·음수 모두 허용하며 이번 갱신의 전체 시계열에 고정됩니다. signed_loading은 경제적 방향까지 곱한 계수입니다. Momentum은 같은 PCA의 차분으로 별도 로딩이 없습니다.</p><div class="scroll">'+table.to_html(index=False)+'</div>',encoding='utf8')
    counts=table.groupby(['country','axis']).size().unstack(fill_value=0).reindex(columns=list(d['axes'])).rename(index=d['names'])
    audit=pd.read_csv(BASE/'blackrock_coverage.csv').fillna('')
    audit['편입']=audit.action.map({'existing':'편입','added':'편입','duplicate':'중복 연결 · 1회 사용','excluded':'제외'})
    (BASE/'blackrock_coverage.html').write_text(common+f'<h1>BlackRock 참조 목록만 사용 · {len(table)}개 시계열</h1><p>제공된 패널 목록의 개념과 Haver 정의를 대조한 결과입니다. 원본 BlackRock 티커·변환·로딩의 동일성을 뜻하지 않습니다. Capex에 제조업을 포함하며, 확인된 대리지표는 match=proxy로 표시합니다. 프랑스 및 유로존 제외, 독일·일본 Housing 없음.</p>'+counts.to_html()+'<h2>전체 참조 항목 검토</h2><p><a href="blackrock_coverage.csv">전체 검토표 CSV</a></p><div class="scroll">'+audit[['country','axis','reference','편입','match','pk','descriptor','kind','direction','last','reason','note']].to_html(index=False)+'</div>',encoding='utf8')
    rows=[]
    for cc,c in d['countries'].items():
        for mode,v in c['versions'].items():
            i=v['dates'].index(v['latest'])
            for a in d['axes']:rows.append(dict(country=cc,version=mode,axis=a,included=a in c['active_axes'],date=v['latest'],score=v['blocks'][a][i],weight=c['weights'][a],contribution=v['contributions'][a][i]))
    pd.DataFrame(rows).to_csv(BASE/'component_signs.csv',index=False,encoding='utf-8-sig')
    print('PCA III dashboard ready:',len(table),'inputs; Level and Momentum stacked')

if __name__=='__main__':main()
