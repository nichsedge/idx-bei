"""
Tests for Bandarmology broker concentration, technical indicators, and composite alpha ranking.
"""

import unittest

import numpy as np
import pandas as pd

from idx.signals import (
    broker_concentration_screen,
    composite_alpha_ranking,
    compute_technical_indicators,
)


class TestBandarmologySignals(unittest.TestCase):
    def setUp(self):
        self.broker_data = pd.DataFrame(
            [
                {
                    "Date": "2026-08-01",
                    "IDFirm": "AK",
                    "FirmName": "UBS Sekuritas",
                    "Value": 100_000_000_000,
                    "Volume": 10_000_000,
                },
                {
                    "Date": "2026-08-01",
                    "IDFirm": "BK",
                    "FirmName": "JP Morgan",
                    "Value": 80_000_000_000,
                    "Volume": 8_000_000,
                },
                {
                    "Date": "2026-08-01",
                    "IDFirm": "ZP",
                    "FirmName": "Maybank",
                    "Value": 50_000_000_000,
                    "Volume": 5_000_000,
                },
                {
                    "Date": "2026-08-01",
                    "IDFirm": "YP",
                    "FirmName": "Mirae Asset",
                    "Value": 30_000_000_000,
                    "Volume": 3_000_000,
                },
                {
                    "Date": "2026-08-01",
                    "IDFirm": "PD",
                    "FirmName": "Indo Premier",
                    "Value": 20_000_000_000,
                    "Volume": 2_000_000,
                },
                {
                    "Date": "2026-08-01",
                    "IDFirm": "CC",
                    "FirmName": "Mandiri Sekuritas",
                    "Value": 20_000_000_000,
                    "Volume": 2_000_000,
                },
            ]
        )

        dates = pd.date_range("2026-06-01", periods=60, freq="B")
        rows = []
        base = 5000.0
        for i, d in enumerate(dates):
            base += np.sin(i / 5.0) * 50 + 10
            rows.append(
                {
                    "Date": d.strftime("%Y-%m-%d"),
                    "StockCode": "TEST",
                    "OpenPrice": base - 10,
                    "High": base + 30,
                    "Low": base - 20,
                    "Close": base,
                    "Volume": 1_000_000 + i * 50_000,
                    "Value": (1_000_000 + i * 50_000) * base,
                    "Previous": base - 10,
                    "ForeignBuy": 600_000,
                    "ForeignSell": 200_000,
                    "TradebleShares": 100_000_000,
                }
            )
        self.stock_data = pd.DataFrame(rows)

        self.ratios_data = pd.DataFrame(
            [
                {
                    "code": "TEST",
                    "stockName": "Test Emisi",
                    "fsDate": "2026-06-30",
                    "roe": 22.5,
                    "per": 8.5,
                    "deRatio": 0.45,
                    "priceBV": 1.2,
                    "opini": "WTP",
                    "sharia": "S",
                }
            ]
        )

    def test_broker_concentration_screen(self):
        summary, top_df = broker_concentration_screen(self.broker_data, top_k=3)
        self.assertIn("cr1_pct", summary)
        self.assertIn("cr3_pct", summary)
        self.assertIn("institutional_share_pct", summary)
        self.assertGreater(summary["cr3_pct"], 50.0)
        self.assertEqual(len(top_df), 3)
        self.assertEqual(top_df.iloc[0]["IDFirm"], "AK")

    def test_compute_technical_indicators(self):
        tech = compute_technical_indicators(self.stock_data, ticker="TEST")
        self.assertEqual(len(tech), len(self.stock_data))
        self.assertIn("RSI14", tech.columns)
        self.assertIn("EMA20", tech.columns)
        self.assertIn("EMA50", tech.columns)
        self.assertIn("TrendRegime", tech.columns)
        last_row = tech.iloc[-1]
        self.assertTrue(pd.notna(last_row["RSI14"]))
        self.assertTrue(pd.notna(last_row["EMA20"]))

    def test_composite_alpha_ranking(self):
        ranked = composite_alpha_ranking(self.stock_data, self.ratios_data, top_n=10)
        self.assertGreaterEqual(len(ranked), 1)
        self.assertIn("AlphaScore", ranked.columns)
        self.assertGreater(ranked.iloc[0]["AlphaScore"], 50.0)


if __name__ == "__main__":
    unittest.main()
