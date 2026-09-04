"""
Unit tests for the dividend arbitrage backtest strategy simulator.
"""

import unittest

import pandas as pd

from idx.backtest import run_backtest, simulate_dividend_arbitrage


class TestDividendArbitrageBacktest(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range("2026-06-01", periods=30, freq="B")
        self.mock_stock_df = pd.DataFrame(
            [
                {
                    "Date": d,
                    "StockCode": "TLKM",
                    "Close": 3000.0 + (i * 20 if i < 10 else -100 + (i - 10) * 10),
                    "ListedShares": 99_000_000_000,
                    "Value": 50_000_000_000,
                    "ForeignBuy": 25_000_000_000,
                    "ForeignSell": 20_000_000_000,
                }
                for i, d in enumerate(dates)
            ]
        )

        # Cum date on 10th trading day, Ex date on 11th trading day
        cum_date = dates[9].strftime("%Y-%m-%d")
        ex_date = dates[10].strftime("%Y-%m-%d")

        self.mock_details = {
            "TLKM": {
                "Dividen": [
                    {
                        "TanggalCum": f"{cum_date}T00:00:00",
                        "TanggalExRegulerDanNegosiasi": f"{ex_date}T00:00:00",
                        "CashDividenPerSaham": 180.0,
                        "CashDividenPerSahamMU": "IDR",
                        "CashDividenTotal": 17_000_000_000_000.0,
                        "CashDividenTotalMU": "IDR",
                    }
                ]
            }
        }

    def test_dividend_arbitrage_simulation(self):
        metrics, trades = simulate_dividend_arbitrage(
            stock_df=self.mock_stock_df,
            details_dict=self.mock_details,
            pre_cum_days=5,
            post_ex_entry_delay=2,
            post_ex_holding_days=5,
        )

        self.assertEqual(metrics["strategy"], "dividend_arbitrage")
        self.assertIn("strategy_a_naive_hold", metrics)
        self.assertIn("strategy_b_precum_exit", metrics)
        self.assertIn("strategy_c_postex_rebuy", metrics)
        self.assertFalse(trades.empty)

        # Check that trades DataFrame contains all 3 strategies
        strategies_present = set(trades["Strategy"].unique())
        self.assertTrue(any("Naive Hold" in s for s in strategies_present))
        self.assertTrue(any("Pre-Cum Exit" in s for s in strategies_present))

    def test_run_backtest_with_dividend_arbitrage(self):
        metrics, trades = run_backtest(
            strategy="dividend_arbitrage",
            stock_df=self.mock_stock_df,
        )
        self.assertEqual(metrics.get("strategy"), "dividend_arbitrage")
