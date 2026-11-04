from datetime import date, timedelta
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

import build_sp500_ai_value_chain as ai
import build_ai_value_chain_html as report
import index_levels


class MarketCapReturnTests(unittest.TestCase):
    def test_start_cap_weights_and_never_end_cap_weights(self):
        prices = np.array([[100, 110], [100, 90]], dtype=float)
        caps = np.array([[900, 1], [100, 9999]], dtype=float)
        self.assertEqual(ai.cap_weighted_return(prices, caps, [0, 1], 0, 1), 0.08)

    def test_missing_price_and_nonpositive_or_missing_cap_are_excluded(self):
        prices = np.array([[100, 110], [100, 200], [100, 200], [100, 200], [100, np.nan]], dtype=float)
        caps = np.array([[5, 1], [0, 1], [-1, 1], [np.nan, 1], [1000, 1]], dtype=float)
        self.assertEqual(ai.cap_weighted_return(prices, caps, list(range(5)), 0, 1), 0.1)
        self.assertIsNone(ai.cap_weighted_return(prices, caps, [1, 2, 3, 4], 0, 1))
        self.assertIsNone(ai.cap_weighted_return(prices, caps, [], 0, 1))
        self.assertIsNone(ai.cap_weighted_return(prices, caps, [0], None, 1))

    def test_daily_series_uses_each_preceding_cap(self):
        prices = np.array([[100, 110, 121], [100, 90, 81]], dtype=float)
        caps = np.array([[900, 100, 1], [100, 900, 1]], dtype=float)
        dates = [date(2026, 10, day) for day in (5, 6, 7)]
        series = ai.chain_series(prices, caps, [0, 1], dates)
        self.assertEqual([point[1] for point in series], [100.0, 108.0, 99.36])
        fixed = ai.period_series(prices, caps, [0, 1], dates, 0)
        self.assertEqual(fixed[-1][1], 117.0)

    def test_series_does_not_convert_missing_caps_to_zero_return(self):
        prices = np.array([[100, 110, 121]], dtype=float)
        caps = np.array([[1, np.nan, 1]], dtype=float)
        dates = [date(2026, 10, day) for day in (5, 6, 7)]
        self.assertEqual(ai.chain_series(prices, caps, [0], dates)[-1][1], None)
        self.assertEqual(ai.period_series(prices, caps, [0], dates, None), [])

    def test_short_windows_are_unavailable_and_baseline_is_retained(self):
        dates = [date(2026, 10, 5) + timedelta(days=i) for i in range(5)]
        periods = ai.period_indices(dates)
        self.assertEqual(periods['1D'], 3)
        for period in ('5D', '1W', '1M', '3M', '6M', 'YTD'):
            self.assertIsNone(periods[period])
        dates.append(date(2026, 10, 12))
        self.assertEqual(ai.period_indices(dates)['5D'], 0)
        prices = np.array([[100, 101, 101, 102], [100, 99, 99, 98]], dtype=float)
        self.assertEqual(ai.actual_session_indices(prices), [0, 1, 3])

    def test_core_expanded_chart_and_official_benchmark_are_consistent(self):
        dates = [date(2026, 10, d) for d in (5, 6, 7, 8, 9, 12, 13)]
        prices = np.array([[100 * factor ** i for i in range(7)] for factor in (1.1, 0.9, 1.2)])
        caps = np.array([[900.0] * 7, [100.0] * 7, [1000.0] * 7])
        caps[:, -1] = [1, 10000, 1]
        raw = SimpleNamespace(
            metrics={'price': prices, 'mcap': caps}, dates=dates,
            tickers=['MSFT US Equity', 'NVDA US Equity', 'AMZN US Equity'],
            companies=['Microsoft', 'NVIDIA', 'Amazon'], sectors=['IT'] * 3,
            industries=['Software'] * 3, source='synthetic fixture',
        )
        stage = {'key': 'fixture', 'name': 'Fixture', 'short': 'Fixture', 'color': '#000000',
                 'description': 'Fixture', 'core': ['MSFT', 'NVDA'], 'adjacent': ['AMZN']}
        official_levels = [[day.isoformat(), 1000 + i * 10] for i, day in enumerate(dates)]
        with patch.object(ai, 'STAGES', [stage]), patch.object(index_levels, 'series', return_value=(official_levels, {'code': 'SPX Index'})):
            data = ai.build_data(raw)
        core = data['modes']['Core']['fixture']
        expanded = data['modes']['Expanded']['fixture']
        # 5-session MSFT +61.051%, NVDA -40.951%, AMZN +148.832%.
        self.assertEqual(core['performance']['5D']['return'], 0.508508)
        self.assertEqual(expanded['performance']['5D']['return'], 0.998414)
        self.assertAlmostEqual(core['periodSeries']['5D'][-1][1] / 100 - 1, 0.508508)
        self.assertEqual(core['performance']['5D']['breadth'], 0.5)
        self.assertEqual(core['performance']['5D']['weightedMembers'], 2)
        self.assertEqual(core['performance']['5D']['startMarketCap'], 1000.0)
        self.assertEqual(data['benchmark']['returns']['5D'], round(1060 / 1010 - 1, 6))
        self.assertEqual(data['benchmark']['series'], official_levels)
        self.assertIsNone(data['periodStarts']['1M'])
        self.assertIsNone(core['performance']['1M']['return'])
        self.assertEqual(core['periodSeries']['1M'], [])
        self.assertEqual(data['meta']['weighting'], 'market_cap')
        self.assertRegex(report.render(data, '5D'), r'(시총|시가총액)\s*가중')
        json.dumps(data, allow_nan=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
