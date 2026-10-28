"""Readable, filterable mapping and country/axis comparison for the union model."""
import json,html
from pathlib import Path
import pandas as pd
B=Path(__file__).resolve().parent
def build_report(d):
    old=json.loads((B/'pre_blackrock_union.json').read_text(encoding='utf8'))
    before=pd.DataFrame(old['indicators']).groupby(['country','axis']).size()
    after=pd.DataFrame(d['indicators']).groupby(['country','axis']).size()
    summary=[]
    for cc in d['countries']:
        row={'국가':d['names'][cc]}
        for axis in d['axes']:row[axis]=str(before.get((cc,axis),0))+' → '+str(after.get((cc,axis),0))
        summary.append(row)
    audit=pd.read_csv(B/'blackrock_coverage.csv').fillna('')
    labels={'existing':'기존 유지','added':'신규 편입','duplicate':'중복 연결','excluded':'제외'}
    cols=['국가','분류','참조 지표','처리','일치 범위','선택 Haver 코드','Haver 정의','주기','마지막 월','전처리','경제적 부호','PCA 로딩','비고']
    ind={(r['country'],r['pk']):r for r in d['indicators']};entries=[]
    for r in audit.to_dict('records'):
        s=ind.get((r['country'],r['pk']),{})
        loading=s.get('signed_loading')
        note=' · '.join(str(x) for x in [r['reason'],r['note']] if x)
        if r.get('original_pk') and r['original_pk']!=r['pk']:note+=' · 원후보 '+r['original_pk']
        entries.append([d['names'][r['country']],r['included_axis'] or r['axis'],r['reference'],labels[r['action']],{'concept':'명칭·개념 대응','proxy':'대리계열','derived':'동일 설문 재구성'}.get(r['match'],r['match']),r['pk'],r['descriptor'],r.get('frequency',''),r['last'],s.get('kind',''),('+' if s.get('direction',0)>0 else '−') if s else '',f'{loading:+.4f}' if loading is not None else '',note])
    table=pd.DataFrame(entries,columns=cols).to_html(index=False,table_id='mapping',escape=True)
    counts=audit.action.value_counts();nold=len(old['indicators']);nnew=len(d['indicators'])
    htmlpage='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>BlackRock 지표 통합 검토</title><style>body{font:14px/1.6 "Malgun Gothic",sans-serif;background:#f3f6fa;color:#183047;margin:28px}h1{margin-bottom:8px}section{background:white;padding:22px;border:1px solid #d9e3ee;border-radius:12px;margin:18px 0}table{border-collapse:collapse;width:100%}td,th{border:1px solid #d9e3ee;padding:9px;text-align:left;vertical-align:top}th{background:#edf3fa;position:sticky;top:0}input,select{padding:9px;margin-right:10px;border:1px solid #b9ccdf;border-radius:6px}.scroll{max-height:72vh;overflow:auto}#mapping{font-size:12px}#mapping td:nth-child(7){min-width:260px}#mapping td:last-child{min-width:300px}a{color:#216caf}.sub{color:#60778d}</style><h1>BlackRock 참조 지표 + 기존 지표</h1>'''
    htmlpage+=f'<p>기존 {nold}개 유지 → 전체 {nnew}개 · 신규 {nnew-nold}개. 유로존 제외, 프랑스 포함 기존 7개국.</p><p><a href="index.html">Growth PCA로 돌아가기</a> · <a href="blackrock_coverage.csv">검토표 CSV</a> · <a href="classification_signs.html">전체 편입 지표·부호</a></p>'
    htmlpage+='<section><h2>국가·블록별 지표 수</h2>'+pd.DataFrame(summary).to_html(index=False)+'<p>Capex는 기업활동·제조업·수주·설비투자를 포괄합니다. GDP 가중치는 기존 민간 비주거 투자 비중이며 기업활동의 GDP 기여율 자체를 뜻하지 않습니다.</p></section>'
    htmlpage+=f'<section><h2>참조 항목별 확인 결과 · {len(audit)}항목</h2><p>기존 유지 {counts.get("existing",0)} · 신규 편입 {counts.get("added",0)} · 중복 연결 {counts.get("duplicate",0)} · 제외 {counts.get("excluded",0)}. 참조 항목 수와 고유 시계열 수는 다릅니다.</p>'
    htmlpage+='''<p>사용자가 제공한 BlackRock 패널의 지표명으로 Haver 정의를 대조했습니다. 원본 BlackRock 티커·단위·표본·변환까지 동일하다는 검증은 아닙니다. 조회 가능한 13개 Haver 데이터베이스의 1,126,010개 고유 코드 카탈로그를 검색하고 선택 후보를 API로 재조회했습니다. 미확인은 해당 검색·접근 범위에서 찾지 못했다는 뜻입니다.</p><p>월별·36개월 이상·최근 6개월 내 관측을 가진 현행 계열을 신규 편입합니다. 중단·비월별 자료는 적절한 월별 대리가 확인된 경우만 대체합니다. 기존 지표는 보존합니다. 물가 지표는 제외하고, BlackRock 목록에 명시된 신용 지표만 추가했습니다. 경제적 부호는 입력 전처리 방향입니다. 표의 PCA 로딩은 추정 계수에 이 방향을 곱한 계수이며 이번 갱신의 전체 시계열에 고정됩니다. 음수 계수도 허용하므로 개별 경제적 방향을 보장하지 않습니다.</p><input id="q" placeholder="국가·지표·코드 검색"><select id="status"><option value="">모든 처리</option><option>신규 편입</option><option>기존 유지</option><option>중복 연결</option><option>제외</option></select><p id="visible" class="sub"></p><div class="scroll">'''+table+'''</div></section><script>const q=document.getElementById('q'),status=document.getElementById('status');function filter(){let n=0;document.querySelectorAll('#mapping tbody tr').forEach(r=>{let ok=r.textContent.toLowerCase().includes(q.value.toLowerCase())&&(!status.value||r.cells[3].textContent===status.value);r.hidden=!ok;n+=ok});document.getElementById('visible').textContent=n+'개 항목 표시'}q.oninput=filter;status.onchange=filter;filter()</script></html>'''
    (B/'blackrock_coverage.html').write_text(htmlpage,encoding='utf8')
    pd.DataFrame(summary).to_csv(B/'blackrock_counts.csv',index=False,encoding='utf-8-sig')
