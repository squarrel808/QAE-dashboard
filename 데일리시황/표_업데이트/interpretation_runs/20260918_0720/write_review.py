import copy, hashlib, json, pathlib, re, sqlite3, sys
from datetime import datetime
P=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
sys.path.insert(0,str(R/'ecocal_dashboard'))
import build_dashboard as b
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
data=read(P/'validated_WECO/dashboard_data.json'); inp=read(P/'input.json')
c=sqlite3.connect((R/'data/research.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
now=datetime.now().astimezone().isoformat(timespec='seconds'); pages=set()
def h(pre,start,end,summary,comment,kind='reaction',limitation='',pg=1):
 d=c.execute('select * from documents where doc_id like ?',(pre+'%',)).fetchone()
 t=c.execute('select text from pages where doc_id=? and page=?',(d['doc_id'],pg)).fetchone()[0]
 a=re.search(r'\s+'.join(map(re.escape,start.split())),t);assert a,start
 z=re.search(r'\s+'.join(map(re.escape,end.split())),t[a.start():]);assert z,end
 pages.add((d['doc_id'],pg))
 return dict(house=d['house'],kind=kind,summary=summary,comment=comment,limitation=limitation,evidence=[dict(doc_id=d['doc_id'],page=pg,quote=t[a.start():a.start()+z.end()])],reviewed_pages=[dict(doc_id=d['doc_id'],page=pg)])
gsfed=h('746aca','The FOMC raised','third 25bp cut in March 2028.','GS는 25bp 인상 뒤 추가 인상 점도표와 중립금리 상향을 예상보다 매파적으로 평가하고, 10월 25bp 추가 인상을 기본 전망에 넣었다.','AI 비교: Citi는 회의 후에도 10월·12월 동결을 예상한다. 추가 인상 필요성뿐 아니라 시점에서도 JPM의 기존 12월 전망과 차이가 있다.',limitation='표지 발행은 9월 16일 20:37 EDT, 수집 메타데이터는 9월 17일이다. 표지 시각상 같은 FOMC의 사후 분석이며 다운로드일을 발행일로 사용하지 않았다.')
citifed=h('275372','Details of the FOMC meeting,','resuming rate cuts in June 2027.','Citi는 만장일치 인상·추가 인상 점도표를 대체로 예상했지만 일부 매파적 신호를 확인했다. 향후 물가 둔화와 PCE 수정으로 10월·12월 동결, 2027년 6월 인하 재개를 예상한다.','AI 비교: 기존 회의 전 전망과 달리 이번에는 사후 원문을 확인했다. GS의 10월 추가 인상 및 JPM의 12월 추가 인상 전망과 비교할 수 있다.',limitation='표지 발행은 9월 16일 16:22:54 ET, 메타데이터는 9월 17일이다. 같은 회의 사후 자료로 확인했으며 정확한 원문 시각을 보존한다.')
tic=h('ed407','July saw net purchases','Official investors drove net purchases of long-term US Treasuries.','GS는 7월 외국인의 미국 주식·국채·기관채 매수와 회사채 매도를 구분했다. 주식은 민간, 장기 국채는 공공 투자자가 순매수를 주도했다고 설명했다.','AI 비교: GS의 외국인 미국증권 보유·가치조정 흐름은 원본 전체/장기 TIC 순흐름과 범위가 다르다. 원본 장기 -27.9를 외국인의 모든 미국증권 순매도로 일반화하지 않는다.',kind='related',limitation='동일 7월의 자산·투자자별 가치조정 분석이다. WECO 장기 TIC -27.9 및 전체 TIC 83.7의 동일 정의 수치를 직접 검증한 자료는 아니다. 표지는 9월 16일 17:20 EDT, 메타데이터는 9월 17일.')
jppmi=h('fa77ff36','Japan’s August PMI suggests','future output index, which rose 1.5pts to 56.4—', 'JPM은 8월 속보 PMI에서 제조업·서비스의 동반 개선과 내수 회복을 확인했다. AI 관련 수요가 제조업을 지지했다고 평가했다.','AI 비교: 최종치의 소폭 상향은 속보 단계의 확장 신호와 일관되지만, 최종 구성에 대한 새 JPM 반응으로 보지는 않는다.',kind='related',limitation='8월 21일 속보치(종합 53.4·서비스 52.3) 분석이다. 9월 3일 최종치 53.5·52.5에 대한 사후 평가는 아니다.')
eupmi=h('e8ca17f2','The July-August surveys suggest','over-predicted growth in recent quarters.','JPM은 7~8월 PMI가 이탈리아·독일의 완만한 성장과 프랑스의 상대적 부진을 시사한다고 봤다. 프랑스는 정치 불확실성과 PMI의 최근 성장 과대예측에 유의했다.','AI 비교: 같은 유로존에서도 국가별 신호가 다르다. 설문이 시사하는 GDP 속도는 실제 성장률 발표값이 아니다.')
ukpmi=h('7d954de2','The flash PMI for August','held back by elevated cost pressures and external geopolitical uncertainty.','JPM은 8월 속보 종합 PMI 개선이 서비스 주도로 이어지며 완만한 성장 상방 위험을 보인다고 평가했다.','AI 비교: 최종 서비스 PMI는 속보보다 낮아졌다. 속보 단계의 성장 판단을 최종 발표에 대한 새 코멘트로 오인하지 않는다.',kind='related',limitation='8월 21일 속보 종합 52.5·서비스 52.8 분석으로, 9월 3일 최종 서비스 52.5의 직접 반응은 미확보다.')
usservices=h('cdefbe36','Although their manufacturing counterparts','otherwise strong signal for activity.','JPM은 ISM 55.4와 S&P 서비스 PMI 56.5가 모두 견조한 성장을 시사하지만 ISM 가격지수 상승은 부담이라고 봤다.','AI 비교: S&P 서비스 최종치의 속보 대비 하향과 전월 대비 개선은 동시에 가능하다. 두 설문의 고용·물가 신호도 동일하지 않다.')
orders=h('07bc375d','BOTTOM LINE:','we expect Monday’s industrial production data to show -0.4% growth in July.','GS는 7월 수주 증가가 대형 운송장비 주문에 집중됐고 대형 주문 제외 수주는 전월비 1.4% 감소했다고 지적했다.','AI 비교: 예상 상회 자체보다 주문의 폭과 실제 생산 연결을 봐야 한다. 원문의 생산 -0.4%는 당시 전망이며 이후 실제값 -1.1%와 구분한다.')
ca=h('b4ef0e13','BOTTOM LINE:','BoC will remain on hold at 2.25% in 2026.','GS는 서비스·정규직 중심의 고용 감소와 임금 둔화를 확인하고 연내 캐나다 정책금리 동결 전망을 지지한다고 평가했다.','AI 비교: 고용 감소에도 실업률이 그대로인 것은 노동공급 변화와 함께 봐야 한다. BofA도 고용 약화와 동결 전망을 연결했다.')
bofaca=h('9c98b0da','Job market relapses in August','employment rate fell 0.1pp, to 60.8% (Exhibit 3).','BofA는 8월 고용 감소가 3개월 증가 흐름을 끊었고 정규직·민간·공공 부문에 걸쳐 나타났다고 지적했다.','AI 비교: GS와 고용 약화 판단이 같다. BofA 자체 예상 +2천 명과 원본 시장 예상 +1.5만 명은 다른 비교 기준이다.')
pay=h('5d7f1701','Job creation came in strong','today’s report will support the hawks.','JPM은 비농업 고용 증가와 과거 상향 수정, 근로시간 증가를 긍정적으로 평가했다. 노동참가율 회복과 완만한 임금 상승이 함께 나타났다고 봤다.','AI 비교: 실업률 반올림 수치 4.1% 유지와 세부 수치 4.09%→4.14% 상승은 모순이 아니다. 한 달 고용 강세를 지속적인 과열로 단정하지 않는다.')
manpay=h('5d7f1701','Elsewhere, factory jobs were up','highest since last May.','JPM은 제조업 고용이 1.6만 명 늘어 3개월 연속 증가했고 지난해 5월 이후 최고 수준이라고 확인했다.','AI 비교: 원본 예상 +5천 명을 웃돌았지만 제조업 한 업종의 반등을 노동시장 전체로 확장하지 않는다.')
ip=h('7192a2cc','BOTTOM LINE:','especially if autos production rebounds.','GS는 자동차 생산 급감이 독일 산업생산 약세를 주도했다고 봤다. 3분기 초 제조업은 부진하지만 향후 주문·설문과 자동차 반등 가능성을 함께 평가했다.','AI 비교: 대형 수주 증가와 현재 생산 부진은 공존한다. 일시적 공장 가동 중단 여부와 다음 달 회복을 확인한다.')
wage=h('d82d1a54','BOTTOM LINE:','positive yoy growth since the beginning of the year.','GS는 명목임금 4.7% 상승에 상여금이 크게 기여했고 실질임금도 플러스를 유지했다고 설명했다. 다만 동일표본 상용직 기본급 증가율은 2.7%로 둔화했다.','AI 비교: 전체 현금급여와 동일표본 기본급의 방향이 다르다. 임금 총액 가속을 기조 임금의 일률적 가속으로 읽지 않는다.')
gdp=h('3321901f','BOTTOM LINE:','were limited.','GS는 일본 2분기 연율 성장률 상향이 주로 설비투자 수정 때문이지만 설비투자는 여전히 2분기 연속 감소했다고 평가했다.','AI 비교: 같은 분기 잠정치에서 상향된 것이며 전분기 성장률과의 비교가 아니다. 원문 시장예상 1.7%와 원본 1.75%는 구분한다.')
claims=h('454b3536','5. Initial jobless claims','in line with expectations.','GS는 8월 29일 신규 청구가 20.6만 건으로 2천 건 늘고 4주 평균은 20.7만 건이라고 확인했다.','AI 비교: 작은 주간 증가만으로 해고 확대 추세를 선언하기 어렵다. 오늘 확보된 9월 청구 보고서는 대상 주가 달라 이 수치를 대체하지 않는다.',pg=2)
cont=h('454b3536','Nationwide continuing claims—','in line with expectations.','GS는 8월 22일 계속 청구가 수정 종전보다 8천 건 늘어난 177.9만 건이라고 확인했다.','AI 비교: 원본 예상 1783.5천 건과 보고서의 반올림 기대 수준을 구분한다. 신규 청구와 대상 주도 다르다.',pg=2)
trade=h('454b3536','3. The trade deficit widened','services surplus increased slightly by $0.2bn.','GS는 컴퓨터·반도체 수입 증가와 원유·금 수출 감소로 7월 무역적자가 확대됐으며 서비스 흑자는 소폭 늘었다고 설명했다.','AI 비교: 예상보다 작은 적자와 전월보다 큰 적자는 동시에 성립한다. 자본재 수입 증가는 내수 투자와 순수출에 상반된 영향을 준다.',pg=2)

spec={}
def add(eid,head,summary,watch,hs=()): spec[eid]=(head,summary,watch,list(hs))
add('d22b54ccd0be4f932b42','러시아 주간 물가 소폭 하락','8월 31일 주간 CPI는 -0.01%로 종전 +0.01%에서 하락 전환했다. AI 해석 초안: 변동 폭이 작고 주간 계절성이 있어 지속적인 물가 안정의 증거로는 부족하다.','월간·근원 CPI와 식품 가격 흐름을 확인한다.')
add('3099770bd39945f8929a','러시아 실질 소매판매 둔화','7월 실질 소매판매는 전년비 5.3%로 예상 5.2%를 소폭 웃돌았지만 종전 7.3%보다 둔화했다. AI 해석 초안: 소비는 증가하되 속도는 느려졌으며 명목 판매와 혼동하지 않는다.','임금·소비신용과 다음 달 실질판매를 확인한다.')
add('5ac5e1ec6f0a02c9f712','러시아 실업률 소폭 상승','7월 실업률은 2.3%로 예상·종전 2.2%보다 0.1%p 높다. AI 해석 초안: 낮은 수준에서의 소폭 상승만으로 노동력 부족 해소를 판단하기 어렵다.','노동참가율·구인·임금 흐름을 확인한다.')
add('1627fbcbc540244fac20','일본 해외채권 순매도 축소','8월 28일 주간 해외채권 매입은 원본 b 배율 -824.0으로 수정 종전 -1976.8보다 순매도 폭이 작다. AI 해석 초안: 순매도 지속과 매도 둔화를 구별하며 원본 미표기 통화는 보완하지 않았다.','여러 주 누적 흐름과 환헤지 비용을 확인한다.')
add('057c1a13f70dbbdea485','일본 종합 PMI 최종치 소폭 상향','8월 최종 종합 PMI는 53.5로 속보 53.4에서 소폭 상향됐다. JPM의 속보 분석은 제조업·서비스의 확장 신호를 확인했다. AI 판단: 속보 대비 수정은 전월 대비 변화가 아니다.','서비스 신규 주문과 제조업 수출 수요를 확인한다.',[jppmi])
add('bab038bd35599a75b9c5','일본 서비스 PMI 확장 유지','8월 최종 서비스 PMI는 52.5로 속보 52.3보다 높다. JPM의 속보 분석은 내수 회복과 비용 부담의 공존을 지적했다. AI 판단: 최종 지수는 확장 영역이나 세부 구성의 재검증은 필요하다.','국내·해외 신규 주문과 서비스 가격을 확인한다.',[jppmi])
add('1dfd1f67d6da741f7333','러시아 종합 PMI 50 상회','8월 종합 PMI는 50.6으로 종전 49.6에서 확장 영역에 진입했다. AI 해석 초안: 50 근처의 작은 개선이며 생산 증가율이나 GDP 성장률을 직접 뜻하지 않는다.','제조업·서비스별 주문과 고용의 지속성을 확인한다.')
add('21e7f5cf9ce3301639fb','러시아 서비스 PMI 개선','8월 서비스 PMI는 51.3으로 종전 49.0보다 높아 확장 영역으로 돌아왔다. AI 해석 초안: 종합지수 개선과 일관되지만 한 달의 설문 반등이다.','신규 사업·고용과 가격 부담을 확인한다.')
for eid,head,summary in [
 ('29e60538ceb0ad6361b9','이탈리아 종합 PMI 예상 상회','8월 종합 PMI는 53.6으로 예상 53.1과 종전 52.5를 웃돌았다. JPM도 이탈리아의 완만한 성장 신호를 확인했다.'),
 ('ae8eb22ba987cb1cfab7','프랑스 종합 PMI 위축 신호','8월 최종 종합 PMI는 48.5로 예상·속보 48.8보다 낮다. JPM은 프랑스를 역내 상대적 약점으로 보고 정치 불확실성을 지적했다.'),
 ('c39855fd5d5778b97849','독일 종합 PMI 상향 수정','8월 최종 종합 PMI는 51.8로 예상·속보 51.0보다 높다. JPM은 독일 설문이 완만한 성장과 일관된다고 봤다.')]:add(eid,head,summary+' AI 판단: 설문상의 확장·위축과 실제 GDP를 구별한다.','다음 달 주문·고용 및 실제 생산을 확인한다.',[eupmi])
add('a825db1a2d531bef0b18','이탈리아 서비스 확장 강화','8월 서비스 PMI는 55.2로 예상 53.35와 종전 52.5를 웃돌았다. AI 해석 초안: 서비스 확장 신호가 강해졌지만 개별 국가·서비스 최종치에 대한 직접 IB 근거는 이번 검토에서 채택하지 않았다.','서비스 신규 주문과 고용의 후속 개선을 확인한다.')
add('233755991b4fc4e86506','프랑스 서비스 최종치 하향','8월 최종 서비스 PMI는 48.0으로 예상·속보 48.4보다 낮다. AI 해석 초안: 위축 신호가 강화됐으며 속보 대비 하향을 월간 감소폭으로 해석하지 않는다.','신규 주문과 정치 불확실성의 기업 활동 영향을 확인한다.')
add('543f6ed12cdd89644704','독일 서비스 PMI 개선해도 50 미달','8월 최종 서비스 PMI는 49.7로 예상·속보 48.5보다 높지만 50에는 못 미친다. AI 해석 초안: 종합지수의 확장을 서비스업 전반의 확장으로 동일시하지 않는다.','서비스 신규 주문이 확장 영역에 진입하는지 확인한다.')
add('5162d3e533b027e8f4b2','영국 종합 PMI 속보 수준 유지','8월 최종 종합 PMI 52.5는 예상·속보와 같다. JPM의 속보 분석은 서비스 중심의 성장 개선을 확인했다. AI 판단: 확정 발표의 추가 놀라움은 제한적이다.','활동 개선과 서비스 가격 압력의 동행을 확인한다.',[ukpmi])
add('3d708b5a62d42799dedb','영국 서비스 PMI 소폭 하향 확정','8월 최종 서비스 PMI 52.5는 예상·속보 52.8보다 낮지만 확장 영역이다. AI 판단: JPM 속보 분석의 성장 개선과 최종치 하향을 함께 봐야 한다.','다음 달 신규 사업·고용·가격 신호를 확인한다.',[ukpmi])
add('e3dcc2f3dfae1853488b','미국 계속 청구 소폭 증가','8월 22일 계속 청구는 1779천 건으로 예상 1783.5천 건보다 작지만 수정 종전 1771천 건보다는 늘었다. AI 판단: 낮은 신규 청구와 재취업 속도는 별도로 봐야 한다.','계속 청구 4주 추세와 실업 기간을 확인한다.',[cont])
add('a14b978e7362e3222eb8','미국 신규 청구 낮은 수준 유지','8월 29일 신규 청구는 206천 건으로 예상 205천 건, 수정 종전 204천 건보다 조금 많다. GS는 4주 평균 207천 건을 확인했다. AI 판단: 작은 증가만으로 해고 추세 전환을 판단하지 않는다.','다음 주 청구와 주별 변동 집중 여부를 확인한다.',[claims])
add('fcafd169f15606a3ee5c','미국 무역적자 확대, 예상보다는 작아','7월 무역수지는 원본 b 배율 -88.6으로 예상 -90.2보다 양호하지만 수정 종전 -71.2보다 악화했다. GS는 기술제품 수입 증가와 원유·금 수출 감소를 확인했다.','수입 자본재의 투자 연결과 실질 순수출 기여를 확인한다.',[trade])
add('62e9538d97f60cd1d7b2','러시아 금·외환보유액 증가','8월 28일 보유액은 원본 b 배율 774.2로 종전 761.2보다 많다. AI 해석 초안: 거래 흐름뿐 아니라 금·환율 평가효과가 반영될 수 있어 증가분을 자금 유입으로 단정하지 않는다.','금 평가효과와 외환자산 거래 변화를 분리해 확인한다.')
add('e4aa7df123ba37868743','미국 종합 PMI 확장 유지','8월 최종 종합 PMI는 56.0으로 속보와 같고 예상 56.05와 거의 일치한다. AI 해석 초안: 확장 신호는 견조하되 서비스 또는 ISM 단일 설문을 종합 PMI 직접 코멘트로 대신 쓰지 않았다.','제조업·서비스 주문과 실질 지출의 동행을 확인한다.')
add('44d61c8ca47f52c0d74d','미국 서비스 PMI 강세, 속보보다 하향','8월 최종 S&P 서비스 PMI 56.5는 예상·속보 56.8보다 낮지만 JPM이 확인한 7월 54.6보다는 높다. AI 판단: 속보 하향과 월간 개선을 구분한다.','고용과 판매가격의 구성 변화를 확인한다.',[usservices])
add('afe3742ff98df9c0c352','미국 ISM 서비스 강세와 가격 부담','8월 ISM 서비스는 55.4로 예상 54.05와 종전 54.1을 웃돌았다. JPM은 신규 주문 강세와 가격 압력 지속을 함께 지적했다. AI 판단: 활동 강세가 고용 전반 강세를 보장하지 않는다.','ISM 고용·지불가격과 S&P 설문의 차이를 확인한다.',[usservices])
add('c7eb749805ed8778de96','독일 수주 예상 상회, 대형 주문 편중','7월 공장수주는 전월비 2.5%로 예상 0.3%를 웃돌았다. 종전은 3.1%에서 3.7%로 상향됐다. GS는 대형 주문 제외 시 감소했다고 지적했다.','대형 주문 제외 추세와 생산 전환을 확인한다.',[orders])
add('d8c375c9b01c75696236','이탈리아 소매판매 월간 감소','7월 소매판매는 전월비 -0.4%로 수정 종전 -0.2%보다 감소폭이 커졌다. AI 해석 초안: 단월 소비 약화 신호이나 품목 구성과 가격 효과가 미확인이다.','판매 물량과 필수·재량 소비 구성을 확인한다.')
add('b80e29030d5954b0b424','이탈리아 소매판매 연간 증가 둔화','7월 소매판매는 전년비 0.8%로 종전 3.1%보다 둔화했다. AI 해석 초안: 월간 감소와 함께 약한 판매 흐름을 보이지만 명목·실질을 혼용하지 않는다.','물량 기준 판매와 소비심리를 확인한다.')
add('adb7cb1e9764f2520fea','영국 건설 PMI 위축 심화','8월 건설 PMI는 44.3으로 예상 46.0과 종전 44.7보다 낮다. AI 해석 초안: 건설 위축을 보여주지만 서비스 중심 종합 PMI 확장과는 업종 범위가 다르다.','주택·상업·토목 공사와 신규 주문을 확인한다.')
add('7b60251c4a848e27f282','캐나다 고용 감소, 서비스 약세','8월 고용은 41.7천 명 감소해 예상 15천 명 증가를 크게 밑돌았다. GS·BofA는 서비스·정규직 중심 약화를 확인했다. AI 판단: 종전 75.1천 명 증가 뒤 변동성과 추세를 함께 본다.','3개월 평균 고용·근로시간·임금을 확인한다.',[ca,bofaca])
add('c4af46e213a193c2e05a','캐나다 실업률 유지, 고용은 약화','8월 실업률은 6.4%로 예상·종전과 같다. GS는 고용 감소와 임금 둔화를 함께 확인했다. AI 판단: 실업률 유지가 고용 수요의 안정을 뜻하지는 않는다.','참가율과 연령별 실업·고용률을 확인한다.',[ca])
add('3aef7537c1b34d166b51','미국 제조업 고용 예상 상회','8월 제조업 고용은 16천 명 늘어 예상 5천 명을 웃돌았다. 종전은 5천 명에서 14천 명으로 상향됐다. JPM은 제조업 고용 3개월 연속 증가를 확인했다.','생산·신규 주문과 고용 증가의 동행을 확인한다.',[manpay])
add('795502e15628e7291cfb','미국 비농업 고용 반등과 상향 수정','8월 고용은 162천 명 증가해 예상 55천 명을 크게 웃돌았다. 종전은 -23천 명에서 +21천 명으로 수정됐다. JPM은 근로시간·노동공급 개선도 긍정적으로 봤다.','교육·음식업 집중 효과와 3개월 추세를 확인한다.',[pay])
add('ebda2b89709dd52de82b','미국 실업률 반올림 기준 유지','8월 실업률은 4.1%로 예상·종전과 같다. JPM은 반올림 전 수치가 4.09%에서 4.14%로 소폭 높아졌고 참가율도 올랐다고 설명했다. AI 판단: 안정된 헤드라인 안의 공급 변화를 확인해야 한다.','참가율·실직자와 구직 기간을 확인한다.',[pay])
add('9959261ffb1fc6e0c0b3','일본 선행지수 상승, 예상 소폭 하회','7월 잠정 선행지수는 117.9로 예상 118.0보다 낮지만 수정 종전 116.2보다 높다. AI 해석 초안: 경기 방향의 개선 신호이며 지수 상승폭을 성장률로 해석하지 않는다.','동행지수와 다음 확정치·구성항목을 확인한다.')
add('b21be94dc32f1aa11a24','독일 생산 감소, 자동차 부진','7월 산업생산은 전월비 -1.1%로 예상 +0.2%를 하회했다. 종전은 +0.2%에서 0.0%로 수정됐다. GS는 자동차를 중심으로 제조업 모멘텀이 약하다고 평가했다.','자동차 가동 정상화와 에너지 다소비 업종을 확인한다.',[ip])
iprel=copy.deepcopy(ip);iprel.update(kind='related',limitation='같은 7월 산업생산의 전월비·업종 구성 분석이며 WDA 전년비 -1.6%의 직접 평가는 아니다.')
add('52c7e0a2b873ebb5907f','독일 산업생산 연간 감소폭 확대','7월 근무일수 조정 산업생산은 전년비 -1.6%로 예상 0.0%를 밑돌고 수정 종전 -0.5%보다 약하다. AI 판단: 월간 부진과 방향은 같지만 조정 방식·기저가 다르다.','자동차와 에너지 다소비 업종의 연간 기저를 확인한다.',[iprel])
add('97a36234c2ca8ba3251e','일본 현금급여 강세, 상여금 영향','7월 현금급여는 전년비 4.7%로 예상 3.8%, 수정 종전 4.0%를 웃돌았다. GS는 상여금 기여와 동일표본 기본급 둔화를 구분했다.','동일표본 기본급·실질임금·가계소비를 확인한다.',[wage])
add('d71734446c8a3139781d','일본 경상흑자 예상 상회','7월 경상수지는 원본 b 배율 2988.9로 예상 2849.45보다 크고 종전 -92.3에서 흑자 전환했다. AI 해석 초안: 무역수지와 소득수지·계절성이 달라 수출 회복만으로 설명할 수 없다.','본원소득·서비스·계절조정 경상수지를 확인한다.')
add('cd5c2f731ac95db0b2b1','일본 2분기 GDP 상향, 기대에는 미달','2분기 GDP는 전분기비 연율 1.4%로 속보 1.1%보다 높지만 원본 예상 1.75%보다 낮다. GS는 설비투자 수정이 상향을 주도했으나 투자 자체는 여전히 감소했다고 봤다.','재고 기여와 최종수요·설비투자 회복을 확인한다.',[gdp])
add('0648b968169e094adb52','일본 GDP 디플레이터 수정 없음','2분기 GDP 디플레이터는 전년비 2.6%로 예상·종전과 같다. AI 해석 초안: 국내 생산 전반의 가격지표이며 소비자물가와 범위가 달라 CPI 해석을 대신하지 않는다.','내수·수출입 가격과 다음 분기 디플레이터를 확인한다.')
gdprel=copy.deepcopy(gdp);gdprel.update(kind='related',limitation='같은 2분기의 연율 성장률·설비투자 수정 분석이다. 원본 비연율 전분기비 0.4%와 연율 1.4%를 구분하며 반올림 수치를 기계적으로 연율화하지 않는다.')
add('b4db72bcdb4f16678d0d','일본 비연율 GDP 예상 부합','2분기 GDP는 비연율 전분기비 0.4%로 예상에 부합하고 속보 0.3%에서 상향됐다. AI 판단: 연율 1.4%와 표현 단위가 다르며 같은 분기의 수정 발표다.','소비·투자·재고의 성장 기여를 확인한다.',[gdprel])
add('e12470142c03d9e5acca','일본 국제수지 기준 무역적자 확대','7월 국제수지 기준 무역수지는 원본 b 배율 -399.9로 예상 -385.5와 종전 -135.2보다 약하다. AI 해석 초안: 경상흑자와 무역적자는 소득수지 차이로 공존할 수 있다.','통관 기준과 국제수지 기준 차이·소득수지를 확인한다.')
add('4e9ab03977ecc151e19b','미국 소기업 낙관지수 하락','8월 NFIB 지수는 98.7로 예상 99.3과 종전 99.8보다 낮다. AI 해석 초안: 소기업 심리 약화이며 대기업·전체 경기 둔화와 동일시하지 않는다.','매출 기대·채용계획·가격 인상계획의 기여를 확인한다.')
for eid in ['1a26b1295325c42d6832','9929bd5a068495d067a3']:
 old=next(e['commentary'] for e in data['events'] if e['id']==eid)
 jpm=[{k:v for k,v in x.items()} for x in old['houses'] if x['house']=='JPM']
 # Existing validated JPM source remains; new GS/Citi reactions supersede the prior Citi preview.
 add(eid,'FOMC 사후 전망 분화: GS 10월 인상·Citi 동결','정책금리 범위는 3.75~4.00%로 25bp 인상돼 원본 예상에 부합했다. 사후 원문에서 GS는 10월 추가 인상을 새로 예상하고 Citi는 10월·12월 동결을 유지한다. JPM의 기존 사후 전망은 12월 추가 인상이다. AI 판단: 추가 인상의 필요성과 시점 모두 이견이 있다.','근원 PCE 방법론 수정과 새 물가·고용이 각 하우스 전제를 바꾸는지 확인한다.',[gsfed,citifed]+jpm)
add('ee15b937b353a7195a53','장기 TIC 순유출과 외국인 자산 매수 구분','7월 장기 TIC는 원본 b 배율 -27.9로 수정 종전 174.4에서 순유출로 바뀌었다. GS는 별도 가치조정·외국인 보유 분석에서 주식·국채 매수를 확인했다. AI 판단: 포괄 범위가 달라 두 수치를 모순이나 전면 자금 이탈로 단정하지 않는다.','거주자·비거주자, 외국증권 거래와 가치조정 여부를 대조한다.',[tic])
add('e9f87d3ca604b8ca5ac4','전체 TIC 유입 유지, 자산별 흐름 분화','7월 전체 TIC는 원본 b 배율 83.7로 수정 종전 135.5보다 작지만 순유입이다. GS는 외국인의 주식·국채 매수와 회사채 매도를 구분했다. AI 판단: 해당 세부 분석으로 전체 TIC 순유입 감소 원인을 완전히 설명할 수는 없다.','단기·장기 자금과 투자자·자산별 순흐름을 확인한다.',[tic])

auth=R/'ecocal_dashboard/authored_commentary.json';original=auth.read_bytes()
assert not (P/'authored_commentary.before.json').exists(),'Duplicate run'
baseline=read(P/'baseline.json');assert hashlib.sha256(original).hexdigest()==baseline['hashes'][str(auth)]
bundle=json.loads(original);updated=[]
for e in data['events']:
 if e['id'] not in spec:continue
 assert e['available_at_request']
 head,summary,watch,hs=spec[e['id']]
 review=dict(event_id=e['id'],review_id='comment-'+hashlib.sha256((e['id']+now).encode()).hexdigest()[:24],headline=head,summary=summary,watch=watch,houses=hs,match={k:e[k] for k in b.FIELDS[:5]},snapshot={k:e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS},reviewed_on='2026-09-18',reviewed_at=now,review_status='draft',origin='assistant_review_of_local_reports',workbook_sha256=inp['sha256'],review_log='5개 하우스 지표·지역·기간 후보 재검색. 채택 근거의 전체 페이지를 읽고 발행일·단위·기간 대조. 과거 누적 지표는 보존된 수치 스냅샷 기준이며 9월 18일 신규 발표가 아님. 직접 근거 미채택 하우스는 미확보; 수치 기반 설명은 AI 초안. 원문 전체 검토 완료를 뜻하지 않음.')
 bundle['event_reviews'].append(review);updated.append(e['id'])
assert len(updated)==46 and all(e.get('commentary') or e['id'] in updated for e in data['events'] if e['available_at_request'])
(P/'authored_commentary.before.json').write_bytes(original)
bundle['reviewed_on']='2026-09-18';auth.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
try:
 selected,stale=b.load_authored_comments(c,data['events'],'2026-09-18');assert len(selected)==194 and not stale
except Exception:
 auth.write_bytes(original);raise
(P/'review_result.json').write_text(json.dumps(dict(updated_events=updated,updated_count=len(updated),new_summaries=42,revised_summaries=4,retained_summaries=148,adopted_pages=[dict(doc_id=d,page=p) for d,p in sorted(pages)],reviewed_on='2026-09-18'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Validated',len(selected),'summaries;',len(updated),'new/revised')
