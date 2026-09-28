import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\infomax\Documents\python\QAE")
RUN = ROOT / "데일리시황/표_업데이트/interpretation_runs/20260925_0720"
SOURCE = ROOT / "데일리시황/Context/_macro/Research_Context/ecocal_dashboard/authored_commentary.json"
BACKUP = RUN / "authored_commentary_before.json"
DOC_ID = "588fa8e9dff8878926c985ebd497ee49364ee7f081b39fec1dde37185272bcb9"
EVENT_IDS = {"1085bf15e1098089b0e5", "6f5bbdd3f8bdf8f5d47d"}
QUOTE = (
    "The positive news from jobless claims continues. Initial claims for the week ending \n"
    "September 19 were 197k, about the same as the 198k the prior week, with both \n"
    "readings low and continuing to run well below prior-year levels. Continuing claims \n"
    "for the week ending September 12, the September household survey reference \n"
    "week, were 1.719k, about unchanged from a downward-revised prior week, and \n"
    "down 52k from the August reference week. Continuing claims over the last two \n"
    "weeks are also the lowest since May 2023, and point to ongoing declines in \n"
    "unemployment. The unemployment rate was 4.14% in August, so getting it to \n"
    "round down to 4.0% in September could be difficult, but the underlying trajectory \n"
    "should remain toward lower unemployment."
)

data = json.loads(SOURCE.read_text(encoding="utf-8"))
shutil.copy2(SOURCE, BACKUP)
now = datetime.now().astimezone().isoformat(timespec="seconds")
updated = []
for review in data["event_reviews"]:
    if review["event_id"] not in EVENT_IDS:
        continue
    jpm = next(item for item in review["houses"] if item["house"] == "JPM")
    if not any(item["doc_id"] == DOC_ID for item in jpm["evidence"]):
        jpm["summary"] = (
            "JPM은 9월 17일 발표의 낮은 청구가 실업률 하락 신호라는 판단을 유지했다. "
            "한 주 뒤에도 신규 19.7만·계속 171.9만 건으로 낮은 흐름이 이어져 이번 감소가 단순한 한 주 이상은 아니라고 평가했다."
        )
        jpm["comment"] = (
            "AI 비교: 후속 수치는 낮은 해고와 실업률 하락 방향을 보강하지만, "
            "JPM도 9월 실업률이 4.0%로 내려가기는 어려울 수 있고 계절성으로 계속청구가 재반등할 수 있다고 봤다."
        )
        jpm["limitation"] = (
            "9월 24일 보고서는 이번 WECO 항목보다 한 주 뒤의 신규·계속 청구를 다룬 후속 분석으로, 해당 주간 수치에 대한 직접 반응은 아니다."
        )
        jpm["evidence"].append({"doc_id": DOC_ID, "page": 1, "quote": QUOTE})
        jpm["reviewed_pages"].append({"doc_id": DOC_ID, "page": 1})
    review["watch"] = "9월 고용보고서의 실업률과 9월 하순 계속청구의 계절적 반등 여부를 확인한다."
    review["reviewed_on"] = "2026-09-25"
    review["reviewed_at"] = now
    review["review_log"] = (
        "9월 24일 JPM 후속 보고서 1쪽 전체를 읽고 한 주 뒤 청구가 낮은 흐름을 유지했다는 근거를 related로 보강. "
        "직접 사후 반응이 아니며 대상 주간 차이를 제한으로 명시. 다른 하우스는 기존 근거 유지."
    )
    updated.append(review["event_id"])

assert set(updated) == EVENT_IDS
data["reviewed_on"] = "2026-09-25"
SOURCE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"updated": sorted(updated), "backup": str(BACKUP)}, ensure_ascii=False))
