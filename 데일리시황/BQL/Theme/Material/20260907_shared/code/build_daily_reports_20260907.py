from pathlib import Path
import json, html, math
from collections import Counter
import xlsxwriter

BASE=Path(__file__).resolve().parent
OUT=BASE.parent if BASE.name=='code' else BASE/'daily_20260907'
D=json.loads((OUT/'data.json').read_text(encoding='utf-8'))
assert D['report_date']=='2026-09-07' and D['ai']['meta']['asOf']=='2026-09-04', 'Snapshot script: do not reuse dated narrative for a different dataset.'
D['cutoff_note']='신규 파일의 9월 5~7일 가격이 반복되어 9월 4일 마지막 유효 관측일 사용.'
(OUT/'data.json').write_text(json.dumps(D,ensure_ascii=False,allow_nan=False),encoding='utf-8')
SOURCES={
 'us':('AP · 9월 4일 미국 증시 종가','https://apnews.com/article/stock-market-dow-nasdaq-jobs-ebc11cfa2cf8baf4491bf3d4199c1d74'),
 'eu':('Reuters · 9월 4일 유럽 종가','https://in.marketscreener.com/news/european-shares-log-weekly-losses-on-inflation-worries-volkswagen-jumps-ce785bdbd98cf522'),
 'cn':('Reuters · 9월 4일 중국 종가','https://economia.uol.com.br/noticias/reuters/2026/09/04/acoes-da-china-encerram-semana-em-baixa-com-perda-de-forca-da-alta-por-ia.htm'),
 'cnsector':('신화재경 · 9월 4일 업종 동향','https://www.cnfin.com/yw-lb/detail/20260904/4465240_1.html'),
 'lulu':('lululemon · 9월 3일 FY2026 Q2 실적 발표','https://corporate.lululemon.com/newsroom/press-releases/2026/09-03-2026-210528733'),
 'fico':('Investing.com · 9월 4일 FICO / VantageScore','https://www.investing.com/news/stock-market-news/why-is-fair-isaac-stock-sliding-today-93CH-4889420'),
 'adobe':('Adobe · 9월 4일 CEO 승계 공지(일본어판)','https://news.adobe.com/ja/news/2026/09/20260904-adobe-ceo-announcement'),
 'soitec':('Soitec · 9월 2일 Trading Update / 회사 배포문','https://rss.globenewswire.com/news-release/2026/09/02/3355388/0/en/soitec-trading-update.html'),
 'cssc':('증권일보 · 9월 2일 중국선박 수주 공시 보도','https://finance.eastmoney.com/a/202609023863027532.html'),
}
SEC={'Communication Services':'커뮤니케이션','Consumer Discretionary':'경기소비재','Consumer Staples':'필수소비재','Energy':'에너지','Financials':'금융','Health Care':'헬스케어','Industrials':'산업재','Information Technology':'IT','Materials':'소재','Real Estate':'부동산','Utilities':'유틸리티'}
NAMES={'SPX':'미국 · S&P 500','SHSZ300':'중국 · CSI 300','SXXP':'유럽 · STOXX Europe 600'}
def pct(x):return '—' if x is None else f'{x:+.2%}'
def ratio(x):return '—' if x is None else f'{x:.1%}'
def num(x):return '—' if x is None else f'{x:,.2f}'
def p(text,*refs):return {'type':'p','text':text,'refs':list(refs)}
def h(text):return {'type':'h','text':text}
def table(title,heads,rows,appendix=False):return {'type':'table','title':title,'heads':heads,'rows':rows,'appendix':appendix}

MARKET_TEXT={
'SPX':[
 p('미국은 지수 하락 속 AI 하드웨어의 선택적 반등이었다. 공식 S&P 500은 9월 4일 약 0.4% 하락했다. 같은 날 발표된 미국 고용 증가 16.2만 명과 채권금리 상승은 시장의 부담으로 보도됐다. 이 배경과 별개로 제공 데이터에서 S&P 500의 상승 종목은 175개, 하락은 327개였다. 지수 전반으로 위험선호가 확산된 날로 보기는 어렵다.','us'),
 p('상승 상위 100개 가운데 IT 32개, 산업재 31개로 둘을 합하면 63개다. Sandisk +11.90%, KLA +7.32%, Marvell +7.05%, Coherent +6.60%, Seagate +6.34%, Micron +6.10%가 상위권에 함께 나타났다. 메모리·저장장치·반도체 장비·광통신을 가로지르는 동반 강세라는 점은 확인된다. 다만 이를 당일 신규 수주나 실적 상향이 일제히 발생한 결과라고 해석할 근거는 이번 검색에서 확보하지 못했다.'),
 p('반대편에서는 소프트웨어와 데이터 서비스가 압박받았다. FICO -16.68%, Autodesk -8.26%, Adobe -6.73%, PTC -6.04%, Synopsys -5.40%, Workday -5.38%다. 특히 FICO는 VantageScore 이용 확대 지시가 경쟁 부담으로 보도된 별도 촉매가 있었다. 기술주 하락을 모두 같은 AI 대체 논리로 설명하면 이 규제·경쟁 이슈를 놓친다.','fico'),
 p('Adobe는 12월 1일 Anil Chakravarthy가 CEO를 맡는 승계 계획을 발표했다. 발표 사실은 확인되지만, -6.73% 하락 중 승계 뉴스와 업종 요인이 각각 얼마나 기여했는지는 분리할 수 없다. Lululemon -17.38%는 더 명확한 실적 이벤트다. 회사 발표상 매출은 4%, 비교매출은 9% 감소했다. 보고 EPS 2.92달러에는 관세 환급·관련 이자 효과 0.86달러가 포함돼, 이 효과를 제외한 2.06달러와 혼동하면 안 된다.','adobe','lulu'),
 p('10거래일 관점은 하루와 다르다. Salesforce +23.93%, Dell +18.56%, Meta +12.16%, CrowdStrike +11.02%, ServiceNow +9.95%가 최근 10거래일 상승 상위권이다. 따라서 오늘의 소프트웨어 약세는 지난 2주간 전부 하락했다는 뜻이 아니라, 일부 반등 주도주의 최근 흐름이 꺾인 것이다. 다음 관찰점은 하드웨어가 1~2일 반등에 그치는지, 소프트웨어의 10일 강세 종목이 다시 상대강도를 회복하는지다.'),
],
'SHSZ300':[
 p('중국은 미국과 다른 방향의 로테이션이다. Reuters가 전한 CSI 300 공식 수익률은 약 -0.1%였다. 그러나 제공 구성종목에서는 174개가 오르고 120개가 내렸다. 지수의 소폭 하락과 상승 종목 우위는 양립할 수 있으며, 시가총액이 큰 약세 종목과 업종 간 차별화를 함께 봐야 한다.','cn'),
 p('하락 하위 100개 중 IT가 45개, 소재가 23개로 합계 68개다. IEIT Systems(浪潮信息) -9.99%, Unisplendour -7.50%, Envicool -6.69%, Ruijie -6.33%, JCET -5.49%, WUS PCB -4.23%가 서버·네트워크·냉각·패키징·PCB에 걸쳐 약세였다. 중국 AI 하드웨어 약세는 한 종목의 돌발 하락보다 범위가 넓다. 신화재경도 컴퓨팅 관련 업종이 장중 상승분을 반납하고 오후에 하락했다고 보도했다. 개별 악재가 확인되지 않은 기업에는 별도의 규제나 주문 취소 원인을 붙이지 않았다.','cnsector'),
 p('강세는 조선·게임·콘텐츠·소비로 이동했다. China CSSC +9.18%, Century Huatong +7.96%, Wens +6.15%, Mango Excellent Media +5.46%, Luzhou Laojiao +5.16%, Shanxi Fen Wine +4.79%, Muyuan +4.49%다. 필수소비재 16개는 모두 상승했고 모두 일간 상위 100개에 들었다. 이는 필수소비재 안에서 소수 종목만 오른 날과 구분되는 특징이다.'),
 p('중국선박은 9월 2일 공시 보도에서 자회사 등의 LNG 이중연료 자동차운반선 10척, 10억 달러 초과 계약이 확인된다. 계약 체결은 9월 1일로, 9월 4일에 새로 나온 수주라고 쓰면 안 된다. 당일 강세의 관련 배경으로는 유효하지만 수주 뉴스만으로 전체 상승분을 설명하지는 않는다.','cssc'),
 p('10거래일로 보면 Mango +41.38%, Envicool +18.09%, Century Huatong +13.82%다. Envicool은 오늘 -6.69%지만 10일 전체로는 여전히 강해 단기 되돌림과 중기 약세를 구분해야 한다. 반대로 Sungrow -21.80%, JCET -14.27%, Zhongji Innolight -13.68%, Ruijie -13.60%는 10일 약세가 누적됐다. 중국 AI를 단일 바스켓으로 판단하기보다 냉각·광모듈·전력변환·콘텐츠를 따로 보는 것이 유용하다.'),
],
'SXXP':[
 p('유럽은 STOXX Europe 600 전체를 사용했다. 유로존 50종목으로 범위를 줄이지 않았다. Reuters 기준 지수는 9월 4일 +0.12%였지만 주간으로는 약 -0.8%였다. 제공 데이터에서는 상승 323개, 하락 270개로 미국보다 상승의 폭이 넓다. 그렇다고 유럽 전체로 자금이 순유입됐다고 단정할 수는 없다. 여기서 확인하는 것은 종목 수익률의 분포다.','eu'),
 p('상위 100개의 중심은 산업재 27개, IT 16개, 소재 13개, 경기소비재 13개다. AT&S +11.16%, ASM International +6.20%, Technoprobe +3.94%, Soitec +3.89%가 기술 하드웨어 강세를 보여준다. 반면 Dassault Systèmes -6.49%, Nemetschek -6.02%는 소프트웨어 약세였다. 미국에서 관찰된 하드웨어 대 소프트웨어 차별화가 유럽에서도 일부 나타났다.'),
 p('Soitec은 가격 반등과 연결할 수 있는 실적 근거가 있다. 9월 2일 회사는 Photonics-SOI 수요 증가를 이유로 FY2027 2분기 매출 성장 가이던스를 30% 초과에서 약 50%로 높였다. 그 분기 Photonics-SOI 매출은 전년의 약 3배를 예상했다. 오늘 수익률만 아니라 10일 +16.85%와 함께 볼 만한 구체적인 상향이다. AT&S 등 다른 상승 종목에 동일한 회사별 실적 상향이 있었다고 일반화하지 않는다.','soitec'),
 p('Volkswagen 우선주(VOW3)는 제공 데이터에서 +6.47%다. Reuters는 노사와 구조조정 계획의 진전 및 자동차 업종 강세를 보도했다. 이는 자동차 수요가 전면 개선됐다는 신호와 다르다. 비용·설비 구조조정 기대와 수요 회복을 구분해야 한다. 보도에 나온 다른 주식 종류의 상승률을 VOW3 가격에 덮어쓰지 않았다.','eu'),
 p('유럽에서 눈에 띄는 취약점은 방산의 10일 성과다. Hensoldt -10.75%, QinetiQ -10.71%, Babcock -10.63%, Rheinmetall -10.51%, Saab -10.50%, Leonardo -10.29%, CSG -10.17%, Renk -9.74%로 하위 10개 중 8개가 방산 관련이다. 정책 테마가 유효하더라도 최근 주가 리더십은 약하다. 특정 평화 협상이나 예산 삭감을 확인 없이 원인으로 달지 않았으며, 이번에는 가격상 확인되는 동반 약세로 정리한다.'),
],
}
STAGE_TEXT={
'generation':'발전·전력판매가 하루 +4.94%, 1주 +8.04%로 가장 강했다. NRG +6.42%, Constellation +4.88%, Vistra +3.52%로 세 종목 모두 상승했다. 단일 대형주 의존이 아닌 공통 움직임이다. 1개월도 +5.99%지만 3개월은 -0.15%로, 장기 상승 추세라기보다 최근 회복이 빠른 구간이다. 새로운 대규모 전력계약이 이날 일제히 발표됐다는 근거는 확보하지 못했다. 가격에서 확인되는 강세와 개별 계약 뉴스는 분리한다.',
'compute':'연산·메모리는 하루 +3.46%, 7개 모두 상승했다. Marvell +7.05%, Micron +6.10%, AMD +4.69%, Intel +4.51%가 Nvidia +0.84%, Broadcom +0.21%보다 강했다. 오늘의 강세는 Nvidia 단독 주도라기보다 주변 반도체로 퍼진 반등이다. 다만 바스켓 1개월 -1.39%, 3개월 -11.08%가 남아 있어, 하루 강세만으로 중기 추세 반전을 선언하기는 이르다.',
'server':'서버·스토리지는 +3.20%지만 내부 편차가 컸다. Sandisk +11.90%, Seagate +6.34%, Western Digital +5.86%가 주도했고 HPE는 -4.48%였다. 저장장치 3개와 서버 제조사를 같은 강도로 묶으면 잘못 읽게 된다. 9개 중 8개가 상승했으며 1주 +4.94%, 1개월 +2.28%다. Sandisk의 이 바스켓 내 하루 기여도는 약 +1.32%p로, 전체 +3.20% 중 상당 부분을 설명한다.',
'network':'네트워크·광통신은 +3.19%로 6개 유효 종목이 모두 올랐다. Coherent +6.60%, Corning +5.68%, Lumentum 약 +4.00%가 Arista +1.22%, Cisco +0.54%보다 강하다. 광통신 부품과 소재 쪽 반등이 더 컸다는 뜻이다. 그러나 1주 -2.33%, 1개월 -6.80%, 3개월 -16.73%여서 아직 가장 약한 중기 그룹 중 하나다. 최근 하루와 지난 3개월은 같은 방향이 아니다.',
'semicap':'반도체 장비·EDA 평균 +2.14%는 특히 분해해서 봐야 한다. KLA +7.32%, Teradyne +5.45%, Lam +5.12%, Applied Materials +4.31%는 모두 강했다. 반면 Synopsys -5.40%, Cadence -3.99%는 하락했다. 물리 장비 4개 평균과 설계 소프트웨어 2개 평균을 별도 표로 제시했다. 기존 분류 체계는 유지하되, 장비와 EDA가 오늘 반대 방향이었다는 정보를 평균 속에 묻지 않았다.',
'power_equipment':'전력기기·냉각은 +1.65%, 7개 모두 상승했다. Vertiv +4.35%, Eaton +3.46%가 가장 강했고 GE Vernova는 +0.01%로 사실상 보합이었다. 데이터센터 전력·열관리의 회복이 발전주 강세와 함께 나타났지만, 전력기기 바스켓 1개월 -5.57%, 3개월 -4.94%는 아직 부진하다. 냉각·전력관리와 발전사업의 상대강도를 구분할 필요가 있다.',
'construction':'데이터센터 시공·엔지니어링은 +1.45%다. Comfort Systems +1.91%, EMCOR +1.73%, Quanta +0.70%가 모두 올랐고 1주 +3.84%다. 반면 1개월 -9.02%, 3개월 -13.06%로 낙폭 회복에 해당하는 모습이다. 향후에는 신규 수주와 백로그가 실제 이익 추정치 상향으로 이어지는지를 별도로 확인해야 한다. 이번 가격 표만으로 수주 개선을 확정하지 않는다.',
'dc_reit':'데이터센터 REIT는 +0.50%로 하드웨어·발전보다 약했다. Iron Mountain +1.64%, Digital Realty +0.32%, Equinix -0.47%로 갈렸다. 전력 공급망이 오른 날에도 데이터센터 임대·운영 자산이 같은 폭으로 오르지는 않았다. 1개월 -3.70%, 3개월 -4.99%여서 물리 AI 인프라라는 공통 주제만으로 발전·냉각·리츠를 동일 취급하기 어렵다.',
'hyperscale':'하이퍼스케일러·플랫폼은 +0.13%에 그쳤다. Oracle +3.08%, Meta +1.00%와 Microsoft -2.04%, Alphabet -1.17%, Amazon -0.15%가 상쇄됐다. AI 인프라 공급업체가 오른 것이 곧 대형 플랫폼의 동반 강세는 아니었다. 6개 중 3개 상승, 1주 +0.59%, 1개월 -0.30%로 방향성이 약하다. IBM을 포함한 기존 확장 분류를 그대로 사용했다.',
'cyber':'사이버보안은 -0.78%다. Palo Alto +0.40%를 제외하면 CrowdStrike -0.87%, Akamai -1.20%, Gen Digital -2.17%, Fortinet 약 -0.04%로 약했다. 1주 -4.31%이고 그 기간에는 5개 모두 하락했다. 응용 소프트웨어뿐 아니라 보안에도 단기 약세가 퍼져 있다는 신호지만, 사이버보안 지출 자체가 감소했다는 결론은 가격만으로 낼 수 없다.',
'edge':'엣지·피지컬 AI는 -0.92%다. Tesla -5.92%, Axon -4.18%, Apple -2.51%가 아날로그·차량용 반도체와 자동화 종목의 소폭 상승을 압도했다. 8개 중 5개는 상승해 평균 수익률과 상승 종목 비율이 다른 방향이다. 이 그룹은 로봇·스마트폰·차량·산업자동화가 섞인 인접 노출이므로 순수 AI 하드웨어의 지표로 읽지 않는다.',
'software':'AI 소프트웨어·서비스는 -2.98%로 12개 단계 중 최하위다. Adobe -6.73%, Workday -5.38%, Palantir -4.49%, Intuit -3.37%, Accenture -3.31%가 하락했고 AppLovin +2.23%만 상승했다. 1주 -4.20%지만 1개월 +4.17%, 3개월 +7.90%다. 지난 3개월의 상대적 우위와 최근 단기 약세가 공존한다. Adobe CEO 승계 발표는 확인된 사건이지만, 이 그룹 전체 약세를 설명하는 단일 원인으로 확대하지 않는다.',
}

NOTE=[
 '작성일은 2026-09-07, 가격 기준일은 2026-09-04다. 신규 파일의 9월 5~7일 가격은 해당 4개 분석 지수에서 전 행 대비 변화가 없어 신규 거래일로 취급하지 않았다. 1D=9/3→9/4, 10거래일=8/21→9/4, AI 1주=8/28→9/4, 1개월=8/4→9/4, 3개월=6/4→9/4. 연율화하지 않았다.',
 '종목 수익률은 제공 가격의 기말/기초−1이며 배당을 별도로 더하지 않았다. 종목 비교는 현지통화 기준이다. 현재 제공 구성종목을 과거에도 적용하므로 공식 과거 구성종목 지수나 편입·편출을 반영한 백테스트가 아니다.',
 '시장·섹터의 시총가중 수익률은 전일 전체 시총을 가중치로 계산한 참고치다. 유동주식 비율, 상한, 공식 지수 제수와 환산통화를 반영하지 않아 공식 지수 수익률과 다르다. 특히 STOXX 600의 시총 원천 통화가 혼합돼 있어 섹터 가중 결과는 근사치다. 보고서의 공식 지수 종가는 기사와 분리해 표시했다.',
 'AI는 기존 S&P 500 확장 분류(Core + Adjacent) 73개를 유지했다. APH는 3개월 구간의 가격 조정 불연속 후보로 수익률 산출에서 제외해 유효 72개, 12개 단계다. 분류 자체에는 APH의 역할을 남겼다. 외부 비상장기업·비구성종목을 임의로 추가하지 않았다.',
 'AI 단계 수익률은 종목의 일일 단순수익률을 동일가중한 뒤 일별 복리 누적했다. 주가 절대값의 평균이 아니다. 표의 1D 기여도는 종목 1D 수익률/그 단계 유효 종목 수이며 합계가 단계 1D 수익률과 일치한다. 여러 기간의 종목 수익률을 단순 평균한 값은 일일 재조정 바스켓 누적수익률과 같지 않으므로 다기간 기여도로 표시하지 않았다.',
 '상승 비율은 가격 상승 종목 수/해당 기간 유효 종목 수다. EPS revision breadth나 애널리스트 추정치 상향 비율이 아니다. 이번 보고서는 주가 로테이션 보고서이며 가격 움직임을 이익 추정치 상향으로 바꾸어 서술하지 않았다.',
 'Top/Bottom 100은 시장마다 각 100개다. 1D 순위를 기본으로 하고 10거래일 순위를 별도로 제공한다. 미수익률을 0으로 채우지 않았다. S&P 500 503개, CSI 300 300개, STOXX 600 600개 모두 1D·10D 계산에 필요한 가격이 있다.',
 '뉴스는 이 작업에서 웹 검색으로 확인했다. 명시된 회사 이벤트 외의 순위·동반 움직임·지속성 평가는 제공 가격에서 도출한 해석이다. 모든 1,403개 종목의 뉴스를 전수 확인한 것은 아니다. API 키를 사용하는 유료 모델 호출은 하지 않았다.',
]

def stock_rank(rows):return [[i,x['ticker'],x['name'],SEC.get(x['sector'],x['sector']),pct(x['return1d']),pct(x['return10d'])] for i,x in enumerate(rows,1)]
RH=['순위','티커','종목','섹터','1D','10거래일']
markets=[h('오늘의 결론'),p('미국은 AI 하드웨어·전력의 반등과 소프트웨어 하락, 중국은 AI 하드웨어 약세와 소비·게임·조선 강세, 유럽은 일부 하드웨어의 실적 기대와 자동차 구조조정 기대가 공존했다. 같은 AI 테마라도 국가·단계·측정 기간에 따라 움직임이 다르다. 오늘의 순위와 최근 10거래일 순위를 분리해 읽어야 한다.'),
 table('시장 내부 분포 — 제공 구성종목 가격',['시장','유효 종목','상승','하락','보합','시총가중 1D 참고치'],[[NAMES[m['code']],m['members'],m['advancers'],m['decliners'],m['members']-m['advancers']-m['decliners'],pct(m['marketReturn1dProxy'])] for m in D['markets']]),
 p('Top/Bottom은 각각 100개로 구성했다. 아래 본문에는 핵심 10개씩을 먼저 싣고, HTML 하단과 엑셀에 1D·10거래일별 100개 전체를 수록했다. 위 참고치를 공식 지수 수익률로 사용하지 않는다.')]
for m in D['markets']:
 markets += [h(NAMES[m['code']])]+MARKET_TEXT[m['code']]
 markets += [table('당일 상승 상위 10',RH,stock_rank(m['top100_1d'][:10])),table('당일 하락 하위 10',RH,stock_rank(m['bottom100_1d'][:10]))]
 top=Counter(x['sector'] for x in m['top100_1d']);bottom=Counter(x['sector'] for x in m['bottom100_1d'])
 markets += [table('모든 섹터 — 어디에 강세·약세가 몰렸나',['섹터','전체 수','상위100 내','하위100 내','1D 가중 참고치','상승 비율'],[[SEC.get(s['sector'],s['sector']),s['n'],top[s['sector']],bottom[s['sector']],pct(s['return1d']),ratio(s['breadth'])] for s in sorted(m['sectors'],key=lambda s:s['return1d'],reverse=True)])]
markets += [h('다음 거래일에 확인할 세 가지'),p('① 미국: 저장장치·광통신의 강세가 Nvidia·하이퍼스케일러까지 연결되는가. ② 중국: 소비·게임의 상승 폭이 유지되는 가운데 서버·광모듈 약세가 멈추는가. ③ 유럽: Soitec처럼 구체적인 상향 근거가 있는 하드웨어와 단순 반등 종목의 성과가 벌어지는가. 방향 예측보다 이 세 가지의 연속성을 먼저 확인한다.'),h('계산·데이터 확인')]+[p(t) for t in NOTE]
for m in D['markets']:
 for period,label in [('1d','1D'),('10d','10거래일')]:
  for side,sideko in [('top','상위'),('bottom','하위')]:
   markets.append(table(f"{NAMES[m['code']]} · {label} {sideko} 100 전체",RH,stock_rank(m[f'{side}100_{period}']),True))

ai=D['ai'];stages=sorted(ai['stages'],key=lambda s:s['return1d'],reverse=True)
stocks=ai['stocks'];lookup={s['ticker']:s for s in stocks}
ai_blocks=[h('오늘의 결론'),p('최근 하루는 미국 AI 안에서 소프트웨어보다 하드웨어·전력 쪽이 강했다. 발전 +4.94%, 연산·메모리 +3.46%, 서버·스토리지 +3.20%, 네트워크·광통신 +3.19%에 비해 AI 소프트웨어·서비스는 -2.98%였다. 발전과 소프트웨어의 하루 격차는 약 7.93%p다. 그러나 최근 3개월로 보면 소프트웨어 +7.90%, 네트워크 -16.73%다. 오늘의 방향이 곧 지난 분기의 방향은 아니다.'),
 p('지수가 약한 날에도 하드웨어·전력이 반등했다는 점이 핵심이다. 다만 가격만으로 실제 자금 유입·유출을 확정하지는 않는다. 본문에서 말하는 로테이션은 단계별 상대수익률의 변화다. 수익률 계산은 기존 미국 S&P 500 확장 분류를 유지했고, 아래에 12개 단계와 73개 분류 종목 전부를 실었다.'),
 table('밸류체인 전체 — 1D 수익률 내림차순',['단계','유효 수','1D','1주','1개월','3개월','1D 상승 비율'],[[s['name'],s['members'],pct(s['return1d']),pct(s['return1w']),pct(s['return1m']),pct(s['return3m']),ratio(s['breadth1d'])] for s in stages]),
 h('평균 속에서 가려지는 분화'),
 p('기존 장비·EDA 분류와 서버·스토리지 분류는 유지하되, 오늘의 방향을 오해하지 않도록 하위 묶음을 별도 계산했다. 아래는 1D 종목 동일가중 평균으로, 임의로 새 중장기 지수를 만든 것이 아니다.')]
subsets=[('물리 반도체 장비·테스트',['AMAT','LRCX','KLAC','TER']),('반도체 설계 소프트웨어·EDA',['CDNS','SNPS']),('저장장치',['SNDK','STX','WDC']),('서버·제조·기타 스토리지',['DELL','HPE','SMCI','FLEX','JBL','NTAP'])]
ai_blocks += [table('세부 묶음의 하루 차이',['하위 묶음','구성','1D 동일가중'],[[name,', '.join(ts),pct(sum(lookup[t]['return1d'] for t in ts)/len(ts))] for name,ts in subsets])]
for s in stages:
 refs=['adobe'] if s['key']=='software' else []
 ai_blocks += [h(s['name']),p(STAGE_TEXT[s['key']],*refs)]
 group=sorted([x for x in stocks if x['stageKey']==s['key']],key=lambda x:x['return1d'] if x['return1d'] is not None else -1e9,reverse=True)
 rows=[]
 for x in group:
  role=x['rationale']+(' [가격 조정 불연속 후보: 수익률 제외]' if x['excluded'] else '')
  rows.append([x['ticker']+' · '+x['name'],role,pct(x['return1d']),pct(x['return1w']),pct(x['return1m']),pct(x['return3m']), '—' if x['excluded'] else f"{x['return1d']/s['members']*100:+.2f}"])
 ai_blocks += [table('전체 종목과 AI 역할',['종목','밸류체인 역할','1D','1주','1개월','3개월','1D 기여 %p'],rows)]
ai_blocks += [h('미국 밖에서 확인되는 교차 신호'),p('중국 CSI 300에서 IEIT -9.99%, Envicool -6.69%, Ruijie -6.33%가 하락한 반면, 유럽 STOXX 600의 AT&S +11.16%, ASM +6.20%, Soitec +3.89%는 상승했다. 미국 AI 공급망 반등을 중국 AI 공급망의 강세로 자동 연결할 수 없는 날이다. 이 종목들은 비교 사례이며 미국 바스켓 수익률에는 넣지 않았다.'),p('유럽 Soitec의 경우 Photonics-SOI 수요를 반영한 회사 매출 가이던스 상향이 확인된다. 미국 바스켓의 모든 하드웨어 상승에도 동일한 실적 상향 근거가 있는 것은 아니다. 국가별 수익률과 회사별 실적 촉매를 각각 확인하는 방식이 필요하다.','soitec'),h('관찰 포인트'),p('다음 갱신에서는 발전·전력의 1주 강세가 지속되는지, 연산·메모리와 네트워크가 1개월 마이너스를 줄이는지, 소프트웨어의 3개월 상대 우위가 단기 약세로 훼손되는지를 우선 본다. 특히 EDA와 물리 장비를 따로 확인한다. 이 보고서의 가격 반등은 EPS 추정치 상향이나 주문 증가를 직접 측정한 결과가 아니다.'),h('계산·데이터 확인')]+[p(t) for t in NOTE]

REPORTS=[{'slug':'Daily_TopBottom100_20260907','title':'미국·중국·유럽 데일리 시황','subtitle':'S&P 500 · CSI 300 · STOXX 600 | Top / Bottom 100','blocks':markets}, {'slug':'AI_ValueChain_Daily_20260907','title':'미국 AI 밸류체인 데일리 로테이션','subtitle':'12개 단계 · 73개 분류 종목 | 하루 / 1주 / 1개월 / 3개월','blocks':ai_blocks}]
CSS='''body{font-family:"Malgun Gothic","맑은 고딕",Arial,sans-serif;background:#f0f3f7;color:#182c43;margin:0;font-size:15px;line-height:1.8}main{max-width:1150px;margin:28px auto;background:white;padding:48px 52px;border-top:7px solid #17365d;box-shadow:0 5px 25px #142e4912}h1{font-size:32px;line-height:1.35;margin:12px 0}h2{margin:42px 0 14px;border-bottom:2px solid #17365d;padding-bottom:9px;font-size:23px}h3{font-size:17px;margin-top:25px}.meta{color:#61758b;font-size:13px}.lead{color:#247d89;font-weight:600}p{margin:15px 0;text-align:justify}a{color:#1b63a3;text-decoration:none}.refs{font-size:12px;display:block}.tablewrap{overflow:auto;margin:16px 0 24px}table{width:100%;border-collapse:collapse;font-size:12px;line-height:1.5}th{background:#17365d;color:white;text-align:left;padding:10px 8px;white-space:nowrap}td{padding:8px;border-bottom:1px solid #dce4ec;vertical-align:top}tr:nth-child(even){background:#f3f6fa}td:first-child{min-width:60px}details{margin:15px 0;border:1px solid #dce4ec;border-radius:5px;padding:12px}summary{font-weight:bold;cursor:pointer}.up{color:#087b67}.down{color:#bc344a}nav{margin:20px 0;font-size:13px}.tag{background:#e8f3f4;padding:4px 10px;border-radius:4px}@media(max-width:700px){main{margin:0;padding:24px 16px}h1{font-size:26px}}@media print{body{background:white}main{box-shadow:none;margin:0;padding:0}h2,h3{break-after:avoid}tr{break-inside:avoid}a{color:inherit}nav{display:none}}'''
def esc(x):return html.escape(str(x))
def table_html(b):
 head=''.join('<th>'+esc(x)+'</th>' for x in b['heads']); rows=[]
 for r in b['rows']:
  cells=[]
  for v in r:
   cl='up' if str(v).startswith('+') else 'down' if str(v).startswith('-') else ''
   cells.append(f'<td class="{cl}">{esc(v)}</td>')
  rows.append('<tr>'+''.join(cells)+'</tr>')
 return '<div class="tablewrap"><table><thead><tr>'+head+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
for rep in REPORTS:
 parts=[f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(rep["title"])}</title><style>{CSS}</style><main>',f'<div class="lead">DAILY EQUITY RESEARCH · 2026.09.07</div><h1>{esc(rep["title"])}</h1><div>{esc(rep["subtitle"])}</div><p class="meta">가격 기준 2026.09.04 종가 · 신규 파일의 9/5~9/7 반복 가격 제외 · 작성 2026.09.07</p><nav><a href="Daily_TopBottom100_20260907.html">시장별 보고서</a> · <a href="AI_ValueChain_Daily_20260907.html">AI 밸류체인</a> · <a href="Daily_Tables_20260907.xlsx">전체 숫자 엑셀</a></nav>']
 for b in rep['blocks']:
  if b['type']=='h':parts.append('<h2>'+esc(b['text'])+'</h2>')
  elif b['type']=='p':
   refs=' · '.join(f'<a href="{SOURCES[k][1]}">{esc(SOURCES[k][0])}</a>' for k in b.get('refs',[]))
   parts.append('<p>'+esc(b['text'])+(f'<span class="refs">근거: {refs}</span>' if refs else '')+'</p>')
  else:
   t=table_html(b)
   parts.append('<details><summary>'+esc(b['title'])+'</summary>'+t+'</details>' if b['appendix'] else '<h3>'+esc(b['title'])+'</h3>'+t)
 parts.append('<p class="meta">숫자: 사용자 제공 BQuant 구성종목·가격. 회사 역할: 기존 AI 분류표. 일간 시황의 사실과 해석을 구분해 작성.</p></main></html>')
 (OUT/(rep['slug']+'.html')).write_text(''.join(parts),encoding='utf-8')
(OUT/'report_blocks.json').write_text(json.dumps({'reports':REPORTS,'sources':SOURCES},ensure_ascii=False),encoding='utf-8')

# Full numeric workbook; source prices and formula cells have cached results.
wb=xlsxwriter.Workbook(OUT/'Daily_Tables_20260907.xlsx')
wb.set_properties({'title':'Daily market and AI value-chain tables','author':'Research','comments':'Provided BQuant prices; as of 2026-09-04'})
head=wb.add_format({'bold':True,'bg_color':'#17365D','font_color':'white','font_name':'Arial','text_wrap':True})
txt=wb.add_format({'font_name':'Arial','font_size':10})
per=wb.add_format({'font_name':'Arial','font_size':10,'num_format':'+0.00%;-0.00%;0.00%'})
dec=wb.add_format({'font_name':'Arial','font_size':10,'num_format':'#,##0.00'})
wrap=wb.add_format({'font_name':'Malgun Gothic','font_size':10,'text_wrap':True,'valign':'top'})
def sheet(name,headers,rows,percentcols=(),wide=None):
 ws=wb.add_worksheet(name);ws.freeze_panes(1,2);ws.write_row(0,0,headers,head);ws.set_row(0,30);ws.set_column(0,len(headers)-1,15,txt)
 for c,width in (wide or {}).items():ws.set_column(c,c,width,wrap if width>45 else txt)
 for r,row in enumerate(rows,1):
  for c,v in enumerate(row):
   if v is None:ws.write_blank(r,c,None,txt)
   elif isinstance(v,(float,int)):ws.write_number(r,c,v,per if c in percentcols else dec)
   else:ws.write(r,c,str(v),txt)
 ws.autofilter(0,0,len(rows),len(headers)-1)
 for c in percentcols:ws.conditional_format(1,c,len(rows),c,{'type':'3_color_scale','min_color':'#F6C7CE','mid_color':'#FFFFFF','max_color':'#B9E5D1','mid_type':'num','mid_value':0})
 return ws
sheet('README',['항목','내용'],[['작성일','2026-09-07'],['가격 기준일','2026-09-04'],['신규 원본','Bquant_All_19_Raw_Refreshed12시 (5).xlsb']]+[[str(i),v] for i,v in enumerate(NOTE,1)],wide={0:22,1:125})
for m in D['markets']:
 allheaders=['Ticker','Company','Sector','Industry','Price 2026-08-21','Price 2026-09-03','Price 2026-09-04','1D return','10D return','10D max drawdown','Current market cap (source currency)']
 rows=[[x[k] for k in ['ticker','name','sector','industry','priceStart','pricePrevious','priceEnd','return1d','return10d','maxDrawdown10d','mcap']] for x in m['all']]
 ws=sheet(m['code']+'_All',allheaders,rows,(7,8,9),{0:22,1:40,2:25,3:38,10:25})
 for r,x in enumerate(m['all'],1):
  er=r+1;ws.write_formula(r,7,f'=G{er}/F{er}-1',per,x['return1d']);ws.write_formula(r,8,f'=G{er}/E{er}-1',per,x['return10d'])
 for period in ['1d','10d']:
  for side in ['top','bottom']:
   rr=m[f'{side}100_{period}']
   sheet(f"{m['code']}_{period}_{side}100",['Rank','Ticker','Company','Sector','1D','10D','End price'],[[i,x['ticker'],x['name'],x['sector'],x['return1d'],x['return10d'],x['priceEnd']] for i,x in enumerate(rr,1)],(4,5),{1:22,2:40,3:27})
 top=Counter(x['sector'] for x in m['top100_1d']);bt=Counter(x['sector'] for x in m['bottom100_1d'])
 sheet(m['code']+'_Sectors',['Sector','Members','Top100 count','Bottom100 count','1D cap weighted proxy','Price advancer ratio'],[[s['sector'],s['n'],top[s['sector']],bt[s['sector']],s['return1d'],s['breadth']] for s in m['sectors']],(4,5),{0:30})
sheet('AI_Stages',['Stage','Valid stocks','Classified','1D','1W','1M','3M','1D advancer ratio'],[[s['name'],s['members'],s['classifiedMembers'],s['return1d'],s['return1w'],s['return1m'],s['return3m'],s['breadth1d']] for s in stages],(3,4,5,6,7),{0:35})
airows=[]
sm={s['key']:s for s in stages}
for x in stocks:
 airows.append([x['ticker'],x['name'],x['stage'],x['rationale'],x['confidence'],x['price3mStart'],x['price1mStart'],x['price1wStart'],x['pricePrev'],x['priceEnd'],x['return1d'],x['return1w'],x['return1m'],x['return3m'],None if x['excluded'] else x['return1d']/sm[x['stageKey']]['members'],'EXCLUDED - price adjustment break candidate' if x['excluded'] else 'Included'])
ws=sheet('AI_All_73',['Ticker','Company','Stage','Role','Core/Adjacent','Price Jun04','Price Aug04','Price Aug28','Price Sep03','Price Sep04','1D','1W','1M','3M','1D contribution (fraction)','Status'],airows,(10,11,12,13,14),{1:34,2:30,3:80,15:42})
for r,x in enumerate(stocks,1):
 if x['excluded']:continue
 er=r+1
 for col,start,key in [(10,'I','return1d'),(11,'H','return1w'),(12,'G','return1m'),(13,'F','return3m')]:ws.write_formula(r,col,f'=J{er}/{start}{er}-1',per,x[key])
 ws.write_formula(r,14,f'=K{er}/{sm[x["stageKey"]]["members"]}',per,x['return1d']/sm[x['stageKey']]['members'])
dates=stages[0]['series'];sheet('AI_Daily_Levels',['Date']+[s['name'] for s in stages],[[dt]+[dict(s['series']).get(dt) for s in stages] for dt,v in dates],wide={0:15})
sheet('Date_Audit',['Index','Date','Valid prices','Changed vs previous row'],[[x[k] for k in ['index','date','valid','changed']] for x in D['audit']],wide={0:15,1:16})
sheet('News_Sources',['Key','Title','URL'],[[k,*v] for k,v in SOURCES.items()],wide={0:16,1:60,2:100})
wb.close()

# Reconciliation assertions, no silent substitution of missing returns.
for m in D['markets']:
 assert len(m['all'])==m['sourceMembers']
 for period in ['1d','10d']:
  for side in ['top','bottom']:assert len(m[f'{side}100_{period}'])==100
 for x in m['all']:
  assert abs(x['priceEnd']/x['pricePrevious']-1-x['return1d'])<1e-10
  assert abs(x['priceEnd']/x['priceStart']-1-x['return10d'])<1e-10
for s in stages:
 valid=[x for x in stocks if x['stageKey']==s['key'] and not x['excluded']]
 assert abs(sum(x['return1d'] for x in valid)/len(valid)-s['return1d'])<1e-10
assert len(stocks)==73 and sum(not x['excluded'] for x in stocks)==72
(OUT/'verification.json').write_text(json.dumps({'price_asof':'2026-09-04','markets':{m['code']:m['members'] for m in D['markets']},'ranking_tables':12,'rows_per_ranking':100,'ai_classified':73,'ai_valid':72,'price_ratio_checks':'PASS','AI_1D_contribution_reconciliation':'PASS','news_sources':len(SOURCES)},indent=2),encoding='utf-8')
print('HTML / XLSX / report blocks / verification written',flush=True)
