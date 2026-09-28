from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image


MODULE_PATH = Path(__file__).with_name("build_sector_snapshot.py")
SPEC = importlib.util.spec_from_file_location("sector_snapshot", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def panel(dates: list[date], levels: list[float]) -> object:
    count = 20
    offsets = np.arange(count, dtype=float).reshape(-1, 1) / 10
    prices = np.tile(np.asarray(levels, dtype=float), (count, 1)) + offsets
    return MODULE.MarketPanel(
        key="TOPIX",
        title="TOPIX",
        source_sheet="TEST",
        source_code="TEST",
        currency="JPY",
        source_workbook="synthetic.xlsx",
        tickers=[f"T{i:03d}" for i in range(count)],
        names=[f"Stock {i:03d}" for i in range(count)],
        sectors=["Industrials"] * 10 + ["Information Technology"] * 10,
        industries=["Capital Goods"] * 10 + ["Semiconductors & Semiconductor Equipment"] * 10,
        dates=dates,
        prices=prices,
        market_caps=prices * 1_000_000,
    )


class SectorSnapshotTests(unittest.TestCase):
    def test_percent_format_suppresses_negative_zero(self) -> None:
        self.assertEqual(MODULE.percent(-0.0001), "0.0%")
        self.assertEqual(MODULE.percent(-0.0001, points=True), "0.0%p")

    def test_session_detection_keeps_baseline_and_skips_carries(self) -> None:
        source = panel(
            [date(2026, 9, day) for day in range(1, 9)],
            [100, 101, 102, 103, 103, 103, 104, 104],
        )
        self.assertEqual(MODULE.actual_sessions(source.prices), [0, 1, 2, 3, 6])

    def test_1d_and_5d_use_two_and_six_genuine_closes(self) -> None:
        dates = [
            date(2026, 8, 28),
            date(2026, 8, 29),
            date(2026, 8, 30),
            date(2026, 8, 31),
            date(2026, 9, 1),
            date(2026, 9, 2),
            date(2026, 9, 3),
            date(2026, 9, 4),
        ]
        source = panel(dates, [100, 100, 100, 101, 102, 103, 104, 105])
        daily = MODULE.build_market(source, "1D", 8, 0.80)
        weekly = MODULE.build_market(source, "5D", 8, 0.80)
        self.assertEqual(daily["sessionDates"], ["2026-09-03", "2026-09-04"])
        self.assertEqual(weekly["sessionDates"], [
            "2026-08-28", "2026-08-31", "2026-09-01",
            "2026-09-02", "2026-09-03", "2026-09-04",
        ])

    def test_top_bottom_cap_and_table_render(self) -> None:
        source = panel(
            [date(2026, 9, 3), date(2026, 9, 4)],
            [100, 102],
        )
        market = MODULE.build_market(source, "1D", 8, 0.80)
        MODULE.validate_market(market, 8)
        for sector in market["sectors"]:
            self.assertLessEqual(len(sector["topGainers"]), 8)
            self.assertLessEqual(len(sector["bottomLosers"]), 8)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "table.png"
            MODULE.render_table(market, target)
            self.assertTrue(target.exists())
            with Image.open(target) as image:
                self.assertGreater(image.width, 1000)
                self.assertGreater(image.height, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
