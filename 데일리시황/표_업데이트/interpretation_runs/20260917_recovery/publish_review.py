import collections, copy, hashlib, importlib.util, json, pathlib, re, shutil, sys
from datetime import datetime
P=pathlib.Path(__file__).resolve().parent
BASE=pathlib.Path('데일리시황/표_업데이트').resolve()
ROOT=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
sys.path.insert(0,str(ROOT/'ecocal_dashboard'))
import build_dashboard as b
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
now=datetime.now().astimezone().isoformat(timespec='seconds')
m=read(BASE/'latest.json');w=pathlib.Path(m['review_queue']).parent;s=P/'validated_WECO';inp=read(P/'input.json');book=pathlib.Path(inp['path'])
assert sha(book)==inp['sha256'],'Input changed; stop before publication'
data=read(s/'dashboard_data.json');old=read(w/'dashboard_data.json');res=read(P/'review_result.json')
events=b.load_calendar(book);fresh={e['id']:e for e in events}
assert len(fresh)==116 and len(data['events'])==116
assert data['meta']['workbook_sha256']==inp['sha256']
for e in data['events']:
 assert all(e.get(k)==fresh[e['id']].get(k) for k in list(b.FIELDS)+list(b.COMMENT_SNAPSHOT_FIELDS))
 if e['available_at_request']:
  assert e['commentary'] and e['commentary']['review_status']=='draft'
  assert all(e['commentary']['snapshot'][k]==e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS)
 else:assert not e['commentary']
 assert len(e['houses'])==5
meta=data['meta'];assert meta['available_at_request']==meta['authored_event_count']==63
assert meta['commentary_needs_recheck']==0
assert meta['macro_views']['view_payload_sha256']==m['weco']['macro_views']['view_payload_sha256']
scope='JPM·Citi 수집 완료; GS 확보 PDF 15개 사용 가능하나 실패 1건으로 수집 미완료; BofA timeout. HSBC는 이번 실제 로그에서 PDF 9개 확보 확인. 전체 수집 완료를 가정하지 않고 확보 자료로 계속 갱신.'
meta.update(actual_values_snapshot_date=max(e['date'] for e in data['events'] if e['available_at_request']),collection_scope=scope,interpretation_updated_events=26,interpretation_retained_events=37,generated_at=now)
note='2026-09-17 WECO·IB 해석 갱신: 최신 원본의 실제값 63개 · 요약 26개 새 작성/재검토, 일치하는 37개 유지 · 사용자 검토 전 초안. 수치 최신 발표일 9월 17일, IB 검색 자료 최신일 9월 16일. 일부 수집 실패는 미확보로 남기고 확보 자료로 반영했습니다.'
encoded=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('</','<\\/')
(s/'dashboard_data.json').write_text(encoded,encoding='utf-8')
html=(ROOT/'ecocal_dashboard/dashboard.html').read_text(encoding='utf-8').replace('__DASHBOARD_DATA__',encoded)
html=html.replace('<main>','<main><p class="foot">'+note+'</p><nav><a href="../../../index.html">메인 INDEX</a> · <a href="../index.html">실행별 INDEX</a></nav>',1)
(s/'index.html').write_text(html,encoding='utf-8')
macro=(s/'macro_views.html').read_text(encoding='utf-8');macro=re.sub(r'href="[^"]*">← INDEX 대시보드','href="../../../index.html">← INDEX 대시보드',macro)
macro=macro.replace('<h1>','<a href="../index.html">실행별 INDEX</a><h1>',1);(s/'macro_views.html').write_text(macro,encoding='utf-8')
oldmap={e['id']:e for e in old['events']};queue=[];counts=collections.Counter()
for e in data['events']:
 if not e['available_at_request']:continue
 prev=oldmap.get(e['id']);status='new_actual' if prev is None or not prev['available_at_request'] else 'revised' if any(prev.get(k)!=e.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS) else 'unchanged'
 item=copy.deepcopy(e);item['change_status']=status;queue.append(item);counts[status]+=1
write(s/'review_queue.json',dict(requested_at=now,mode='source_reviewed_ai_draft',events=queue))
val=read(s/'validation.json');val.update(input_numeric_match=True,authored_events=63,commentary_needs_recheck=0,new_reviewed_events=26,retained_reviews=37,review_status='draft',macro_views_payload_unchanged=True)
write(s/'validation.json',val)
for page in ['index.html','macro_views.html']:
 t=(s/page).read_text(encoding='utf-8');assert '__DASHBOARD_DATA__' not in t and '__MACRO_VIEW_DATA__' not in t
 for href in re.findall(r'href="([^"]+)"',t):
  if href in ['index.html','macro_views.html','../index.html','../../../index.html']:assert (w/href).resolve().exists()
targets=[w/f.name for f in s.iterdir() if f.is_file()]+[BASE/'latest.json',BASE/'index.html',w.parent/'manifest.json',w.parent/'index.html',ROOT/'ecocal_dashboard/daily_interpretation_state.json']
before={str(f):sha(f) for f in targets if f.exists()};livinghash=sha(ROOT/'data/living_ib.sqlite3')
backup=P/'published_before';assert not backup.exists(),'Already published; inspect audit';backup.mkdir()
for i,f in enumerate(targets):
 if f.exists():shutil.copy2(f,backup/(str(i)+'_'+f.name))
write(backup/'paths.json',{str(i)+'_'+f.name:str(f) for i,f in enumerate(targets)})
try:
 assert sha(book)==inp['sha256']
 for f,h in before.items():assert sha(pathlib.Path(f))==h,'Concurrent publication change'
 for f in s.iterdir():
  if f.is_file():shutil.copy2(f,w/f.name)
 m['inputs']['weco']=dict(path=str(book),name=book.name,sha256=inp['sha256'],modified=datetime.fromtimestamp(book.stat().st_mtime).astimezone().isoformat(timespec='seconds'))
 m.update(weco=meta,weco_refreshed_at=now,commentary_written_at=now,new_ai_interpretations=True,queue_changes=dict(counts),interpretation_run=dict(status='published_partial_source_coverage',record=str(P/'run_record.json'),updated_events=26,completed_at=now))
 spec=importlib.util.spec_from_file_location('daily',BASE.parent/'update_daily_tables.py');daily=importlib.util.module_from_spec(spec);sys.modules['daily']=daily;spec.loader.exec_module(daily)
 for dest in [BASE/'index.html',w.parent/'index.html']:
  daily.render_index(m,[pathlib.Path(p) for p in m['outputs']],dest)
  t=dest.read_text(encoding='utf-8').replace('<h1>','<section id="ib-daily-interpretation"><p><b>'+note+'</b></p><p>'+scope+'</p></section><h1>',1).replace('요청 시점 '+m['requested_at'],'기존 표·가격 실행 시점 '+m['requested_at'])
  dest.write_text(t,encoding='utf-8')
 write(w.parent/'manifest.json',m);write(BASE/'latest.json',m)
 state=read(ROOT/'ecocal_dashboard/daily_interpretation_state.json')
 state.setdefault('publication_history',[]).append({k:state.get(k) for k in ['last_successful_publication_at','input_sha256','run_record']})
 state.update(last_successful_publication_at=now,status='published_partial_source_coverage',input_sha256=inp['sha256'],reviewed_event_ids=res['updated_events'],reviewed_evidence_pages=res['adopted_pages'],completed_document_ids=[],run_record=str(P/'run_record.json'))
 state['operating_rule']='일부 수집 실패 또는 새 WECO 없음으로 중단하지 않고 현재 숫자와 확보 근거로 갱신. 숫자 기준일과 해석일 분리.'
 write(ROOT/'ecocal_dashboard/daily_interpretation_state.json',state)
 for f in s.iterdir():
  if f.is_file():assert sha(f)==sha(w/f.name)
 assert sha(ROOT/'data/living_ib.sqlite3')==livinghash
except Exception:
 for i,f in enumerate(targets):
  saved=backup/(str(i)+'_'+f.name)
  if saved.exists():shutil.copy2(saved,f)
 raise
record=dict(automation_id='qae-ib-07-20',completed_at=now,status='published_partial_source_coverage',supersedes='20260917_0720 deferred decision corrected by user',input=inp,actual_values_snapshot_date=meta['actual_values_snapshot_date'],collector=read(ROOT.parent/'.collector/logs/latest_daily.json'),collection_scope=scope,updated_summaries=26,retained_summaries=37,valid_summaries=63,house_comments=meta['authored_house_count'],reviewed_event_ids=res['updated_events'],reviewed_evidence_pages=res['adopted_pages'],whole_documents_completed=[],validation=val,queue_changes=dict(counts),living_db_unchanged=True,publication_paths=[str(BASE/'index.html'),str(w/'index.html'),str(w/'macro_views.html')],limitations=['IB 직접 근거 없는 지표는 수치 기반 AI 초안만 작성; 하우스 미확보 유지.','JPM FOMC 사후 보고서는 달력 날짜 차이로 관련 분석 분류, 실제 시점 제한 명시.','현재 원본 범위 밖의 이전 지표는 authored 이력과 게시 전 백업에 보존.','미검토 페이지를 완료로 기록하지 않음.'],published_hashes={str(w/f.name):sha(w/f.name) for f in s.iterdir() if f.is_file()})
write(P/'run_record.json',record)
print(json.dumps({'published':str(BASE/'index.html'),'actuals':63,'new_reviews':26,'retained':37,'house_comments':meta['authored_house_count'],'numeric_date':meta['actual_values_snapshot_date'],'queue_changes':dict(counts)},ensure_ascii=False))
