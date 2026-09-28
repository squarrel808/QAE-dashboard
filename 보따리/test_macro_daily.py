"""Offline policy tests; no browser, production database, or downloads are used."""
from __future__ import annotations

import contextlib
import io
import json
import logging
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import macro_daily as daily


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.args = daily.parse_args(['--end', '2026-09-09', '--lookback-days', '7'])
        self.args.state_dir = self.root / 'state'
        self.args.output = self.root / 'output'

    def tearDown(self):
        logging.shutdown()
        for handler in list(logging.getLogger().handlers):
            logging.getLogger().removeHandler(handler)
            handler.close()
        self.temp.cleanup()

    def report(self):
        return json.loads((self.args.state_dir / 'logs/latest_daily.json').read_text(encoding='utf-8'))

    def check(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = daily.run_daily(self.args)
        return code, json.loads(output.getvalue())

    def test_defaults_and_fixed_destination(self):
        self.assertEqual(self.args.lookback_days, 7)
        self.assertEqual(set(self.args.houses), {'BofA', 'JPM', 'GS', 'Citi', 'HSBC'})
        self.assertEqual(self.args.timeout_minutes, 120)
        self.assertEqual(self.args.stall_minutes, 15)
        self.assertEqual(self.args.min_free_gib, 5)
        normal = daily.parse_args([])
        self.assertEqual(normal.lookback_days, 1)
        self.assertEqual(normal.state_dir, daily.STATE_DIR)
        self.assertEqual(normal.output, daily.OUTPUT)
        self.assertEqual(daily.PORT, 9223)

    def test_invalid_or_unsafe_options_rejected(self):
        cases = [
            ['--lookback-days', '0'], ['--lookback-days', '32'],
            ['--min-free-gib', '4.9'], ['--stall-minutes', '0'],
            ['--timeout-minutes', '1500'], ['--timeout-minutes', '10'],
            ['--lookback', '10'], ['--cdp-url', 'http://localhost:9222'],
            ['--profile-dir', 'C:/selenium_profile'], ['--state-dir', str(self.root)],
        ]
        for argv in cases:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                daily.parse_args(argv)

    def test_command_uses_verified_launcher_and_explicit_window(self):
        command = daily.build_command(self.args, '20260909_180000_abcdef', date(2026, 9, 3), date(2026, 9, 9))
        self.assertEqual(Path(command[2]), daily.MACRO_DIR / 'run_macro_separate_chrome.py')
        for key, value in {'--mode': 'daily', '--start': '2026-09-03', '--end': '2026-09-09',
                           '--lookback-days': '7', '--run-id': '20260909_180000_abcdef',
                           '--state-dir': str(self.args.state_dir), '--output': str(self.args.output)}.items():
            self.assertEqual(command[command.index(key) + 1], value)
        self.assertNotIn('--cdp-url', command)
        self.assertNotIn('--profile-dir', command)
        self.assertFalse(any('9222' in item for item in command))

    def test_check_ready_creates_nothing(self):
        self.args.check = True
        with patch.object(daily.subprocess, 'Popen', side_effect=AssertionError('No child in check')), \
             patch.object(daily.importlib.util, 'find_spec', return_value=object()):
            code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'ready_to_launch')
        self.assertEqual((report['start'], report['end']), ('2026-09-03', '2026-09-09'))
        self.assertTrue(report['check_only'])
        self.assertFalse(report['scheduled'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_check_busy_starts_nothing(self):
        self.args.check = True
        with patch.object(daily, 'lock_busy', return_value=True), \
             patch.object(daily.subprocess, 'Popen', side_effect=AssertionError('No child')), \
             patch.object(daily.importlib.util, 'find_spec', return_value=object()):
            code, report = self.check()
        self.assertEqual(code, 3)
        self.assertEqual(report['status'], 'blocked_by_active_collection')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_lock_probe_matches_real_os_lock_without_changing_file(self):
        self.assertFalse(daily.lock_busy(self.args.state_dir))
        self.assertFalse(self.args.state_dir.exists())
        with daily.m.run_lock(self.args.state_dir):
            lock_file = self.args.state_dir / 'collector.lock'
            before = lock_file.stat()
            self.assertTrue(daily.lock_busy(self.args.state_dir))
            after = lock_file.stat()
            self.assertEqual((before.st_size, before.st_mtime_ns), (after.st_size, after.st_mtime_ns))
        self.assertFalse(daily.lock_busy(self.args.state_dir))

    def test_check_low_space_starts_nothing(self):
        self.args.check = True
        with patch.object(daily.shutil, 'disk_usage', return_value=SimpleNamespace(free=4 * 1024**3)), \
             patch.object(daily.subprocess, 'Popen', side_effect=AssertionError('No child')):
            code, report = self.check()
        self.assertEqual(code, 4)
        self.assertEqual(report['status'], 'stopped_low_disk_space')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_check_missing_dependency_starts_nothing(self):
        self.args.check = True
        with patch.object(daily.importlib.util, 'find_spec', return_value=None), \
             patch.object(daily.subprocess, 'Popen', side_effect=AssertionError('No child')):
            code, report = self.check()
        self.assertEqual(code, 5)
        self.assertEqual(report['status'], 'missing_dependency')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_disk_reserve_checks_both_targets(self):
        with patch.object(daily.shutil, 'disk_usage', side_effect=[
            SimpleNamespace(free=6 * 1024**3), SimpleNamespace(free=4 * 1024**3)
        ]) as usage, self.assertRaises(daily.DailyStop) as caught:
            daily.check_space(self.args.state_dir, self.args.output, 5)
        self.assertEqual(caught.exception.code, 4)
        self.assertEqual(usage.call_count, 2)

    def test_active_campaign_or_collector_blocks_before_child(self):
        for blocked in ('campaign-control', 'state'):
            @contextlib.contextmanager
            def lock(folder):
                if Path(folder).name == blocked:
                    raise RuntimeError('Busy')
                yield
            with self.subTest(blocked=blocked), patch.object(daily.m, 'run_lock', lock), \
                 patch.object(daily.subprocess, 'Popen', side_effect=AssertionError('No child')):
                self.assertEqual(daily.run_daily(self.args), 3)
                self.assertFalse((self.args.state_dir / 'logs/latest_daily.json').exists())
                reports = list((self.args.state_dir / 'logs/daily').glob('*/daily_*.json'))
                self.assertTrue(reports)
                for path in reports:
                    report = json.loads(path.read_text(encoding='utf-8'))
                    self.assertEqual(report['status'], 'blocked_by_active_collection')
                    self.assertEqual(report['exit_code'], 3)

    def test_busy_attempt_preserves_existing_active_latest(self):
        latest = self.args.state_dir / 'logs/latest_daily.json'
        latest.parent.mkdir(parents=True)
        original = b'{"run_id":"existing_active_run","status":"running"}\n'
        latest.write_bytes(original)
        original_mtime = latest.stat().st_mtime_ns
        for blocked in ('campaign-control', 'state'):
            @contextlib.contextmanager
            def lock(folder):
                if Path(folder).name == blocked:
                    raise RuntimeError('Busy')
                yield
            with self.subTest(blocked=blocked), patch.object(daily.m, 'run_lock', lock), \
                 patch.object(daily.subprocess, 'Popen', side_effect=AssertionError('No child')):
                self.assertEqual(daily.run_daily(self.args), 3)
                self.assertEqual(latest.read_bytes(), original)
                self.assertEqual(latest.stat().st_mtime_ns, original_mtime)

    def test_low_disk_normal_run_blocks_child(self):
        with patch.object(daily.shutil, 'disk_usage', return_value=SimpleNamespace(free=4 * 1024**3)), \
             patch.object(daily.subprocess, 'Popen', side_effect=AssertionError('No child')):
            self.assertEqual(daily.run_daily(self.args), 4)
        self.assertEqual(self.report()['status'], 'stopped_low_disk_space')

    def fake_launcher(self, mutation=None, exit_code=0, held=None):
        def launch(command, **kwargs):
            if held is not None:
                self.assertEqual(held, ['campaign-control'])
            run_id = command[command.index('--run-id') + 1]
            day = f'{run_id[:4]}-{run_id[4:6]}-{run_id[6:8]}'
            artifact = self.args.state_dir / 'logs' / day / f'run_{run_id}.json'
            artifact.parent.mkdir(parents=True, exist_ok=True)
            result = {'run_id': run_id, 'mode': 'daily', 'start': '2026-09-03', 'end': '2026-09-09',
                      'finished': '2026-09-09T18:01:00+09:00',
                      'houses': {house: {'status': 'complete'} for house in self.args.houses}}
            if mutation:
                mutation(result)
            artifact.write_text(json.dumps(result), encoding='utf-8')
            worker = Mock(pid=123456, returncode=exit_code)
            worker.poll.return_value = exit_code
            return worker
        return launch

    def test_success_requires_final_report_and_holds_campaign_lock(self):
        held = []
        final_writes = []
        real_save = daily.m.atomic_write_json
        @contextlib.contextmanager
        def lock(folder):
            held.append(Path(folder).name)
            try:
                yield
            finally:
                held.remove(Path(folder).name)
        def stop(worker):
            self.assertEqual(held, ['campaign-control'])
        def save(path, report):
            if report.get('finished'):
                self.assertEqual(held, ['campaign-control'])
                final_writes.append(Path(path).name)
            real_save(path, report)
        with patch.object(daily.m, 'run_lock', lock), \
             patch.object(daily.subprocess, 'Popen', side_effect=self.fake_launcher(held=held)), \
             patch.object(daily.m, 'atomic_write_json', side_effect=save), \
             patch.object(daily, 'stop_owned_worker', side_effect=stop) as stopped:
            self.assertEqual(daily.run_daily(self.args), 0)
        self.assertEqual(held, [])
        stopped.assert_called_once()
        result = self.report()
        self.assertEqual(result['status'], 'complete')
        self.assertFalse(result['scheduled'])
        self.assertTrue(result['finished'])
        self.assertEqual(len(list((self.args.state_dir / 'logs/daily').glob('*/daily_*.json'))), 1)
        self.assertEqual(len(final_writes), 2)
        self.assertIn('latest_daily.json', final_writes)

    def test_final_write_failure_releases_campaign_lock_after_attempt(self):
        held = []
        real_save = daily.m.atomic_write_json
        @contextlib.contextmanager
        def lock(folder):
            held.append(Path(folder).name)
            try:
                yield
            finally:
                held.remove(Path(folder).name)
        def save(path, report):
            if report.get('finished'):
                self.assertEqual(held, ['campaign-control'])
                raise OSError('Simulated final checkpoint failure')
            real_save(path, report)
        with patch.object(daily.m, 'run_lock', lock), \
             patch.object(daily.subprocess, 'Popen', side_effect=self.fake_launcher(held=held)), \
             patch.object(daily.m, 'atomic_write_json', side_effect=save), \
             patch.object(daily, 'stop_owned_worker'), \
             self.assertRaisesRegex(OSError, 'Simulated final checkpoint failure'):
            daily.run_daily(self.args)
        self.assertEqual(held, [])

    def test_incomplete_or_wrong_final_summary_is_not_success(self):
        mutations = [
            lambda result: result['houses']['JPM'].update(status='incomplete'),
            lambda result: result['houses'].pop('Citi'),
            lambda result: result.update(start='2026-09-02'),
            lambda result: result.update(run_id='20260909_180000_wrong'),
            lambda result: result.update(finished=None),
            lambda result: result.update(mode='backfill'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), \
                 patch.object(daily.subprocess, 'Popen', side_effect=self.fake_launcher(mutation)), \
                 patch.object(daily, 'stop_owned_worker'):
                self.assertEqual(daily.run_daily(self.args), 2)
                self.assertEqual(self.report()['status'], 'incomplete')

    def test_nonzero_child_exit_is_not_success(self):
        with patch.object(daily.subprocess, 'Popen', side_effect=self.fake_launcher(exit_code=2)), \
             patch.object(daily, 'stop_owned_worker'):
            self.assertEqual(daily.run_daily(self.args), 2)

    def test_missing_final_summary_is_error(self):
        worker = Mock(pid=123456, returncode=0)
        worker.poll.return_value = 0
        with patch.object(daily.subprocess, 'Popen', return_value=worker), \
             patch.object(daily, 'stop_owned_worker'):
            self.assertEqual(daily.run_daily(self.args), 5)
        self.assertEqual(self.report()['status'], 'startup_or_collector_error')

    def test_timeout_and_stall_stop_owned_worker_under_campaign_lock(self):
        for times, expected in [([0, 7201], 'stopped_time_limit'), ([0, 0, 901], 'stopped_no_progress')]:
            held = []
            @contextlib.contextmanager
            def lock(folder):
                held.append(Path(folder).name)
                try:
                    yield
                finally:
                    held.remove(Path(folder).name)
            worker = Mock(pid=123456, returncode=None)
            worker.poll.return_value = None
            def stop(child):
                self.assertIs(child, worker)
                self.assertEqual(held, ['campaign-control'])
                child.returncode = 143
            with self.subTest(status=expected), patch.object(daily.m, 'run_lock', lock), \
                 patch.object(daily.subprocess, 'Popen', return_value=worker), \
                 patch.object(daily.time, 'monotonic', side_effect=times), \
                 patch.object(daily.time, 'sleep'), \
                 patch.object(daily, 'stop_owned_worker', side_effect=stop) as stopped:
                self.assertEqual(daily.run_daily(self.args), 6)
                self.assertEqual(self.report()['status'], expected)
                stopped.assert_called_once_with(worker)
                self.assertEqual(held, [])

    def test_failure_of_first_running_checkpoint_still_stops_owned_worker(self):
        real_save = daily.m.atomic_write_json
        failed = False
        worker = Mock(pid=123456, returncode=None)
        worker.poll.return_value = None
        def save(path, report):
            nonlocal failed
            if report.get('status') == 'running' and not failed:
                failed = True
                raise OSError('Simulated checkpoint write failure')
            real_save(path, report)
        with patch.object(daily.subprocess, 'Popen', return_value=worker), \
             patch.object(daily.m, 'atomic_write_json', side_effect=save), \
             patch.object(daily, 'stop_owned_worker') as stop:
            self.assertEqual(daily.run_daily(self.args), 5)
        stop.assert_called_once_with(worker)
        self.assertEqual(self.report()['status'], 'error')

    def test_disk_space_depletion_during_download_stops_owned_worker(self):
        worker = Mock(pid=123456, returncode=None)
        worker.poll.return_value = None
        with patch.object(daily.subprocess, 'Popen', return_value=worker), \
             patch.object(daily, 'check_space', side_effect=[{}, daily.DailyStop('stopped_low_disk_space', 'Low disk', 4)]), \
             patch.object(daily, 'stop_owned_worker') as stop:
            self.assertEqual(daily.run_daily(self.args), 4)
        stop.assert_called_once_with(worker)
        self.assertEqual(self.report()['status'], 'stopped_low_disk_space')

    def test_finished_worker_is_not_killed(self):
        worker = Mock()
        worker.poll.return_value = 0
        with patch.object(daily.subprocess, 'run', side_effect=AssertionError('No taskkill')):
            daily.stop_owned_worker(worker)
        worker.terminate.assert_not_called()

    @unittest.skipUnless(daily.sys.platform == 'win32', 'Windows-specific task tree behavior')
    def test_windows_stop_targets_exact_owned_pid_only(self):
        worker = Mock(pid=123456)
        worker.poll.return_value = None
        with patch.object(daily.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            daily.stop_owned_worker(worker)
        self.assertEqual(run.call_args.args[0], ['taskkill', '/PID', '123456', '/T', '/F'])
        worker.wait.assert_called_once_with(timeout=20)


if __name__ == '__main__':
    unittest.main()
