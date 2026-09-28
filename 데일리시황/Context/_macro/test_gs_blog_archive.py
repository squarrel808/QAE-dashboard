"""Offline checks for GS web-article archival; no login or network required."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import macro_bulk_downloader as m


class GSBlogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.url = 'https://marquee.gs.com/content/research/en/blogs/2026/09/15/example.html'
        self.report = m.Report('GS', 'example', 'Example weekly update', '', self.url,
                               self.url, published='2026-09-15')
        self.saver = m.PDFSaver(Mock(), self.root)
        self.snapshot = {
            'body': 'Example weekly update Research | Economics | 15 September 2026 '
                    + 'Article paragraph. ' * 50 + 'Goldman Sachs All rights reserved.',
            'ready': 'complete', 'blocked': False, 'embedded': False,
            'links': [{'label': 'Security Guidance', 'href': '/content/dam/research/securityguidance2021.pdf'}],
        }
        self.page = Mock(url=self.url)
        self.page.frames = [SimpleNamespace(evaluate=lambda _: self.snapshot)]
        self.response = SimpleNamespace(status=200, headers={'content-type': 'text/html'})

    def evidence(self):
        return self.saver.no_original_pdf_evidence(self.report, self.page, self.response)

    def test_complete_blog_with_only_legal_pdf_is_recognized(self):
        self.assertTrue(self.evidence())

    def test_pdf_or_blocked_or_unfinished_content_is_not_classified(self):
        original = copy.deepcopy(self.snapshot)
        variants = [
            {'links': [{'label': 'PDF', 'href': '/content/research/example.pdf'}]},
            {'links': [{'label': 'PDF', 'href': ''}]},
            {'embedded': True}, {'blocked': True}, {'ready': 'loading'},
            {'body': 'Example weekly update'},
            {'body': original['body'].replace('Example weekly update', 'Different article')},
            {'body': original['body'].replace('Goldman Sachs All rights reserved.', '')},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                self.snapshot = dict(original, **changes)
                self.assertFalse(self.evidence())

    def test_redirect_and_non_blog_and_bad_response_are_not_classified(self):
        for url in [self.url.replace('example.html', 'other.html'),
                    self.url.replace('/blogs/', '/reports/'),
                    self.url.replace('marquee.gs.com', 'other.example')]:
            with self.subTest(url=url):
                self.page.url = url
                self.assertFalse(self.evidence())
        self.page.url = self.url
        self.response.status = 403
        self.assertFalse(self.evidence())

    def test_archive_and_resume_require_intact_html(self):
        self.page.content.return_value = '<html><body>Original article</body></html>'
        self.page.locator.return_value.inner_text.return_value = self.snapshot['body']
        path, raw = self.saver.archive_gs_blog(self.report, self.page, self.evidence())
        self.assertEqual(path.suffix, '.html')
        self.assertEqual(path.read_bytes(), raw)
        self.assertTrue(path.with_suffix('.txt').exists())
        self.assertEqual(json.loads(path.with_suffix('.json').read_text())['source_url'], self.url)
        state = m.State(self.root / 'state')
        self.addCleanup(state.db.close)
        state.record(self.report)
        state.result(self.report, 'no_original_pdf', path=path, raw=raw)
        self.assertTrue(state.known_no_original_pdf(self.report))
        path.write_text('damaged', encoding='utf-8')
        self.assertFalse(state.known_no_original_pdf(self.report))


if __name__ == '__main__':
    unittest.main()
