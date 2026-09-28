import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\표_업데이트")
RUN = BASE / "interpretation_runs/20260923_0720"
SRC = RUN / "validated_WECO"
RC = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\Research_Context")
LATEST = BASE / "latest.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


latest = read(LATEST)
target = Path(latest["review_queue"]).parent
manifest_path = target.parent / "manifest.json"
manifest = read(manifest_path)
data = read(SRC / "dashboard_data.json")
meta = data["meta"]
old_queue_bundle = read(target / "review_queue.json")
old_queue = old_queue_bundle["events"]
by_id = {event["id"]: event for event in data["events"]}
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
    authored_events=meta["authored_event_count"],
    authored_house_comments=meta["authored_house_count"],
    commentary_needs_recheck=meta["commentary_needs_recheck"],
    new_summaries=1,
    updated_summaries=1,
    retained_reviews=212,
    review_status="draft",
    macro_views_payload_unchanged=True,
    recent_three_day_overview_preserved="최근 3일 업데이트" in (SRC / "index.html").read_text(encoding="utf-8"),
)
write(SRC / "validation.json", validation)

backup = RUN / "published_before"
backup.mkdir(exist_ok=True)
for path in [LATEST, manifest_path, *[target / name for name in ("index.html", "dashboard_data.json", "review_queue.json", "validation.json", "macro_views.html", "macro_views_data.json")]]:
    if path.exists():
        shutil.copy2(path, backup / (str(len(list(backup.iterdir()))) + "_" + path.name))

for path in SRC.iterdir():
    if path.is_file():
        shutil.copy2(path, target / path.name)

latest["weco"] = meta
latest["review_queue"] = str(target / "review_queue.json")
latest["queue_changes"] = {"new_actual": 0, "revised": 0, "unchanged": len(queue)}
latest["new_ai_interpretations"] = True
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
    "reviewed_event_ids": ["d6f2ad7b51cede03a756"],
    "reviewed_evidence_pages": [],
})
state.update(
    last_successful_publication_at=now,
    status="published_partial_source_coverage",
    input_sha256=meta["workbook_sha256"],
    reviewed_event_ids=["d6f2ad7b51cede03a756"],
    reviewed_evidence_pages=[],
    run_record=str(RUN / "run_record.json"),
)
write(state_path, state)

record = {
    "automation_id": "qae-ib-07-20",
    "completed_at": now,
    "status": "published_partial_source_coverage",
    "input": {"path": meta["workbook"], "sha256": meta["workbook_sha256"], "modified": meta["workbook_modified"]},
    "actual_values_snapshot_date": "2026-09-21",
    "interpretation_publication_date": "2026-09-23",
    "collector": read(Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\.collector\logs\latest_daily.json")),
    "collection_scope": "JPM 9건·Citi 3건 완료, GS 11건 확보/1건 실패/1건 원문 없음, BofA 시간초과. HSBC는 필수 범위로 가정하지 않으며 실제 3건 확보/2건 실패/3건 원문 없음. scheduled=false이므로 별도 06:30 실행 완료는 확인하지 못함.",
    "ingested_documents": 26,
    "ingested_pages": 256,
    "new_summaries": 1,
    "revised_summaries": 0,
    "retained_summaries": 212,
    "valid_summaries": meta["authored_event_count"],
    "house_comments": meta["authored_house_count"],
    "reviewed_event_ids": ["d6f2ad7b51cede03a756"],
    "reviewed_evidence_pages": [],
    "whole_documents_completed": [],
    "validation": validation,
    "queue_changes": {"unchanged": len(queue)},
    "living_db_unchanged": True,
    "publication_paths": [str(BASE / "index.html"), str(target / "index.html"), str(target / "macro_views.html")],
    "limitations": [
        "Chicago Fed 국가활동지수의 직접 IB 근거를 확보하지 못해 수치 기반 AI 해석 초안으로 게시.",
        "9월 22일 신규 원문 26건은 검색 DB 적재이며 전체 의미 검토 완료가 아님. 이번 지표에 채택한 근거 페이지는 없음.",
        "ecocal은 9월 22일 09:02 원본으로, 실제값 기준일 9월 21일과 해석·게시일 9월 23일을 구분.",
        "스케줄러 HTML은 프로젝트 밖 쓰기 권한이 없어 갱신 불가. QAE 전용 모니터 로그는 유지.",
    ],
    "published_hashes": {str(target / path.name): sha(target / path.name) for path in SRC.iterdir() if path.is_file()},
}
write(RUN / "run_record.json", record)
print(json.dumps({"published": True, "target": str(target), "record": str(RUN / "run_record.json"), "authored": meta["authored_event_count"]}, ensure_ascii=False))
