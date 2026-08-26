"""
Tests for KSEI shareholder drift and tycoon position tracking.
"""

import unittest

import pandas as pd

from idx.core.ownership import (
    compute_ownership_deltas,
    track_tycoon_drift,
)


class TestOwnershipDrift(unittest.TestCase):
    def setUp(self):
        self.prev_df = pd.DataFrame(
            [
                {
                    "DATE": "2025-02-01",
                    "SHARE_CODE": "DILD",
                    "ISSUER_NAME": "Intiland",
                    "INVESTOR_NAME": "LO KHENG HONG",
                    "TOTAL_HOLDING_SHARES": "650.000.000",
                    "PERCENTAGE": "6,25",
                    "Pct": 6.25,
                    "Shares": 650000000.0,
                    "InvestorUpper": "LO KHENG HONG",
                    "ShareCode": "DILD",
                    "INVESTOR_TYPE": "ID",
                    "LOCAL_FOREIGN": "L",
                },
                {
                    "DATE": "2025-02-01",
                    "SHARE_CODE": "TINS",
                    "ISSUER_NAME": "Timah",
                    "INVESTOR_NAME": "BPJS KETENAGAKERJAAN",
                    "TOTAL_HOLDING_SHARES": "100.000.000",
                    "PERCENTAGE": "5,10",
                    "Pct": 5.10,
                    "Shares": 100000000.0,
                    "InvestorUpper": "BPJS KETENAGAKERJAAN",
                    "ShareCode": "TINS",
                    "INVESTOR_TYPE": "IS",
                    "LOCAL_FOREIGN": "L",
                },
            ]
        )

        self.curr_df = pd.DataFrame(
            [
                {
                    "DATE": "2025-03-01",
                    "SHARE_CODE": "DILD",
                    "ISSUER_NAME": "Intiland",
                    "INVESTOR_NAME": "LO KHENG HONG",
                    "TOTAL_HOLDING_SHARES": "700.000.000",
                    "PERCENTAGE": "6,75",
                    "Pct": 6.75,
                    "Shares": 700000000.0,
                    "InvestorUpper": "LO KHENG HONG",
                    "ShareCode": "DILD",
                    "INVESTOR_TYPE": "ID",
                    "LOCAL_FOREIGN": "L",
                },
                {
                    "DATE": "2025-03-01",
                    "SHARE_CODE": "TINS",
                    "ISSUER_NAME": "Timah",
                    "INVESTOR_NAME": "BPJS KETENAGAKERJAAN",
                    "TOTAL_HOLDING_SHARES": "80.000.000",
                    "PERCENTAGE": "4,10",
                    "Pct": 4.10,
                    "Shares": 80000000.0,
                    "InvestorUpper": "BPJS KETENAGAKERJAAN",
                    "ShareCode": "TINS",
                    "INVESTOR_TYPE": "IS",
                    "LOCAL_FOREIGN": "L",
                },
            ]
        )

    def test_compute_ownership_deltas(self):
        deltas = compute_ownership_deltas(self.prev_df, self.curr_df, min_pct_delta=0.01)
        self.assertEqual(len(deltas), 2)
        dild = deltas[deltas["ShareCode"] == "DILD"].iloc[0]
        self.assertEqual(dild["Action"], "ACCUMULATING")
        self.assertEqual(dild["PctDelta"], 0.5)

        tins = deltas[deltas["ShareCode"] == "TINS"].iloc[0]
        self.assertEqual(tins["Action"], "DISTRIBUTING")
        self.assertEqual(tins["PctDelta"], -1.0)

    def test_track_tycoon_drift(self):
        tycoon_deltas = track_tycoon_drift(self.prev_df, self.curr_df)
        self.assertEqual(len(tycoon_deltas), 1)
        self.assertEqual(tycoon_deltas.iloc[0]["InvestorName"], "LO KHENG HONG")


if __name__ == "__main__":
    unittest.main()
