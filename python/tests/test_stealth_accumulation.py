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

    def test_multiday_wyckoff_phases_and_scores(self):
        # Create multi-day stock timeseries
        days_data = []
        for i, dt in enumerate(["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05"]):
            days_data.append({
                "Date": dt,
                "StockCode": "BMRI",
                "Close": 7000.0 + (i * 10),  # very tight consolidation ~ +0.5% total
                "Previous": 7000.0 + ((i - 1) * 10) if i > 0 else 7000.0,
                "Value": 50_000_000_000,
                "ForeignBuy": 30_000_000_000,  # massive net foreign accumulation
                "ForeignSell": 5_000_000_000,
                "Volume": 7_000_000,
            })
            days_data.append({
                "Date": dt,
                "StockCode": "GOTO",
                "Close": 50.0 + (i * 2),  # +16% pump
                "Previous": 50.0 + ((i - 1) * 2) if i > 0 else 50.0,
                "Value": 20_000_000_000,
                "ForeignBuy": 1_000_000_000,
                "ForeignSell": 10_000_000_000,  # retail buying into institutional distribution
                "Volume": 40_000_000,
            })
        stock_multi = pd.DataFrame(days_data)
        neutral_broker = pd.DataFrame([
            {"Date": "2026-08-05", "IDFirm": "AK", "Value": 10_000_000_000, "Volume": 1000},
            {"Date": "2026-08-05", "IDFirm": "YP", "Value": 10_000_000_000, "Volume": 1000},
        ])

        res = detect_stealth_accumulation(neutral_broker, stock_multi, on_date="2026-08-05", lookback_days=5)
        df_res = res["anomalies_df"]
        self.assertFalse(df_res.empty)

        # BMRI should be flagged with high accumulation score and STEALTH_ACCUMULATION / SPRING
        bmri_row = df_res[df_res["StockCode"] == "BMRI"].iloc[0]
        self.assertEqual(bmri_row["Signal"], "STEALTH_ACCUMULATION")
        self.assertEqual(bmri_row["WyckoffPhase"], "ACCUMULATION_SPRING")
        self.assertGreaterEqual(bmri_row["AccumulationScore"], 75)

        # GOTO should be flagged as RETAIL_TRAP
        goto_row = df_res[df_res["StockCode"] == "GOTO"].iloc[0]
        self.assertEqual(goto_row["Signal"], "RETAIL_TRAP")
        self.assertEqual(goto_row["WyckoffPhase"], "RETAIL_TRAP")
