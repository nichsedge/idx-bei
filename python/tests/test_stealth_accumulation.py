"""
Unit tests for Intraday Bandarmology Stealth Accumulation vs Retail Trap anomaly detection.
"""

import unittest

import pandas as pd

from idx.signals import detect_stealth_accumulation


class TestStealthAccumulation(unittest.TestCase):
    def setUp(self):
        # Mock broker summary
        self.mock_broker_stealth = pd.DataFrame(
            [
                {"Date": "2026-08-01", "IDFirm": "AK", "Value": 40_000_000_000, "Volume": 1000},
                {"Date": "2026-08-01", "IDFirm": "BK", "Value": 30_000_000_000, "Volume": 1000},
                {"Date": "2026-08-01", "IDFirm": "ZP", "Value": 20_000_000_000, "Volume": 1000},
                # Retail firm with small volume
                {"Date": "2026-08-01", "IDFirm": "YP", "Value": 5_000_000_000, "Volume": 500},
                {"Date": "2026-08-01", "IDFirm": "PD", "Value": 5_000_000_000, "Volume": 500},
            ]
        )

        self.mock_broker_retail_trap = pd.DataFrame(
            [
                # Smart money small
                {"Date": "2026-08-01", "IDFirm": "AK", "Value": 2_000_000_000, "Volume": 100},
                # Retail heavy
                {"Date": "2026-08-01", "IDFirm": "YP", "Value": 40_000_000_000, "Volume": 5000},
                {"Date": "2026-08-01", "IDFirm": "PD", "Value": 30_000_000_000, "Volume": 4000},
                {"Date": "2026-08-01", "IDFirm": "XC", "Value": 10_000_000_000, "Volume": 1000},
            ]
        )

        # Mock stock summary
        self.mock_stock_df = pd.DataFrame(
            [
                {
                    "Date": "2026-08-01",
                    "StockCode": "BBCA",
                    "Close": 10000.0,
                    "Previous": 9950.0,  # +0.5% move (<1%)
                    "Value": 100_000_000_000,
                    "ForeignBuy": 60_000_000_000,
                    "ForeignSell": 20_000_000_000,
                },
                {
                    "Date": "2026-08-01",
                    "StockCode": "FREN",
                    "Close": 110.0,
                    "Previous": 100.0,  # +10% move
                    "Value": 20_000_000_000,
                    "ForeignBuy": 1_000_000_000,
                    "ForeignSell": 10_000_000_000,
                },
            ]
        )

    def test_stealth_accumulation_detection(self):
        res = detect_stealth_accumulation(self.mock_broker_stealth, self.mock_stock_df)
        self.assertEqual(res["signal"], "STEALTH_ACCUMULATION")
        # Smart: 90B / Retail: 10B = 9.0
        self.assertGreaterEqual(res["smart_money_delta"], 3.0)
        self.assertIn("BBCA", res["anomalies_df"]["StockCode"].values)

    def test_retail_trap_detection(self):
        res = detect_stealth_accumulation(self.mock_broker_retail_trap, self.mock_stock_df)
        self.assertEqual(res["signal"], "RETAIL_TRAP")
        # Smart: 2B / Retail: 80B = 0.025 < 0.5
        self.assertLess(res["smart_money_delta"], 0.5)

    def test_empty_broker_graceful_handling(self):
        res = detect_stealth_accumulation(pd.DataFrame(), pd.DataFrame())
        self.assertEqual(res["signal"], "NO_DATA")
        self.assertEqual(res["smart_money_delta"], 0.0)
        self.assertTrue(res["anomalies_df"].empty)
