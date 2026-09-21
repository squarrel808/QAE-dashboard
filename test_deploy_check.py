import importlib.util
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import deploy_check
import run_qae


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.public = self.root / 'macro_hub/public'
        (self.public / 'data').mkdir(parents=True)
        (self.public / 'embeds').mkdir()
        (self.root / 'report_pipeline').mkdir()
        self.today = str(date.today())
        self.records = [{'date': self.today, 'pub_date': self.today, 'house': 'GS', 'title': 'Example'}]
        self.write('report_pipeline/houseview_records.json', self.records)
        self.write('macro_hub/public/data/reports.json', [
            {'date': self.today, 'source': 'GS', 'title': 'Example'}])
        self.write('macro_hub/public/data/houseviews.json', {'views': [{'date': self.today}]})

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), 'utf-8')

    def test_nightly_reads_reports_without_browser_or_haver(self):
        opts = run_qae.parse_opts(['run_qae.py', '/nightly'])
        self.assertTrue(opts['report'])
        self.assertTrue(opts['web'])
        self.assertFalse(opts['collect_report'])
        self.assertFalse(opts['build'])
        self.assertFalse(opts['haver'])

    def test_nohouseviews_still_updates_report_list(self):
        opts = run_qae.parse_opts(['run_qae.py', '/nightly', '/nohouseviews'])
        self.assertTrue(opts['report'])
        self.assertFalse(opts['houseviews'])

    def test_fresh_summary_missing_from_output_blocks_publish(self):
        self.write('macro_hub/public/data/reports.json', [
            {'date': self.today, 'source': 'GS', 'title': 'Old report'}])
        with self.assertRaisesRegex(ValueError, '누락'):
            deploy_check.prepare('test', self.root)

    def test_stale_input_blocks_publish(self):
        self.records[0]['date'] = str(date.today() - timedelta(days=15))
        self.write('report_pipeline/houseview_records.json', self.records)
        with self.assertRaisesRegex(ValueError, '오래'):
            deploy_check.prepare('test', self.root)

    def test_remote_marker_without_matching_data_is_not_success(self):
        marker = deploy_check.prepare('test', self.root)
        def fetch(path, run_id):
            if path.endswith('deployment_status.json'):
                return json.dumps(marker).encode()
            return b'old data'
        self.assertFalse(deploy_check.verify(marker, log=lambda x: None, timeout=0, fetch=fetch))

    def test_matching_files_and_report_page_confirm_success(self):
        marker = deploy_check.prepare('test', self.root)
        def fetch(path, run_id):
            return self.today.encode() if path == 'reports' else (self.public / path).read_bytes()
        self.assertTrue(deploy_check.verify(marker, log=lambda x: None, timeout=0, fetch=fetch))

    def test_windows_git_line_endings_do_not_report_false_failure(self):
        (self.public / 'embeds/example.html').write_bytes(b'<html>\r\n<body>example</body>\r\n</html>')
        marker = deploy_check.prepare('test', self.root)
        def fetch(path, run_id):
            return self.today.encode() if path == 'reports' else (self.public / path).read_bytes().replace(b'\r\n', b'\n')
        self.assertTrue(deploy_check.verify(marker, log=lambda x: None, timeout=0, fetch=fetch))

    def test_report_page_must_also_update(self):
        marker = deploy_check.prepare('test', self.root)
        def fetch(path, run_id):
            return b'<html>error</html>' if path == 'reports' else (self.public / path).read_bytes()
        self.assertFalse(deploy_check.verify(marker, log=lambda x: None, timeout=0, fetch=fetch))

    def test_empty_input_preserves_previous_records(self):
        path = Path(__file__).parent / 'report_pipeline/parse_daily_docx.py'
        spec = importlib.util.spec_from_file_location('parse_fixture', path)
        parser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parser)
        parser.BASE = str(self.root / 'empty')
        parser.OUT = str(self.root / 'report_pipeline/houseview_records.json')
        before = Path(parser.OUT).read_bytes()
        with self.assertRaises(SystemExit):
            parser.main()
        self.assertEqual(before, Path(parser.OUT).read_bytes())

    def test_previous_commit_is_pushed_even_without_new_changes(self):
        commands = []
        def popen(cmd, **kwargs):
            commands.append(cmd)
            return object()
        with patch.object(run_qae.subprocess, 'check_output', return_value=''), \
             patch.object(run_qae.subprocess, 'Popen', side_effect=popen), \
             patch.object(run_qae, '_stream', return_value=0), \
             patch.object(run_qae, 'log'), patch.object(run_qae, 'append_step'):
            result = run_qae.run_git('test', True, False)
        self.assertIn(['git', 'push'], commands)
        self.assertEqual(result[0], 'SENT')

    def test_unrelated_staged_changes_block_commit_and_push(self):
        with patch.object(run_qae.subprocess, 'check_output', return_value='unrelated.py\n'), \
             patch.object(run_qae.subprocess, 'Popen') as popen, \
             patch.object(run_qae, 'log'), patch.object(run_qae, 'append_step'):
            result = run_qae.run_git('test', True, False)
        popen.assert_not_called()
        self.assertEqual(result[0], 'FAILED')


if __name__ == '__main__':
    unittest.main()
