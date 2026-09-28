import copy,hashlib,json,pathlib,re,sqlite3,sys
from datetime import datetime
P=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
B=pathlib.Path('데일리시황/표_업데이트').resolve()
sys.path.insert(0,str(R/'ecocal_dashboard'));import build_dashboard as b
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
m=read(B/'latest.json');data=read(pathlib.Path(m['review_queue']).parent/'dashboard_data.json');inp=read(P/'input.json')
c=sqlite3.connect(R/'data/research.sqlite3');c.row_factory=sqlite3.Row
now=datetime.now().astimezone().isoformat(timespec='seconds');pages=set();spec={}
def h(pre,pg,start,end,summary,comment,kind='reaction',limitation=''):
 d=c.execute('select * from documents where doc_id like ?',(pre+'%',)).fetchone();t=c.execute('select text from pages where doc_id=? and page=?',(d['doc_id'],pg)).fetchone()[0]
 a=re.search(r'\s+'.join(map(re.escape,start.split())),t);assert a,start
 z=re.search(r'\s+'.join(map(re.escape,end.split())),t[a.start():]);assert z,end
 pages.add((d['doc_id'],pg))
 return dict(house=d['house'],kind=kind,summary=summary,comment=comment,limitation=limitation,evidence=[dict(doc_id=d['doc_id'],page=pg,quote=t[a.start():a.start()+z.end()])],reviewed_pages=[dict(doc_id=d['doc_id'],page=pg)])
cadate='원문 표지 발행일은 2026-09-18, 검색 메타데이터는 9월 19일이다. 8월 발표 이후의 후속 평가로 연결하며 다운로드일을 발행일로 쓰지 않는다.'
china=h('44d694',2,'China’s August activity data','overall strength of the Chinese economy.','GS는 8월 생산 5.2%와 소매판매 0.4%의 격차가 확대됐다고 분석했다. 대형 소매업체 매출은 약 4% 감소한 반면 소형은 3% 증가해 추정 방식이 내수 약세를 완화해 보일 가능성을 지적했다.','AI 비교: 기존 JPM·Citi의 생산과 내수 괴리 판단을 보강한다. 새 GS 근거는 업종·표본 차이까지 보여주므로 산업생산 강세를 가계수요 회복으로 읽기 어렵다.')
ca=h('8290dad',2,'The summary of deliberations','new home prices are still declining.','Citi는 8월 전체 CPI -0.1%·3.0%와 목표 부근 근원을 확인했다. 에너지의 광범위한 전가가 부족하고 의류·가구 가격도 약해, 2026년 인상이 없을 것으로 봤다. 임대료 반등은 7월 급락 뒤의 되돌림으로 구분했다.','AI 비교: 기존 GS·JPM의 제외근원 단기 속도 경계와 Citi의 전가 제한 판단을 구분한다. 9월 근원 CPI와 에너지의 다른 품목 전가가 다음 판단 기준이다.',limitation=cadate)
ca['evidence'].append(h('8290dad',1,'Headline CPI remained','this year or next.','x','x')['evidence'][0]);ca['reviewed_pages'].append(dict(doc_id=ca['evidence'][-1]['doc_id'],page=1));ca['summary']+=' 표지에서는 2027년에도 인상이 없을 것으로 예상했다.'
home=h('8290dad',3,'Housing demand weakening again','through the rest of this year.','Citi는 8월 주택판매 -0.7%가 앞선 반등을 되돌렸으며 과거 봄·여름 반등에는 잔존 계절성 가능성이 있다고 봤다. 높은 모기지 금리와 약한 수요로 연말까지 주택가격의 전년비 하락을 예상했다.','AI 비교: 기존 7월 관련 분석을 같은 8월 판매의 사후 평가로 교체했다. 전월비 판매 감소와 월간 주택가격 보합은 다른 통계이며 함께 나타날 수 있다.',limitation=cadate)
fed=h('096f3ee',1,'The FOMC delivered','consequently increasingly fragile.','Citi는 25bp 인상 후에도 물가 둔화에 따른 당분간 동결·내년 인하를 기본으로 유지하지만, 이르면 10월 추가 인상 위험이 커졌다고 평가했다. 긴축이 비AI 제조업·주택·채용에 더 큰 부담을 줄 것으로 봤다.','AI 비교: GS 10월 인상·JPM 12월 인상과 Citi 동결이라는 기본 전망 차이는 유지된다. Citi가 인상 위험을 높여 본 것을 인상 기본 전망으로의 전환으로 표시하지 않는다.',limitation=cadate)
fed['evidence'].append(h('096f3ee',2,'With only two “dots”','again want to hold.','x','x')['evidence'][0]);fed['reviewed_pages'].append(dict(doc_id=fed['evidence'][-1]['doc_id'],page=2))
lab=h('096f3ee',3,'Regarding the labor market','hiring will accelerate.','Citi는 8월 고용 반등에도 3개월 평균 증가가 7만 명이고 채용률·고용률이 낮아 노동시장의 재가속 증거는 부족하다고 봤다. 4.1% 부근 실업률의 안정에는 노동참가율 하락도 작용했다고 설명했다.','AI 비교: JPM의 8월 단월 반등·참가율 회복 평가와 Citi의 최근 여러 달 추세 평가는 관측 구간이 다르다. 강한 한 달을 추세적 과열로 일반화하지 않는다.',limitation=cadate+' 참가율 평가는 최근 추세이며 JPM이 언급한 8월 단월 상승을 부정하는 동일 구간 비교가 아니다.')
core=h('096f3ee',5,'Chair Warsh made the same statement','downtrend more convincing.','Citi는 8월 근원 CPI 0.29% 전월비에도 3개월 대 3개월 연율이 5월 3.1%에서 8월 2.0%로 낮아졌다고 강조했다. 근원 PCE의 주가·무선통신 기여도 별도로 구분했다.','AI 비교: 원본의 반올림 전월비 0.3% 및 전년비 2.4%와 원문의 3개월 연율 2.0%는 서로 다른 척도다. 한 달 상승과 단기 추세 둔화가 공존할 수 있다.',limitation=cadate+' PCE 0.29%는 보고서의 추정이며 WECO 실제 CPI를 대신하지 않는다.')
ecb=h('7a7cf064',2,'Hence, there is both','deposit rate to 3%.','JPM은 12월 인상 전망에 2027년 3월 추가 인상을 더해 예금금리 정점을 3%로 예상했다. 성장 급락이나 중동의 지속적 진정이 없으면 12월 이후 동결을 유지하기 어렵다고 판단했다.','AI 비교: 기존 GS의 12월 2.75% 예상보다 JPM이 더 먼 시점의 추가 긴축을 명시했다. 이것은 JPM 전망이며 ECB의 확정 경로나 9월 발표값 변경이 아니다.',kind='related',limitation='9월 10일 결정 이후 9월 18일 정책경로 후속 분석이다. 미래 예금금리 전망만 직접 다루므로 재융자·한계대출금리의 새 수치 전망으로 환산하지 않는다.')
def add(eid,head,summary,watch,new):
 e=next(x for x in data['events'] if x['id']==eid);old=copy.deepcopy(e['commentary']);hs=[x for x in old['houses'] if x['house'] not in {h['house'] for h in new}]+copy.deepcopy(new)
 spec[eid]=(head,summary,watch,hs)
for eid,head,summary in [('853eb2e42fd95db18ebb','중국 생산 강세와 가계수요의 괴리','8월 산업생산은 전년비 5.2%로 예상 4.8%와 종전 4.5%를 웃돌았다. GS 후속 분석은 로봇·반도체와 스마트폰·PC의 생산 차이를 강조한다. AI 판단: 생산 호조가 소비·고용 전반의 회복을 뜻하지 않는다.'),('2a28e526354ddf6fd1d7','중국 소매판매 둔화, 표본별 격차 확인','8월 소매판매는 전년비 0.4%로 예상 0.8%와 종전 0.6%를 밑돌았다. GS는 대형 소매업체 약세와 소형업체 추정치의 차이로 실제 내수 격차가 더 클 가능성을 제기했다. AI 판단: 추정 방식의 가능성이며 공식 수치가 잘못됐다고 확정하지 않는다.')]:add(eid,head,summary,'소매업체 규모별 매출·가계 고용소득과 제조업 세부 생산을 확인한다.',[china])
for eid in ['257c384943811ede2edb','f8291371a72e4552017b','10754cbb2efbfb46043e','d3cfd8195aa7e6bb6a92','621738f00a5edf903da8']:
 e=next(x for x in data['events'] if x['id']==eid);old=e['commentary'];add(eid,old['headline'],old['summary']+' 9월 18일 Citi 후속 판단: 에너지의 광범위한 전가가 제한적이라는 근거로 2027년까지 인상 없는 경로를 예상한다. AI 판단: 동결 전망의 조건은 다음 근원물가의 안정이다.','9월 CPI의 에너지 전가·중앙값·절사평균과 임대료 반등 지속성을 확인한다.',[ca])
add('6a5da26ffe48b6285fb8','캐나다 주택판매 감소, 사후 수요 평가 보강','8월 기존주택판매는 전월비 -0.7%로 예상 -0.5%보다 약하고 종전 +0.5%에서 감소로 전환했다. Citi는 앞선 반등의 계절성과 높아진 금융비용을 경계했다. AI 판단: 한 달 감소만이 아니라 판매·신규매물 비율과 후속 거래가 회복 여부를 가른다.','주택판매·신규매물 비율과 모기지 금리, 가격의 월간·연간 변화를 구분해 확인한다.',[home])
for eid in ['1a26b1295325c42d6832','9929bd5a068495d067a3']:add(eid,'FOMC: Citi 동결 기본 유지, 추가 인상 위험 확대','정책금리 범위 3.75~4.00%의 25bp 인상은 원본 예상에 부합했다. GS는 10월, JPM은 12월 추가 인상을 예상하며 Citi는 동결 기본을 유지하되 이르면 10월 인상 위험이 커졌다고 평가한다. AI 판단: 기본 경로와 위험 시나리오를 구분해야 한다.','9월 물가·9월 30일 PCE 수정과 비AI 부문 고용·주택의 긴축 영향을 확인한다.',[fed])
for eid in ['795502e15628e7291cfb','ebda2b89709dd52de82b']:
 e=next(x for x in data['events'] if x['id']==eid);add(eid,e['commentary']['headline'],e['commentary']['summary']+' Citi 후속 분석은 3개월 평균 고용 증가 7만 명과 낮은 채용률을 들어 재가속 판단에 신중하다. AI 비교: JPM의 단월 개선과 Citi의 추세 평가는 함께 읽어야 한다.','3개월 고용 평균·채용률·노동참가율의 단월과 추세를 구분한다.',[lab])
for eid in ['4a3505096a43b67e4234','173ac64daad75c6e6692']:
 e=next(x for x in data['events'] if x['id']==eid);add(eid,e['commentary']['headline'],e['commentary']['summary']+' Citi 후속 분석은 근원 CPI 3개월 연율이 5월 3.1%에서 8월 2.0%로 낮아진 점을 강조한다. AI 비교: 월간·연간 발표치와 3개월 연율을 구분한다.','무선통신·주거비 기여와 향후 3개월 연율, PCE 방법론 수정을 확인한다.',[core])
for eid in ['0aa02540774735098165','43d080d9befd864c4f16','735ebd8f454565504ab1']:
 e=next(x for x in data['events'] if x['id']==eid);add(eid,e['commentary']['headline'],e['commentary']['summary']+' 9월 18일 JPM은 12월에 이어 2027년 3월 인상을 추가해 예금금리 3%를 예상했다. AI 판단: 원본의 이번 결정 수치는 그대로이며 이후 경로에 대한 하우스 전망만 보강한다.','에너지 경로·임금 및 기업 가격 전가, 12월 ECB 전망을 확인한다.',[ecb])
auth=R/'ecocal_dashboard/authored_commentary.json';original=auth.read_bytes();baseline=read(P/'baseline.json');assert hashlib.sha256(original).hexdigest()==baseline['hashes'][str(auth)]
bundle=json.loads(original);updated=[]
for e in data['events']:
 if e['id'] not in spec:continue
 assert e['available_at_request'];head,summary,watch,hs=spec[e['id']]
 review=dict(event_id=e['id'],review_id='comment-'+hashlib.sha256((e['id']+now).encode()).hexdigest()[:24],headline=head,summary=summary,watch=watch,houses=hs,match={k:e[k] for k in b.FIELDS[:5]},snapshot={k:e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS},reviewed_on='2026-09-21',reviewed_at=now,review_status='draft',origin='assistant_review_of_local_reports',workbook_sha256=inp['sha256'],review_log='5개 하우스 지표·지역 후보 검색 후 신규 원문 전체 근거 페이지를 검토. 9월 18~20일 후속 분석만 채택. 숫자는 9월 17일 최신 실제값 스냅샷 유지. HSBC 주간표는 정성 논거가 없어 새 해석으로 채택하지 않음. 원문 전체 검토 완료 아님.')
 bundle['event_reviews'].append(review);updated.append(e['id'])
assert len(updated)==17
(P/'authored_commentary.before.json').write_bytes(original);bundle['reviewed_on']='2026-09-21';auth.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
try:
 selected,stale=b.load_authored_comments(c,data['events'],'2026-09-21');assert len(selected)==194 and not stale
except Exception:auth.write_bytes(original);raise
(P/'review_result.json').write_text(json.dumps(dict(updated_events=updated,updated_count=len(updated),new_summaries=0,revised_summaries=17,retained_summaries=177,adopted_pages=[dict(doc_id=d,page=p) for d,p in sorted(pages)],reviewed_on='2026-09-21'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Validated',len(selected),'summaries;',len(updated),'revised')
