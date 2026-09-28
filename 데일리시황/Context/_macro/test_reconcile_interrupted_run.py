import json
import tempfile
import unittest
from pathlib import Path

from macro_bulk_downloader import State, atomic_write_json
from reconcile_interrupted_run import reconcile


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.run_id = "20260909_133207_4bb1f1"
        self.report = {"run_id": self.run_id, "finished": None, "overall_status": "running",
                       "houses": {"Citi": {"status": "running", "counts": {"already_saved": 8}},
                                  "HSBC": {"status": "not_started", "counts": {}}}}
        self.state = State(self.folder)
        self.addCleanup(self.state.db.close)
        self.state.db.execute("INSERT INTO runs(run_id,summary) VALUES(?,?)",
                              (self.run_id, json.dumps(self.report["houses"])))
        self.state.db.execute("INSERT INTO reports(house,doc_id,status,updated) VALUES('Citi','existing','downloaded','2026-09-09T14:00:00')")
        self.state.db.commit()
        self.path = self.folder / "logs/2026-09-09" / f"run_{self.run_id}.json"
        self.latest = self.folder / "logs/latest_run.json"
        atomic_write_json(self.path, self.report)
        atomic_write_json(self.latest, self.report)
        self.path.with_suffix(".log").write_text(f"INFO Run={self.run_id} mode=backfill\nINFO [Citi] saved a.pdf\nWARNING [Citi] failed b: error\n", encoding="utf-8")

    def run_reconcile(self, **kwargs):
        return reconcile(self.folder, self.run_id, "Stopped for isolation", **kwargs)

    def test_preview_is_read_only_and_requires_shutdown_confirmation_to_apply(self):
        result = self.run_reconcile()
        self.assertFalse(result["applied"])
        self.assertEqual(json.loads(self.path.read_text())["overall_status"], "running")
        self.assertIsNone(self.state.db.execute("SELECT finished FROM runs").fetchone()[0])
        with self.assertRaisesRegex(ValueError, "confirm-stopped"):
            self.run_reconcile(apply=True)

    def test_preserves_reports_and_recovers_only_logged_counts(self):
        before = list(map(tuple, self.state.db.execute("SELECT * FROM reports")))
        result = self.run_reconcile(apply=True, confirmed_stopped=True)
        self.assertEqual(before, list(map(tuple, self.state.db.execute("SELECT * FROM reports"))))
        self.assertEqual(result["run"]["houses"]["Citi"]["counts"],
                         {"already_saved": 8, "downloaded": 1, "failed": 1})
        self.assertEqual(result["run"]["houses"]["HSBC"]["previous_status"], "not_started")
        self.assertTrue(result["latest_updated"])
        self.assertTrue((self.folder / "manifest.csv").exists())
        self.assertEqual(json.loads(self.latest.read_text())["overall_status"], "incomplete")
        self.assertIsNotNone(self.state.db.execute("SELECT finished FROM runs").fetchone()[0])

    def test_does_not_overwrite_newer_latest(self):
        atomic_write_json(self.latest, {"run_id": "20260909_150000_abcdef"})
        before = self.latest.read_bytes()
        self.assertFalse(self.run_reconcile(apply=True, confirmed_stopped=True)["latest_updated"])
        self.assertEqual(self.latest.read_bytes(), before)

    def test_finished_runs_are_rejected(self):
        self.state.db.execute("UPDATE runs SET finished='2026-09-09T14:30:00'")
        self.state.db.commit()
        with self.assertRaisesRegex(ValueError, "already finished"):
            self.run_reconcile(apply=True, confirmed_stopped=True)


if __name__ == "__main__":
    unittest.main()
