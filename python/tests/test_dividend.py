"""
Unit tests for the IDX Dividend Decision Engine & Trap Analyzer.
"""

import unittest
from unittest.mock import patch

import pandas as pd
from starlette.testclient import TestClient

from idx.api import app
from idx.dividend import (
    _calculate_rsi,
    analyze_stock_dividend,
    format_dividend_report,
    get_latest_dividend,
    screen_upcoming_dividends,
)


class TestDividendEngine(unittest.TestCase):
    def setUp(self):
        # Mock company details dictionary
        self.mock_details = {
            "GOOD": {
                "Search": {"NamaEmiten": "PT Good Company Tbk"},
                "Dividen": [
                    {
                        "Nama": "PT Good Company Tbk",
                        "Jenis": "dt",
                        "TahunBuku": "2025",
                        "CashDividenPerSaham": 150.0,
                        "CashDividenPerSahamMU": "IDR",
                        "CashDividenTotal": 150_000_000_000.0,
                        "CashDividenTotalMU": "IDR",
                        "TanggalCum": "2026-06-15T00:00:00",
                        "TanggalExRegulerDanNegosiasi": "2026-06-16T00:00:00",
                        "TanggalDPS": "2026-06-17T16:00:00",
                        "TanggalPembayaran": "2026-07-02T00:00:00",
                    }
                ],
            },
            "TRAP": {
                "Search": {"NamaEmiten": "PT Cyclical Trap Tbk"},
                "Dividen": [
                    {
                        "Nama": "PT Cyclical Trap Tbk",
                        "Jenis": "dt",
                        "TahunBuku": "2025",
                        "CashDividenPerSaham": 500.0,
                        "CashDividenPerSahamMU": "IDR",
                        "CashDividenTotal": 500_000_000_000.0,
                        "CashDividenTotalMU": "IDR",
                        "TanggalCum": "2026-05-10T00:00:00",
                        "TanggalExRegulerDanNegosiasi": "2026-05-11T00:00:00",
                        "TanggalDPS": "2026-05-12T16:00:00",
                        "TanggalPembayaran": "2026-05-28T00:00:00",
                    }
                ],
            },
            "NODIV": {
                "Search": {"NamaEmiten": "PT Growth No Div Tbk"},
                "Dividen": [],
            },
        }

        # Mock stock summary dataframe
        dates = pd.date_range("2026-05-01", periods=25, freq="B")
        good_rows = [
            {
                "Date": d,
                "StockCode": "GOOD",
                "Close": 3000.0 + i * 10,
                "ListedShares": 1_000_000_000.0,
                "NetForeignFlow": 5_000_000_000.0,
                "Value": 20_000_000_000.0,
            }
            for i, d in enumerate(dates)
        ]
        trap_rows = [
            {
                "Date": d,
                "StockCode": "TRAP",
                "Close": 2500.0 + i * 50,  # steep runup
                "ListedShares": 1_000_000_000.0,
                "NetForeignFlow": -15_000_000_000.0,  # smart money dumping
                "Value": 30_000_000_000.0,
            }
            for i, d in enumerate(dates)
        ]
        self.mock_stock_df = pd.DataFrame(good_rows + trap_rows)

        # Mock financial ratios dataframe
        self.mock_ratios_df = pd.DataFrame(
            [
                {
                    "code": "GOOD",
                    "eps": 300.0,
                    "roe": 18.5,
                    "deRatio": 0.5,
                    "per": 10.0,
                    "priceBV": 1.8,
                    "opini": "WTP",
                    "profitAttrOwner": 300_000_000_000.0,
                },
                {
                    "code": "TRAP",
                    "eps": 400.0,  # DPR = 500 / 400 = 125% (over-distributing!)
                    "roe": 8.0,
                    "deRatio": 2.8,
                    "per": 6.5,
                    "priceBV": 1.2,
                    "opini": "WDP",  # non-clean audit!
                    "profitAttrOwner": 400_000_000_000.0,
                },
            ]
        )

    def test_calculate_rsi(self):
        prices = pd.Series([100 + i for i in range(25)])
        rsi = _calculate_rsi(prices, 14)
        self.assertGreater(rsi, 70.0)

        prices_down = pd.Series([100 - i for i in range(25)])
        rsi_down = _calculate_rsi(prices_down, 14)
        self.assertLess(rsi_down, 30.0)

    def test_get_latest_dividend(self):
        div = get_latest_dividend("GOOD", details_dict=self.mock_details)
        self.assertIsNotNone(div)
        self.assertEqual(div["CashDividenPerSaham"], 150.0)

        no_div = get_latest_dividend("NODIV", details_dict=self.mock_details)
        self.assertIsNone(no_div)

    def test_analyze_stock_dividend_good(self):
        analysis = analyze_stock_dividend(
            "GOOD",
            details_dict=self.mock_details,
            stock_df=self.mock_stock_df,
            ratios_df=self.mock_ratios_df,
        )
        self.assertTrue(analysis["has_dividend"])
        self.assertEqual(analysis["ticker"], "GOOD")
        self.assertEqual(analysis["dps_idr"], 150.0)
        self.assertAlmostEqual(analysis["fundamentals"]["dpr_pct"], 50.0, places=1)
        # Trap score should be low
        self.assertLessEqual(analysis["dividend_trap_score"], 35.0)
        self.assertIn(analysis["verdict"], ["BUY / ACCUMULATE", "HOLD"])

    def test_analyze_stock_dividend_trap(self):
        analysis = analyze_stock_dividend(
            "TRAP",
            details_dict=self.mock_details,
            stock_df=self.mock_stock_df,
            ratios_df=self.mock_ratios_df,
        )
        self.assertTrue(analysis["has_dividend"])
        self.assertEqual(analysis["ticker"], "TRAP")
        self.assertEqual(analysis["dps_idr"], 500.0)
        # Yield should be high (500 / ~3700 = ~13.5%)
        self.assertGreater(analysis["dividend_yield_pct"], 10.0)
        # Payout ratio should exceed 100%
        self.assertGreater(analysis["fundamentals"]["dpr_pct"], 100.0)
        # Trap score should be high / critical
        self.assertGreaterEqual(analysis["dividend_trap_score"], 60.0)
        self.assertEqual(analysis["verdict"], "SELL BEFORE CUM DATE")

    def test_format_dividend_report(self):
        analysis = analyze_stock_dividend(
            "GOOD",
            details_dict=self.mock_details,
            stock_df=self.mock_stock_df,
            ratios_df=self.mock_ratios_df,
        )
        report = format_dividend_report(analysis)
        self.assertIn("IDX DIVIDEND DECISION RADAR: GOOD", report)
        self.assertIn("Cum Date", report)
        self.assertIn("Ex Date", report)
        self.assertIn("DIVIDEND TRAP RISK SCORE", report)

    def test_api_dividend_endpoints(self):
        client = TestClient(app)
        with (
            patch("idx.dividend.load_json", return_value=self.mock_details),
            patch("pandas.read_parquet", side_effect=[self.mock_stock_df, self.mock_ratios_df]),
        ):
            resp = client.get("/api/dividend/GOOD")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["ticker"], "GOOD")
            self.assertEqual(data["dps_idr"], 150.0)

    def test_screen_upcoming_dividends(self):
        with (
            patch("idx.dividend.load_json", return_value=self.mock_details),
            patch("pandas.read_parquet", side_effect=[self.mock_stock_df, self.mock_ratios_df] * 5),
        ):
            df = screen_upcoming_dividends(min_yield=2.0, year_filter="2026")
            self.assertGreaterEqual(len(df), 1)
            self.assertIn("Ticker", df.columns)
            self.assertIn("Yield%", df.columns)


if __name__ == "__main__":
    unittest.main()
