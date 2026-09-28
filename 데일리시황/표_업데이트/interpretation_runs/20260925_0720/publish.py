import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\infomax\Documents\python\QAE")
BASE = ROOT / "데일리시황/표_업데이트"
RUN = BASE / "interpretation_runs/20260925_0720"
SRC = RUN / "candidates_WECO"
LATEST = BASE / "latest.json"
RC = ROOT / "데일리시황/Context/_macro/Research_Context"
COLLECTOR = ROOT / "데일리시황/Context/_macro/.collector/logs/latest_daily.json"
REVIEWED_IDS = ["1085bf15e1098089b0e5", "6f5bbdd3f8bdf8f5d47d"]
EVIDENCE_PAGE = {"doc_id": "588fa8e9dff8878926c985ebd497ee49364ee7f081b39fec1dde37185272bcb9", "page": 1}

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

latest_before = LATEST.read_bytes()
latest = read(LATEST)
target = Path(latest["review_queue"]).parent
manifest_path = target.parent / "manifest.json"
manifest_before = manifest_path.read_bytes()
old_data = read(target / "dashboard_data.json")
new_data = read(SRC / "dashboard_data.json")
meta = new_data["meta"]

assert meta["workbook_sha256"] == latest["inputs"]["weco"]["sha256"]
assert len(old_data["events"]) == len(new_data["events"]) == 261
fields = ("country", "date", "time", "event", "period", "survey", "actual", "prior", "revised", "scale", "currency", "unit")
old_facts = {e["id"]: tuple(e.get(k) for k in fields) for e in old_data["events"]}
new_facts = {e["id"]: tuple(e.get(k) for k in fields) for e in new_data["events"]}
assert old_facts == new_facts
assert meta["authored_event_count"] == 213
assert meta["authored_house_count"] == 250
assert meta["commentary_needs_recheck"] == 0
assert old_data["meta"]["macro_views"]["view_payload_sha256"] == meta["macro_views"]["view_payload_sha256"]
assert "최근 3일 업데이트" in (SRC / "index.html").read_text(encoding="utf-8")

by_id = {event["id"]: event for event in new_data["events"]}
for event_id in REVIEWED_IDS:
    review = by_id[event_id]["commentary"]
    assert review["reviewed_on"] == "2026-09-25"
    jpm = next(h for h in review["houses"] if h["house"] == "JPM")
    assert any(e["doc_id"] == EVIDENCE_PAGE["doc_id"] and e["page"] == 1 for e in jpm["evidence"])
    assert "한 주 뒤" in jpm["limitation"]

old_queue = read(target / "review_queue.json")["events"]
queue = []
for old in old_queue:
    event = dict(by_id[old["id"]])
    event.update(
        change_status="unchanged",
        changed_fields=[],
        previous_actual=event.get("actual"),
        observed_at=meta["generated_at"],
        review_status="source_reviewed_ai_draft" if event.get("commentary") else old.get("review_status", "awaiting_manual_or_requested_ai_review"),
    )
    queue.append(event)
write(SRC / "review_queue.json", {"requested_at": meta["generated_at"], "mode": "source_reviewed_commentary", "events": queue})

validation = read(SRC / "validation.json")
validation.update(
    input_numeric_match=True,
    authored_events=213,
    authored_house_comments=250,
    commentary_needs_recheck=0,
    new_summaries=0,
    updated_summaries=2,
    retained_reviews=211,
    review_status="draft",
    macro_views_payload_unchanged=True,
    recent_three_day_overview_preserved=True,
    reviewed_new_documents=1,
    eligible_commentary_changes=2,
)
write(SRC / "validation.json", validation)

# Guard against concurrent morning-table publication before replacing the maintained WECO files.
assert LATEST.read_bytes() == latest_before
assert manifest_path.read_bytes() == manifest_before
assert read(LATEST)["inputs"]["weco"]["sha256"] == meta["workbook_sha256"]

backup = RUN / "published_before"
backup.mkdir(exist_ok=True)
paths = [LATEST, manifest_path, *[target / n for n in ("index.html", "dashboard_data.json", "review_queue.json", "validation.json", "macro_views.html", "macro_views_data.json")]]
for index, path in enumerate(paths):
    if path.exists():
        shutil.copy2(path, backup / f"{index}_{path.name}")
for path in SRC.iterdir():
    if path.is_file():
        shutil.copy2(path, target / path.name)

latest["weco"] = meta
latest["review_queue"] = str(target / "review_queue.json")
latest["queue_changes"] = {"new_actual": 0, "revised": 0, "unchanged": len(queue)}
latest["new_ai_interpretations"] = True
manifest = read(manifest_path)
manifest.update(latest)
write(manifest_path, manifest)
write(LATEST, latest)

now = datetime.now().astimezone().isoformat(timespec="seconds")
state_path = RC / "ecocal_dashboard/daily_interpretation_state.json"
state = read(state_path)
publication = {
    "last_successful_publication_at": now,
    "input_sha256": meta["workbook_sha256"],
    "run_record": str(RUN / "run_record.json"),
    "reviewed_event_ids": REVIEWED_IDS,
    "reviewed_evidence_pages": [EVIDENCE_PAGE],
}
state.setdefault("publication_history", []).append(publication)
state.update(
    last_successful_publication_at=now,
    status="published_two_followup_revisions_partial_source_coverage",
    input_sha256=meta["workbook_sha256"],
    reviewed_event_ids=REVIEWED_IDS,
    reviewed_evidence_pages=[EVIDENCE_PAGE],
    run_record=str(RUN / "run_record.json"),
)
write(state_path, state)

collector = read(COLLECTOR)
record = {
    "automation_id": "qae-ib-07-20",
    "monitor_run_id": "20260925_072033_codex",
    "completed_at": now,
    "status": "published_two_followup_revisions_partial_source_coverage",
    "input": {"path": meta["workbook"], "sha256": meta["workbook_sha256"], "modified": meta["workbook_modified"]},
    "actual_values_snapshot_date": "2026-09-21",
    "interpretation_publication_date": "2026-09-25",
    "collector": collector,
    "collection_scope": "JPM 12건·Citi 5건 완료, GS 17건 확보/1건 실패, BofA 시간초과. HSBC는 필수 범위로 가정하지 않으며 실제 14건 확보/3건 실패/3건 원문 없음. scheduled=false이므로 별도 06:30 실행 완료는 확인하지 못함.",
    "ingested_documents": 48,
    "ingested_pages": 577,
    "reviewed_documents": ["JPM US: Low unemployment signal from claims continues"],
    "new_summaries": 0,
    "revised_summaries": 2,
    "retained_summaries": 211,
    "valid_summaries": 213,
    "house_comments": 250,
    "reviewed_event_ids": REVIEWED_IDS,
    "reviewed_evidence_pages": [EVIDENCE_PAGE],
    "whole_documents_completed": [],
    "validation": validation,
    "queue_changes": {"new_actual": 0, "revised": 0, "unchanged": len(queue)},
    "living_db_unchanged": True,
    "publication_paths": [str(BASE / "index.html"), str(target / "index.html"), str(target / "macro_views.html")],
    "limitations": [
        "ecocal 수치는 9월 21일까지로 전일과 동일하며, 해석·게시일 9월 25일과 분리함.",
        "JPM 9월 24일 실업수당 보고서는 WECO 항목보다 한 주 뒤 수치를 다룬 후속 related 근거이며 직접 반응으로 표시하지 않음.",
        "신규주택판매·PMI 등 신규 원문의 대상 발표는 현재 ecocal에 실제값이 없어 기존 기간에 연결하지 않음.",
        "BofA 수집 실패와 GS·HSBC 부분 실패를 성공으로 표시하지 않음.",
        "스케줄러 HTML은 프로젝트 밖 쓰기 권한이 없어 갱신 불가. QAE 전용 모니터 로그는 유지.",
    ],
    "published_hashes": {str(target / p.name): sha(target / p.name) for p in SRC.iterdir() if p.is_file()},
}
write(RUN / "run_record.json", record)
print(json.dumps({"published": True, "target": str(target), "record": str(RUN / "run_record.json"), "revised": 2}, ensure_ascii=False))
