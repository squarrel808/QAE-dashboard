"""Offline regression tests: launcher must not create a second CDP client."""
import builtins
import subprocess
import unittest
from unittest.mock import Mock, patch

import run_macro_separate_chrome as launcher


class IsolatedWorkerTests(unittest.TestCase):
    def test_minimize_delegated_without_importing_playwright(self):
        command = ['python', 'macro_bulk_downloader.py', '--houses', 'GS']
        worker = Mock()
        worker.wait.return_value = 2
        real_import = builtins.__import__

        def no_playwright(name, *args, **kwargs):
            if name.startswith('playwright'):
                raise AssertionError('Launcher must not create another Playwright client')
            return real_import(name, *args, **kwargs)

        with patch.object(launcher.subprocess, 'Popen', return_value=worker) as popen:
            with patch('builtins.__import__', side_effect=no_playwright):
                self.assertEqual(launcher.run_collector(command), 2)
        self.assertEqual(popen.call_args.args[0], command + ['--minimize-window'])
        self.assertNotIn('--minimize-window', command)
        worker.wait.assert_called_once_with()

    def test_show_window_does_not_add_minimize(self):
        command = ['python', 'macro_bulk_downloader.py']
        worker = Mock()
        worker.wait.return_value = 0
        with patch.object(launcher.subprocess, 'Popen', return_value=worker) as popen:
            self.assertEqual(launcher.run_collector(command, minimize=False), 0)
        self.assertEqual(popen.call_args.args[0], command)

    def test_existing_minimize_flag_not_duplicated(self):
        worker = Mock()
        worker.wait.return_value = 0
        with patch.object(launcher.subprocess, 'Popen', return_value=worker) as popen:
            launcher.run_collector(['python', 'collector.py', '--minimize-window'])
        self.assertEqual(popen.call_args.args[0].count('--minimize-window'), 1)

    def test_interrupt_allows_graceful_child_exit(self):
        worker = Mock()
        worker.wait.side_effect = [KeyboardInterrupt(), 2]
        with patch.object(launcher.subprocess, 'Popen', return_value=worker):
            with patch.object(launcher.subprocess, 'run') as taskkill:
                self.assertEqual(launcher.run_collector(['python', 'collector.py']), 130)
        self.assertEqual(worker.wait.call_args_list[-1].kwargs, {'timeout': 15})
        taskkill.assert_not_called()
        worker.kill.assert_not_called()

    def test_interrupt_terminates_only_owned_windows_child_tree(self):
        worker = Mock(pid=24680)
        worker.wait.side_effect = [KeyboardInterrupt(), subprocess.TimeoutExpired('child', 15), 1]
        worker.poll.return_value = None
        with patch.object(launcher.subprocess, 'Popen', return_value=worker):
            with patch.object(launcher.subprocess, 'run') as taskkill:
                with patch.object(launcher.sys, 'platform', 'win32'):
                    self.assertEqual(launcher.run_collector(['python', 'collector.py']), 130)
        self.assertEqual(taskkill.call_args.args[0], ['taskkill', '/PID', '24680', '/T', '/F'])
        self.assertEqual(taskkill.call_args.kwargs['timeout'], 15)
        self.assertEqual(worker.wait.call_args_list[-1].kwargs, {'timeout': 10})
        worker.kill.assert_not_called()

    def test_failed_tree_stop_has_bounded_owned_worker_fallback(self):
        worker = Mock(pid=24680)
        worker.wait.side_effect = [KeyboardInterrupt(), subprocess.TimeoutExpired('child', 15),
                                   subprocess.TimeoutExpired('child', 10), 1]
        worker.poll.return_value = None
        with patch.object(launcher.subprocess, 'Popen', return_value=worker):
            with patch.object(launcher.subprocess, 'run', side_effect=OSError('taskkill failed')):
                with patch.object(launcher.sys, 'platform', 'win32'):
                    self.assertEqual(launcher.run_collector(['python', 'collector.py']), 130)
        worker.kill.assert_called_once_with()
        self.assertEqual(worker.wait.call_args_list[-1].kwargs, {'timeout': 5})


if __name__ == '__main__':
    unittest.main()
