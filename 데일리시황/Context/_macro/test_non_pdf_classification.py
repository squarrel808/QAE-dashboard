"""Offline regression tests for conservative, page-verified non-PDF classification.

DOM snapshots model the observed HSBC templates. No real browser, broker requests,
production database, or download directories are used by these tests.
"""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import macro_bulk_downloader as m


def newsletter_report():
    return m.Report('HSBC', '24lNTWShrCxjQZ', 'Global Essentials', '04 Sep 2026',
                    'https://www.research.hsbc.com/O/24lNTWShrCxjQZ',
                    'https://www.research.hsbc.com/ibcom/in/reach/servlet/Reach?productid=5')


def content_snapshot(**changes):
    result = {
        'ready': 'complete', 'blocked': False, 'pdf_control': False,
        'newsletter_title': 'Global Essentials', 'newsletter_date': '04 September 2026',
        'focus_reports': 7, 'newsletter_actions': True, 'linked_report_disclosures': True,
        'media_player': False, 'media_disclosures': False,
    }
    result.update(changes)
    return result


class NonPDFClassificationTests(unittest.TestCase):
    def setUp(self):
        self.report = newsletter_report()
        self.response = Mock(status=200, headers={'content-type': 'text/html; charset=UTF-8'})
        self.page = Mock(url=self.report.url)
        self.frame = Mock()
        self.frame.evaluate.return_value = content_snapshot()
        self.page.frames = [self.frame]
        self.saver = m.PDFSaver(None, Path('unused-test-output'))

    def evidence(self):
        return self.saver.no_original_pdf_evidence(self.report, self.page, self.response)

    def test_verified_newsletter_records_identity_and_structural_evidence(self):
        evidence = self.evidence()
        self.assertIn('Verified HSBC HTML newsletter: Global Essentials', evidence)
        self.assertIn('2026-09-04', evidence)
        self.assertIn('7 linked Research Focus entries', evidence)
        self.assertIn('no original PDF/download control', evidence)

    def test_verified_standalone_media_requires_player_and_disclosures(self):
        self.report = m.Report('HSBC', 'media123', 'Podcast: The Macro Brief', '04 Sep 2026',
                               'https://www.research.hsbc.com/R/10/media123', self.report.source_url)
        self.page.url = self.report.url
        self.frame.evaluate.return_value = content_snapshot(
            newsletter_title='', newsletter_date='', focus_reports=0,
            newsletter_actions=False, linked_report_disclosures=False,
            media_player=True, media_disclosures=True)
        self.assertIn('Verified HSBC standalone media page', self.evidence())
        for missing in ('media_player', 'media_disclosures'):
            with self.subTest(missing=missing):
                self.frame.evaluate.return_value = content_snapshot(
                    media_player=missing != 'media_player', media_disclosures=missing != 'media_disclosures')
                self.assertEqual(self.evidence(), '')

    def test_title_or_missing_controls_alone_are_not_evidence(self):
        for missing, value in [('focus_reports', 0), ('newsletter_actions', False),
                               ('linked_report_disclosures', False), ('ready', 'loading'),
                               ('newsletter_title', 'Unrecognized newsletter')]:
            with self.subTest(missing=missing):
                self.frame.evaluate.return_value = content_snapshot(**{missing: value})
                self.assertEqual(self.evidence(), '')

    def test_login_redirect_and_rendered_access_error_are_not_classified(self):
        self.page.url = 'https://www.research.hsbc.com/login'
        self.assertEqual(self.evidence(), '')
        self.frame.evaluate.assert_not_called()
        self.page.url = self.report.url
        self.frame.evaluate.return_value = content_snapshot(blocked=True)
        self.assertEqual(self.evidence(), '')

    def test_permission_error_or_non_html_response_is_not_classified(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                self.response.status = status
                self.assertEqual(self.evidence(), '')
        self.response.status = 200
        self.response.headers = {'content-type': 'application/pdf'}
        self.assertEqual(self.evidence(), '')
        self.response = None
        self.assertEqual(self.evidence(), '')
        self.frame.evaluate.assert_not_called()

    def test_other_document_host_house_or_unsupported_route_is_not_classified(self):
        for url in ('https://www.research.hsbc.com/O/another-id',
                    'https://login.example.test/O/24lNTWShrCxjQZ'):
            with self.subTest(url=url):
                self.page.url = url
                self.assertEqual(self.evidence(), '')
        self.page.url = self.report.url
        self.report.doc_id = 'another-id'
        self.assertEqual(self.evidence(), '')
        self.report = newsletter_report()
        self.report.house = 'GS'
        self.assertEqual(self.evidence(), '')
        self.report = newsletter_report()
        self.report.url = self.page.url = 'https://www.research.hsbc.com/R/101/24lNTWShrCxjQZ'
        self.assertEqual(self.evidence(), '')

    def test_other_publication_date_is_not_classified(self):
        for stamp in ('03 September 2026', '', 'Unparseable date'):
            with self.subTest(stamp=stamp):
                self.frame.evaluate.return_value = content_snapshot(newsletter_date=stamp)
                self.assertEqual(self.evidence(), '')

    def test_pdf_control_in_main_or_secondary_frame_blocks_classification(self):
        self.frame.evaluate.return_value = content_snapshot(pdf_control=True)
        self.assertEqual(self.evidence(), '')
        self.frame.evaluate.return_value = content_snapshot()
        secondary = Mock()
        secondary.evaluate.return_value = content_snapshot(pdf_control=True)
        self.page.frames.append(secondary)
        self.assertEqual(self.evidence(), '')
        secondary.evaluate.return_value = content_snapshot(blocked=True)
        self.assertEqual(self.evidence(), '')

    def test_unreadable_or_empty_frames_do_not_establish_non_pdf(self):
        self.frame.evaluate.side_effect = RuntimeError('Frame detached')
        self.assertEqual(self.evidence(), '')
        self.page.frames = []
        self.assertEqual(self.evidence(), '')

    def test_positive_evidence_must_remain_stable_before_download_exits(self):
        context = Mock()
        page = Mock()
        page.frames = []
        page.is_closed.return_value = False
        context.new_page.return_value = page
        clock = [0.0]
        page.wait_for_timeout.side_effect = lambda millis: clock.__setitem__(0, clock[0] + millis / 1000)
        saver = m.PDFSaver(context, Path('unused-test-output'), timeout=4)
        saver.request_pdf = Mock(return_value=None)
        saver.no_original_pdf_evidence = Mock(return_value='Verified newsletter evidence')
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(m.NoOriginalPDF, 'Verified newsletter evidence'):
                saver.download(self.report, Mock())
        self.assertGreaterEqual(clock[0], 2)
        self.assertGreater(saver.no_original_pdf_evidence.call_count, 1)
        page.close.assert_called_once()

    def test_verified_non_pdf_is_recorded_once_and_not_retried_on_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = m.parser().parse_args(['--mode', 'backfill', '--output', str(root / 'out'),
                                         '--retries', '3', '--delay', '0'])
            state = m.State(root / 'state')
            try:
                collector = m.Collector(None, args, state, date(2026, 3, 9), date(2026, 9, 9), m.START_URLS)
                reason = 'Verified HSBC HTML newsletter: Global Essentials; exact date and linked-report template.'
                collector.saver.download = Mock(side_effect=m.NoOriginalPDF(reason))
                collector.consume([self.report], None)
                collector.saver.download.assert_called_once()
                row = state.db.execute('SELECT status,error,attempts,path FROM reports').fetchone()
                self.assertEqual((row['status'], row['error'], row['attempts'], row['path']),
                                 ('no_original_pdf', reason, 1, ''))
                self.assertEqual(collector.counts['HSBC']['no_original_pdf'], 1)
                self.assertEqual(collector.counts['HSBC']['failed'], 0)
                resumed = m.Collector(None, args, state, date(2026, 3, 9), date(2026, 9, 9), m.START_URLS)
                resumed.saver.download = Mock(side_effect=AssertionError('Verified non-PDF should not be retried'))
                resumed.consume([self.report], None)
                resumed.saver.download.assert_not_called()
                self.assertEqual(resumed.counts['HSBC']['no_original_pdf'], 1)
            finally:
                state.db.close()

    def test_plain_timeout_remains_a_retryable_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = m.parser().parse_args(['--mode', 'backfill', '--output', str(root / 'out'),
                                         '--retries', '2', '--delay', '0'])
            state = m.State(root / 'state')
            try:
                collector = m.Collector(None, args, state, date(2026, 3, 9), date(2026, 9, 9), m.START_URLS)
                collector.saver.download = Mock(side_effect=m.Incomplete('Original PDF did not arrive'))
                with patch.object(m.time, 'sleep'):
                    collector.consume([self.report], None)
                self.assertEqual(collector.saver.download.call_count, 2)
                row = state.db.execute('SELECT status,attempts FROM reports').fetchone()
                self.assertEqual((row['status'], row['attempts']), ('failed', 2))
                self.assertEqual(collector.counts['HSBC']['failed'], 1)
                self.assertEqual(collector.counts['HSBC']['no_original_pdf'], 0)
            finally:
                state.db.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
