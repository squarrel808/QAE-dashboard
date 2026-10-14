"""Focused return-date and unavailable-data checks for the separate stock map."""
from datetime import date, timedelta
import unittest

import numpy as np

from build_regional_dashboards import RawIndex, build_stock_map, stock_map_month_back


def panel(start: date, end: date, count: int = 3) -> RawIndex:
    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    close = 100.0
    values = []
    for value_date in dates:
        if value_date.weekday() < 5:
            close += 1
        values.append(close)
    prices = np.array([np.array(values) * (i + 1) for i in range(count)])
    caps = np.array([[float((i + 1) * 100)] * len(dates) for i in range(count)])
    return RawIndex("TEST", "Test", "USD", "synthetic", "TEST Raw", dates,
                    [f"T{i}" for i in range(count)], [f"Company {i}" for i in range(count)],
                    ["Sector"] * count, ["Industry"] * count, {"price": prices, "mcap": caps})


class StockMapTests(unittest.TestCase):
    def test_calendar_months_clip_end_of_month_and_leap_day(self):
        self.assertEqual(stock_map_month_back(date(2026, 3, 31), 1), date(2026, 2, 28))
        self.assertEqual(stock_map_month_back(date(2024, 3, 31), 1), date(2024, 2, 29))
        self.assertEqual(stock_map_month_back(date(2026, 1, 30), 3), date(2025, 10, 30))

    def test_sessions_calendar_periods_and_year_boundary(self):
        raw = panel(date(2025, 12, 29), date(2026, 8, 31))
        result = build_stock_map(raw)
        expected = {"1d": "2026-08-28", "1w": "2026-08-24", "1m": "2026-07-31",
                    "mtd": "2026-07-31", "3m": "2026-05-29", "6m": "2026-02-27", "ytd": "2025-12-31"}
        self.assertEqual(result["asOf"], "2026-08-31")
        for period, start in expected.items():
            self.assertEqual(result["periods"][period], {"startDate": start, "endDate": "2026-08-31"})
            baseline = raw.dates.index(date.fromisoformat(start))
            self.assertAlmostEqual(result["stocks"][0]["returns"][period], raw.metrics["price"][0, -1] / raw.metrics["price"][0, baseline] - 1)

    def test_trailing_stale_market_date_does_not_change_asof_or_caps(self):
        raw = panel(date(2026, 9, 1), date(2026, 10, 5))
        raw.metrics["price"][:, -1] = raw.metrics["price"][:, -2]
        raw.metrics["mcap"][:, -1] = [1, 1, 1]
        result = build_stock_map(raw)
        self.assertEqual(result["asOf"], "2026-10-02")
        self.assertEqual(result["periods"]["1d"]["startDate"], "2026-10-01")
        self.assertAlmostEqual(result["stocks"][0]["weight"], 1 / 6)

    def test_returns_do_not_require_base_cap_and_are_not_clipped(self):
        raw = panel(date(2026, 9, 1), date(2026, 10, 5))
        raw.metrics["mcap"][0, :-1] = np.nan
        raw.metrics["price"][0, -1] *= 20
        result = build_stock_map(raw)
        self.assertGreater(result["stocks"][0]["returns"]["1m"], 5.0)
        self.assertAlmostEqual(result["stocks"][0]["weight"], 1 / 6)

    def test_missing_stock_endpoints_are_null_with_area_preserved(self):
        raw = panel(date(2026, 9, 1), date(2026, 10, 5))
        raw.metrics["price"][0, -1] = np.nan
        raw.metrics["price"][1, raw.dates.index(date(2026, 9, 30))] = 0
        result = build_stock_map(raw)
        self.assertTrue(all(value is None for value in result["stocks"][0]["returns"].values()))
        self.assertIsNone(result["stocks"][1]["returns"]["mtd"])
        self.assertAlmostEqual(sum(stock["weight"] for stock in result["stocks"]), 1)

    def test_insufficient_history_does_not_clamp_to_first_date(self):
        raw = panel(date(2026, 10, 1), date(2026, 10, 5))
        result = build_stock_map(raw)
        self.assertIsNotNone(result["stocks"][0]["returns"]["1d"])
        for period in ("1w", "1m", "mtd", "3m", "6m", "ytd"):
            self.assertIsNone(result["periods"][period]["startDate"])
            self.assertIsNone(result["stocks"][0]["returns"][period])

    def test_empty_and_no_valid_price_panels(self):
        raw = panel(date(2026, 10, 1), date(2026, 10, 5))
        raw.metrics["price"][:] = np.nan
        self.assertEqual(build_stock_map(raw)["stocks"], [])
        self.assertIsNone(build_stock_map(raw)["asOf"])
        self.assertEqual(build_stock_map(raw)["dates"], [])
        raw.dates = []
        self.assertEqual(build_stock_map(raw)["stocks"], [])

    def test_custom_history_matches_presets_and_retains_older_dates(self):
        raw = panel(date(2025, 12, 29), date(2026, 8, 31))
        result = build_stock_map(raw)
        self.assertEqual(result["dates"], sorted(set(result["dates"])))
        self.assertEqual(result["dates"][0], "2025-12-29")
        self.assertEqual(result["dates"][-1], result["asOf"])
        self.assertTrue(all(date.fromisoformat(d).weekday() < 5 for d in result["dates"]))
        for stock in result["stocks"]:
            self.assertEqual(len(stock["prices"]), len(result["dates"]))
            for key, window in result["periods"].items():
                start = result["dates"].index(window["startDate"])
                end = result["dates"].index(window["endDate"])
                self.assertAlmostEqual(stock["prices"][end] / stock["prices"][start] - 1,
                                       stock["returns"][key])

    def test_custom_history_preserves_missing_prices_without_forward_fill(self):
        raw = panel(date(2026, 9, 1), date(2026, 10, 5), count=5)
        day = raw.dates.index(date(2026, 9, 15))
        raw.metrics["price"][0, day] = np.nan
        raw.metrics["price"][1, day] = 0
        raw.metrics["price"][2, day] = np.inf
        result = build_stock_map(raw)
        column = result["dates"].index("2026-09-15")
        for stock in result["stocks"][:3]:
            self.assertIsNone(stock["prices"][column])
            self.assertIsNotNone(stock["prices"][column - 1])
            self.assertIsNotNone(stock["prices"][column + 1])

    def test_custom_history_stops_before_trailing_stale_session(self):
        raw = panel(date(2026, 9, 1), date(2026, 10, 5))
        raw.metrics["price"][:, -1] = raw.metrics["price"][:, -2]
        result = build_stock_map(raw)
        self.assertEqual(result["dates"][-1], "2026-10-02")
        self.assertNotIn("2026-10-05", result["dates"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
