"""
Tests for Vectorized Backtest Strategy Simulator and performance metrics.
"""

import unittest

import numpy as np
import pandas as pd

from idx.backtest import calculate_metrics, run_backtest


class TestBacktest(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        rows = []
        for ticker in ["BBCA", "BBRI", "TLKM", "ASII"]:
            base = 5000.0
            for i, d in enumerate(dates):
                base += np.sin(i / 3.0) * 40 + 5
                rows.append(
                    {
                        "Date": d.strftime("%Y-%m-%d"),
                        "StockCode": ticker,
                        "OpenPrice": base - 10,
                        "High": base + 30,
                        "Low": base - 20,
                        "Close": base,
                        "Volume": 2_000_000,
                        "Value": 2_000_000 * base,
                        "Previous": base - 5,
                        "ForeignBuy": 1_200_000,
                        "ForeignSell": 400_000,
                        "TradebleShares": 100_000_000,
                    }
                )
        self.stock_df = pd.DataFrame(rows)
        self.ratios_df = pd.DataFrame(
            [
                {
                    "code": t,
                    "stockName": t,
                    "fsDate": "2026-06-30",
                    "roe": 20.0,
                    "per": 10.0,
                    "deRatio": 0.5,
                    "opini": "WTP",
                    "sharia": "S",
                }
                for t in ["BBCA", "BBRI", "TLKM", "ASII"]
            ]
        )

    def test_calculate_metrics(self):
        returns = pd.Series([0.05, -0.02, 0.04, 0.08, -0.01, 0.03])
        metrics = calculate_metrics(returns)
        self.assertIn("total_return_pct", metrics)
        self.assertIn("sharpe_ratio", metrics)
        self.assertIn("win_rate_pct", metrics)
        self.assertEqual(metrics["total_trades"], 6)
        self.assertGreater(metrics["win_rate_pct"], 50.0)

    def test_run_backtest_foreign_flow(self):
        metrics, trades = run_backtest(
            strategy="foreign_flow",
            holding_days=10,
            top_n=2,
            stock_df=self.stock_df,
            ratios_df=self.ratios_df,
        )
        self.assertIn("total_return_pct", metrics)
        self.assertEqual(metrics["strategy"], "foreign_flow")
        self.assertGreaterEqual(len(trades), 1)

    def test_run_backtest_with_stop_loss_and_take_profit(self):
        metrics, trades = run_backtest(
            strategy="foreign_flow",
            holding_days=10,
            top_n=2,
            stop_loss_pct=5.0,
            take_profit_pct=10.0,
            stock_df=self.stock_df,
            ratios_df=self.ratios_df,
        )
        self.assertIn("total_return_pct", metrics)
        self.assertGreaterEqual(len(trades), 1)


if __name__ == "__main__":
    unittest.main()
