import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\infomax\Documents\python\QAE\데일리시황")
RC = BASE / "Context/_macro/Research_Context"
AUTH = RC / "ecocal_dashboard/authored_commentary.json"
RUN = BASE / "표_업데이트/interpretation_runs/20260923_0720"
EVENT_ID = "d6f2ad7b51cede03a756"
WORKBOOK_HASH = "1042bc3fa5b765694d2e96afccd85bfeeb3f5f6e788a7cc8b941a8032834f7c2"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


bundle = json.loads(AUTH.read_text(encoding="utf-8"))
before = copy.deepcopy(bundle)
now = datetime.now().astimezone().isoformat(timespec="seconds")
review = {
    "event_id": EVENT_ID,
    "headline": "미국 활동지수 소폭 음수, 성장 모멘텀 판단은 보류",
    "summary": "8월 Chicago Fed 국가활동지수는 -0.04로 예상 -0.035를 소폭 밑돌았다. 다만 종전치가 -0.08에서 +0.08로 크게 상향 수정돼, 신규 수치만으로 활동이 급격히 약화됐다고 보기 어렵다. AI 해석 초안으로는 0 부근의 약한 활동을 시사하며, 해당 지수의 직접 IB 근거는 미확보다.",
    "watch": "3개월 이동평균과 생산·고용·소비 구성항목이 동시에 약화되는지 확인한다.",
    "houses": [],
    "review_log": "GS·JPM·Citi·BofA·HSBC별로 Chicago Fed National Activity Index/국가활동지수+미국+발표 전후를 검색했으나 이번 8월 발표를 직접 해석한 원문은 미확보. Chicago Fed CFSEC 고용표와 금융상황지수 검색 결과는 다른 지표이므로 채택하지 않음.",
    "review_id": "comment-" + hashlib.sha256((EVENT_ID + now).encode()).hexdigest()[:24],
    "match": {"country": "United States", "date": "2026-09-21", "time": "21:30", "event": "Chicago Fed Nat Activity Index", "period": "Aug"},
    "snapshot": {"survey": -0.035, "actual": -0.04, "prior": -0.08, "revised": 0.08, "scale": None, "currency": None, "unit": "index"},
    "reviewed_on": "2026-09-23",
    "reviewed_at": now,
    "review_status": "draft",
    "origin": "assistant_review_of_local_reports",
    "workbook_sha256": WORKBOOK_HASH,
}

if not any(x.get("event_id") == EVENT_ID and x.get("snapshot") == review["snapshot"] for x in bundle["event_reviews"]):
    bundle["event_reviews"].append(review)
bundle["reviewed_on"] = "2026-09-23"
write_json(RUN / "authored_commentary.before.json", before)
write_json(AUTH, bundle)
write_json(RUN / "review_result.json", {"review": review, "added": len(bundle["event_reviews"]) - len(before["event_reviews"])})
print(json.dumps({"event_id": EVENT_ID, "review_id": review["review_id"], "total_reviews": len(bundle["event_reviews"])}, ensure_ascii=False))
