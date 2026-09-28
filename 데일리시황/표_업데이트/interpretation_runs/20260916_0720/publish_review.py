import collections, copy, hashlib, json, os, pathlib, re, shutil, sqlite3, sys
from datetime import datetime
P=pathlib.Path(__file__).resolve().parent
BASE=pathlib.Path('데일리시황/표_업데이트').resolve()
ROOT=pathlib.Path('데일리시황/Context/_macro/Research_Context').resolve()
sys.path.insert(0,str(ROOT/'ecocal_dashboard'))
import build_dashboard as b
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
now=datetime.now().astimezone().isoformat(timespec='seconds')
m=read(BASE/'latest.json');w=pathlib.Path(m['review_queue']).parent;s=P/'validated_WECO'
hashes=read(P/'before_publish_hashes.json')
for name,h in hashes.items():assert sha(pathlib.Path(name))==h, 'Concurrent change: '+name
book=pathlib.Path(m['inputs']['weco']['path']);assert sha(book)==m['inputs']['weco']['sha256']
data=read(s/'dashboard_data.json');old=read(w/'dashboard_data.json')
c=sqlite3.connect((ROOT/'data/research.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
selected,stale=b.load_authored_comments(c,b.load_calendar(book),'2026-09-16');assert not stale
refs={x['doc_id']:x for x in data['sources']}
for e in data['events']:
    prev=next(x for x in old['events'] if x['id']==e['id'])
    assert all(e.get(k)==prev.get(k) for k in b.COMMENT_SNAPSHOT_FIELDS)
    if e['id'] not in selected:continue
    e['commentary']=selected[e['id']]
    for h in e['houses']:
        h['commentary']=next((x for x in e['commentary']['houses'] if x['house']==h['house']),None)
        if h['commentary']:
            h['status']=h['commentary']['kind'];h['interpretation_status']='source_reviewed_draft'
            for ref in h['commentary']['evidence']:refs[ref['doc_id']]=ref
data['sources']=list(refs.values());meta=data['meta'];meta['source_documents']=len(refs)
counts=collections.Counter(h['status'] for e in data['events'] for h in e['houses'])
meta['comment_counts']=dict(counts);meta['generated_at']=now
meta['actual_values_snapshot_date']='2026-09-15'
meta['collection_scope']='BofA/JPM/GS/Citi 완료; HSBC timeout 미완료. 07:00 실행 로그 기준이며 06:30 예정 작업 실행 여부와 동일시하지 않음.'
meta['interpretation_updated_events']=32
note='2026-09-16 IB 해석: 32개 지표 보강 · 사용자 검토 전 초안. BofA·JPM·GS·Citi 수집 완료, HSBC 미완료. 지표 숫자는 9월 15일 원본 그대로이며 신규 숫자 갱신이 아닙니다. 미검토 원문은 검토 대기로 유지합니다.'
encoded=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('</','<\\/')
(s/'dashboard_data.json').write_text(encoded,encoding='utf-8')
html=(ROOT/'ecocal_dashboard/dashboard.html').read_text(encoding='utf-8').replace('__DASHBOARD_DATA__',encoded)
html=html.replace('<main>','<main><p class="foot">'+note+'</p><nav><a href="../../../index.html">메인 INDEX</a> · <a href="../index.html">실행별 INDEX</a></nav>',1)
(s/'index.html').write_text(html,encoding='utf-8')
macro=(s/'macro_views.html').read_text(encoding='utf-8')
macro=re.sub(r'href="[^"]*">← INDEX 대시보드', 'href="../../../index.html">← INDEX 대시보드',macro)
macro=macro.replace('<h1>','<a href="../index.html">실행별 INDEX</a><h1>',1)
(s/'macro_views.html').write_text(macro,encoding='utf-8')
queue={'requested_at':now,'mode':'source_reviewed_ai_draft','events':[]}
for e in data['events']:
    if e['available_at_request']:
        item=copy.deepcopy(e);item['change_status']='unchanged';queue['events'].append(item)
write(s/'review_queue.json',queue)
val=read(s/'validation.json');val.update(status_counts=dict(counts),numeric_snapshots_unchanged=True,authored_events=len(selected),commentary_needs_recheck=0,review_status='draft',new_reviewed_events=32,collection_partial=True)
write(s/'validation.json',val)
assert meta['macro_views']['view_payload_sha256']==m['weco']['macro_views']['view_payload_sha256']
assert len(data['events'])==259 and len(queue['events'])==130
for page in ['index.html','macro_views.html']:
    text=(s/page).read_text(encoding='utf-8');assert '__DASHBOARD_DATA__' not in text and '__MACRO_VIEW_DATA__' not in text
    for href in re.findall(r'href="([^"]+)"',text):
        if href in ['index.html','macro_views.html','../index.html','../../../index.html']:assert (w/href).resolve().exists()
result=read(P/'review_result.json');changed=set(result['event_ids'])
new=read(P/'new_document_inventory.json')
pages={(x['doc_id'],x['page']) for e in data['events'] if e['id'] in changed for h in e['commentary']['houses'] for x in h['reviewed_pages'] if any(d['doc_id']==x['doc_id'] for d in new)}
reviewed_docs={d for d,p in pages}
audit={'automation_id':'qae-ib-07-20','finished_at':now,'status':'published_partial_coverage','input_sha256':sha(book),'actual_values_snapshot_date':'2026-09-15','actual_release_max':max(e['date'] for e in queue['events']),'collector':read(ROOT.parent/'.collector/logs/latest_daily.json'),'input_numbers_changed':False,'indexed_documents_added':76,'indexed_not_equivalent_to_reviewed':True,'updated_summary_count':32,'new_event_count':0,'valid_summary_count':130,'house_comments_before':137,'house_comments_after':meta['authored_house_count'],'reviewed_event_ids':sorted(changed),'new_evidence_pages':[{'doc_id':d,'page':p} for d,p in sorted(pages)],'documents_with_unreviewed_pages':sorted(d['doc_id'] for d in new),'documents_without_adopted_evidence':sorted(d['doc_id'] for d in new if d['doc_id'] not in reviewed_docs),'validation':val,'publication_paths':[str(w/'index.html'),str(w/'macro_views.html')],'limitations':['HSBC 당일 수집 실패; 신규 근거 미확보 하우스는 유지.','76개 적재 중 채택 근거는 일부 페이지이며 전체 보고서 검토 완료가 아님.','BofA Japan Capital Goods 표지 9월16일/메타데이터 9월15일 충돌: 이번 지표 근거에 미채택.','GS PPI·Citi 주택/심리·후속 CPI/ECB의 원문 표지일과 DB 날짜 차이는 코멘트에 명시.']}
write(P/'run_record.json',audit)
write(P/'review_result.json',{**result,'finished_at':now,'authored_after_sha256':sha(ROOT/'ecocal_dashboard/authored_commentary.json'),'new_evidence_pages':audit['new_evidence_pages']})
# All validations have passed. Back up every file before replacing the published version.
targets=[w/f.name for f in s.iterdir() if f.is_file()]+[BASE/'latest.json',BASE/'index.html',w.parent/'manifest.json',w.parent/'index.html']
backup=P/'published_before';backup.mkdir(exist_ok=True)
for f in targets:
    if f.exists():
        dest=backup/f.relative_to(BASE);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
try:
    for f in s.iterdir():
        if f.is_file():shutil.copy2(f,w/f.name)
    m['weco']=meta;m['weco_refreshed_at']=now;m['commentary_written_at']=now
    m['new_ai_interpretations']=True;m['interpretation_run']={'status':audit['status'],'record':str(P/'run_record.json'),'updated_events':32,'completed_at':now}
    m['queue_changes']={'new_actual':0,'revised':0,'unchanged':130}
    for f in [BASE/'index.html',w.parent/'index.html']:
        t=f.read_text(encoding='utf-8');t=re.sub(r'<section id="ib-daily-interpretation">.*?</section>','',t,flags=re.S)
        t=t.replace('<h1>','<section id="ib-daily-interpretation"><p><b>'+note+'</b></p></section><h1>',1)
        t=t.replace('IB 원문 요약·비교 코멘트 137건','IB 원문 요약·비교 코멘트 166건')
        f.write_text(t,encoding='utf-8')
    write(w.parent/'manifest.json',m);write(BASE/'latest.json',m)
    assert read(BASE/'latest.json')['weco']['authored_house_count']==166
    for f in s.iterdir():
        if f.is_file():assert sha(f)==sha(w/f.name)
except Exception:
    for f in targets:
        saved=backup/f.relative_to(BASE)
        if saved.exists():shutil.copy2(saved,f)
    raise
state={'schema_version':1,'last_successful_publication_at':now,'status':'published_partial_coverage','input_sha256':sha(book),'reviewed_event_ids':sorted(changed),'reviewed_evidence_pages':audit['new_evidence_pages'],'pending_document_ids':audit['documents_with_unreviewed_pages'],'completed_document_ids':[],'run_record':str(P/'run_record.json')}
write(ROOT/'ecocal_dashboard/daily_interpretation_state.json',state)
print(json.dumps({'published':str(BASE/'index.html'),'updated_events':32,'adopted_new_documents':len(reviewed_docs),'adopted_new_pages':len(pages),'valid_events':130,'house_comments':166,'validation':'passed'},ensure_ascii=False))
