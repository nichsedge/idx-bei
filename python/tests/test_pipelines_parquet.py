"""
Unit tests for Parquet export pipeline and data consolidator.
"""

import os
import tempfile
import unittest

from idx.pipelines.parquet import (
    export_corporate_actions,
    export_financial_ratios,
    export_stock_timeseries,
)


class TestParquetPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.parquet_dir = os.path.join(self.temp_dir.name, "parquet")
        self.timeseries_dir = os.path.join(self.temp_dir.name, "timeseries")
        os.makedirs(self.parquet_dir, exist_ok=True)
        os.makedirs(self.timeseries_dir, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_stock_timeseries_empty_graceful(self):
        out_file = os.path.join(self.parquet_dir, "stock_summary.parquet")
        res = export_stock_timeseries(output=out_file)
        # Should handle gracefully without raising error
        self.assertIsNotNone(res)

    def test_export_financial_ratios(self):
        json_file = os.path.join(self.temp_dir.name, "financial_ratio.json")
        out_file = os.path.join(self.parquet_dir, "financial_ratios.parquet")
        mock_data = [{"code": "BBCA", "per": "15.5", "roe": "20.2", "deRatio": "0.4", "eps": "450"}]
        import json

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(mock_data, f)

        res = export_financial_ratios(source=json_file, output=out_file)
        self.assertEqual(res["rows"], 1)
        self.assertTrue(os.path.exists(out_file))

    def test_export_corporate_actions(self):
        json_file = os.path.join(self.temp_dir.name, "corporateActions.json")
        out_file = os.path.join(self.parquet_dir, "corporate_actions.parquet")
        mock_data = {
            "categories": {
                "tanpaHmetd": {
                    "count": 1,
                    "data": [
                        {
                            "id": 1,
                            "KodeEmiten": "UNSP",
                            "TanggalPencatatan": "2026-08-04T00:00:00",
                            "JenisTindakan": "tanpaHmetd",
                            "JumlahSaham": 1000000,
                        }
                    ],
                }
            }
        }
        import json

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(mock_data, f)

        res = export_corporate_actions(source=json_file, output=out_file)
        self.assertEqual(res["rows"], 1)
        self.assertTrue(os.path.exists(out_file))
