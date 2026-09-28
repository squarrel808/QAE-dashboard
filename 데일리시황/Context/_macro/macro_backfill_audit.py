"""Read-only integrity and completion gate for staged historical collection.

The collector's successful traversal is the coverage evidence. Saved-file date
extremes and month counts are descriptive, never proof of full list coverage.
This module neither repairs state nor downloads, prints, or renders documents.
"""
from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

import macro_bulk_downloader as m


RESOLVED_STATUSES = frozenset({"downloaded", "no_original_pdf"})
UNRESOLVED_RUN_COUNTS = (
    "failed", "pending", "unknown_date", "unresolved_print_control"
)


def _month_keys(start: date, end: date) -> list[str]:
    current = start.replace(day=1)
    keys = []
    while current <= end:
        keys.append(current.strftime("%Y-%m"))
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return keys


def _verify_file(row: sqlite3.Row) -> list[dict]:
    """Read one report at a time; retain only its small error descriptions."""
    errors = []
    base = {"doc_id": row["doc_id"], "path": row["path"] or ""}

    def fail(code: str, message: str) -> None:
        errors.append({**base, "code": code, "message": message})

    if not row["path"]:
        fail("missing_path", "Downloaded record has no file path.")
        return errors
    path = Path(row["path"])
    if not path.is_absolute():
        # Collector writes absolute paths. Relative paths otherwise depend on
        # the supervisor's working directory and cannot be safely verified.
        fail("relative_path", "Downloaded file path is not absolute.")
        return errors
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        fail("missing_file", "Downloaded file does not exist.")
        return errors
    except OSError as exc:
        fail("file_read_error", f"{type(exc).__name__}: {exc}")
        return errors

    if len(raw) != row["bytes"]:
        fail("size_mismatch", f"Recorded bytes={row['bytes']}; actual bytes={len(raw)}.")
    if not m.is_pdf(raw):
        fail("invalid_pdf", "Original PDF header/EOF validation failed.")
    digest = hashlib.sha256(raw).hexdigest()
    if not row["sha256"] or digest != row["sha256"]:
        fail("sha256_mismatch", "File SHA256 does not match the recorded digest.")
    return errors


def audit_house(
    state_dir: Path, house: str, start: date, end: date, run_result: dict
) -> dict:
    """Return a JSON-serializable pass/fail audit without changing any state.

    ``run_result`` must be this house's Collector.run_house result for the
    supplied inclusive interval, not the entire run artifact. A positive
    ``counts.in_range`` is required to prove fresh discovery. Unknown dates
    anywhere in the same house block expansion because their interval cannot
    be established. Known dated records outside the interval are excluded.

    The caller must prevent another collector from modifying this house while
    auditing and must associate run_result with the correct dates. If optional
    house/start_date/end_date metadata is supplied, it is checked as well.
    """
    result = {
        "house": house,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "run_status": run_result.get("status"),
        "eligible": False,
        "gate_reasons": [],
        "coverage_evidence": "Collector completion and fresh in-range discovery; date spans are descriptive only.",
        "counts": {
            "reports_in_window": 0,
            "downloaded": 0,
            "validated_downloads": 0,
            "no_original_pdf": 0,
            "unresolved": 0,
            "unknown_or_invalid_date": 0,
            "file_error_count": 0,
        },
        "status_counts": {},
        "min_published": None,
        "max_published": None,
        "downloaded_min_published": None,
        "downloaded_max_published": None,
        "month_counts": {},
        "errors": [],
        "unresolved": [],
    }
    reasons = result["gate_reasons"]
    counts = result["counts"]

    if house not in m.HOUSES:
        reasons.append(f"Unknown house: {house!r}.")
    if start > end:
        reasons.append("Requested start date is after end date.")
        return result
    result["month_counts"] = {
        key: {"reports": 0, "downloaded": 0, "validated_downloads": 0,
              "no_original_pdf": 0, "unresolved": 0}
        for key in _month_keys(start, end)
    }
    if run_result.get("status") != "complete":
        reasons.append(f"Collector status must be 'complete', got {run_result.get('status')!r}.")
        if run_result.get("reason"):
            reasons.append(f"Collector reason: {run_result['reason']}")
    for key, expected in (("house", house), ("start_date", start.isoformat()),
                          ("end_date", end.isoformat())):
        if key in run_result and run_result[key] != expected:
            reasons.append(f"Collector {key} does not match the audit request.")
    run_counts = run_result.get("counts")
    if not isinstance(run_counts, dict):
        run_counts = {}
    in_range = run_counts.get("in_range")
    if type(in_range) is not int or in_range <= 0:
        reasons.append("Collector must report a positive integer counts.in_range for fresh discovery.")
    for key in UNRESOLVED_RUN_COUNTS:
        value = run_counts.get(key, 0)
        if type(value) is not int or value < 0:
            reasons.append(f"Collector count {key!r} is invalid: {value!r}.")
        elif value:
            reasons.append(f"Collector reported {key}={value}.")

    status_counts = Counter()
    db_path = (Path(state_dir) / "downloads.sqlite3").resolve()
    try:
        # mode=ro refuses missing databases and cannot create/repair tables.
        with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only = ON")
            rows = db.execute(
                "SELECT doc_id, published, status, path, sha256, bytes, error "
                "FROM reports WHERE house=? ORDER BY published, doc_id", (house,)
            )
            for row in rows:
                published = row["published"] or ""
                try:
                    published_date = date.fromisoformat(published)
                    if published_date.isoformat() != published:
                        raise ValueError("Noncanonical publication date")
                except (TypeError, ValueError):
                    published_date = None
                if published_date is not None and not start <= published_date <= end:
                    continue

                status = row["status"] or "<missing>"
                status_counts[status] += 1
                month = None
                if published_date is None:
                    counts["unknown_or_invalid_date"] += 1
                else:
                    counts["reports_in_window"] += 1
                    month = result["month_counts"][published_date.strftime("%Y-%m")]
                    month["reports"] += 1
                    result["min_published"] = min(result["min_published"] or published, published)
                    result["max_published"] = max(result["max_published"] or published, published)

                if published_date is None or status not in RESOLVED_STATUSES:
                    counts["unresolved"] += 1
                    if month is not None:
                        month["unresolved"] += 1
                    result["unresolved"].append({
                        "doc_id": row["doc_id"], "published": published,
                        "status": status, "error": row["error"] or "",
                        "reason": "Publication date is unknown or invalid."
                        if published_date is None else "Report status is unresolved.",
                    })
                if published_date is None:
                    continue
                if status == "no_original_pdf":
                    counts["no_original_pdf"] += 1
                    month["no_original_pdf"] += 1
                elif status == "downloaded":
                    counts["downloaded"] += 1
                    month["downloaded"] += 1
                    result["downloaded_min_published"] = min(
                        result["downloaded_min_published"] or published, published)
                    result["downloaded_max_published"] = max(
                        result["downloaded_max_published"] or published, published)
                    errors = _verify_file(row)
                    result["errors"].extend(errors)
                    counts["file_error_count"] += len(errors)
                    if not errors:
                        counts["validated_downloads"] += 1
                        month["validated_downloads"] += 1
    except (sqlite3.Error, OSError) as exc:
        result["errors"].append({"code": "database_read_error", "message": f"{type(exc).__name__}: {exc}"})
        reasons.append("Could not read the existing collector database.")
    finally:
        if "db" in locals():
            db.close()

    result["status_counts"] = dict(sorted(status_counts.items()))
    if not counts["reports_in_window"]:
        reasons.append("No dated reports are recorded in the requested interval.")
    if type(in_range) is int and in_range > counts["reports_in_window"]:
        reasons.append(f"Collector discovered {in_range} in-range reports but the database contains only {counts['reports_in_window']}.")
    if counts["unknown_or_invalid_date"]:
        reasons.append(f"{counts['unknown_or_invalid_date']} same-house reports have unknown or invalid dates.")
    unresolved_status_counts = Counter(r["status"] for r in result["unresolved"])
    if counts["unresolved"]:
        detail = ", ".join(f"{key}={value}" for key, value in sorted(unresolved_status_counts.items()))
        reasons.append(f"{counts['unresolved']} unresolved database reports remain ({detail}).")
    if counts["file_error_count"]:
        reasons.append(f"Downloaded-file integrity verification found {counts['file_error_count']} errors.")
    result["eligible"] = not reasons
    return result
