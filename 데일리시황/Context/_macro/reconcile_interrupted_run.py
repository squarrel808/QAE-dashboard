#!/usr/bin/env python3
"""Close one abandoned run after independently confirming its process stopped.

Defaults to a read-only preview. Apply requires both --apply and
--confirm-stopped. Does not alter report rows, downloaded files, or browsers.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from macro_bulk_downloader import KST, atomic_write_json, run_lock


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def reconcile(state_dir, run_id, reason, *, apply=False, confirmed_stopped=False, log_dir=None):
    if apply and not confirmed_stopped:
        raise ValueError("Independently verify shutdown, then pass --confirm-stopped.")
    if not re.fullmatch(r"\d{8}_\d{6}_[0-9a-f]{6}", run_id):
        raise ValueError("Invalid run ID.")
    if not reason.strip():
        raise ValueError("An interruption reason is required.")
    state_dir = Path(state_dir).resolve()
    log_dir = Path(log_dir).resolve() if log_dir else state_dir / "logs"
    day = f"{run_id[:4]}-{run_id[4:6]}-{run_id[6:8]}"
    report_path = log_dir / day / f"run_{run_id}.json"
    log_path = report_path.with_suffix(".log")
    audit_path = report_path.with_suffix(".interruption.json")
    latest_path = log_dir / "latest_run.json"
    db_path = state_dir / "downloads.sqlite3"

    def execute():
        # mode=rw refuses to create a database at a mistaken path.
        mode = "rw" if apply else "ro"
        db = sqlite3.connect(db_path.as_uri() + f"?mode={mode}", uri=True)
        db.row_factory = sqlite3.Row
        try:
            if apply:
                db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise ValueError("Run is absent from the database.")
            original = read_json(report_path)
            if original.get("run_id") != run_id:
                raise ValueError("Run artifact ID mismatch.")
            if row["finished"] or original.get("finished"):
                raise ValueError("Run is already finished; refusing to rewrite its history.")
            log = log_path.read_text(encoding="utf-8")
            if f"Run={run_id} " not in log:
                raise ValueError("Run log has no matching invocation header.")
            observed = defaultdict(Counter)
            for house, event in re.findall(r"\[(HSBC|GS|JPM|Citi|BofA)\] (saved|failed)\b", log):
                observed[house]["downloaded" if event == "saved" else "failed"] += 1
            result = copy.deepcopy(original)
            houses = result["houses"]
            before_summary = json.loads(row["summary"] or "{}")
            for house, entry in houses.items():
                counts = entry.setdefault("counts", {})
                # Preserve checkpoint counts, using logged completions only as a floor.
                for source in (before_summary.get(house, {}).get("counts", {}), observed[house]):
                    for key, value in source.items():
                        counts[key] = max(counts.get(key, 0), value)
                if entry.get("status") in ("running", "not_started"):
                    entry["previous_status"] = entry["status"]
                    entry["status"] = "incomplete"
                    entry["reason"] = reason if entry["previous_status"] == "running" else "Not started because the run stopped. " + reason
            finished = datetime.now(KST).isoformat()
            result.update(finished=finished, overall_status="incomplete")
            result["interruption"] = {
                "reason": reason,
                "reconciled_at": finished,
                "process_shutdown_independently_confirmed": confirmed_stopped,
                "count_evidence": "Existing checkpoint counts preserved; downloaded/failed recovered from this run's log. Unlogged counts remain unknown. reports.updated was not used.",
            }
            totals = [dict(r) for r in db.execute(
                "SELECT house,status,count(*) AS count FROM reports GROUP BY house,status ORDER BY house,status"
            )]
            latest = read_json(latest_path) if latest_path.exists() else None
            update_latest = latest is not None and latest.get("run_id") == run_id
            response = {"applied": apply, "report": str(report_path), "audit": str(audit_path),
                        "manifest": str(state_dir / "manifest.csv"), "latest_updated": apply and update_latest,
                        "run": result, "inventory": totals}
            if apply:
                if audit_path.exists():
                    raise ValueError("An interruption audit already exists; inspect it before retrying.")
                atomic_write_json(audit_path, {"before_db_run": dict(row), "before_report": original,
                                               "before_latest": latest if update_latest else None,
                                               "after_report": result, "inventory": totals})
                db.execute("UPDATE runs SET finished=?,summary=? WHERE run_id=? AND finished IS NULL",
                           (finished, json.dumps(houses, ensure_ascii=False), run_id))
                db.commit()
                atomic_write_json(report_path, result)
                # Recheck immediately before writing; never replace a newer invocation.
                if update_latest and latest_path.exists() and read_json(latest_path).get("run_id") == run_id:
                    atomic_write_json(latest_path, result)
                else:
                    response["latest_updated"] = False
                rows = db.execute("SELECT * FROM reports ORDER BY house,published,doc_id")
                manifest = state_dir / "manifest.csv"
                temporary = manifest.with_suffix(".csv.tmp")
                with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow([field[0] for field in rows.description])
                    writer.writerows(rows)
                temporary.replace(manifest)
                with log_path.open("a", encoding="utf-8") as stream:
                    stream.write(f"{datetime.now(KST):%Y-%m-%d %H:%M:%S} INFO Run={run_id} reconciled status=incomplete reason={reason}\n")
            return response
        finally:
            db.close()

    if apply:
        with run_lock(state_dir):
            return execute()
    return execute()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path(__file__).parent / ".collector")
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-stopped", action="store_true")
    args = parser.parse_args()
    print(json.dumps(reconcile(args.state_dir, args.run_id, args.reason, apply=args.apply,
                               confirmed_stopped=args.confirm_stopped, log_dir=args.log_dir),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
