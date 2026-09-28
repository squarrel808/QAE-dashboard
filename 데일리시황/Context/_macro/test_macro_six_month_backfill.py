"""Offline tests for the one-off trial-before-six-month collection policy."""
import argparse
import json
import logging
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import run_macro_six_month_backfill as runner


class CampaignTests(unittest.TestCase):
    def run_case(self, prior, trial_results, extension_results):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = argparse.Namespace(state_dir=root/'state', output=root/'out',
                end=date(2026,9,9), trial_start=date(2026,6,8), extension_start=date(2026,3,9),
                houses=['HSBC','BofA'], after_run='prior', trial_retries=1, extension_retries=0,
                min_free_gib=5, stall_minutes=15, house_timeout_minutes=360)
            calls = []

            def execute(args, house, start, end, phase, campaign, save):
                calls.append((house, phase, start, end))
                result = (trial_results if phase == 'trial' else extension_results)[house]
                return result, phase + '_' + house

            def audit(state, house, start, end, result):
                passed = result.get('status') == 'complete'
                return {'eligible': passed, 'gate_reasons': [] if passed else ['incomplete trial']}

            try:
                with patch.object(runner, 'wait_for_prior_run', return_value=prior), \
                     patch.object(runner, 'execute_house', side_effect=execute), \
                     patch.object(runner, 'audit_house', side_effect=audit):
                    code = runner.run_campaign(args)
                result = json.loads((args.state_dir/'logs'/'latest_campaign.json').read_text(encoding='utf-8'))
                return code, calls, result
            finally:
                logging.shutdown()
                for handler in logging.getLogger().handlers[:]:
                    logging.getLogger().removeHandler(handler)

    def test_only_trial_verified_houses_expand_and_never_before_six_months(self):
        prior = {'finished':'done','mode':'backfill','start_date':'2026-06-08','end_date':'2026-09-09',
                 'houses':{'HSBC':{'status':'complete','coverage_guard_version':1},'BofA':{'status':'incomplete'}}}
        code, calls, result = self.run_case(prior, {'BofA':{'status':'incomplete'}}, {'HSBC':{'status':'complete'}})
        self.assertEqual(code, 2)
        self.assertEqual([(h,p) for h,p,*_ in calls], [('BofA','trial'),('HSBC','extension')])
        self.assertEqual(calls[-1][2:], (date(2026,3,9), date(2026,6,7)))
        self.assertTrue(result['houses']['HSBC']['extension']['eligible'])
        self.assertEqual(result['houses']['BofA']['extension']['status'], 'held_for_trial_errors')
        self.assertNotIn('year_start', result)
        self.assertFalse(result['scheduled'])

    def test_unfinished_or_short_prior_run_requires_new_trials(self):
        prior = {'finished':None,'mode':'backfill','start_date':'2026-09-01','end_date':'2026-09-09',
                 'houses':{'HSBC':{'status':'complete'},'BofA':{'status':'complete'}}}
        complete = {h:{'status':'complete'} for h in ['HSBC','BofA']}
        code, calls, result = self.run_case(prior, complete, complete)
        self.assertEqual(code, 0)
        self.assertEqual([(h,p) for h,p,*_ in calls],
                         [('HSBC','trial'),('BofA','trial'),('HSBC','extension'),('BofA','extension')])
        self.assertEqual(result['status'], 'complete')

    def test_january_window_is_rejected(self):
        with patch.object(runner, 'run_campaign') as launch, self.assertRaises(SystemExit):
            runner.main(['--end','2026-09-09','--extension-start','2026-01-01'])
        launch.assert_not_called()

    def test_old_completion_without_pagination_proof_requires_recheck(self):
        prior = {'finished':'done','mode':'backfill','start_date':'2026-06-08','end_date':'2026-09-09',
                 'houses':{h:{'status':'complete'} for h in ['HSBC','BofA']}}
        complete = {h:{'status':'complete'} for h in ['HSBC','BofA']}
        _, calls, _ = self.run_case(prior, complete, complete)
        self.assertEqual([(h,p) for h,p,*_ in calls[:2]], [('HSBC','trial'),('BofA','trial')])

    def test_low_disk_space_prevents_collection(self):
        with patch.object(runner, 'check_disk_space', side_effect=runner.LowDiskSpace('low disk')):
            code, calls, result = self.run_case({}, {}, {})
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])
        self.assertEqual(result['status'], 'stopped_low_disk_space')

    def test_disk_reserve_checks_output_and_state(self):
        with tempfile.TemporaryDirectory() as temp:
            args = argparse.Namespace(output=Path(temp)/'out', state_dir=Path(temp)/'state', min_free_gib=5)
            usage = argparse.Namespace(free=4*1024**3)
            with patch.object(runner.shutil, 'disk_usage', return_value=usage), self.assertRaises(runner.LowDiskSpace):
                runner.check_disk_space(args, {})

    def test_runtime_low_disk_stops_only_its_owned_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = argparse.Namespace(output=root/'out', state_dir=root/'state', campaign_dir=root,
                                      min_free_gib=5, stall_minutes=15, house_timeout_minutes=360)
            campaign = {'attempts': [], 'active': None}
            worker = Mock(pid=98765)
            worker.poll.side_effect = [None, None, -1]
            worker.wait.return_value = -1
            with patch.object(runner, 'check_disk_space', side_effect=[None, runner.LowDiskSpace('low disk')]), \
                 patch.object(runner.subprocess, 'Popen', return_value=worker) as spawn, \
                 patch.object(runner.subprocess, 'run', return_value=Mock(returncode=0)) as stop, \
                 self.assertRaises(runner.LowDiskSpace):
                runner.execute_house(args, 'HSBC', date(2026,3,9), date(2026,6,7), 'extension', campaign, Mock())
            command = spawn.call_args.args[0]
            self.assertEqual(command[command.index('--start')+1], '2026-03-09')
            self.assertEqual(command[command.index('--end')+1], '2026-06-07')
            if runner.sys.platform == 'win32':
                self.assertEqual(stop.call_args.args[0], ['taskkill','/PID','98765','/T','/F'])
            else:
                worker.terminate.assert_called_once()
            self.assertIsNone(campaign['active'])
            self.assertEqual(campaign['attempts'][0]['status'], 'stopped_low_disk_space')

    def test_watchdog_defaults_and_invalid_limits(self):
        with patch.object(runner, 'run_campaign', return_value=0) as run:
            self.assertEqual(runner.main([]), 0)
        self.assertEqual(run.call_args.args[0].stall_minutes, 15)
        self.assertEqual(run.call_args.args[0].house_timeout_minutes, 360)
        for values in [('0','360'), ('20','10'), ('15','1441')]:
            with self.subTest(values=values), patch.object(runner, 'run_campaign') as run, self.assertRaises(SystemExit):
                runner.main(['--stall-minutes', values[0], '--house-timeout-minutes', values[1]])
            run.assert_not_called()

    def test_watchdog_failure_does_not_prevent_next_house(self):
        prior = {'finished':'done','mode':'backfill','start_date':'2026-06-08','end_date':'2026-09-09',
                 'houses':{}}
        code, calls, result = self.run_case(prior,
            {'HSBC':{'status':'incomplete', 'stop_kind':'stopped_no_progress'},
             'BofA':{'status':'complete'}}, {'BofA':{'status':'complete'}})
        self.assertEqual(code, 2)
        self.assertEqual([(h,p) for h,p,*_ in calls], [('HSBC','trial'),('BofA','trial'),('BofA','extension')])
        self.assertEqual(result['houses']['HSBC']['extension']['status'], 'held_for_trial_errors')


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.args = argparse.Namespace(output=root/'out', state_dir=root/'state', campaign_dir=root,
                                       min_free_gib=5, stall_minutes=15, house_timeout_minutes=360)
        self.campaign = {'attempts': [], 'active': None}
        self.worker = Mock(pid=98765, returncode=None)
        self.worker.poll.side_effect = lambda: self.worker.returncode
        self.worker.wait.side_effect = lambda timeout: self.worker.returncode
        self.save = Mock()

    def stop(self, worker):
        worker.returncode = -1
        return -1

    def invoke(self):
        return runner.execute_house(self.args, 'GS', date(2026,6,8), date(2026,9,9),
                                    'trial', self.campaign, self.save)

    def patches(self, clocks, snapshots=None, run=None):
        stack = ExitStack()
        stack.enter_context(patch.object(runner, 'check_disk_space'))
        stack.enter_context(patch.object(runner.subprocess, 'Popen', return_value=self.worker))
        self.stop_mock = stack.enter_context(patch.object(runner, 'stop_owned_worker', side_effect=self.stop))
        stack.enter_context(patch.object(runner, 'read_run', return_value=run))
        stack.enter_context(patch.object(runner, 'collector_idle', return_value=True))
        stack.enter_context(patch.object(runner.time, 'monotonic', side_effect=clocks))
        stack.enter_context(patch.object(runner.time, 'sleep'))
        if snapshots is not None:
            stack.enter_context(patch.object(runner, 'progress_snapshot', side_effect=snapshots))
        return stack

    def test_no_progress_stops_attempt_and_records_confirmed_exit(self):
        with self.patches([0, 0, 901]):
            result, run_id = self.invoke()
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['stop_kind'], 'stopped_no_progress')
        self.stop_mock.assert_called_once_with(self.worker)
        attempt = self.campaign['attempts'][0]
        self.assertEqual(attempt['exit_code'], -1)
        self.assertTrue(attempt['console_log_exists'])
        self.assertFalse(attempt['collector_log_exists'])
        self.assertEqual(attempt['run_id'], run_id)
        self.assertIsNone(self.campaign['active'])

    def test_real_child_log_change_resets_stall_clock(self):
        # Activity at 899 seconds postpones the deadline to 1799, not 900.
        with self.patches([0, 899, 901, 1800], [('a',), ('b',), ('b',), ('b',)]):
            result, _ = self.invoke()
        self.assertEqual(result['stop_kind'], 'stopped_no_progress')
        self.assertEqual(self.campaign['attempts'][0]['elapsed_seconds'], 1800)
        self.assertEqual(self.campaign['attempts'][0]['idle_seconds'], 901)

    def test_runtime_limit_applies_even_with_continuing_logs(self):
        self.args.stall_minutes = self.args.house_timeout_minutes = 1
        with self.patches([0, 61], [('a',), ('b',)]):
            result, _ = self.invoke()
        self.assertEqual(result['stop_kind'], 'stopped_time_limit')

    def test_post_spawn_checkpoint_failure_still_reaps_worker(self):
        self.save.side_effect = [None, OSError('checkpoint write failed'), None]
        with self.patches([]), self.assertRaisesRegex(OSError, 'checkpoint write failed'):
            self.invoke()
        self.stop_mock.assert_called_once_with(self.worker)
        self.assertEqual(self.campaign['attempts'][0]['exit_code'], -1)
        self.assertEqual(self.campaign['attempts'][0]['status'], 'interrupted')
        self.assertIsNone(self.campaign['active'])

    def test_keyboard_interrupt_is_not_converted_to_next_house(self):
        self.save.side_effect = [None, KeyboardInterrupt(), None]
        with self.patches([]), self.assertRaises(KeyboardInterrupt):
            self.invoke()
        self.stop_mock.assert_called_once()
        self.assertEqual(self.campaign['attempts'][0]['status'], 'interrupted')

    def test_missing_run_log_prevents_false_success(self):
        self.worker.returncode = 0
        run = {'finished':'done', 'houses':{'GS':{'status':'complete', 'counts':{'in_range':3}}}}
        with self.patches([0], run=run):
            self.stop_mock.side_effect = None
            self.stop_mock.return_value = 0
            result, _ = self.invoke()
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('collector log present=False', result['reason'])

    def test_reconciliation_requires_dead_worker_and_free_collector_lock(self):
        with patch.object(runner, 'reconcile') as reconcile:
            with self.assertRaisesRegex(RuntimeError, 'still alive'):
                runner.reconcile_stopped_attempt(self.args, self.worker, '20260909_123456_a1b2c3', 'stalled', {})
            self.worker.returncode = -1
            with patch.object(runner, 'collector_idle', return_value=False), self.assertRaisesRegex(RuntimeError, 'lock remains held'):
                runner.reconcile_stopped_attempt(self.args, self.worker, '20260909_123456_a1b2c3', 'stalled', {})
        reconcile.assert_not_called()

    def test_reconciliation_only_exact_stopped_run_with_matching_artifacts(self):
        self.worker.returncode = -1
        run_id = '20260909_123456_a1b2c3'
        report = self.args.state_dir / 'logs' / '2026-09-09' / f'run_{run_id}.json'
        report.parent.mkdir(parents=True)
        report.touch()
        report.with_suffix('.log').touch()
        attempt = {}
        with patch.object(runner, 'collector_idle', return_value=True), \
             patch.object(runner, 'read_run', return_value={'finished':None}), \
             patch.object(runner, 'reconcile', return_value={'audit':'audit.json'}) as reconcile:
            runner.reconcile_stopped_attempt(self.args, self.worker, run_id, 'stalled', attempt)
        reconcile.assert_called_once_with(self.args.state_dir, run_id, 'stalled', apply=True, confirmed_stopped=True)
        self.assertEqual(attempt['interruption_audit'], 'audit.json')

    def test_snapshot_tracks_size_mtime_and_missing_file(self):
        log = self.args.campaign_dir / 'child.log'
        log.touch()
        self.assertEqual(runner.progress_snapshot((log, log.with_suffix('.missing'))),
                         ((log.stat().st_mtime_ns, 0), None))

    def test_tree_stop_failure_is_not_treated_as_confirmed_exit(self):
        with patch.object(runner.sys, 'platform', 'win32'), \
             patch.object(runner.subprocess, 'run', return_value=Mock(returncode=1)) as stop, \
             self.assertRaisesRegex(RuntimeError, 'Could not stop owned collector tree'):
            runner.stop_owned_worker(self.worker)
        self.assertEqual(stop.call_args.args[0], ['taskkill', '/PID', '98765', '/T', '/F'])
        self.worker.wait.assert_not_called()


if __name__ == '__main__':
    unittest.main()
