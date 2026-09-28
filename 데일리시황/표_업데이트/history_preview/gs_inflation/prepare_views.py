import hashlib, json, pathlib, re, sqlite3, sys

ROOT=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
OUT=pathlib.Path(__file__).resolve().parent
src=sqlite3.connect(ROOT/'data/research.sqlite3')
src.row_factory=sqlite3.Row

def ref(prefix,page,start,end):
    doc_id=src.execute('select doc_id from documents where doc_id like ?',(prefix+'%',)).fetchone()[0]
    text=src.execute('select text from pages where doc_id=? and page=?',(doc_id,page)).fetchone()[0]
    sm=re.search(r'\s+'.join(map(re.escape,start.split())),text)
    assert sm,start
    em=re.search(r'\s+'.join(map(re.escape,end.split())),text[sm.start():])
    assert em,end
    return {'doc_id':doc_id,'page':page,'quote':text[sm.start():sm.start()+em.end()]}

base={'house':'GS','country':'US','scope':'country_research','review_status':'draft','origin':'assistant_review_of_local_reports'}
def view(ident,track,date,summary,evidence,prior,change,change_note,assumptions,questions,limits):
    return {**base,'view_id':ident,'track':track,'effective_date':date,'summary':summary,'assumptions':assumptions,
            'watch':['US_CORE_CPI','US_CORE_PCE'],'analyst_questions':questions,'limitations':limits,
            'evidence':evidence,'prior_view_id':prior,'change':change,'change_note':change_note}

v1=view('GS-US-inflation.outlook-20260911','inflation.outlook','2026-09-11',
 '8월 근원 CPI가 전월비 0.29%로 예상보다 높게 나오자, 무선통신료·여행서비스 강세와 완만한 주거비를 구분했다. CPI·PPI 세부항목을 반영한 8월 근원 PCE 추정치를 0.24%에서 0.26%로 높였다.',
 [ref('fe41dc',1,'BOTTOM LINE: Core CPI increased','year-over-year rate of +3.16%')],
 None,'uncompared','새 물가 경로의 첫 저장 견해. 9월 2일의 물가 발표 전 약 0.2% 예상과 시점을 구별하며 같은 트랙의 저장 선행 견해는 없다.',
 ['8월 CPI·PPI 세부항목을 이용한 근원 PCE 추정이며 확정 발표값이 아니다.'],
 ['무선통신료 상승이 되돌아오는가?','주거비 둔화가 지속되는가?'],
 ['원문 발행일 9월 11일. CPI 실측과 아직 발표되지 않은 PCE 추정을 구별한다.'])
v2=view('GS-US-inflation.trend-20260914','inflation.trend','2026-09-14',
 'GS는 목표 2%를 웃도는 물가를 주로 한시적 요인으로 보고, 최근 3개월 근원 PCE 상승 속도가 약 2.5%로 낮아진 점과 기대인플레이션의 즉각적인 이탈 위험이 낮다는 점을 강조했다. 다만 관세 영향으로 상승이 광범위해 보인다고 평가했다.',
 [ref('ff3282',1,'We do not see a strong economic case','raising rates.')],
 None,'uncompared','동일 미국 물가 추세 트랙의 선행 저장 견해가 없어 이력 연결을 만들지 않았다.',
 ['한시적 요인의 효과가 약해지고 최근 근원 PCE 둔화가 지속된다는 판단이다.'],
 ['관세·에너지 충격의 파급이 예상보다 길어지는가?','근원 PCE의 3개월 속도가 다시 높아지는가?'],
 ['원문 표지 9월 13일 밤 EDT, 수집 메타데이터 발행일 9월 14일을 기준일로 썼다. 9월 16일 한 달 수치 추정 변경이 이 중기 판단의 철회를 뜻한다는 근거는 없다.'])
v3=view('GS-US-inflation.outlook-20260916','inflation.outlook','2026-09-16',
 '8월 근원 수입물가가 예상보다 높고 해외여행비에 반영되는 국제항공료가 2.1% 오르자, GS는 8월 근원 PCE 전월비 추정을 0.26%에서 0.27%, 전년비 추정을 3.17%로 높였다. 전자제품 가격도 올해 근원물가의 상방 압력으로 봤다.',
 [ref('8e0382',1,'Core import prices rose 0.8% in August','year-over-year rate of +3.17%.'),
  ref('8e0382',2,'3. Core import prices rose 0.8%','2.1% (SA by GS).')],
 v1['view_id'],'revised','9월 11일 CPI 직후 근원 PCE 추정 0.26%를 9월 16일 수입물가 반영 후 0.27%로 0.01%p 상향했다. 두 원문을 직접 대조했다.',
 ['8월 근원 PCE 발표 전 추정치이며, 방법론 변경에 따른 과거치 수정 전망을 포함한다.'],
 ['확정 8월 근원 PCE가 0.27% 추정과 일치하는가?','국제항공료와 전자제품 가격 압력이 다른 품목으로 확산되는가?'],
 ['9월 16일 원문에 근거한 8월 한 달 추정과 올해 전자제품 가격 위험이다. 중장기 물가 경로 전체의 새로운 수치 전망으로 확대하지 않는다.'])

bundle={'schema_version':1,'as_of':'2026-09-17','source_snapshot_documents':3551,
        'scope_note':'사용자 요청에 따른 GS 미국 물가 하우스뷰 누락 보완. 9월 11일·14일·16일 원문 페이지 검토. 모두 검토 전 초안.',
        'views':[v1,v2,v3]}
path=OUT/'gs_us_inflation_views.json';path.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
sys.path.insert(0,str(ROOT));import living_ib
state=sqlite3.connect(ROOT/'data/living_ib.sqlite3')
state.row_factory=sqlite3.Row
living_ib.validate_views(bundle['views'],src,living_ib.all_views(state))
backup=OUT/'living_ib_before.sqlite3'
if not backup.exists():
    target=sqlite3.connect(backup);state.backup(target);target.close()
print(json.dumps({'validated_views':len(bundle['views']),'source_pages':sum(len(x['evidence']) for x in bundle['views']),
                  'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest()},ensure_ascii=False))
state.close();src.close()
