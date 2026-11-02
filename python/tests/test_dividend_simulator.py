"""
Unit tests for Indonesian Dividend Reinvestment & Tax Drag Sovereign Runway Simulator.
"""

import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from idx.api import app
from idx.dividend_simulator import (
    calculate_statutory_deadlines,
    get_cash_cow_profiles,
    simulate_sovereign_runway,
)


class TestDividendSimulator(unittest.TestCase):
    def setUp(self):
        usd_patcher = patch("idx.dividend_simulator.get_usd_idr_rate", return_value=16000.0)
        usd_patcher.start()
        self.addCleanup(usd_patcher.stop)
        self.client = TestClient(app)

    def test_calculate_statutory_deadlines_march_31(self):
        deadlines = calculate_statutory_deadlines("2026-05-15")
        self.assertEqual(deadlines["tax_year_received"], 2026)
        # Reinvestment deadline must be March 31 of Year T+1
        self.assertEqual(deadlines["reinvestment_deadline"], "2027-03-31")
        # 3 full tax years holding release date must be December 31 of Year T+3
        self.assertEqual(deadlines["holding_release_date"], "2029-12-31")
        self.assertEqual(deadlines["statutory_holding_years"], 3)
        self.assertEqual(len(deadlines["annual_reporting_deadlines"]), 3)
        self.assertEqual(
            deadlines["annual_reporting_deadlines"][0]["submission_deadline"], "2027-03-31"
        )
        self.assertEqual(
            deadlines["annual_reporting_deadlines"][1]["submission_deadline"], "2028-03-31"
        )
        self.assertEqual(
            deadlines["annual_reporting_deadlines"][2]["submission_deadline"], "2029-03-31"
        )
        self.assertTrue(len(deadlines["qualified_instruments"]) >= 5)

    def test_get_cash_cow_profiles(self):
        profiles = get_cash_cow_profiles(["BBCA", "BBRI", "ASII", "ADRO"])
        self.assertEqual(len(profiles), 4)
        prof_map = {p["ticker"]: p for p in profiles}

        for ticker in ["BBCA", "BBRI", "ASII", "ADRO"]:
            self.assertIn(ticker, prof_map)
            p = prof_map[ticker]
            self.assertGreater(p["dividend_yield_pct"], 0)
            self.assertGreater(p["dividend_cagr_pct"], 0)
            self.assertIn("moat", p)
            self.assertIn("sovereign_tier", p)

    def test_simulate_sovereign_runway_tax_drag_gap(self):
        sim = simulate_sovereign_runway(
            starting_capital=1_000_000_000.0,
            monthly_living_expense=15_000_000.0,
            expense_inflation_pct=4.0,
            projection_years=15,
            portfolio_weights={"BBCA": 0.5, "BBRI": 0.5},
        )

        regimes = sim["regimes"]
        uu = regimes["uu_cipta_kerja_0pct"]
        std = regimes["standard_tax_drag_10pct"]
        forgn = regimes["foreign_tax_drag_20pct"]

        # UU Cipta Kerja 0% tax must compound to strictly higher net worth than 10% tax drag
        self.assertGreater(uu["final_portfolio_value_idr"], std["final_portfolio_value_idr"])
        # Standard 10% must compound to strictly higher net worth than foreign 20%
        self.assertGreater(std["final_portfolio_value_idr"], forgn["final_portfolio_value_idr"])

        # UU Cipta Kerja tax paid must be zero
        self.assertEqual(uu["total_tax_paid_idr"], 0.0)
        # Standard tax paid must be positive
        self.assertGreater(std["total_tax_paid_idr"], 0.0)

        # Tax drag comparison metrics
        comp = sim["comparison"]
        self.assertGreater(comp["tax_drag_wealth_gap_idr"], 0)
        self.assertGreater(comp["total_tax_saved_via_uu_cipta_kerja_idr"], 0)
        self.assertGreater(comp["wealth_multiplier"], 1.0)
        self.assertIn("UU Cipta Kerja", comp["verdict"])

    def test_api_dividend_simulator_endpoints(self):
        # 1. Cash cows endpoint
        resp_cows = self.client.get("/api/dividend-simulator/cash-cows")
        self.assertEqual(resp_cows.status_code, 200)
        cows_data = resp_cows.json()
        self.assertTrue(len(cows_data) >= 5)

        # 2. Deadlines endpoint
        resp_deadlines = self.client.get(
            "/api/dividend-simulator/statutory-deadlines?receipt_date=2026-08-01"
        )
        self.assertEqual(resp_deadlines.status_code, 200)
        dl_data = resp_deadlines.json()
        self.assertEqual(dl_data["reinvestment_deadline"], "2027-03-31")

        # 3. POST simulation
        payload = {
            "starting_capital": 500_000_000.0,
            "monthly_living_expense": 10_000_000.0,
            "expense_inflation_pct": 3.5,
            "projection_years": 10,
            "portfolio_weights": {"BBCA": 0.5, "BBRI": 0.5},
        }
        resp_sim = self.client.post("/api/dividend-simulator/simulate", json=payload)
        self.assertEqual(resp_sim.status_code, 200)
        sim_data = resp_sim.json()
        self.assertIn("regimes", sim_data)
        self.assertIn("comparison", sim_data)

        # 4. GET simulation convenience
        resp_get = self.client.get(
            "/api/dividend-simulator/simulate?capital=500000000&monthly_expense=10000000&years=10&tickers=BBCA,BBRI"
        )
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn("regimes", resp_get.json())


if __name__ == "__main__":
    unittest.main()
