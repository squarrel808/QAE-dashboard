import collections, copy, hashlib, importlib.util, json, pathlib, re, shutil, sqlite3, sys
from datetime import datetime
P=pathlib.Path(__file__).resolve().parent
BASE=pathlib.Path('데일리시황/표_업데이트').resolve()
R=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
sys.path.insert(0,str(R/'ecocal_dashboard'))
import build_dashboard as b
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
now=datetime.now().astimezone().isoformat(timespec='seconds')
baseline=read(P/'baseline.json');m=read(BASE/'latest.json');w=pathlib.Path(m['review_queue']).parent
s=P/'validated_WECO';inp=read(P/'input.json');book=pathlib.Path(inp['path']);res=read(P/'review_result.json')
assert sha(book)==inp['sha256']
for f,h in baseline['hashes'].items():
 if pathlib.Path(f).name!='authored_commentary.json':assert sha(pathlib.Path(f))==h,'Concurrent change: '+f
data=read(s/'dashboard_data.json');old=read(w/'dashboard_data.json');oldmap={e['id']:e for e in old['events']}
fresh={e['id']:e for e in b.load_calendar(book)}
assert len(data['events'])==len(old['events'])==247
assert len(fresh)==116
for e in data['events']:
 expected=fresh.get(e['id'],oldmap[e['id']])
 assert all(e.get(k)==expected.get(k) for k in list(b.FIELDS)+list(b.COMMENT_SNAPSHOT_FIELDS))
 if e['available_at_request']:
  assert e['commentary'] and e['commentary']['review_status']=='draft'
  assert all(e['commentary']['snapshot'][k]==e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS)
 else:assert not e['commentary']
 assert len(e['houses'])==5
meta=data['meta'];assert meta['available_at_request']==meta['authored_event_count']==194
assert meta['commentary_needs_recheck']==0
assert meta['macro_views']['view_payload_sha256']==m['weco']['macro_views']['view_payload_sha256']
collector=read(R.parent/'.collector/logs/latest_daily.json')
collector_report=read(pathlib.Path(collector['collector_report']))
write(P/'collector_snapshot.json',collector);write(P/'collector_report.json',collector_report)
scope='JPM 13개·Citi 9개 수집 완료. GS PDF 13개 확보·3개 실패, BofA timeout, HSBC PDF 5개 확보·3개 실패. 07:00 scheduled=false 로그이며 별도 06:30 작업 실행 여부는 이 로그만으로 확인하지 못함. 확보된 안정 원문으로 부분 갱신.'
note='2026-09-18 IB 지표 해석: 미작성 과거 지표 42개 추가·FOMC/TIC 4개 보강·기존 148개 유지. 누적 실제값 194개 요약은 모두 사용자 검토 전 초안. 최신 WECO 수치 발표일 9월 17일(새 수치 없음), 검색 DB 최신 보고서일 9월 17일, 거시 견해 자료일 9월 16일. 원문 전체 검토 완료를 뜻하지 않습니다.'
meta.update(actual_values_snapshot_date=max(e['date'] for e in data['events'] if e['available_at_request']),collection_scope=scope,interpretation_updated_events=46,interpretation_retained_events=148,generated_at=now)
encoded=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('</','<\\/')
(s/'dashboard_data.json').write_text(encoded,encoding='utf-8')
html=(R/'ecocal_dashboard/dashboard.html').read_text(encoding='utf-8').replace('__DASHBOARD_DATA__',encoded)
html=html.replace('<main>','<main><p class="foot">'+note+'</p><nav><a href="../../../index.html">메인 INDEX</a> · <a href="../index.html">실행별 INDEX</a></nav>',1)
(s/'index.html').write_text(html,encoding='utf-8')
macro=(s/'macro_views.html').read_text(encoding='utf-8');macro=re.sub(r'href="[^"]*">← INDEX 대시보드','href="../../../index.html">← INDEX 대시보드',macro)
macro=macro.replace('<h1>','<a href="../index.html">실행별 INDEX</a><h1>',1);(s/'macro_views.html').write_text(macro,encoding='utf-8')
queue=[];counts=collections.Counter()
for e in data['events']:
 if not e['available_at_request']:continue
 prev=oldmap.get(e['id']);status='new_actual' if prev is None or not prev['available_at_request'] else 'revised' if any(prev.get(k)!=e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS) else 'unchanged'
 item=copy.deepcopy(e);item['change_status']=status;queue.append(item);counts[status]+=1
write(s/'review_queue.json',dict(requested_at=now,mode='source_reviewed_ai_draft',events=queue))
val=read(s/'validation.json');val.update(input_numeric_match=True,historical_numeric_match=True,authored_events=194,commentary_needs_recheck=0,new_summaries=42,updated_summaries=4,retained_reviews=148,review_status='draft',macro_views_payload_unchanged=True)
write(s/'validation.json',val)
for page in ['index.html','macro_views.html']:
 t=(s/page).read_text(encoding='utf-8');assert '__DASHBOARD_DATA__' not in t and '__MACRO_VIEW_DATA__' not in t
 for href in re.findall(r'href="([^"]+)"',t):
  if href in ['index.html','macro_views.html','../index.html','../../../index.html']:assert (w/href).resolve().exists()
auth=R/'ecocal_dashboard/authored_commentary.json';previous=read(P/'authored_commentary.before.json');current=read(auth)
assert current['event_reviews'][:len(previous['event_reviews'])]==previous['event_reviews']
assert len(current['event_reviews'])==len(previous['event_reviews'])+46
inventory=read(P/'source_inventory.json')
for x in inventory:
 p=pathlib.Path(x['path']);assert x['stable'] and sha(p)==x['sha256']
targets=[w/f.name for f in s.iterdir() if f.is_file()]+[BASE/'latest.json',BASE/'index.html',w.parent/'manifest.json',w.parent/'index.html',R/'ecocal_dashboard/daily_interpretation_state.json']
before={str(f):sha(f) for f in targets if f.exists()};authhash=sha(auth);livinghash=sha(R/'data/living_ib.sqlite3')
backup=P/'published_before';assert not backup.exists(),'Duplicate publication';backup.mkdir()
for i,f in enumerate(targets):
 if f.exists():shutil.copy2(f,backup/(str(i)+'_'+f.name))
write(backup/'paths.json',{str(i)+'_'+f.name:str(f) for i,f in enumerate(targets)})
try:
 assert sha(book)==inp['sha256'] and sha(auth)==authhash
 for f,h in before.items():assert sha(pathlib.Path(f))==h,'Concurrent publication change'
 for f in s.iterdir():
  if f.is_file():shutil.copy2(f,w/f.name)
 m.update(weco=meta,weco_refreshed_at=now,commentary_written_at=now,new_ai_interpretations=True,queue_changes=dict(counts),interpretation_run=dict(status='published_partial_source_coverage',record=str(P/'run_record.json'),updated_events=46,completed_at=now))
 spec=importlib.util.spec_from_file_location('daily',BASE.parent/'update_daily_tables.py');daily=importlib.util.module_from_spec(spec);sys.modules['daily']=daily;spec.loader.exec_module(daily)
 for dest in [BASE/'index.html',w.parent/'index.html']:
  daily.render_index(m,[pathlib.Path(p) for p in m['outputs']],dest)
  t=dest.read_text(encoding='utf-8').replace('<h1>','<section id="ib-daily-interpretation"><p><b>'+note+'</b></p><p>'+scope+'</p></section><h1>',1).replace('요청 시점 '+m['requested_at'],'기존 표·가격 실행 시점 '+m['requested_at'])
  dest.write_text(t,encoding='utf-8')
 write(w.parent/'manifest.json',m);write(BASE/'latest.json',m)
 state=read(R/'ecocal_dashboard/daily_interpretation_state.json')
 state.setdefault('publication_history',[]).append({k:state.get(k) for k in ['last_successful_publication_at','input_sha256','run_record','reviewed_event_ids','reviewed_evidence_pages']})
 state.update(last_successful_publication_at=now,status='published_partial_source_coverage',input_sha256=inp['sha256'],reviewed_event_ids=res['updated_events'],reviewed_evidence_pages=res['adopted_pages'],completed_document_ids=[],run_record=str(P/'run_record.json'))
 state['operating_rule']='확보된 안정 자료로 계속 갱신. 숫자 기준일과 해석일 분리. 채택하지 않은 원문·페이지는 완료 처리하지 않음.'
 write(R/'ecocal_dashboard/daily_interpretation_state.json',state)
 for f in s.iterdir():
  if f.is_file():assert sha(f)==sha(w/f.name)
 assert sha(R/'data/living_ib.sqlite3')==livinghash
 for page in [BASE/'index.html',w.parent/'index.html']:
  t=page.read_text(encoding='utf-8');assert 'WECO/index.html' in t and 'WECO/macro_views.html' in t
except Exception:
 for i,f in enumerate(targets):
  saved=backup/(str(i)+'_'+f.name)
  if saved.exists():shutil.copy2(saved,f)
 if sha(auth)==authhash:shutil.copy2(P/'authored_commentary.before.json',auth)
 raise
record=dict(automation_id='qae-ib-07-20',completed_at=now,status='published_partial_source_coverage',input=inp,actual_values_snapshot_date=meta['actual_values_snapshot_date'],collector=collector_report,collection_scope=scope,ingested_documents=40,ingested_pages=345,new_summaries=42,revised_summaries=4,updated_summaries=46,retained_summaries=148,valid_summaries=194,house_comments=meta['authored_house_count'],reviewed_event_ids=res['updated_events'],reviewed_evidence_pages=res['adopted_pages'],whole_documents_completed=[],validation=val,queue_changes=dict(counts),living_db_unchanged=True,history_facts_unchanged=True,publication_paths=[str(BASE/'index.html'),str(w/'index.html'),str(w/'macro_views.html')],limitations=['신규 PDF 40개 적재는 전체 의미 검토 완료가 아님. FOMC/TIC 등 채택된 페이지·지표 연결만 완료.','42개 누적 미작성 지표를 현재 보존된 스냅샷 기준으로 작성. 직접 근거 없는 하우스는 미확보.','9월 17일 미국 청구·주택 및 영국 정책결정 등 새 보고서의 수치를 WECO 실제값에 대신 입력하지 않음.','GS/Citi FOMC 및 GS TIC 표지 9월 16일과 메타데이터 9월 17일 차이를 코멘트 제한에 명시.','7~8월/속보·최종/전체·세부 통계 범위가 다른 자료는 관련 분석 또는 미채택.','오늘 HSBC 확보는 실제 로그로 확인했으나 수집 전체는 미완료. BofA 과거 9월 4일 캐나다 자료만 사용.'],uncovered_event_houses=[dict(event_id=e['id'],houses=[h for h in b.HOUSES if h not in {x['house'] for x in e['commentary']['houses']}]) for e in data['events'] if e['available_at_request']],published_hashes={str(w/f.name):sha(w/f.name) for f in s.iterdir() if f.is_file()})
write(P/'run_record.json',record)
print(json.dumps(dict(published=str(BASE/'index.html'),new=42,revised=4,total=194,house_comments=meta['authored_house_count'],numeric_date=meta['actual_values_snapshot_date']),ensure_ascii=False))
