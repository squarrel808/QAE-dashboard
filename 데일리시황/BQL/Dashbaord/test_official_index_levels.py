from datetime import date, timedelta
from types import SimpleNamespace
import unittest

import build_regional_dashboards as builder
import official_index_levels as official


class OfficialIndexTests(unittest.TestCase):
    def fixture(self):
        dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(200)]
        metrics = {key: {d: 10.0 + i / 100 for i, d in enumerate(dates)}
                   for key in builder.METRIC_PREFIXES.values()}
        metrics['eps_fy2'] = {d: 100 + i for i, d in enumerate(dates)}
        rows = [{'level': 'Index', 'eps4': -0.9}, {'level': 'Sector', 'eps4': -0.9}]
        boxes = [{'level': 'Index'}]
        histories = [{'level': 'Index', 'values': []}]
        raw = SimpleNamespace(code='AS51', dates=dates)
        config = {'attribution_start': dates[0], 'earnings_start': dates[0]}
        return raw, rows, boxes, histories, {'AS51': metrics}, config

    def test_index_uses_direct_levels_and_leaves_sector_aggregation(self):
        args = self.fixture()
        official.apply(builder, *args)
        raw, rows, boxes, histories, data, _ = args
        self.assertAlmostEqual(histories[0]['values'][-1][5], 1.99)
        self.assertAlmostEqual(rows[0]['eps4'], 11.99 / 11.71 - 1)
        self.assertEqual(rows[1]['eps4'], -0.9)
        self.assertAlmostEqual(boxes[0]['current'], 11.99)
        for p in histories[0]['values']:
            self.assertAlmostEqual(p[2] + p[3], p[8])

    def test_daily_fy_levels_are_raw_and_missing_stays_missing(self):
        args = self.fixture()
        last = args[0].dates[-1]
        args[4]['AS51']['eps_fy1'][last] = float('nan')
        official.apply(builder, *args)
        history = args[3][0]
        self.assertEqual(history['source'], 'Index Level')
        self.assertEqual(len(history['indexFYLevels']), 200)
        self.assertEqual(history['indexFYLevels'][-1][2], 299)
        self.assertTrue(builder.np.isnan(history['indexFYLevels'][-1][1]))

    def test_missing_index_fails_instead_of_using_constituents(self):
        args = list(self.fixture())
        args[4] = {}
        with self.assertRaisesRegex(ValueError, 'not an index fallback'):
            official.apply(builder, *args)

    def test_stale_source_fails(self):
        args = self.fixture()
        del args[4]['AS51']['price'][args[0].dates[-1]]
        with self.assertRaisesRegex(ValueError, 'stale'):
            official.apply(builder, *args)

    def test_short_constituent_history_does_not_reset_index_baseline(self):
        args = self.fixture()
        args[0].dates = args[0].dates[-10:]
        official.apply(builder, *args)
        self.assertAlmostEqual(args[3][0]['values'][-1][5], 1.99)


if __name__ == '__main__':
    unittest.main()
