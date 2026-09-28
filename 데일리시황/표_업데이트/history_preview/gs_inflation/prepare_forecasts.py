import hashlib, json, pathlib, sqlite3, sys
ROOT=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
OUT=pathlib.Path(__file__).resolve().parent
views=json.loads((OUT/'gs_us_inflation_views.json').read_text(encoding='utf-8'))['views']
v11=next(x for x in views if x['view_id'].endswith('20260911'))
v16=next(x for x in views if x['view_id'].endswith('20260916'))
base={'house':'GS','country':'US','indicator':'US_CORE_PCE','reference_period':'2026-08',
      'scenario':'base','review_status':'draft','origin':'assistant_review_of_local_reports'}
forecasts=[
  {**base,'forecast_id':'gs.us.core_pce.2026-08.mom.20260911','as_of':'2026-09-11','unit':'pct_mom','value':0.26,
   'qualifier':'8월 CPI 발표 후 PPI·CPI 항목을 반영한 근원 PCE 전월비 추정; 원문은 발표 직전 0.24%에서 상향. 9월 2일 초기 약 0.2% 전망과 직접 비교.',
   'evidence':v11['evidence'],'prior_forecast_id':'gs.us.core_pce.2026-08.mom.20260902','change':'revised'},
  {**base,'forecast_id':'gs.us.core_pce.2026-08.mom.20260916','as_of':'2026-09-16','unit':'pct_mom','value':0.27,
   'qualifier':'8월 수입물가 발표 후 국제항공료를 반영해 0.26%에서 0.27%로 상향한 근원 PCE 전월비 추정. 아직 확정 발표값 아님.',
   'evidence':[v16['evidence'][0]],'prior_forecast_id':'gs.us.core_pce.2026-08.mom.20260911','change':'revised'},
  {**base,'forecast_id':'gs.us.core_pce.2026-08.yoy.20260916','as_of':'2026-09-16','unit':'pct_yoy','value':3.17,
   'qualifier':'8월 근원 PCE 전년비 추정. 예정된 방법론 변경에 따른 과거치 수정 예상을 포함하며 확정 발표값 아님.',
   'evidence':[v16['evidence'][0]],'prior_forecast_id':None,'change':'uncompared'}]
bundle={'schema_version':1,'as_of':'2026-09-17','forecasts':forecasts}
path=OUT/'gs_us_inflation_forecasts.json';path.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
sys.path.insert(0,str(ROOT));import living_ib
src=living_ib.source_db(ROOT/'data/research.sqlite3');state=living_ib.source_db(ROOT/'data/living_ib.sqlite3')
living_ib.validate_forecasts(forecasts,src,living_ib.all_forecasts(state))
backup=OUT/'living_ib_before_forecasts.sqlite3'
if not backup.exists():
    target=sqlite3.connect(backup);state.backup(target);target.close()
print(json.dumps({'validated_forecasts':len(forecasts),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest()}))
src.close();state.close()
