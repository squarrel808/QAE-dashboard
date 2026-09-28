import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\표_업데이트")
RUN = BASE / "interpretation_runs/20260924_0720"
SRC = RUN / "candidates_WECO"
LATEST = BASE / "latest.json"
RC = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\Research_Context")
COLLECTOR = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\.collector\logs\latest_daily.json")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


latest_before_bytes = LATEST.read_bytes()
latest = read(LATEST)
target = Path(latest["review_queue"]).parent
manifest_path = target.parent / "manifest.json"
manifest_before_bytes = manifest_path.read_bytes()
old_data = read(target / "dashboard_data.json")
new_data = read(SRC / "dashboard_data.json")
meta = new_data["meta"]

assert meta["workbook_sha256"] == latest["inputs"]["weco"]["sha256"]
assert len(old_data["events"]) == len(new_data["events"]) == 261
old_facts = {e["id"]: tuple(e.get(k) for k in ("country", "date", "time", "event", "period", "survey", "actual", "prior", "revised", "scale", "currency", "unit")) for e in old_data["events"]}
new_facts = {e["id"]: tuple(e.get(k) for k in ("country", "date", "time", "event", "period", "survey", "actual", "prior", "revised", "scale", "currency", "unit")) for e in new_data["events"]}
assert old_facts == new_facts
assert meta["authored_event_count"] == 213
assert meta["authored_house_count"] == 250
assert meta["commentary_needs_recheck"] == 0
assert old_data["meta"]["macro_views"]["view_payload_sha256"] == meta["macro_views"]["view_payload_sha256"]
assert "최근 3일 업데이트" in (SRC / "index.html").read_text(encoding="utf-8")

old_queue = read(target / "review_queue.json")["events"]
by_id = {event["id"]: event for event in new_data["events"]}
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
    updated_summaries=0,
    retained_reviews=213,
    review_status="draft",
    macro_views_payload_unchanged=True,
    recent_three_day_overview_preserved=True,
    reviewed_new_documents=13,
    eligible_commentary_changes=0,
)
write(SRC / "validation.json", validation)

# Re-check publication inputs immediately before replacing the maintained output.
assert LATEST.read_bytes() == latest_before_bytes
assert manifest_path.read_bytes() == manifest_before_bytes
assert read(LATEST)["inputs"]["weco"]["sha256"] == meta["workbook_sha256"]

backup = RUN / "published_before"
backup.mkdir(exist_ok=True)
for index, path in enumerate([LATEST, manifest_path, *[target / name for name in ("index.html", "dashboard_data.json", "review_queue.json", "validation.json", "macro_views.html", "macro_views_data.json")]]):
    if path.exists():
        shutil.copy2(path, backup / f"{index}_{path.name}")

for path in SRC.iterdir():
    if path.is_file():
        shutil.copy2(path, target / path.name)

latest["weco"] = meta
latest["review_queue"] = str(target / "review_queue.json")
latest["queue_changes"] = {"new_actual": 0, "revised": 0, "unchanged": len(queue)}
latest["new_ai_interpretations"] = False
manifest = read(manifest_path)
manifest.update(latest)
write(manifest_path, manifest)
write(LATEST, latest)

now = datetime.now().astimezone().isoformat(timespec="seconds")
state_path = RC / "ecocal_dashboard/daily_interpretation_state.json"
state = read(state_path)
state["publication_history"].append({
    "last_successful_publication_at": now,
    "input_sha256": meta["workbook_sha256"],
    "run_record": str(RUN / "run_record.json"),
    "reviewed_event_ids": [],
    "reviewed_evidence_pages": [],
})
state.update(
    last_successful_publication_at=now,
    status="published_no_eligible_commentary_change_partial_source_coverage",
    input_sha256=meta["workbook_sha256"],
    reviewed_event_ids=[],
    reviewed_evidence_pages=[],
    run_record=str(RUN / "run_record.json"),
)
write(state_path, state)

collector = read(COLLECTOR)
record = {
    "automation_id": "qae-ib-07-20",
    "monitor_run_id": "20260924_072207_codex",
    "completed_at": now,
    "status": "published_no_eligible_commentary_change_partial_source_coverage",
    "input": {"path": meta["workbook"], "sha256": meta["workbook_sha256"], "modified": meta["workbook_modified"]},
    "actual_values_snapshot_date": "2026-09-21",
    "interpretation_publication_date": "2026-09-24",
    "collector": collector,
    "collection_scope": "JPM 11건·Citi 5건 완료, GS 10건 확보/1건 실패, BofA 시간초과. HSBC는 필수 범위로 가정하지 않으며 실제 5건 확보/1건 실패/3건 원문 없음. scheduled=false이므로 별도 06:30 실행 완료는 확인하지 못함.",
    "ingested_documents": 31,
    "ingested_pages": 281,
    "reviewed_documents": [
        "Citi South Africa Economics: August CPI neither here nor there",
        "GS CEEMEA Inflation Monitor",
        "GS Euro Area Data Update",
        "GS Europe September Flash PMIs",
        "GS Hungary MNB",
        "GS Singapore Core inflation",
        "GS South Africa inflation",
        "GS USA S&P PMIs",
        "HSBC EM Webcast: CEE inflation",
        "JPM Korea Consumer sentiment",
        "JPM Singapore August core inflation",
        "JPM UK Flash PMI",
        "JPM US September flash PMI",
    ],
    "new_summaries": 0,
    "revised_summaries": 0,
    "retained_summaries": 213,
    "valid_summaries": 213,
    "house_comments": 250,
    "reviewed_event_ids": [],
    "reviewed_evidence_pages": [],
    "whole_documents_completed": [],
    "validation": validation,
    "queue_changes": {"unchanged": len(queue)},
    "living_db_unchanged": True,
    "publication_paths": [str(BASE / "index.html"), str(target / "index.html"), str(target / "macro_views.html")],
    "limitations": [
        "9월 23일 신규 원문의 직접 반응 대상(PMI, 싱가포르·남아공 CPI, 한국 소비심리)은 현재 ecocal에 실제값이 수록되지 않아 해석을 신규 작성하지 않음.",
        "신규 원문은 검색 DB에 적재했지만, 채택하지 않은 문서·페이지를 검토 완료로 표시하지 않음.",
        "ecocal은 9월 22일 09:02 원본으로, 실제값 기준일 9월 21일과 해석·게시일 9월 24일을 구분.",
        "BofA 수집 실패와 GS 부분 실패를 성공으로 표시하지 않음.",
        "스케줄러 HTML은 프로젝트 밖 쓰기 권한이 없어 갱신 불가. QAE 전용 모니터 로그는 유지.",
    ],
    "published_hashes": {str(target / path.name): sha(target / path.name) for path in SRC.iterdir() if path.is_file()},
}
write(RUN / "run_record.json", record)
print(json.dumps({"published": True, "target": str(target), "record": str(RUN / "run_record.json"), "authored": 213, "changes": 0}, ensure_ascii=False))
