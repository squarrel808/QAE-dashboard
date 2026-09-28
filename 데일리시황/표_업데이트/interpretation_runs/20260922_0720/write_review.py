import copy,hashlib,json,pathlib,re,sqlite3,sys
from datetime import datetime
P=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
B=pathlib.Path('데일리시황/표_업데이트').resolve()
sys.path.insert(0,str(R/'ecocal_dashboard'));import build_dashboard as b
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
m=read(B/'latest.json');data=read(P/'candidates_WECO/dashboard_data.json');inp=read(P/'input.json')
c=sqlite3.connect(R/'data/research.sqlite3');c.row_factory=sqlite3.Row
now=datetime.now().astimezone().isoformat(timespec='seconds');pages=set();spec={}
def h(pre,pg,start,end,summary,comment,kind='reaction',limitation=''):
 d=c.execute('select * from documents where doc_id like ?',(pre+'%',)).fetchone();t=c.execute('select text from pages where doc_id=? and page=?',(d['doc_id'],pg)).fetchone()[0]
 a=re.search(r'\s+'.join(map(re.escape,start.split())),t);assert a,start
 z=re.search(r'\s+'.join(map(re.escape,end.split())),t[a.start():]);assert z,end
 pages.add((d['doc_id'],pg))
 return dict(house=d['house'],kind=kind,summary=summary,comment=comment,limitation=limitation,evidence=[dict(doc_id=d['doc_id'],page=pg,quote=t[a.start():a.start()+z.end()])],reviewed_pages=[dict(doc_id=d['doc_id'],page=pg)])
# Each quote comes from a full page read in this run.
gsclaim=h('25d34f232',2,'4. Initial jobless claims','January 2024.','GS는 신규 19.6만·계속 173만 건의 하락을 확인하면서 늦은 노동절에 따른 계절조정 잡음이 일부 작용했을 수 있다고 봤다.','AI 비교: JPM의 낮은 실업률 신호와 방향은 같지만 휴일 효과를 제거한 지속성을 확인해야 한다.')
jpclaim=h('4151d6b21',1,'Jobless claims continue','late September.','JPM은 최근 몇 년보다 낮은 청구가 고용 증가와 실업률 하락에 부합한다고 봤다. 노동절·잔존 계절성을 지적하고 계속청구가 9월 하순 다시 오를 가능성을 열어뒀다.','AI 비교: 청구 감소를 신규 채용 급증으로 동일시하지 않는다.')
gshouse=h('25d34f232',2,'2. Housing starts','quarter-over-quarter annualized).','GS는 착공 총량 감소와 달리 단독주택 착공 +7.6% 및 7월 상향수정에 주목해 3분기 GDP 추적치를 0.2%p 높인 연율 3.2%로 제시했다.','AI 비교: 단기 GDP 추적치 개선과 건축허가의 선행 약화는 양립한다.',limitation='보고서의 착공·허가 컨센서스는 WECO와 다르다. 예상 대비 차이는 WECO 수치로만 계산한다.')
jphouse=h('5aff80dc3',1,'The August housing starts','real residential investment in 3Q.','JPM은 단독주택 반등에도 허가가 연초 대비 5.9% 낮아 주택 둔화가 해소됐다는 증거가 부족하고 3분기 실질 주거투자의 소폭 감소에 부합한다고 봤다.','AI 비교: GS의 이번 GDP 추적치 상향과 JPM의 주거투자 수준 전망은 서로 다른 비교 기준이다.')
cthouse=h('641766cc9',2,'Data – Housing starts','GDP growth in coming quarters.','Citi는 높은 금리와 수요 약화가 착공·허가를 추가로 낮추고 주거투자가 향후 GDP에 부담을 줄 것으로 봤다.','AI 비교: 단독주택의 한 달 반등을 추세 회복으로 보지 않는다는 점에서 JPM과 유사하다.')
philly=h('25d34f232',2,'1. The Philadelphia','highest level since 1983.','GS는 지수 하락폭이 예상보다 작았지만 고용·신규주문 하락으로 구성은 약했다고 평가했다. 투입·판매가격과 배송기간 상승도 지적했다.','AI 비교: 예상 상회와 전월 대비 둔화가 공존하며 지역 제조업 설문을 전국 ISM으로 바꾸지 않는다.')
pending=h('5aff80dc3',1,'Pending home sales, which','year-ago declines.','JPM은 8월 +0.3%에도 7월 하향수정으로 최근 3개월 계약이 7% 줄고 6개월 저점 부근이라고 설명했다.','AI 비교: 전월 반등은 침체된 수준에서의 소폭 회복이며 확정 거래와 구분한다.')
kr=h('5be1d5fa2',1,'Korea’s producer price','ongoing geopolitical risks.','JPM은 8월 PPI 전년비 7.9%와 계절조정 전월비 0.4%를 확인했다. 3개월 연율은 6.0%로 둔화해 순차적 디스인플레이션 가능성을 남기되 지정학적 변동성을 경계했다.','AI 비교: 전년비 상승과 단기 연율 둔화는 다른 기준이다. PPI 상승을 CPI에 전부 전가한다고 가정하지 않는다.')
jpcpi=h('041c4ae69',1,'The August nationwide CPI','gaining momentum.','JPM은 신선식품 제외 CPI 1.7% 둔화가 전기·가스 보조금과 쌀값 하락의 영향을 받았고, 식품·에너지 제외 지수는 계절조정 전월비 0.3% 올라 기조 압력이 남았다고 봤다.','AI 비교: 신선식품 제외와 전체 식품·에너지 제외 지수는 정의가 다르므로 같은 근원 수치로 비교하지 않는다.')
ctcpi=h('bd145fa96',1,'The August nationwide core','in our view.','Citi는 보조금·쌀값으로 근원이 1.7%로 낮아졌으나 유가 전가로 9월 2%를 넘고 내년 초 3%에 접근할 것으로 예상했다. BOJ 예상 범위 안이어서 정책 영향은 제한적이라고 봤다.','AI 비교: JPM과 일시적 하락 요인에는 동의하되 Citi는 이번 발표 자체의 정책 파급을 제한적으로 평가한다.')
hscpi=h('c84a19836',1,'Headline CPI rose','Prior: 1.9%).','HSBC는 전체 CPI 1.9%, 신선식품 제외 1.7%를 확인했다.','AI 비교: 전체와 근원을 구분하며 두 수치 모두 원본과 일치한다.')
jpboj=h('a50d987fb',2,'We continue to expect','coming quarters.','JPM은 향후 물가 상승 경로를 근거로 다음 BOJ 인상을 12월로 유지했다.','AI 비교: HSBC의 2027년 1분기보다 이른 경로다.')
ctboj=h('715104a5b',1,'The BoJ raised','as our base scenario.','Citi는 두 명의 반대가 내년 이사회 구성 변화 전 인상을 서두를 유인을 높인다고 해석해 2026년 12월, 2027년 3월·7월 인상을 기본으로 제시했다.','AI 비교: 반대 표를 단순 비둘기 신호로만 읽지 않는 해석이며 BOJ의 확정 일정이 아니다.')
hsboj=h('c84a19836',2,'We therefore maintain','18 December MPM','HSBC는 2027년 1분기 25bp 추가 인상으로 1.50%를 기본 전망으로 유지하되 Fed의 추가 인상으로 12월 BOJ 인상 가능성이 커질 위험을 제시했다.','AI 비교: JPM·Citi의 12월 기본과 HSBC의 12월 위험 시나리오를 구분한다.',limitation='1쪽의 vote to hold 표현은 같은 페이지 사실·2쪽의 7대2 인상 설명과 충돌한다. 결정은 WECO와 명확한 2쪽 설명을 기준으로 확인했다.')
gsboj=h('188a8fe374',1,'We also revised up','1.25% and 1.75%).','GS 정책 추적 보고서는 일본 정책금리를 2026년 말 1.25%, 2027년 말 1.75%로 제시했다.','AI 비교: 올해 말 수준 유지 전망은 JPM·Citi의 12월 추가 인상과 다르다.',kind='related',limitation='표지 9월 20일 18:45 EDT·메타데이터 9월 21일. 9월 18일 BOJ 이후의 글로벌 정책 경로 보고서이며 결정문 자체가 아니다.')
ip=h('710ef5751',1,'A run of solid gains','remain a concern.','JPM은 제조업 -0.3%를 유틸리티 +1.8%가 상쇄해 전체 생산이 보합이 됐다고 설명했다. 3분기 증가속도는 2분기보다 둔화하며 공급·물가 압력도 남았다고 봤다.','AI 비교: 전체 생산 보합을 모든 업종의 정체로 해석하지 않는다.')
cap=h('710ef5751',1,'Overall capacity utilization','industrial sector.','JPM은 전체 가동률 76.3%, 제조업 75.7% 모두 장기 평균 아래여서 유휴 생산능력이 남았다고 판단했다.','AI 비교: 일부 공급병목과 산업 전체의 가동여력은 함께 존재할 수 있다.')
ea=h('8c0e34fdf',1,'The final eurozone inflation','a month earlier).','HSBC는 8월 전체 HICP가 속보보다 0.1%p 낮은 3.2%, 근원은 2.4%로 확정됐다고 설명했다. 전체는 7월 2.9%보다 올랐고 근원은 7월 2.5%보다 낮았다.','AI 비교: WECO Prior는 같은 8월 속보치이므로 월간 물가추세 비교로 쓰지 않는다.')
gea=h('026fe43c3',1,'Our summary indicator','18%yoy for Q4.','GS는 기조물가의 순차 상승속도가 완만히 둔화했으나 에너지로 전체 물가 정점 전망을 4분기 3.8%로 높였다고 설명했다.','AI 비교: 근원 둔화와 전체 물가 재상승 위험을 분리한다.',limitation='GS 원문 전체 전년비 3.25%와 WECO 3.2%의 표시 정밀도가 다르다. 원본 수치는 변경하지 않는다.')
spec={}
def add(eid,head,summary,watch,hs):spec[eid]=(head,summary,watch,copy.deepcopy(hs))
add('3f23cf1342dc221a670f','일본 해외채권 매입 확대, 주간 변동 주의','실제 1,082.9는 수정 종전 111.4보다 971.5 증가했다(원본 배율 b). AI 해석 초안: 해외채권 순매입 확대만으로 엔화 방향이나 BOJ 결정을 단정할 수 없다. 해당 주간의 직접 IB 근거는 미확보다.','연속 주간 흐름과 투자자별·환헤지 구성을 확인한다.',[])
for eid,head,s in [('cff4a274dfffba446bb0','유로존 근원 확정치 2.4% 유지','8월 확정 근원은 예상·속보와 같은 2.4%다.'),('c17e9496f181c24844e0','유로존 월간 CPI 0.4% 확정','8월 전체 전월비는 예상·속보와 같은 0.4%다.'),('41fdf167a863cbeae385','유로존 전체 CPI 속보 대비 하향','8월 확정 전체 전년비는 3.2%로 예상·속보 3.3%보다 0.1%p 낮다.')]:
 hs=[ea,gea]
 if eid=='c17e9496f181c24844e0':
  hs=copy.deepcopy(hs)
  for x in hs:x['kind']='related';x['limitation']+=' 8월 전년비·근원 세부 분석이며 전체 전월비 0.4%에 대한 직접 반응은 아니다.'
 add(eid,head,s+' AI 해석 초안: 근원 둔화와 에너지발 전체 물가 위험이 공존한다. Prior는 전월값이 아닌 속보치다.','9월 에너지 기여와 서비스의 계절조정 추세를 확인한다.',hs)
add('48e6ec69f67b93210555','캐나다 생산자물가 예상 상회','8월 산업제품가격은 전월비 1.3%로 예상 보합을 웃돌았다. 종전은 0.6%에서 0.3%로 낮아졌다. AI 해석 초안: 생산단 가격압력 확대지만 CPI 전가율은 별도 확인이 필요하다. 직접 IB 해설 미확보.','에너지·금속 기여와 후속 소비자물가 전가를 확인한다.',[])
add('48349d882a1dea794a71','미국 허가 감소, 건설 선행 약화','8월 허가는 연율 139.4만 건으로 예상 140.75만·종전 143.3만보다 낮다. AI 해석 초안: 단독주택 착공 반등보다 향후 건설 흐름에 신중할 근거다.','단독·다세대 허가와 신규주택 재고를 확인한다.',[gshouse,jphouse,cthouse])
add('d16aa13dabc9012be9ad','미국 착공 총량 감소, 단독주택은 반등','8월 착공은 연율 127.5만 건으로 예상 132만 미달이다. 7월은 123.9만에서 130.9만으로 상향돼 수정 기준 3.4만 감소했다. AI 비교: GS는 단독주택 반등의 당기 GDP 기여, JPM·Citi는 허가·금리 부담에 무게를 둔다.','다세대 변동성과 단독주택 추세를 분리한다.',[gshouse,jphouse,cthouse])
for eid,head,s in [('6f5bbdd3f8bdf8f5d47d','미국 신규 실업수당 19.6만 건','9월 12일 주간 신규 청구는 19.6만으로 예상 20.65만·종전 20.6만을 밑돌았다.'),('1085bf15e1098089b0e5','미국 계속 실업수당도 감소','9월 5일 주간 계속청구는 173만으로 예상 177.9만·수정 종전 176.9만보다 낮다.')]:add(eid,head,s+' AI 비교: 낮은 해고·실업 신호지만 노동절 계절성 때문에 단주간 감소를 추세로 단정하지 않는다.','휴일 이후 수 주와 계속청구의 9월 하순 반등 여부를 확인한다.',[gsclaim,jpclaim])
add('3f473b50589b0ce1686f','필라델피아 제조업 예상 상회, 구성 약화','9월 37.8은 예상 32.1을 웃돌지만 종전 47.4보다 9.6포인트 낮다. AI 해석 초안: 고용·주문 둔화와 가격·배송기간 상승을 함께 읽어야 한다.','다른 지역 설문과 전국 ISM 신규주문·가격을 대조한다.',[philly])
add('5527a108e0df94440ab6','미국 잠정주택판매 소폭 반등','8월 +0.3%는 예상 -0.1%를 웃돈다. 7월은 -2.3%에서 -2.6%로 하향됐다. AI 해석 초안: 반등 폭이 작아 최근 누적 감소를 만회한 회복은 아니다.','계약의 실제 거래 전환과 모기지 비용을 확인한다.',[pending])
add('f7b7c08536d15f0d245e','한국 PPI 전년비 상승, 단기 속도는 둔화','8월 생산자물가는 전년비 7.9%로 종전 7.7%보다 높다. AI 비교: JPM의 단기 연율 둔화와 모순되지 않으며 유가·환율의 추가 전가가 관건이다.','9월 에너지 가격과 비에너지 상품·서비스를 확인한다.',[kr])
for eid,head,s in [('9a735a7bd432aceed474','일본 근원 CPI 1.7%, 보조금 효과','신선식품 제외 CPI는 1.7%로 예상·종전 1.8%보다 낮다.'),('8f0d61422c610861afe9','일본 전체 CPI 1.9%, 기조 압력 분리','전체 CPI는 1.9%로 예상 2.0%보다 낮고 종전과 같다.')]:
 hs=copy.deepcopy([jpcpi,ctcpi,hscpi])
 if eid=='8f0d61422c610861afe9':
  for x in hs[:2]:x['kind']='related';x['limitation']='같은 8월 발표의 신선식품 제외 등 세부지표 분석이며 전체 CPI 1.9%에 대한 직접 수치 반응과 구분한다.'
 add(eid,head,s+' AI 비교: JPM·Citi는 보조금·쌀값의 일시 효과를 강조한다. 낮아진 표시 물가만으로 긴축 종료를 판단하기 어렵다.','보조금 종료 시점, 서비스 임금 전가와 근원 정의별 차이를 확인한다.',hs)
add('d9dc3455a1737467977c','BOJ 1.25% 인상, 다음 시점은 IB별 차이','BOJ는 예상대로 1.00%에서 1.25%로 25bp 올렸다. AI 비교: JPM·Citi는 12월 추가 인상, HSBC는 2027년 1분기 기본, GS 최신 글로벌 표는 2026년 말 1.25%를 제시한다. 전망과 위험 시나리오를 구분한다.','엔화·Fed 경로, 보조금 제외 물가와 BOJ 금융여건 평가를 확인한다.',[gsboj,jpboj,ctboj,hsboj])
add('24c794eee60f4238f7da','미국 산업생산 보합, 제조업 숨고르기','8월 산업생산 0.0%는 예상 0.3%·종전 0.2%보다 약하다. AI 해석 초안: 유틸리티가 제조업 감소를 상쇄한 보합으로 성장 구성의 차이가 크다.','자동차·첨단기술 생산과 9월 주문을 확인한다.',[ip])
add('c5c4b7f83e5edb7c31ba','미국 가동률 76.3%, 여유 생산능력','8월 가동률은 76.3%로 예상 76.4%를 밑돌고 종전과 같다. AI 해석 초안: 생산능력 전반의 과열 증거는 약하지만 업종별 병목은 남을 수 있다.','제조업 가동률과 배송기간·투입가격을 함께 본다.',[cap])
add('3b6b2a83994b8cd51026','미국 선행지수 감소 전환','8월 -0.1%는 예상 +0.1%와 종전 +0.2%보다 약하다. AI 해석 초안: 향후 성장 경계 신호지만 한 달 감소로 경기침체를 확정할 수 없다. 해당 지수 직접 IB 근거는 미확보다.','연속 하락 여부와 구성항목·동행지수를 확인한다.',[])
gsfed=h('188a8fe374',1,'the US (another','cuts in 2027).','GS 최신 글로벌 정책표는 미국의 다음 25bp 인상을 12월로 적고 이후 2027년 50bp 인하를 제시했다.','AI 비교: 앞서 저장된 GS 10월 인상 전망과 시점이 다르므로 최신 자료의 12월 표기를 우선하되 변경의 상세 사유는 미확인이다.',kind='related',limitation='표지 9월 20일 18:45 EDT·메타데이터 9월 21일. 글로벌 추적 보고서의 후속 정책 경로이며 FOMC 결정의 확정 지침이 아니다. 미국 전용 후속 원문과 재대조 필요.')
ctfed=h('db2b11949b',2,'We are most interested','further rate hikes.','Citi는 만장일치 인상이 이후 긴축 강도에 대한 완전한 합의를 뜻하지 않으며 일부 위원이 물가 둔화를 더 긍정적으로 볼 수 있다고 분석했다. Williams 등의 발언을 확인 대상으로 제시했다.','AI 비교: 실제 표결과 향후 경로의 이견 가능성을 구분하며 아직 나오지 않은 발언을 사실로 쓰지 않는다.')
for eid in ['1a26b1295325c42d6832','9929bd5a068495d067a3']:
 e=next(x for x in data['events'] if x['id']==eid);hs=[x for x in e['commentary']['houses'] if x['house'] not in ['GS','Citi']]+[gsfed,ctfed]
 add(eid,'FOMC 후속: GS 최신 표는 12월, Citi는 이견 주목','정책금리 범위 3.75~4.00%는 원본 예상에 부합한 25bp 인상이다. AI 비교: GS 최신 글로벌 보고서는 앞선 10월과 달리 다음 인상을 12월로 적었다. JPM의 12월 전망과 시점이 같아졌으나 GS 변경 사유는 미국 전용 후속 보고서 확인이 필요하다. Citi는 표결 만장일치와 추가 인상 동의는 다를 수 있다고 본다.','Fed 위원 발언과 GS 미국 전용 정책경로의 날짜·시점을 재대조한다.',hs)
ctcore=h('a2e64b86cc',2,'Energy prices have increased','medium-term forecasts.','Citi는 운송비 상승에도 8월 근원 상품 CPI가 전년비 0.7%로 둔화했고 높은 디젤 비용의 광범위한 전가를 기본 전망에 넣기에는 신중하다고 설명했다.','AI 비교: 전가가 없다고 확정한 것이 아니다. 비용 상승 지속기간과 실질소득·수요가 후속 조건이다.',kind='related',limitation='9월 21일의 8월 근원 상품 세부 및 향후 비용 전가 분석이다. 전체 근원 CPI의 새 발표치나 PCE 실제값이 아니다.')
for eid in ['4a3505096a43b67e4234','173ac64daad75c6e6692']:
 e=next(x for x in data['events'] if x['id']==eid);old=e['commentary'];hs=copy.deepcopy(old['houses']);x=next(x for x in hs if x['house']=='Citi');x['summary']+=' '+ctcore['summary'];x['comment']+=' '+ctcore['comment'];x['limitation']+=' '+ctcore['limitation'];x['evidence']+=ctcore['evidence'];x['reviewed_pages']=x.get('reviewed_pages',[])+ctcore['reviewed_pages']
 add(eid,old['headline'],old['summary']+' 9월 21일 Citi는 디젤 운송비의 근원 상품 전가가 아직 명확하지 않다고 보강했다. AI 판단: 비용 충격과 최종 가격 전가를 구분한다.','디젤 가격 지속성과 근원 상품·임대료·실질소득을 확인한다.',hs)
auth=R/'ecocal_dashboard/authored_commentary.json';original=auth.read_bytes();baseline=read(P/'baseline.json');assert hashlib.sha256(original).hexdigest()==baseline['hashes'][str(auth)]
bundle=json.loads(original);updated=[];new=0
for e in data['events']:
 if e['id'] not in spec:continue
 assert e['available_at_request'];head,summary,watch,hs=spec[e['id']];new+=not bool(e['commentary'])
 bundle['event_reviews'].append(dict(event_id=e['id'],review_id='comment-'+hashlib.sha256((e['id']+now).encode()).hexdigest()[:24],headline=head,summary=summary,watch=watch,houses=hs,match={k:e[k] for k in b.FIELDS[:5]},snapshot={k:e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS},reviewed_on='2026-09-22',reviewed_at=now,review_status='draft',origin='assistant_review_of_local_reports',workbook_sha256=inp['sha256'],review_log='5개 하우스 지표·국가 후보와 시점 검색, 채택 근거 전체 페이지 검토. 직접 근거 없는 3개 지표는 수치 기반 AI 초안이며 IB 미확보. 새 PDF 전체 완독 아님.'))
 updated.append(e['id'])
assert len(updated)==22 and new==18
(P/'authored_commentary.before.json').write_bytes(original);bundle['reviewed_on']='2026-09-22';auth.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf8')
try:
 selected,stale=b.load_authored_comments(c,data['events'],'2026-09-22');assert len(selected)==212 and not stale
except Exception:auth.write_bytes(original);raise
(P/'review_result.json').write_text(json.dumps(dict(updated_events=updated,new_summaries=new,revised_summaries=4,retained_summaries=190,adopted_pages=[dict(doc_id=d,page=p) for d,p in sorted(pages)]),ensure_ascii=False,indent=2),encoding='utf8');print('validated',len(selected),'new',new,'revised',4)
