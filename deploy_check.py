"""Validate report freshness and verify the exact public data after a Git push."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "macro_hub" / "public"
SITE = "https://macro-hub-nu.vercel.app"


def content_hash(content):
    # Git on Windows converts CRLF to LF when publishing text files.
    return hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()


def prepare(run_id, root=ROOT):
    public = root / "macro_hub" / "public"
    records = json.loads((root / "report_pipeline/houseview_records.json").read_text("utf-8"))
    reports = json.loads((public / "data/reports.json").read_text("utf-8"))
    views_path = public / "data/houseviews.json"
    views = json.loads(views_path.read_text("utf-8")).get("views", []) if views_path.exists() else []
    if not records or not reports:
        raise ValueError("레코드/리포트가 비어 있습니다")
    latest = max(r["date"] for r in records)
    if (date.today() - date.fromisoformat(latest)).days > int(os.environ.get("REPORT_MAX_AGE_DAYS", "7")):
        raise ValueError("요약 입력이 오래됐습니다: " + latest)
    expected = {(r.get("pub_date") or r["date"], r["house"], r["title"])
                for r in records if r["date"] == latest and r.get("house") and r.get("title")}
    actual = {(r["date"], r["source"], r["title"]) for r in reports}
    if not expected or not expected.issubset(actual):
        raise ValueError("최신 요약의 리포트가 목록에서 누락됐습니다")
    hashes = {}
    for folder in ("data", "embeds"):
        for path in sorted((public / folder).glob("*")):
            if not path.is_file() or path.name == "deployment_status.json":
                continue
            if path.suffix == ".json":
                json.loads(path.read_text("utf-8"))
            hashes[path.relative_to(public).as_posix()] = content_hash(path.read_bytes())
    marker = {"runId": run_id, "generatedAt": datetime.now().isoformat(timespec="seconds"),
              "latestSummary": latest, "latestReport": max(r["date"] for r in reports),
              "latestHouseview": max((r["date"] for r in views), default=None),
              "reports": len(reports), "files": hashes}
    target = public / "data/deployment_status.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(marker, ensure_ascii=False, indent=2), "utf-8")
    temp.replace(target)
    return marker


def fetch_bytes(path, run_id):
    req = urllib.request.Request(SITE + "/" + path + "?qae=" + run_id,
                                 headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def verify(marker, log=print, timeout=900, fetch=fetch_bytes):
    deadline = time.monotonic() + timeout
    while True:
        try:
            remote = json.loads(fetch("data/deployment_status.json", marker["runId"]))
            if remote.get("runId") != marker["runId"]:
                raise ValueError("사이트가 아직 이전 배포를 제공합니다")
            for path, expected in marker["files"].items():
                if content_hash(fetch(path, marker["runId"])) != expected:
                    raise ValueError("배포 데이터 불일치: " + path)
            # JSON만 배포되고 실제 화면이 실패하는 경우도 잡는다.
            page = fetch("reports", marker["runId"]).decode("utf-8")
            if marker["latestReport"] not in page:
                raise ValueError("Report 화면에 최신 날짜가 없습니다")
            log("Vercel 사이트 반영 확인 완료: " + marker["latestReport"])
            return True
        except Exception as exc:
            log("배포 확인 대기: " + str(exc))
            if time.monotonic() >= deadline:
                log("배포 확인 실패 — GitHub 전송과 사이트 반영은 별도 상태입니다")
                return False
            time.sleep(min(30, max(0, deadline - time.monotonic())))
