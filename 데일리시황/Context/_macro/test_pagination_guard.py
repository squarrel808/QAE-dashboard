"""Offline completion tests: no broker, browser, or production files are used."""
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import macro_bulk_downloader as m


def fixture_frame(body='', pager=None, current=None):
    frame = Mock()
    body_locator = Mock()
    body_locator.inner_text.return_value = body
    paging = Mock()
    paging.count.return_value = 0 if pager is None else 1
    paging.is_visible.return_value = pager is not None
    paging.inner_text.return_value = pager or ''
    selected = Mock()
    selected.count.return_value = 0 if current is None else 1
    selected.inner_text.return_value = current or ''
    paging.locator.return_value = selected
    frame.locator.side_effect = lambda selector: paging if selector == '#allReportsPageNumbers' else body_locator
    return frame


def report(ident='one', day='09 Sep 2026'):
    return m.Report('GS', ident, 'Fixture', day, 'https://fixture.test/report', 'https://fixture.test/list')


class PaginationGuardTests(unittest.TestCase):
    def collector(self):
        args = SimpleNamespace(output=None, pdf_timeout=45, max_pages=10,
                               delay=0, mode='backfill')
        collector = m.Collector(Mock(), args, Mock(), date(2026, 6, 9),
                                date(2026, 9, 9), m.START_URLS)
        collector.consume = lambda rows, page: collector.counts['GS'].update(
            in_range=len(rows), already_saved=len(rows))
        return collector

    def test_gs_recent_first_page_missing_next_is_incomplete(self):
        collector = self.collector()
        with patch.object(m, 'frame_with', return_value=fixture_frame()), \
             patch.object(m, 'extract', return_value=[report()]), \
             patch.object(m, 'visible', return_value=None):
            result = collector.run_house('GS')
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('no verified last-page evidence', result['reason'])

    def test_proven_single_page_is_complete_and_versioned(self):
        collector = self.collector()
        with patch.object(m, 'frame_with', return_value=fixture_frame('Page 1 of 1')), \
             patch.object(m, 'extract', return_value=[report()]), \
             patch.object(m, 'visible', return_value=None):
            result = collector.run_house('GS')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['coverage_guard_version'], 1)

    def test_old_page_cutoff_remains_valid_without_pager(self):
        collector = self.collector()
        with patch.object(m, 'extract', return_value=[report(day='01 Jun 2026')]):
            outcome = collector.paginated(Mock(), 'GS', fixture_frame(), lambda: Mock())
        self.assertEqual(outcome, (1, 'cutoff'))

    def test_explicit_last_page_requires_traversal_from_page_one(self):
        with self.assertRaises(m.Incomplete):
            m.pagination_end_evidence(fixture_frame('Page 5 of 5'), 'JPM', 15, 1)
        self.assertEqual(m.pagination_end_evidence(fixture_frame('Page 5 of 5'), 'JPM', 75, 5),
                         'Page 5 of 5')

    def test_advertised_later_page_or_ambiguous_counts_block(self):
        for body in ('Page 1 of 2', 'Page 1 of 1 Page 1 of 2', 'Page 0 of 0'):
            with self.subTest(body=body), self.assertRaises(m.Incomplete):
                m.pagination_end_evidence(fixture_frame(body), 'JPM', 15, 1)

    def test_missing_jpm_and_hsbc_pager_cannot_prove_end(self):
        for house in ('JPM', 'HSBC'):
            with self.subTest(house=house), self.assertRaises(m.Incomplete):
                m.pagination_end_evidence(fixture_frame(), house, 15, 1)

    def test_hsbc_observed_numbered_last_page_is_valid(self):
        frame = fixture_frame(pager='Previous 1 2', current='2')
        self.assertEqual(m.pagination_end_evidence(frame, 'HSBC', 25, 2),
                         'HSBC complete pager 2/2')
        frame = fixture_frame(pager='1', current='1')
        self.assertEqual(m.pagination_end_evidence(frame, 'HSBC', 10, 1),
                         'HSBC complete pager 1/1')

    def test_hsbc_truncated_or_nonterminal_pager_blocks(self):
        for pager, current, visited in (('1 2 3', '2', 2), ('3 4 5', '5', 5),
                                        ('1 2 3 4 5 6', '6', 6), ('1 2', '2', 1)):
            with self.subTest(pager=pager), self.assertRaises(m.Incomplete):
                m.pagination_end_evidence(fixture_frame(pager=pager, current=current),
                                           'HSBC', 30, visited)

    def test_exact_advertised_total_proves_end(self):
        self.assertEqual(m.pagination_end_evidence(fixture_frame(), 'BofA', 25, 2, 25),
                         'advertised total 25 distinct documents')
        for expected in (24, 26, None):
            with self.subTest(expected=expected), self.assertRaises(m.Incomplete):
                m.pagination_end_evidence(fixture_frame(), 'BofA', 25, 2, expected)

    def test_overlapping_pages_do_not_inflate_advertised_total(self):
        collector = self.collector()
        pages = [[report('one'), report('two')], [report('two'), report('three')]]
        with patch.object(m, 'extract', side_effect=pages), \
             patch.object(m, 'visible', side_effect=[Mock(), None]), \
             patch.object(m, 'wait_until'):
            with self.assertRaisesRegex(m.Incomplete, '3 distinct rows'):
                collector.paginated(Mock(), 'BofA', fixture_frame(), lambda: Mock(),
                                    advertised_total=4)


if __name__ == '__main__':
    unittest.main()
