"""Refresh integration: safe preview, successful-build gating, repeatable sync."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_regional_dashboards as builder

spec = importlib.util.spec_from_file_location('equity_entry', Path(__file__).parent / '유로존_dashboard' / 'build_market_rotation_dashboard.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class RefreshTests(unittest.TestCase):
    def test_sync_updates_only_target_and_skips_identical_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target, other = root / 'source.html', root / 'embeds' / 'market.html', root / 'other.html'
            source.write_text('<html>Stock Map 1</html>', encoding='utf-8')
            other.write_text('unrelated', encoding='utf-8')
            self.assertTrue(builder.sync_dashboard_embed(source, target))
            stamp = target.stat().st_mtime_ns
            self.assertFalse(builder.sync_dashboard_embed(source, target))
            self.assertEqual(stamp, target.stat().st_mtime_ns)
            source.write_text('<html>Stock Map 2</html>', encoding='utf-8')
            self.assertTrue(builder.sync_dashboard_embed(source, target))
            self.assertEqual(source.read_bytes(), target.read_bytes())
            self.assertEqual('unrelated', other.read_text(encoding='utf-8'))
            self.assertFalse(list(target.parent.glob('*.tmp')))

    def test_missing_source_and_bad_target_preserve_previous_embed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'market.html'
            target.write_text('last successful', encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                builder.sync_dashboard_embed(root / 'missing.html', target)
            with self.assertRaises(ValueError):
                builder.sync_dashboard_embed(target, target)
            with self.assertRaises(ValueError):
                builder.sync_dashboard_embed(target, root / 'raw.xlsx')
            self.assertEqual('last successful', target.read_text(encoding='utf-8'))

    def test_failed_build_does_not_sync(self):
        argv = ['build', '--region', 'all', '--sync-embed', 'test.html']
        with patch('sys.argv', argv), patch.object(builder, 'load_sources', return_value=({}, [])), \
             patch.object(builder, 'recover_template_from_standalone'), \
             patch.object(builder, 'build', side_effect=[{}, RuntimeError('second region failed')]), \
             patch.object(builder, 'sync_dashboard_embed') as sync:
            with self.assertRaisesRegex(RuntimeError, 'second region failed'):
                builder.main()
            sync.assert_not_called()

    def test_successful_build_syncs_expected_global_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = ['build', '--region', 'europe', '--output-root', str(root), '--sync-embed', str(root / 'web.html')]
            with patch('sys.argv', argv), patch.object(builder, 'load_sources', return_value=({}, [])), \
                 patch.object(builder, 'recover_template_from_standalone'), patch.object(builder, 'build', return_value={}), \
                 patch.object(builder, 'sync_dashboard_embed') as sync:
                builder.main()
                sync.assert_called_once_with(root / '유로존_dashboard' / 'Market_Rotation_Dashboard_17_Indices.html', root / 'web.html')

    def test_invalid_region_rejected_before_loading(self):
        with patch('sys.argv', ['build', '--region', 'japan', '--sync-embed', 'web.html']), \
             patch.object(builder, 'load_sources') as load:
            with self.assertRaises(SystemExit) as error:
                builder.main()
            self.assertEqual(2, error.exception.code)
            load.assert_not_called()

    def test_default_entry_syncs_but_preview_and_optout_do_not(self):
        command = entry.build_command([])
        self.assertIn('--sync-embed', command)
        self.assertEqual(Path(command[-1]), Path(entry.__file__).resolve().parents[4] / 'macro_hub/public/embeds/market_rotation.html')
        for args in (['--no-sync-embed'], ['--output-root', 'preview'], ['--output-root=preview'],
                     ['--asset-root', 'assets'], ['--asset-root=assets'], ['--europe-template=trial.html'], ['--region=us'], ['--help']):
            with self.subTest(args=args):
                self.assertNotIn('--sync-embed', entry.build_command(args))
        self.assertIn('--sync-embed', entry.build_command(['--output-root=preview', '--sync-embed', 'preview/web.html']))

    def test_abbreviated_preview_options_fail_before_any_work(self):
        for argument in ('--output-ro', '--asset-ro', '--europe-temp'):
            command = entry.build_command([argument, 'preview'])
            with self.subTest(argument=argument), patch('sys.argv', command[3:]), patch.object(builder, 'load_sources') as load:
                with self.assertRaises(SystemExit) as error:
                    builder.main()
                self.assertEqual(2, error.exception.code)
                load.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
