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
assert len(data['events'])==len(old['events'])==253
assert len(fresh)==96
for e in data['events']:
 expected=fresh.get(e['id'],oldmap[e['id']])
 assert all(e.get(k)==expected.get(k) for k in list(b.FIELDS)+list(b.COMMENT_SNAPSHOT_FIELDS))
 if e['available_at_request']:
  assert e['commentary'] and e['commentary']['review_status']=='draft'
  assert all(e['commentary']['snapshot'][k]==e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS)
 else:assert not e['commentary']
 assert len(e['houses'])==5
meta=data['meta'];assert meta['available_at_request']==meta['authored_event_count']==212
assert meta['commentary_needs_recheck']==0
assert meta['macro_views']['view_payload_sha256']==m['weco']['macro_views']['view_payload_sha256']
collector=read(R.parent/'.collector/logs/latest_daily.json')
collector_report=read(pathlib.Path(collector['collector_report']))
write(P/'collector_snapshot.json',collector);write(P/'collector_report.json',collector_report)
scope='9월 22일 07:00 수집은 07:17 종료: JPM 4·Citi 5개 완료, GS 9개 확보·3개 실패, BofA 시간초과. HSBC는 실제 로그상 6개 확보·1개 실패·원문 없음 3개로 미완료(문서상 네 하우스 범위와 구분). scheduled=false이므로 별도 06:30 수집 완료는 확인하지 못함. 안정 원문 24개 추가 적재.'
note='2026-09-22 IB 지표 해석: 신규 18개·수정 4개·기존 190개 유지, 총 212개 사용자 검토 전 초안. 수치 최신 발표일 9월 18일, 원본 파일 저장일 9월 21일, 오늘 해석·게시일 9월 22일. 검색 DB 최신 자료일 9월 21일, 거시 견해 자료일 9월 16일. 원문 24개 적재는 전체 의미 검토 완료가 아닙니다.'
meta.update(actual_values_snapshot_date=max(e['date'] for e in data['events'] if e['available_at_request']),collection_scope=scope,interpretation_updated_events=22,interpretation_retained_events=190,generated_at=now)
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
val=read(s/'validation.json');val.update(input_numeric_match=True,historical_numeric_match=True,authored_events=212,commentary_needs_recheck=0,new_summaries=18,updated_summaries=22,retained_reviews=190,review_status='draft',macro_views_payload_unchanged=True)
write(s/'validation.json',val)
for page in ['index.html','macro_views.html']:
 t=(s/page).read_text(encoding='utf-8');assert '__DASHBOARD_DATA__' not in t and '__MACRO_VIEW_DATA__' not in t
 for href in re.findall(r'href="([^"]+)"',t):
  if href in ['index.html','macro_views.html','../index.html','../../../index.html']:assert (w/href).resolve().exists()
auth=R/'ecocal_dashboard/authored_commentary.json';previous=read(P/'authored_commentary.before.json');current=read(auth)
assert current['event_reviews'][:len(previous['event_reviews'])]==previous['event_reviews']
assert len(current['event_reviews'])==len(previous['event_reviews'])+22
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
 m.update(weco=meta,weco_refreshed_at=now,commentary_written_at=now,new_ai_interpretations=True,queue_changes=dict(counts),interpretation_run=dict(status='published_partial_source_coverage',record=str(P/'run_record.json'),updated_events=22,completed_at=now))
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
record=dict(automation_id='qae-ib-07-20',completed_at=now,status='published_partial_source_coverage',input=inp,actual_values_snapshot_date=meta['actual_values_snapshot_date'],collector=collector_report,collection_scope=scope,ingested_documents=24,ingested_pages=256,new_summaries=18,revised_summaries=4,updated_summaries=22,retained_summaries=190,valid_summaries=212,house_comments=meta['authored_house_count'],reviewed_event_ids=res['updated_events'],reviewed_evidence_pages=res['adopted_pages'],whole_documents_completed=[],validation=val,queue_changes=dict(counts),living_db_unchanged=True,history_facts_unchanged=True,publication_paths=[str(BASE/'index.html'),str(w/'index.html'),str(w/'macro_views.html')],limitations=['신규 원문 24개는 검색 DB 적재이며 전체 페이지 의미 검토 완료가 아님. 채택 페이지와 이벤트만 완료 기록.', '일본 해외채권 매입·캐나다 산업제품가격·미국 선행지수는 직접 IB 근거 미확보로 수치 기반 AI 초안. 다른 미확보 하우스도 공백 유지.', 'GS 글로벌 정책표는 표지 9월 20일 EDT·메타데이터 9월 21일. 기존 미국 10월 전망과 달리 12월을 명시하나 변경 사유는 미국 전용 후속 보고서 재확인 필요.', 'GS 유로존 3.25%와 WECO 3.2%는 표시 정밀도 차이를 명시. HSBC BOJ 1쪽 hold 오기는 2쪽 인상 설명과 대조해 제한 기록.', '스케줄러 HTML은 프로젝트 밖 쓰기 권한이 없어 갱신 실패. QAE 전용 모니터 로그는 유지.', '한국 20일 수출 등 새 원문 수치는 ecocal 실제값에 임의 추가하지 않음. 신규 보고서의 다른 지표·미독 페이지는 완료로 처리하지 않음.'],uncovered_event_houses=[dict(event_id=e['id'],houses=[h for h in b.HOUSES if h not in {x['house'] for x in e['commentary']['houses']}]) for e in data['events'] if e['available_at_request']],published_hashes={str(w/f.name):sha(w/f.name) for f in s.iterdir() if f.is_file()})
record['monitor_run_id']='20260922_072137_codex'
record['recheck_items']=['GS US October versus December next-hike timing: latest global report adopted with limitation; US dedicated follow-up needed']
write(P/'run_record.json',record)
print(json.dumps(dict(published=str(BASE/'index.html'),new=18,revised=4,total=212,house_comments=meta['authored_house_count'],numeric_date=meta['actual_values_snapshot_date']),ensure_ascii=False))
