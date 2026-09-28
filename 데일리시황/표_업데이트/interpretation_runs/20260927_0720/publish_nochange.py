import hashlib, json, shutil
from datetime import datetime
from pathlib import Path

ROOT=Path(r"C:\Users\infomax\Documents\python\QAE"); BASE=ROOT/"데일리시황/표_업데이트"
RUN=BASE/"interpretation_runs/20260927_0720"; SRC=RUN/"candidates_WECO"; LATEST=BASE/"latest.json"
RC=ROOT/"데일리시황/Context/_macro/Research_Context"; COLLECTOR=ROOT/"데일리시황/Context/_macro/.collector/logs/latest_daily.json"
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

latest_before=LATEST.read_bytes(); latest=read(LATEST); target=Path(latest["review_queue"]).parent
manifest_path=target.parent/"manifest.json"; manifest_before=manifest_path.read_bytes()
old_data=read(target/"dashboard_data.json"); new_data=read(SRC/"dashboard_data.json"); meta=new_data["meta"]
assert meta["workbook_sha256"]==latest["inputs"]["weco"]["sha256"]
assert len(old_data["events"])==len(new_data["events"])==261
fields=("country","date","time","event","period","survey","actual","prior","revised","scale","currency","unit")
assert {e["id"]:tuple(e.get(k) for k in fields) for e in old_data["events"]}=={e["id"]:tuple(e.get(k) for k in fields) for e in new_data["events"]}
assert meta["authored_event_count"]==213 and meta["authored_house_count"]==250 and meta["commentary_needs_recheck"]==0
assert old_data["meta"]["macro_views"]["view_payload_sha256"]==meta["macro_views"]["view_payload_sha256"]
assert "최근 3일 업데이트" in (SRC/"index.html").read_text(encoding="utf-8")
by_id={e["id"]:e for e in new_data["events"]}; old_queue=read(target/"review_queue.json")["events"]; queue=[]
for old in old_queue:
    event=dict(by_id[old["id"]]); event.update(change_status="unchanged",changed_fields=[],previous_actual=event.get("actual"),observed_at=meta["generated_at"],review_status="source_reviewed_ai_draft" if event.get("commentary") else old.get("review_status","awaiting_manual_or_requested_ai_review")); queue.append(event)
write(SRC/"review_queue.json",{"requested_at":meta["generated_at"],"mode":"source_reviewed_commentary","events":queue})
validation=read(SRC/"validation.json"); validation.update(input_numeric_match=True,authored_events=213,authored_house_comments=250,commentary_needs_recheck=0,new_summaries=0,updated_summaries=0,retained_reviews=213,review_status="draft",macro_views_payload_unchanged=True,recent_three_day_overview_preserved=True,reviewed_new_documents=3,eligible_commentary_changes=0); write(SRC/"validation.json",validation)
assert LATEST.read_bytes()==latest_before and manifest_path.read_bytes()==manifest_before
backup=RUN/"published_before"; backup.mkdir(exist_ok=True)
paths=[LATEST,manifest_path,*[target/n for n in ("index.html","dashboard_data.json","review_queue.json","validation.json","macro_views.html","macro_views_data.json")]]
for i,p in enumerate(paths):
    if p.exists(): shutil.copy2(p,backup/f"{i}_{p.name}")
for p in SRC.iterdir():
    if p.is_file(): shutil.copy2(p,target/p.name)
latest["weco"]=meta; latest["review_queue"]=str(target/"review_queue.json"); latest["queue_changes"]={"new_actual":0,"revised":0,"unchanged":len(queue)}; latest["new_ai_interpretations"]=True
manifest=read(manifest_path); manifest.update(latest); write(manifest_path,manifest); write(LATEST,latest)
now=datetime.now().astimezone().isoformat(timespec="seconds"); state_path=RC/"ecocal_dashboard/daily_interpretation_state.json"; state=read(state_path)
publication={"last_successful_publication_at":now,"input_sha256":meta["workbook_sha256"],"run_record":str(RUN/"run_record.json"),"reviewed_event_ids":[],"reviewed_evidence_pages":[]}
state.setdefault("publication_history",[]).append(publication); state.update(last_successful_publication_at=now,status="published_verified_no_commentary_change_partial_source_coverage",input_sha256=meta["workbook_sha256"],reviewed_event_ids=[],reviewed_evidence_pages=[],run_record=str(RUN/"run_record.json")); write(state_path,state)
collector=read(COLLECTOR)
record={"automation_id":"qae-ib-07-20","monitor_run_id":"20260927_072133_codex","completed_at":now,"status":"published_verified_no_commentary_change_partial_source_coverage","input":{"path":meta["workbook"],"sha256":meta["workbook_sha256"],"modified":meta["workbook_modified"]},"actual_values_snapshot_date":"2026-09-21","interpretation_publication_date":"2026-09-27","collector":collector,"collection_scope":"JPM·Citi 완료(신규 JPM 0건, Citi 4건). GS 5건 확보/1건 실패, BofA 시간초과. HSBC는 필수 범위로 가정하지 않으며 로그상 완료이나 신규 원문 없음. scheduled=false이므로 별도 06:30 실행 완료는 확인하지 못함.","ingested_documents":9,"ingested_pages":110,"reviewed_documents":["Citi US Economics Weekly: A more hawkish reaction function","Citi Canada Economics Weekly: Evidence does not yet support rate hikes","GS Euro Area September Inflation Preview"],"new_summaries":0,"revised_summaries":0,"retained_summaries":213,"valid_summaries":213,"house_comments":250,"reviewed_event_ids":[],"reviewed_evidence_pages":[],"whole_documents_completed":[],"validation":validation,"queue_changes":{"new_actual":0,"revised":0,"unchanged":len(queue)},"living_db_unchanged":True,"publication_paths":[str(BASE/"index.html"),str(target/"index.html"),str(target/"macro_views.html")],"limitations":["ecocal 수치는 9월 21일까지로 전일과 동일하며, 해석·게시일 9월 27일과 분리함.","Citi 미국 주간물은 9월 23일 예비 PMI 등 현재 ecocal 실제값 미수록 자료를 주로 다뤄 기존 과거 지표에 억지 연결하지 않음.","Citi 캐나다 주간물은 8월 CPI의 기존 판단(근원물가 약 2%, 인상 근거 부족)을 재확인했으나 수치·판단 변화가 없어 기존 요약을 유지함.","GS 유로존 9월 물가 자료는 발표 전 전망이므로 미래 실제값 해석으로 저장하지 않음.","BofA 수집 실패와 GS 부분 실패를 성공으로 표시하지 않음.","스케줄러 HTML은 프로젝트 밖 쓰기 권한이 없어 갱신 불가. QAE 전용 모니터 로그는 유지."],"published_hashes":{str(target/p.name):sha(target/p.name) for p in SRC.iterdir() if p.is_file()}}
write(RUN/"run_record.json",record); print(json.dumps({"published":True,"target":str(target),"record":str(RUN/"run_record.json"),"revised":0},ensure_ascii=False))
