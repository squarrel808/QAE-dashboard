"""Offline tests for the read-only backfill expansion gate."""
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import macro_bulk_downloader as m
from macro_backfill_audit import audit_house


PDF = b"%PDF-1.4\n" + b"report fixture\n" * 20 + b"%%EOF\n"
START = date(2026, 6, 9)
END = date(2026, 9, 9)


class BackfillAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = m.State(self.root / "state")
        self.addCleanup(self.state.db.close)

    def add_report(self, ident="one", status="downloaded", day="2026-07-15", house="HSBC"):
        report = m.Report(house, ident, "Fixture", day, "https://fixture.test/report",
                          "https://fixture.test/list", published=day)
        self.state.record(report)
        path = self.root / f"{house}_{ident}.pdf"
        if status == "downloaded":
            path.write_bytes(PDF)
            self.state.result(report, status, path=path, raw=PDF)
        elif status != "pending":
            self.state.result(report, status, error="Fixture state")
        return path

    def audit(self, run=None, **kwargs):
        return audit_house(self.state.folder, kwargs.get("house", "HSBC"),
                           kwargs.get("start", START), kwargs.get("end", END),
                           run or {"status": "complete", "counts": {"in_range": 1}})

    def test_complete_verified_download_and_json_serializable(self):
        self.add_report()
        result = self.audit()
        self.assertTrue(result["eligible"], result["gate_reasons"])
        self.assertEqual(result["counts"]["validated_downloads"], 1)
        self.assertEqual(result["min_published"], "2026-07-15")
        self.assertEqual(result["month_counts"]["2026-07"]["validated_downloads"], 1)
        self.assertEqual(result["month_counts"]["2026-08"]["reports"], 0)
        json.dumps(result)

    def test_scan_and_incomplete_cannot_pass_with_valid_files(self):
        self.add_report()
        for status in ("scan_complete", "incomplete", "running", "not_started"):
            with self.subTest(status=status):
                result = self.audit({"status": status, "counts": {"in_range": 1}})
                self.assertFalse(result["eligible"])
                self.assertIn("must be 'complete'", " ".join(result["gate_reasons"]))

    def test_unresolved_statuses_block(self):
        for index, status in enumerate(("failed", "pending", "unresolved_print_control", "unexpected_status")):
            self.add_report(str(index), status)
        result = self.audit()
        self.assertFalse(result["eligible"])
        self.assertEqual(result["counts"]["unresolved"], 4)
        self.assertEqual({r["status"] for r in result["unresolved"]},
                         {"failed", "pending", "unresolved_print_control", "unexpected_status"})

    def test_unknown_and_malformed_dates_block_even_when_unplaceable(self):
        self.add_report()
        self.add_report("unknown", "unknown_date", day="")
        self.add_report("malformed", "pending", day="2026-02-31")
        result = self.audit()
        self.assertFalse(result["eligible"])
        self.assertEqual(result["counts"]["unknown_or_invalid_date"], 2)
        self.assertEqual(result["counts"]["reports_in_window"], 1)

    def test_explicit_known_no_original_pdf_is_allowed(self):
        self.add_report(status="no_original_pdf")
        result = self.audit()
        self.assertTrue(result["eligible"], result["gate_reasons"])
        self.assertEqual(result["counts"]["no_original_pdf"], 1)
        self.assertEqual(result["counts"]["validated_downloads"], 0)
        self.assertEqual(result["errors"], [])

    def test_missing_file_blocks(self):
        path = self.add_report()
        path.unlink()
        result = self.audit()
        self.assertFalse(result["eligible"])
        self.assertEqual(result["errors"][0]["code"], "missing_file")

    def test_same_size_hash_mismatch_blocks(self):
        path = self.add_report()
        path.write_bytes(PDF.replace(b"fixture", b"changed"))
        result = self.audit()
        self.assertFalse(result["eligible"])
        self.assertEqual([e["code"] for e in result["errors"]], ["sha256_mismatch"])

    def test_recorded_size_mismatch_blocks(self):
        self.add_report()
        self.state.db.execute("UPDATE reports SET bytes=bytes+1")
        self.state.db.commit()
        result = self.audit()
        self.assertFalse(result["eligible"])
        self.assertEqual([e["code"] for e in result["errors"]], ["size_mismatch"])

    def test_invalid_pdf_blocks_even_when_hash_and_size_match(self):
        path = self.add_report()
        raw = b"<html>Login page</html>" * 20
        path.write_bytes(raw)
        self.state.db.execute("UPDATE reports SET bytes=?, sha256=?", (len(raw), hashlib.sha256(raw).hexdigest()))
        self.state.db.commit()
        result = self.audit()
        self.assertFalse(result["eligible"])
        self.assertEqual([e["code"] for e in result["errors"]], ["invalid_pdf"])

    def test_other_houses_and_outside_window_do_not_block(self):
        self.add_report()
        self.add_report("other_house", "failed", house="GS")
        self.add_report("old", "failed", day="2026-01-01")
        self.add_report("future", "pending", day="2026-09-10")
        result = self.audit()
        self.assertTrue(result["eligible"], result["gate_reasons"])
        self.assertEqual(result["counts"]["reports_in_window"], 1)

    def test_date_boundaries_inclusive(self):
        self.add_report("start", day=START.isoformat())
        self.add_report("end", day=END.isoformat())
        result = self.audit({"status": "complete", "counts": {"in_range": 2}})
        self.assertTrue(result["eligible"], result["gate_reasons"])
        self.assertEqual(result["counts"]["validated_downloads"], 2)

    def test_dates_and_existing_files_alone_cannot_prove_coverage(self):
        self.add_report("start", day=START.isoformat())
        self.add_report("end", day=END.isoformat())
        for counts in ({}, {"in_range": 0}, {"in_range": "2"}):
            with self.subTest(counts=counts):
                result = self.audit({"status": "complete", "counts": counts})
                self.assertFalse(result["eligible"])
                self.assertIn("fresh discovery", " ".join(result["gate_reasons"]))

    def test_run_failure_counts_block_even_if_database_clean(self):
        self.add_report()
        result = self.audit({"status": "complete", "counts": {"in_range": 1, "failed": 1}})
        self.assertFalse(result["eligible"])
        self.assertIn("Collector reported failed=1", " ".join(result["gate_reasons"]))

    def test_current_discovery_cannot_exceed_persisted_records(self):
        self.add_report()
        result = self.audit({"status": "complete", "counts": {"in_range": 2}})
        self.assertFalse(result["eligible"])
        self.assertIn("database contains only 1", " ".join(result["gate_reasons"]))

    def test_audit_does_not_change_database_or_create_artifacts(self):
        self.add_report()
        db_path = self.state.folder / "downloads.sqlite3"
        before = db_path.read_bytes()
        names = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        self.audit()
        self.assertEqual(before, db_path.read_bytes())
        self.assertEqual(names, sorted(p.relative_to(self.root) for p in self.root.rglob("*")))

    def test_missing_database_is_not_created(self):
        folder = self.root / "nonexistent"
        result = audit_house(folder, "HSBC", START, END,
                             {"status": "complete", "counts": {"in_range": 1}})
        self.assertFalse(result["eligible"])
        self.assertEqual(result["errors"][0]["code"], "database_read_error")
        self.assertFalse(folder.exists())

    def test_optional_run_window_metadata_is_checked(self):
        self.add_report()
        result = self.audit({"status": "complete", "start_date": "2026-08-01",
                             "counts": {"in_range": 1}})
        self.assertFalse(result["eligible"])
        self.assertIn("start_date does not match", " ".join(result["gate_reasons"]))


if __name__ == "__main__":
    unittest.main()
