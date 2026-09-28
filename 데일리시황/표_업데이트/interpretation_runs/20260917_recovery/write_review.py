import copy, hashlib, json, pathlib, re, sqlite3, sys
from datetime import datetime
P=pathlib.Path(__file__).resolve().parent
ROOT=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
sys.path.insert(0,str(ROOT/'ecocal_dashboard'))
import build_dashboard as b
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
data=read(P/'validated_WECO/dashboard_data.json'); inp=read(P/'input.json')
now=datetime.now().astimezone().isoformat(timespec='seconds')
c=sqlite3.connect((ROOT/'data/research.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
pages=set()
def house(pre,pg,start,end,summary,comment,kind='reaction',limitation=''):
 d=c.execute('select * from documents where doc_id like ?',(pre+'%',)).fetchone()
 t=c.execute('select text from pages where doc_id=? and page=?',(d['doc_id'],pg)).fetchone()[0]
 a=re.search(r'\s+'.join(map(re.escape,start.split())),t);assert a,start
 z=re.search(r'\s+'.join(map(re.escape,end.split())),t[a.start():]);assert z,end
 pages.add((d['doc_id'],pg))
 return dict(house=d['house'],kind=kind,summary=summary,comment=comment,limitation=limitation,evidence=[dict(doc_id=d['doc_id'],page=pg,quote=t[a.start():a.start()+z.end()])],reviewed_pages=[dict(doc_id=d['doc_id'],page=pg)])
gsret=house('8e0382',1,'BOTTOM LINE:','year-over-year rate of +3.17%.','GS는 온라인 판매 반등을 포함한 광범위한 소비 강세로 3분기 GDP 추적치를 전분기비 연율 3.0%로 0.5%p 올렸다. 자동차 제외 소매판매는 1.4% 늘었다.','AI 비교: JPM도 성장 전망을 올렸지만 수준은 3.5%로 다르다. 온라인 할인행사 시점 효과가 있어 월간 반등 전체를 추세 가속으로 보기는 어렵다.',limitation='보고서의 자동차 제외 예상 0.6%는 원본 0.55%의 반올림과 다르므로 비교에는 원본을 쓴다. 자동차 제외와 GDP 통제그룹은 서로 다른 지표이며 이번 달 수치만 1.4%로 같다.')
jpmret=house('68f93a',1,'Following a strong August retail sales report,','despite the spike in energy prices.','JPM은 8월 소비 강세를 반영해 3분기 GDP와 실질 소비 증가율 전망을 각각 전분기비 연율 2.75%에서 3.5%로 올렸다.','AI 비교: GS보다 성장 추적 수준이 높다. JPM도 할인행사 이동으로 8월 증가율이 기조를 과장할 수 있다고 지적했다. 전망치는 GDP 실제값이 아니다.')
citiret=house('12ba06',2,'Citi’s view','back to more typical levels.','Citi는 7~8월을 함께 봐도 소비 증가가 견조하지만 실질소득 정체 속 저축률 하락이 지출을 지탱해 향후 감속 위험이 남는다고 평가했다.','AI 비교: GS·JPM의 당분기 성장 상향과 Citi의 중기 지속성 우려는 시간 범위가 다르다.')
gsimp=house('8e0382',2,'3. Core import prices','foreign travel component of core PCE, increased 2.1% (SA by GS).','GS는 근원 수입물가 0.8% 상승과 전자제품·국제항공료 강세를 확인했다.','AI 비교: 총수입물가 0.7%와 근원 0.8%를 구분한다. 전자제품 가격의 소비물가 전가를 다음에 확인해야 한다.')
jpmimp=house('4c0d15',1,'Import price inflation remained firm','(3.3%oya).','JPM은 비연료 수입물가뿐 아니라 연료·컴퓨터를 제외한 가격도 전월비 0.6% 올라 압력이 넓다고 봤다. 근원 PCE 전월비 추정은 0.25%로 유지했다.','AI 비교: GS와 수입물가 강세 진단은 같지만 소비물가 전가 폭은 별도 판단이다. 수입물가지수에는 관세 자체가 포함되지 않는다.')
jpmorders=house('55b8a3',1,'Core domestic private machinery orders','business capex plans.','JPM은 7월 핵심 기계수주 -3.7%가 자사 예상 -5.5%보다 양호하며 6월 급증 뒤 제한적 반락이라고 봤다. AI 관련 제조업 수요와 기업이익이 설비투자를 지지한다고 평가했다.','AI 비교: 시장 예상 -1.2%에는 못 미쳤지만 JPM 예상에는 상회했다. 예상 기준을 분리해야 하며 수주 감소를 지속적 투자 위축으로 단정하기 어렵다.')
jptrade=house('9f44cf',1,'BOTTOM LINE:','has been rising since July.','GS는 수출물량이 전년비 늘었지만 자체 계절조정 전월비로 감소했으며, 반도체 수출입 강세와 높은 에너지 수입 부담이 공존한다고 평가했다.','AI 비교: 명목 수출 증가가 순수출 개선을 보장하지 않는다. 수입가격과 물량을 나눠 적자 확대를 봐야 한다.',limitation='원문 작년 8월 적자 표기는 핵심수치와 본문이 충돌해 사용하지 않았다. 현재 적자 약 1.1조 엔은 원본 b 배율과 대조했다.')
gschina=house('733b5c',1,'China’s August activity data','4.6% yoy previously).','GS는 수출이 지지한 생산과 약한 소비·투자의 불균형을 확인하고 3분기 성장 전망을 전년비 4.6%에서 4.4%, 연간은 4.6%에서 4.5%로 낮췄다.','AI 비교: Citi의 3분기 4.5%·연간 4.6% 유지와 다르다. 생산 호조만으로 내수 바닥을 판단하지 않는다.')
jpmchina=house('0fc004',1,'August activity data delivered','more balanced.','JPM은 수출 주도 생산 회복과 약한 소매판매·투자의 격차를 강조했다. 생산 강세가 일부 하방 우려를 상쇄해 3분기 성장 전망 위험은 더 균형적이라고 평가했다.','AI 비교: GS의 성장 전망 하향보다 생산 회복의 완충 효과에 무게를 둔다. JPM의 전분기비 연율과 GS·Citi의 전년비 전망은 직접 숫자 비교하지 않는다.')
citichina=house('5f60bc',2,'China’s economic momentum','growth at 4.6%YoY.','Citi는 산업생산 5.2%의 예상 상회와 소매판매 0.4%·누적 투자 -7.2%의 부진을 함께 확인했다. 3분기 4.5%, 연간 4.6%의 전년비 성장 전망은 유지했다.','AI 비교: GS와 내수 부진 진단은 같지만 성장 전망 조정은 달랐다. 재정 집행과 9월 지표가 판단을 가를 확인점이다.')
gsm2=house('d31233',2,'3. M1 growth','slightly faster fiscal spending.','GS는 M2 증가율의 7.5% 둔화를 비은행 금융기관 예금 증가세 약화에서 주로 찾았다.','AI 비교: 통화량 둔화를 정책금리 인상이나 신용수요 전반 붕괴와 동일시하지 말고 예금 구성과 대출을 함께 봐야 한다.')
citim2=house('ac60bf',2,'Money and credit growth','or other M2 components higher.','Citi는 M2 7.5%와 대출·사회융자 증가율 둔화를 확인하고 재정정책 집행 지연이 통화량에도 반영됐다고 평가했다.','AI 비교: GS는 비은행 예금 구성, Citi는 재정 집행 속도에 초점을 둔다. 재정 지출과 기업예금의 후속 회복을 확인한다.')
cacpi=house('e275c9',1,'Headline CPI fell','determining the outcome of the October meeting.','Citi는 8월 CPI 전월비 -0.1%, 전년비 3.0%와 목표 부근 근원물가를 확인했다. 임대료 반등에도 의류·가구 가격에서는 비용 전가가 제한적이라고 봤다.','AI 비교: 원본 예상은 -0.05%이므로 실제는 0.05%p 하회한다. 원문의 예상 부합 평가는 그 보고서의 전망 기준이며 현재 원본 예상과 구분한다.')
fedjpm=house('eecf49',1,'After almost four months','in line with the revised median FOMC expectations.','JPM의 9월 16일 FOMC 사후 분석은 25bp 인상과 추가 인상을 시사한 점도표를 강조하며 12월 한 차례 추가 인상 전망을 유지했다.','AI 비교: Citi의 회의 전 연내 추가 동결 전망과 다르지만 동일 시점의 사후 견해 비교는 아니다. 회의 이후 Citi의 후속 평가는 미확보다.',kind='related',limitation='동일 Sep 16 회의의 사후 보고서다. 원본 달력은 9월 17일 03:00, 보고서는 미국 9월 16일로 날짜가 달라 기존 날짜 검증상 관련 분석으로 보수적으로 분류했다. 시간대는 원본에 명시되지 않아 변환하지 않았으며 사전 전망으로 취급하지 않는다.')
fedciti=house('634485',1,'We expect a 25bp rate hike today.','rate cuts in mid-2027.','Citi는 회의 전 25bp 인상을 예상했지만 큰 인상 사이클보다 소폭 조정으로 보고 10월·12월 동결을 전망했다.','AI 비교: 25bp 인상 예상은 결과와 맞았지만 후속 경로는 JPM 사후 분석과 차이가 있다. 이 코멘트는 발표 전 전망이며 점도표를 확인한 뒤의 반응이 아니다.',kind='preview',limitation='9월 16일 07:00 ET 발행으로 FOMC 발표 전이다. 이후 견해 수정 여부는 이번 확보 원문으로 확인하지 못했다.')

spec={}
def add(eid,head,summary,watch,hs=()):spec[eid]=(head,summary,watch,list(hs))
add('72b1976a6e4baf4ed579','일본 해외채권 순매수 전환, 주간 변동성 유의','9월 4일 주간 해외채권 매입은 원본 b 배율 111.9로 종전 -824.0에서 순매수로 전환했다. AI 해석 초안: 한 주의 방향 전환은 지속적인 해외자산 배분 확대를 입증하지 않는다. 원본에 통화 표기는 없어 통화 환산은 하지 않았다.','다음 주 흐름과 투자자별 매입·환헤지 비용을 확인한다.')
add('a74fc0ada284d786ef65','미국 재정적자 예상보다 작지만 종전 수정폭에 유의','8월 재정수지는 원본 b 배율 -166.797로 예상 -211.1보다 적자 폭이 작다. 종전은 -344.792에서 -432.286으로 수정됐다. AI 해석 초안: 세입·지출 시점의 계절성이 커 월간 적자 축소를 구조적 재정 개선으로 보기는 어렵다. 통화는 원본 미표기로 보완하지 않았다.','누적 회계연도 수지와 세입·이자지출, 종전 수정 원인을 확인한다.')
add('8949ffd9bb3befcf3c90','중국 M2 둔화, 예금 구성과 재정 집행이 관건','8월 M2는 전년비 7.5%로 예상 7.6%와 종전 7.7%를 밑돌았다. GS는 비은행 예금, Citi는 재정 집행 지연을 강조한다. AI 판단: 유동성 공급과 민간 신용수요를 구분해야 한다.','9월 재정 집행·기업예금·신규 대출 회복 여부를 확인한다.',[gsm2,citim2])
add('d3cfd8195aa7e6bb6a92','캐나다 월간 CPI 예상 하회, 근원 구성은 혼재','8월 비계절조정 CPI는 전월비 -0.1%로 예상 -0.05%보다 0.05%p 낮다. Citi는 근원 안정에 무게를 두지만 임대료는 반등했다. AI 판단: 비계절조정 월간 하락을 지속적 디플레이션으로 해석하지 않는다.','절사·중앙값 CPI의 3개월 속도와 임대료·주택금융 비용을 확인한다.',[cacpi])
add('2a28e526354ddf6fd1d7','중국 소매판매 둔화, 생산 호조와 내수 괴리','8월 소매판매는 전년비 0.4%로 예상 0.8%와 종전 0.6%를 밑돌았다. GS·JPM·Citi는 공급·수출보다 내수가 약하다는 데 일치하지만 성장 전망 조정은 다르다.','9월 소비와 재정지원 집행, 자동차 보조금 효과를 확인한다.',[gschina,jpmchina,citichina])
add('d96db3cb937bf219622d','중국 누적 소매판매 증가세 소폭 둔화','1~8월 소매판매는 전년비 1.1%로 종전 누적 1.2%보다 낮다. AI 해석 초안: 누적치 둔화는 8월 단월 0.4%의 부진과 일관되지만 단월 변화율과 누적 증가율을 혼용하지 않는다.','단월 소비와 서비스 소비가 함께 개선되는지 확인한다.')
add('853eb2e42fd95db18ebb','중국 산업생산 예상 상회, 내수 회복은 별개','8월 산업생산은 전년비 5.2%로 예상 4.8%, 종전 4.5%를 웃돌았다. 세 IB 모두 수출·첨단제조업이 생산을 지지했으나 소비·투자가 약하다고 평가했다. AI 판단: 생산 반등만으로 광범위한 경기 회복을 선언하기 어렵다.','수출 주문과 국내 판매·재고, 재정 집행의 투자 연결을 확인한다.',[gschina,jpmchina,citichina])
add('eb602fa587cf9735e7fb','중국 누적 산업생산 증가율 유지','1~8월 산업생산은 전년비 5.3%로 종전 누적치와 같다. AI 해석 초안: 8월 단월 생산 개선에도 누적 증가율은 안정적이며 소비·투자와의 격차가 남는다. 단월 분석을 누적 수치에 대한 IB 직접 평가로 대체하지 않았다.','9월 생산 증가가 수출·첨단업종을 넘어 확산되는지 확인한다.')
add('51d3eefb5031d0634107','중국 누적 투자 감소폭 확대','1~8월 고정자산투자는 전년비 -7.2%로 예상 -7.1%를 하회하고 종전 -6.7%보다 감소폭이 커졌다. GS·Citi는 내수 부진을 확인했다. AI 판단: 누적 감소폭 확대와 일부 단월 기저효과 개선을 구분한다.','정부 채권 발행이 실제 프로젝트 착공·민간 투자로 이어지는지 확인한다.',[gschina,citichina])
add('eaaa9c7d643cbdc191dc','독일 현재상황 개선, 여전히 부정적 응답 우세','9월 ZEW 현재상황은 -47.1로 예상 -52.05보다 높고 종전 -61.1에서 개선됐다. AI 해석 초안: 음수 폭 축소는 평가 개선이지 경기 확장 확인이 아니다. 현재 상황과 기대지수도 구분해야 한다.','다음 기업 설문과 실제 생산·주문이 개선을 뒷받침하는지 확인한다.')
add('74ca4e43e3b7d758370d','일본 무역적자 확대, 수입 부담 지속','8월 무역수지는 원본 b 배율 -1105.607로 예상 -1058.4보다 적자가 크고 수정 종전 -638.34473보다 악화됐다. GS는 반도체 교역 강세에도 에너지 수입 부담이 남는다고 평가했다. AI 판단: 수출 금액·물량과 수입가격을 분리해야 한다.','가을 원유·가스 수입단가와 수출물량 회복을 확인한다.',[jptrade])
add('8759e2d68e870902a13b','일본 기계수주 반락, JPM은 투자 기조 유지','7월 핵심 기계수주는 전월비 -3.6831%로 예상 -1.2%보다 약했지만 6월 9.7495% 급증 뒤 조정이다. JPM은 자사 예상 -5.5%에는 양호했고 AI 제조업 투자 수요가 유지됐다고 봤다.','단칸 설비투자 계획과 비제조업 수주 회복을 확인한다.',[jpmorders])
relatedorders=copy.deepcopy(jpmorders);relatedorders.update(kind='related',limitation='같은 7월 기계수주의 전월비·업종 구성 분석이다. 전년비 11.1623% 자체에 대한 직접 평가는 아니므로 관련 분석으로 제한한다.')
add('eb3a0b311d529c302afc','일본 기계수주 전년비 예상 상회, 월간으로는 조정','7월 핵심 기계수주는 전년비 11.1623%로 예상 9.6%를 웃돌았지만 종전 16.8771%보다 둔화했다. AI 판단: 높은 연간 증가와 월간 반락이 공존하며 전년비 예상 상회만으로 재가속을 뜻하지 않는다.','기저효과와 월간 수주 추세, 업종별 투자 지속성을 확인한다.',[relatedorders])
add('82882e0af5b2c618e8e3','호주 선행지수 소폭 하락 전환','8월 Westpac 선행지수는 전월비 -0.04%로 수정 종전 0.02%에서 하락 전환했다. AI 해석 초안: 작은 월간 하락은 모멘텀 약화를 시사하지만 경기침체를 확정하지 않는다.','선행지수 추세와 고용·소비의 동행 여부를 확인한다.')
add('041895dc9d2ddf6974be','이탈리아 조화물가 확정치 예상 부합','8월 최종 HICP 전년비는 3.2%로 예상과 종전 수치에 일치했다. AI 해석 초안: 확정 발표의 추가 놀라움은 제한적이다. 종전 값은 같은 기간 잠정치일 수 있어 전월 대비 물가 추세로 해석하지 않는다.','다음 달 근원·서비스 물가와 에너지 기여를 확인한다.')
add('95858958526d8be1a4eb','이탈리아 월간 조화물가 확정치 유지','8월 최종 HICP 전월비는 0.1%로 예상·종전과 같다. AI 해석 초안: 확정치에서 새 상방 충격은 확인되지 않지만 전년비 3.2%와 함께 봐야 한다.','잠정·확정 차이보다 다음 달 물가 구성을 확인한다.')
add('ef5a6080c19d76843cb4','미국 주택대출 신청 감소폭 확대','9월 11일 주간 MBA 신청은 -4.1%로 종전 -2.7%보다 감소폭이 커졌다. AI 해석 초안: 주간 금융신청 약세는 주택수요의 부담 신호지만 구매와 재융자 비중을 모르므로 주택거래 감소와 동일시하지 않는다.','구매·재융자 신청 분해와 모기지 금리 흐름을 확인한다.')
add('dce4a6492dfc3edaeb73','캐나다 주택착공 예상 하회','8월 주택착공은 원본 k 배율 229.046로 예상 240.0보다 낮고 수정 종전 229.36에서 소폭 줄었다. AI 해석 초안: 월간 수준은 대체로 유지됐지만 예상한 반등은 나타나지 않았다.','지역·다세대 구성과 6개월 평균 착공을 확인한다.')
add('4b86b31fc72f154236cd','미국 소매판매 강한 반등, 성장 전망 상향','8월 소매판매는 전월비 1.2%로 예상 0.8%를 웃돌고 수정 종전 -0.5%에서 반등했다. GS·JPM은 3분기 성장 전망을 높였고 Citi도 소비 회복을 확인했다. AI 판단: 온라인 행사 시점 효과와 저축률 하락이 있어 증가율을 그대로 연장하지 않는다.','실질 PCE와 가처분소득·저축률, 다음 달 온라인 판매를 확인한다.',[gsret,jpmret,citiret])
add('8384f31e5f8327a4b2ba','미국 자동차 제외 판매도 예상 크게 상회','8월 자동차 제외 소매판매는 전월비 1.4%로 예상 0.55%를 0.85%p 웃돌고 수정 종전 -0.2%에서 반등했다. AI 판단: 자동차만의 반등은 아니지만 명목판매에는 가격 효과가 포함된다. GDP 통제그룹과 지표 범위는 다르다.','휘발유·온라인 판매 영향을 제외한 실질 소비의 지속성을 확인한다.',[gsret,jpmret,citiret])
add('1256580b4b15b87987b9','미국 수입물가 예상 상회, 비연료 압력도 지속','8월 수입물가는 전월비 0.7%로 예상 0.5%를 웃돌고 수정 종전 -0.3%에서 상승 전환했다. GS·JPM은 비연료·전자제품을 포함한 가격 압력을 확인했다. AI 판단: 소비물가 전가 속도는 별도 확인이 필요하다.','전자제품·의류 가격과 근원 PCE의 후속 반영을 확인한다.',[gsimp,jpmimp])
add('15bfae8389f25fccbdb9','캐나다 건축허가 급감, 전월 급증 일부 반납','7월 건축허가는 전월비 -17.3%로 예상 -4.8%를 크게 밑돌고 수정 종전 18.3%에서 급락했다. AI 해석 초안: 대형 프로젝트로 변동이 큰 지표인 만큼 두 달 흐름과 주거·비주거 구분이 필요하다.','허가 금액·지역·용도별 구성과 실제 착공 전환을 확인한다.')
for eid in ['9929bd5a068495d067a3','1a26b1295325c42d6832']:
 add(eid,'FOMC 25bp 인상, 후속 경로의 견해 차이','9월 16일 회의의 원본 실제 정책금리 범위는 3.75~4.00%로 상·하단 모두 종전보다 25bp 높아 예상에 부합했다. JPM 사후 분석은 추가 인상 신호를 강조한다. Citi의 연내 동결 전망은 회의 전 자료이므로 사후 합의로 비교하지 않는다.','회의 후 각 IB 전망 수정과 다음 근원물가·고용을 확인한다.',[fedjpm,fedciti])
add('e9f87d3ca604b8ca5ac4','미국 전체 TIC 순유입 감소, 장기 흐름과 구분','7월 전체 TIC 순유입은 원본 b 배율 83.7로 수정 종전 135.5보다 작다. AI 해석 초안: 순유입은 유지됐지만 장기 TIC는 순유출로 전환해 만기·거래 유형별 구성이 중요하다. 원본 통화 표기는 없어 환산하지 않았다.','민간·공공 투자자 및 단기·장기 자금 구성을 확인한다.')
add('ee15b937b353a7195a53','미국 장기 TIC 순유출 전환','7월 장기 TIC는 원본 b 배율 -27.9로 수정 종전 174.4의 순유입에서 순유출로 전환했다. AI 해석 초안: 전체 TIC 83.7의 순유입과 방향이 달라 장기증권 흐름을 전체 해외자금 이탈로 확대 해석하면 안 된다.','채권·주식과 투자자별 장기자금 변동 및 다음 달 지속성을 확인한다.')

auth=ROOT/'ecocal_dashboard/authored_commentary.json';original=auth.read_bytes()
assert not (P/'authored_commentary.before.json').exists(),'Already applied; inspect before rerun'
(P/'authored_commentary.before.json').write_bytes(original)
bundle=json.loads(original); updated=[]
for e in data['events']:
 if not e['available_at_request'] or e['commentary']:continue
 head,summary,watch,hs=spec[e['id']]
 r=dict(event_id=e['id'],review_id='comment-'+hashlib.sha256((e['id']+now).encode()).hexdigest()[:24],headline=head,summary=summary,watch=watch,houses=hs,match={k:e[k] for k in b.FIELDS[:5]},snapshot={k:e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS},reviewed_on='2026-09-17',reviewed_at=now,review_status='draft',origin='assistant_review_of_local_reports',workbook_sha256=inp['sha256'],review_log='2026-09-17 사용자 정정 후 재개. 최신 원본 수치 대조 및 5개 하우스 지표별 후보 검색. 채택한 원문의 전체 페이지를 읽고 날짜·지역·기간을 검토했다. 근거 없는 하우스는 미확보이며 수치 해석은 AI 초안이다. 수집 실패 하우스 때문에 확보 자료의 게시를 중단하지 않는다.')
 bundle['event_reviews'].append(r);updated.append(e['id'])
assert len(updated)==26
bundle['reviewed_on']='2026-09-17';auth.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
try:
 chosen,stale=b.load_authored_comments(c,b.load_calendar(pathlib.Path(inp['path'])),'2026-09-17');assert len(chosen)==63 and not stale
except Exception:
 auth.write_bytes(original);raise
(P/'review_result.json').write_text(json.dumps(dict(updated_events=updated,updated_count=len(updated),retained_count=37,valid_count=len(chosen),adopted_pages=[dict(doc_id=d,page=p) for d,p in sorted(pages)],reviewed_on='2026-09-17'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Validated',len(chosen),'summaries;',len(updated),'new/revised')
