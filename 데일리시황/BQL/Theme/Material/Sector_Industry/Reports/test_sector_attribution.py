"""Synthetic return-attribution checks; no workbook or network is required."""
from datetime import date
import unittest
from unittest.mock import patch

import numpy as np

import build_sector_rotation_html as report


class SectorAttributionTests(unittest.TestCase):
    def test_cap_weighting_and_percentage_point_units(self):
        returns = {"1D": np.array([0.10, -0.10])}
        caps = {"1D": np.array([70.0, 30.0])}
        full = report.summarize_group([0, 1], returns, caps)
        first = report.summarize_group([0], returns, caps)
        second = report.summarize_group([1], returns, caps)
        self.assertAlmostEqual(full["returns"]["1D"], 0.04)
        self.assertAlmostEqual(first["indexStartWeights"]["1D"], 0.7)
        self.assertAlmostEqual(first["indexReturnContributions"]["1D"], 0.07)
        self.assertAlmostEqual(second["indexReturnContributions"]["1D"], -0.03)
        self.assertEqual(report.contribution_pct(0.07), "+700.0bp")
        self.assertEqual(report.contribution_pct(-0.0001), "-1.0bp")

    def test_each_period_uses_its_own_start_caps_and_reconciles(self):
        returns = {"1D": np.array([0.1, -0.2, 0.4]), "5D": np.array([0.2, 0.1, -0.1])}
        caps = {"1D": np.array([50.0, 30.0, 20.0]), "5D": np.array([10.0, 30.0, 60.0])}
        sector_a = report.summarize_group([0, 1], returns, caps)
        sector_b = report.summarize_group([2], returns, caps)
        benchmark = report.summarize_group([0, 1, 2], returns, caps)
        self.assertAlmostEqual(sector_a["indexStartWeights"]["1D"], 0.8)
        self.assertAlmostEqual(sector_a["indexStartWeights"]["5D"], 0.4)
        for period in returns:
            self.assertAlmostEqual(
                sector_a["indexReturnContributions"][period] + sector_b["indexReturnContributions"][period],
                benchmark["returns"][period],
            )
            for sector in (sector_a, sector_b):
                self.assertAlmostEqual(
                    sector["indexReturnContributions"][period],
                    sector["indexStartWeights"][period] * sector["returns"][period],
                )

    def test_missing_prices_caps_and_negative_caps_are_excluded_not_zeroed(self):
        returns = {"1D": np.array([0.1, np.nan, 0.2, 0.0, 0.3])}
        caps = {"1D": np.array([10.0, 80.0, np.nan, 5.0, -2.0])}
        full = report.summarize_group(list(range(5)), returns, caps)
        missing_group = report.summarize_group([1, 2, 4], returns, caps)
        flat_group = report.summarize_group([3], returns, caps)
        self.assertAlmostEqual(full["returns"]["1D"], 1 / 15)
        self.assertEqual(full["eligibleCount"]["1D"], 2)
        self.assertIsNone(missing_group["returns"]["1D"])
        self.assertIsNone(missing_group["indexStartWeights"]["1D"])
        self.assertIsNone(missing_group["indexReturnContributions"]["1D"])
        self.assertEqual(missing_group["eligibleCount"]["1D"], 0)
        self.assertEqual(flat_group["indexReturnContributions"]["1D"], 0.0)

    def test_unavailable_period_has_no_fabricated_weight_or_contribution(self):
        summary = report.summarize_group([0], {}, {})
        for period in report.PERIODS:
            for field in ("returns", "indexStartWeights", "indexReturnContributions", "eligibleCount"):
                self.assertIsNone(summary[field][period])
        self.assertEqual(report.contribution_pct(None), "데이터 부족")

    def build_synthetic_market(self):
        prices = np.array([[100.0, 105.0, 110.0 + i] for i in range(10)])
        prices[0, 2] = np.nan  # Known start cap but no endpoint return.
        caps = np.array([[float(10 + i)] * 3 for i in range(10)])
        caps[1, :] = np.nan  # Unknown cap must not enter the coverage denominator.
        raw = report.MarketRaw(
            key="SP500", title="S&P 500", source_sheet="SPX Raw", source_code="SPX Index",
            tickers=[f"STOCK{i}" for i in range(10)], names=[f"Stock {i}" for i in range(10)],
            sectors=["Alpha"] * 5 + ["Beta"] * 5, industries=["Industry A"] * 5 + ["Industry B"] * 5,
            dates=[date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)], prices=prices, market_caps=caps,
        )
        starts = {"1D": 1, "5D": 0, "1M": None, "3M": None, "6M": None}

        def official_benchmark(market):
            market["benchmark"]["constituentReturns"] = dict(market["benchmark"]["returns"])
            market["benchmark"]["returns"] = {"1D": 0.005, "5D": 0.02, "1M": None, "3M": None, "6M": None}
            return market

        with patch.object(report, "resolve_windows", return_value=(2, starts, [0, 1, 2])), patch.object(report, "apply_market", side_effect=official_benchmark):
            return report.build_market(raw, "1D", 5, None)

    def test_official_benchmark_preserved_without_scaling_and_coverage_explained(self):
        market = self.build_synthetic_market()
        attribution = market["sectorAttribution"]
        self.assertEqual(market["benchmark"]["returns"]["1D"], 0.005)
        self.assertEqual(attribution["contributionUnit"], "decimal_return")
        self.assertEqual(attribution["displayMultiplier"], 10000)
        for period in ("1D", "5D"):
            total = sum(sector["indexReturnContributions"][period] for sector in market["sectors"])
            self.assertAlmostEqual(total, attribution["totalContributions"][period])
            self.assertAlmostEqual(total, market["benchmark"]["constituentReturns"][period])
            self.assertAlmostEqual(attribution["differenceToOfficialBenchmark"][period], total - market["benchmark"]["returns"][period])
        coverage = attribution["coverage"]["1D"]
        self.assertEqual(coverage["eligibleCount"], 8)
        self.assertEqual(coverage["knownStartCapCount"], 9)
        self.assertEqual(coverage["memberCount"], 10)
        self.assertAlmostEqual(coverage["eligibleStartCapFraction"], sum(range(12, 20)) / (10 + sum(range(12, 20))))
        self.assertIsNone(attribution["totalContributions"]["1M"])
        self.assertIsNone(attribution["differenceToOfficialBenchmark"]["1M"])

    def test_display_keeps_sector_order_and_separates_return_from_contribution(self):
        market = self.build_synthetic_market()
        rendered = report.sector_contribution_table(market)
        self.assertLess(rendered.index(market["sectors"][0]["sector"]), rendered.index(market["sectors"][1]["sector"]))
        self.assertIn("+50.0bp", rendered)  # Official BM uses the same basis-point display.
        self.assertIn("bp", rendered)
        self.assertIn("합계 − 공식 BM", rendered)
        self.assertIn("8/10", rendered)
        panel = report.render_combined_html([market], "1D", {})
        self.assertIn('class="rotation-grid"', panel)
        self.assertIn("전체 지수 수익률 기여도", panel)
        self.assertIn("@media(max-width:1200px)", panel)


if __name__ == "__main__":
    unittest.main()

