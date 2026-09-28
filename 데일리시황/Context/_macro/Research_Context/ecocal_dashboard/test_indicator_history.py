import unittest
from indicator_history import merge, updated


class HistoryTests(unittest.TestCase):
    def row(self, ident, actual, date='2026-09-09'):
        return {'id': ident, 'actual': actual, 'date': date, 'time': '09:00',
                'country_code': 'US', 'event': ident, 'period': 'Aug',
                'houses': [{'search_candidates': [{'title': 'unreviewed'}], 'bases': []}]}

    def test_latest_source_wins_without_erasing_older_dates(self):
        history = {'old': self.row('old', 1), 'same': self.row('same', 2)}
        latest = [self.row('same', 3), self.row('future', None, '2026-09-24')]
        result = merge(latest, history)
        self.assertEqual({e['id']: e['actual'] for e in result},
                         {'old': 1, 'same': 3, 'future': None})
        self.assertEqual(next(e for e in result if e['id']=='old')['record_origin'], 'history')
        self.assertEqual(next(e for e in result if e['id']=='old')['houses'][0]['search_candidates'], [])

    def test_stale_search_candidate_is_not_claimed_as_coverage(self):
        prior=self.row('old',1)
        prior['houses'][0]['status']='candidate'
        archived=merge([],{'old':prior})[0]
        self.assertEqual(archived['houses'][0]['status'],'uncovered')

    def test_unreported_future_rows_are_not_archived(self):
        bundle = updated({}, [self.row('future', None), self.row('old', 0)])
        self.assertEqual([e['id'] for e in bundle['events']], ['old'])


if __name__=='__main__':
    unittest.main()
