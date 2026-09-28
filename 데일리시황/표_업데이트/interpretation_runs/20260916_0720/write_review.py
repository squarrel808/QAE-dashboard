import copy, hashlib, json, pathlib, sqlite3, sys, re
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[4] / 'Context/_macro/Research_Context'
# Resolve from the original QAE project, never from a temporary checkout.
ROOT = pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
OUT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'ecocal_dashboard'))
import build_dashboard as b
now = datetime.now().astimezone().isoformat(timespec='seconds')
manifest = json.loads(pathlib.Path('데일리시황/표_업데이트/latest.json').read_text(encoding='utf-8'))
weco = pathlib.Path(manifest['review_queue']).parent
data = json.loads((weco/'dashboard_data.json').read_text(encoding='utf-8'))
authpath = ROOT/'ecocal_dashboard/authored_commentary.json'
original = authpath.read_bytes()
(OUT/'authored_commentary.before.json').write_bytes(original)
bundle = json.loads(original)
c = sqlite3.connect((ROOT/'data/research.sqlite3').as_uri()+'?mode=ro', uri=True)
c.row_factory=sqlite3.Row
updates={}
reviewed_pages=set()

def house(prefix, house, page, start, end, summary, comment, limitation='', kind='reaction'):
    doc=c.execute('select * from documents where doc_id like ?', (prefix+'%',)).fetchone()
    text=c.execute('select text from pages where doc_id=? and page=?',(doc['doc_id'],page)).fetchone()[0]
    sm=re.search(r'\s+'.join(map(re.escape,start.split())),text)
    assert sm, start
    a=sm.start()
    em=re.search(r'\s+'.join(map(re.escape,end.split())),text[a:])
    assert em, end
    z=a+em.end()
    reviewed_pages.add((doc['doc_id'],page))
    return dict(house=house,kind=kind,summary=summary,comment=comment,limitation=limitation,
                evidence=[dict(doc_id=doc['doc_id'],page=page,quote=text[a:z])],
                reviewed_pages=[dict(doc_id=doc['doc_id'],page=page)])

def add(country,names,h,addition,watch=None):
    for name in names:
        e=next(e for e in data['events'] if e['country_code']==country and e['event']==name and e['available_at_request'])
        r=updates.setdefault(e['id'],copy.deepcopy(e['commentary']))
        r['houses']=[x for x in r['houses'] if x['house']!=h['house']]+[copy.deepcopy(h)]
        if addition and addition not in r['summary']:r['summary']+=' '+addition
        if watch:r['watch']=watch

gs=house('0e4898','GS',1,'The composition of the report was weak','increased.',
 'GS는 9월 7.6의 예상 하회를 신규주문·출하 급락에서 찾았다. 고용은 소폭 개선됐지만 현재·예상 투입가격은 모두 올라 활동과 가격 신호가 엇갈렸다고 평가했다.',
 'AI 비교: JPM과 수요 둔화·가격 압력 지속에는 일치한다. GS의 약한 구성 평가와 JPM의 확장 지속 평가는 강도와 방향을 달리 강조한 것이다.')
jpm=house('f4e558','JPM',1,'The first major regional manufacturing survey','persistent.',
 'JPM은 9월 헤드라인이 20.6에서 7.6으로, ISM 가중 합성지수가 55.4에서 53.7로 낮아졌지만 제조업 확장 신호는 남았다고 봤다. 신규주문·출하는 약해지고 투입·판매가격은 상승해 비용 전가 압력이 지속됐다.',
 'AI 비교: GS와 둔화 진단은 같지만 JPM은 합성지수의 확장 유지에 무게를 둔다. BofA의 10.0은 사전 전망이며 이번 결과보다 2.4포인트 높았다.')
add('US',['Empire Manufacturing'],gs,'새 사후 분석에서 GS·JPM 모두 주문·출하 둔화와 가격 압력 상승을 확인했다. AI 판단: 성장 둔화를 즉각적인 물가 완화로 연결하기 어렵다.','필라델피아 연은·전국 ISM에서 주문 둔화와 투입가격 상승이 함께 나타나는지 확인한다.')
add('US',['Empire Manufacturing'],jpm,'')

gsppi=house('f90600','GS',1,'Core producer prices increased','methodological changes and will be implemented with the\nAugust PCE report.',
 'GS는 근원 PPI가 예상보다 약했어도 항공료·의료 등 PCE에 반영되는 구성은 강했다고 평가했다. PPI 발표 직후 8월 근원 PCE 전월비 추정치를 0.22%에서 0.24%로 높였다.',
 'AI 비교: PPI의 근원 둔화와 소비물가로 연결되는 구성의 강세를 분리해야 한다. 이 PCE 추정은 CPI 발표 전 당시 전망이며 최신 확정값이 아니다.',
 'PDF 표지·본문 발행일은 9월 10일, 검색 DB 메타데이터는 9월 11일이다. 보수적인 DB 날짜를 유지하되 실제 원문 날짜를 병기한다. PPI 이후·CPI 이전 전망이다.')
ppinames=['PPI Final Demand MoM','PPI Ex Food and Energy MoM','PPI Ex Food, Energy, Trade MoM','PPI Final Demand YoY','PPI Ex Food and Energy YoY','PPI Ex Food, Energy, Trade YoY']
add('US',ppinames,gsppi,'AI 비교: GS는 PCE로 연결되는 항공료·의료 구성의 강세를 지적해, PPI 총수치만으로 소비물가 압력 완화를 단정하기 어렵다.')
citippi=house('3a7fcc','Citi',2,'Citi’s view – Details of August PPI','PPI\ngoods yet.',
 'Citi는 8월 PPI 강세가 주로 에너지 관련 가격에 집중됐으며, 높은 투입·운송비가 소비재 전반으로 전가된 증거는 아직 뚜렷하지 않다고 봤다.',
 'AI 비교: GS는 PCE 관련 서비스 구성의 강세, Citi는 소비재 가격 전가의 제한에 초점을 둔다. 서로 다른 구성에 대한 평가이므로 단순한 상반 전망으로 읽지 않는다.')
add('US',ppinames[:3],citippi,'Citi는 소비재 전반으로의 비용 전가 증거가 아직 제한적이라고 봐 품목별 확인이 필요하다.')

cpi=house('7fa4fb','Citi',2,'Slowing shelter inflation','been slowing.',
 'Citi는 8월 근원 CPI 0.29%의 상방 오차가 무선통신료 급등에 집중됐고, 주거비 둔화와 완만한 다수 서비스·재화 가격은 추가 디스인플레이션을 지지한다고 봤다.',
 'AI 비교: 월간 예상 상회 자체와 상승의 지속성은 다르다. 다른 IB의 통신·여행 항목 지적에 더해 Citi는 통신료 되돌림 가능성과 주거비 둔화에 무게를 둔다.')
add('US',['CPI MoM','Core CPI MoM','CPI YoY','Core CPI YoY'],cpi,'Citi 사후 분석은 무선통신료의 일회성 가능성과 주거비 둔화를 강조한다. AI 판단: 다음 달 통신료 되돌림과 주거비 흐름이 지속성을 가를 것이다.')

home=house('5321b4','Citi',2,'Citi’s view – Home sales','weigh on housing activity.',
 'Citi는 8월 398만 호의 부진을 재고 제약보다 약한 수요로 설명했다. 매물 증가와 높은 금리를 감안하면 거래·주택가격 압력이 이어지고 주거비 물가도 추가 둔화할 수 있다고 봤다.',
 'AI 비교: 판매 감소라는 공통 진단에 수요·공급 구분을 보탰다. 매물 증가와 거래 부진의 조합은 공급 부족만으로 설명하기 어렵다.',
 '표지·본문은 9월 10일 발행, DB 메타데이터는 9월 11일이다. Citi의 재고 개월 수와 GS의 계절조정 수치는 정의가 달라 직접 비교하지 않는다.')
add('US',['Existing Home Sales','Existing Home Sales MoM'],home,'새 Citi 사후 분석은 매물이 늘어도 거래가 줄었다는 점에서 수요 약화를 강조한다.')

claims=house('f90600','GS',2,'5. Initial jobless claims','in line with expectations.',
 'GS는 9월 5일 주간 신규청구 20.6만 건과 8월 29일 주간 계속청구 177.4만 건을 대체로 예상에 부합한다고 평가했다. 신규청구의 4주 평균도 낮아졌다.',
 'AI 비교: JPM의 고용 판단을 보강하지만 청구 감소는 해고 흐름에 관한 신호이며 신규 채용 회복을 입증하지는 않는다.',
 '표지·본문은 9월 10일, DB 날짜는 9월 11일이다. GS의 4주 평균 감소 2천 건과 원본 수정치 기준 감소 1.5천 건은 반올림 차이가 있어 원본 수치를 유지한다.')
add('US',['Initial Jobless Claims','Initial Claims 4-Wk Moving Avg','Continuing Claims'],claims,'GS 사후 분석도 낮은 청구 수준을 확인해 급격한 해고 증가 신호는 제한적이다.')

mich=house('31f8c6','Citi',2,'Inflation expectations in the University','tariff increases.',
 'Citi는 9월 심리 약화에 휘발유 가격 상승이 영향을 줬다고 보면서도, 기대물가 조사 변동성이 커졌고 소비자가 가격 상승을 앞둔 선구매 행동을 보이지 않아 기대 이탈로 판단하지 않았다.',
 'AI 비교: GS가 확인한 심리·기대물가 수치의 악화와 Citi의 기대 이탈 유보를 구분한다. 설문 상승을 실제 소비 감소나 장기 기대 불안정으로 곧바로 치환하지 않는다.',
 '표지·본문은 9월 11일, DB 메타데이터는 9월 12일이다. 이번 9월 잠정치에 대한 사후 분석이다.')
add('US',['U. of Mich. Sentiment','U. of Mich. Current Conditions','U. of Mich. Expectations','U. of Mich. 1 Yr Inflation','U. of Mich. 5-10 Yr Inflation'],mich,'Citi는 휘발유 부담을 인정하면서도 선구매 행동과 조사 변동성을 근거로 기대물가 이탈 판단은 유보했다.')

ca=house('e275c9','Citi',2,'Citi’s view – With a surprisingly','negative output gap.',
 'Citi는 8월 중앙값 2.0%·절사평균 1.9%가 목표 부근인 만큼 시장의 인상 기대를 정당화하기 어렵다고 봤다. 2026년 남은 기간 동결을 예상하되 다음 활동·물가 자료를 핵심 확인점으로 제시했다.',
 'AI 비교: 헤드라인 3.0%보다 근원 분포의 안정에 정책 판단의 무게를 둔 해석이다. 다른 IB의 세부 가격 강세 지적과 함께 보면 다음 3개월 물가 속도가 중요하다.')
add('CA',['CPI NSA MoM','CPI YoY','CPI Core- Median YoY%','CPI Core- Trim YoY%'],ca,'Citi는 목표 부근 근원물가를 근거로 추가 인상 필요성에 신중했다. AI 판단: 임대료 반등과 근원 3개월 속도를 함께 점검해야 한다.')

uk=house('0b97b7','Citi',1,'The Labour Market data this morning','private sector wage growth.',
 'Citi는 급여대장 고용 이탈 증가에도 전체 노동시장 유휴여력은 대체로 유지됐고, 공공 임금 강세는 과거 민간 임금 상승을 따라잡는 성격이라고 평가했다. 이번 발표가 BoE 내부 견해를 바꿀 결정적 신호는 아니라고 봤다.',
 'AI 비교: 급여대장 약세와 실업률 정체가 공존한다는 기존 해석에 공공·민간 임금 구성의 차이를 보탰다. 단일 수치로 정책 전환을 단정하기 어렵다.',
 'Citi는 정기임금이 소폭 높아졌다고 서술하지만 원본은 3.5%로 종전과 동일하다. 원본 숫자는 유지하고 차이를 명시한다. 이번 고용 발표 후 해석이며 향후 BoE 동결은 전망이다.')
add('GB',['Weekly Earnings ex Bonus 3M/YoY','ILO Unemployment Rate 3Mths','Payrolled Employees Monthly Change'],uk,'Citi는 공공 임금의 따라잡기와 대체로 유지된 유휴여력을 근거로 이번 수치의 정책 방향 전환 신호를 제한적으로 평가했다.')

ecb=house('3e0d5a','GS',1,'1. The Governing Council raised','future decisions at all.',
 'GS는 25bp 인상이 만장일치였지만 라가르드가 향후 경로를 거의 제시하지 않았다고 평가했다. 성장·물가 전망 상향과 에너지 위험은 확인했지만 ECB의 추가 인상 약속으로 해석하지 않았다.',
 'AI 비교: 다른 IB의 추가 인상 전망과 ECB가 실제로 제시한 가이던스를 구분해야 한다. 이번 결정만으로 후속 인상 시점을 확정할 수 없다.')
add('EA',['ECB Deposit Facility Rate'],ecb,'GS 사후 분석은 향후 금리 경로의 명시적 가이던스가 없었다는 점을 강조해, IB 전망과 ECB 약속을 구별할 필요가 있다.')
it=house('8312fa','GS',1,'1. In Italy','0.17% before).',
 'GS는 7월 이탈리아 산업생산 +0.7%를 광업·제조업의 개선으로 설명하고 3분기 GDP 추적치를 전분기비 0.17%에서 0.19%로 소폭 높였다.',
 'AI 비교: BofA의 사전 생산 전망에 실제 구성과 성장 추적치 반응을 보탰다. 반등이 성장 전망을 크게 바꾼 것은 아니다.',
 'GS 본문 6월 전월비는 -1.0%이나 현재 원본 수정치는 -1.1%다. 기준 차이를 유지하며 GS의 GDP 추적치를 실제 GDP로 표시하지 않는다.')
add('IT',['Industrial Production MoM'],it,'GS는 생산 구성 개선으로 3분기 성장 추적치를 소폭 높였다. 원문 종전 -1.0%와 원본 수정 -1.1%의 차이는 유지한다.')
jp=house('5d09f3','GS',1,'BOTTOM LINE: The domestic','June of last year.',
 'GS는 8월 기업물가의 전월비 -0.2% 전환을 에너지·쌀 가격 하락에서 찾았다. 다만 전년비 7.6%는 여전히 높고 기계류 가격 상승은 남아 있어 전방위 물가 완화로 보지 않았다.',
 'AI 비교: 이전 GS 프리뷰를 실제 발표 후 분석으로 갱신했다. 당월 하락과 높은 연간 상승률이 공존하며 환율·원자재 하락의 파급과 기계류 강세를 따로 봐야 한다.')
add('JP',['PPI MoM','PPI YoY'],jp,'GS 사후 분석은 에너지·쌀의 하락과 기계류 강세가 공존함을 확인했다. 당월 하락만으로 광범위한 가격 압력 해소를 선언하기 어렵다.')

for eid,r in updates.items():
    r['review_id']='comment-'+hashlib.sha256((eid+now).encode()).hexdigest()[:24]
    r['reviewed_on']='2026-09-16';r['reviewed_at']=now
    r['review_log']='2026-09-16: 5개 IB 지표명·동의어/국가/기간 후보 검색 후 채택 원문 페이지 전체와 기존 수치를 대조했다. 추가된 근거만 반영하고 미확보 하우스는 유지. 수집 BofA/JPM/GS/Citi 완료, HSBC 실패. 기존 작성물은 이력 보존. '+r['review_log']
    bundle['event_reviews'].append(r)
bundle['reviewed_on']='2026-09-16'
authpath.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
try:
    chosen, stale=b.load_authored_comments(c,b.load_calendar(pathlib.Path(manifest['inputs']['weco']['path'])),'2026-09-16')
    assert len(chosen)==130 and not stale
except Exception:
    authpath.write_bytes(original)
    raise
record={'started_at':now,'event_ids':list(updates),'updated_summaries':len(updates),'reviewed_pages':[dict(doc_id=d,page=p) for d,p in sorted(reviewed_pages)],'authored_before_sha256':hashlib.sha256(original).hexdigest(),'authored_after_sha256':hashlib.sha256(authpath.read_bytes()).hexdigest()}
(OUT/'review_result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'updated':len(updates),'pages':len(reviewed_pages),'valid_events':len(chosen),'stale':len(stale)}))
