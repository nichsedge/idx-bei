"""
Unit tests for Parquet export pipeline and data consolidator.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from idx.pipelines.parquet import (
    compact_partitions,
    export_all,
    export_broker_timeseries,
    export_corporate_actions,
    export_financial_ratios,
    export_index_timeseries,
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
        import pandas as pd

        out_file = os.path.join(self.parquet_dir, "stock_summary.parquet")
        with patch("idx.core.timeseries.read_dataset", return_value=pd.DataFrame()):
            res = export_stock_timeseries(output=out_file)
        # No partitions: returns None without raising and writes nothing
        self.assertIsNone(res)
        self.assertFalse(os.path.exists(out_file))

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

    def test_export_corporate_actions_none_on_empty(self):
        json_file = os.path.join(self.temp_dir.name, "empty_ca.json")
        with open(json_file, "w", encoding="utf-8") as f:
            f.write("{}")
        res = export_corporate_actions(source=json_file, output="dummy.parquet")
        self.assertIsNone(res)

    def test_export_financial_ratios_none_on_missing(self):
        res = export_financial_ratios(source="non_existent_ratios.json", output="dummy.parquet")
        self.assertIsNone(res)

    @patch("idx.core.timeseries.read_dataset")
    def test_export_broker_timeseries(self, mock_read):
        import pandas as pd

        out_file = os.path.join(self.parquet_dir, "broker_summary.parquet")

        # Empty
        mock_read.return_value = pd.DataFrame()
        res_empty = export_broker_timeseries(output=out_file)
        self.assertIsNone(res_empty)

        # Populated
        df = pd.DataFrame(
            [
                {
                    "Date": "2026-08-01",
                    "IDFirm": "YP",
                    "Volume": 1000,
                    "Value": 50000,
                    "Frequency": 10,
                },
                {
                    "Date": "2026-08-01",
                    "IDFirm": "CC",
                    "Volume": 2000,
                    "Value": 80000,
                    "Frequency": 20,
                },
            ]
        )
        mock_read.return_value = df
        res = export_broker_timeseries(output=out_file)
        self.assertIsNotNone(res)
        self.assertEqual(res["rows"], 2)
        self.assertTrue(os.path.exists(out_file))

        # Incremental with existing file
        mock_read.return_value = pd.DataFrame(
            [
                {
                    "Date": "2026-08-02",
                    "IDFirm": "YP",
                    "Volume": 1500,
                    "Value": 60000,
                    "Frequency": 15,
                },
            ]
        )
        res_inc = export_broker_timeseries(output=out_file, incremental=True)
        self.assertIsNotNone(res_inc)
        self.assertEqual(res_inc["rows"], 3)

    @patch("idx.core.timeseries.read_dataset")
    def test_export_index_timeseries(self, mock_read):
        import pandas as pd

        out_file = os.path.join(self.parquet_dir, "index_summary.parquet")

        # Empty
        mock_read.return_value = pd.DataFrame()
        res_empty = export_index_timeseries(output=out_file)
        self.assertIsNone(res_empty)

        # Populated
        df = pd.DataFrame(
            [
                {
                    "Date": "2026-08-01",
                    "IndexCode": "COMPOSITE",
                    "Close": 7500,
                    "Previous": 7450,
                    "Volume": 100000,
                },
            ]
        )
        mock_read.return_value = df
        res = export_index_timeseries(output=out_file)
        self.assertIsNotNone(res)
        self.assertEqual(res["rows"], 1)
        self.assertTrue(os.path.exists(out_file))

        # Incremental
        mock_read.return_value = pd.DataFrame(
            [
                {
                    "Date": "2026-08-02",
                    "IndexCode": "COMPOSITE",
                    "Close": 7550,
                    "Previous": 7500,
                    "Volume": 120000,
                },
            ]
        )
        res_inc = export_index_timeseries(output=out_file, incremental=True)
        self.assertIsNotNone(res_inc)
        self.assertEqual(res_inc["rows"], 2)

    @patch("idx.pipelines.parquet.export_stock_timeseries")
    @patch("idx.pipelines.parquet.export_broker_timeseries")
    @patch("idx.pipelines.parquet.export_index_timeseries")
    @patch("idx.pipelines.parquet.export_financial_ratios")
    @patch("idx.pipelines.parquet.export_corporate_actions")
    def test_export_all(self, mock_ca, mock_fr, mock_idx, mock_brk, mock_stk):
        mock_stk.return_value = {"rows": 100}
        mock_brk.return_value = None
        mock_idx.return_value = {"rows": 10}
        mock_fr.side_effect = RuntimeError("File missing")
        mock_ca.return_value = {"rows": 5}

        summary = export_all()
        self.assertEqual(summary["stock_timeseries"]["rows"], 100)
        self.assertEqual(summary["broker_timeseries"]["status"], "no_data")
        self.assertEqual(summary["financial_ratios"]["status"], "error")

    def test_compact_partitions(self):
        from idx.core.timeseries import write_partition

        # Write 2 daily partitions
        ds = "stock_summary"
        write_partition(
            ds, "2026-08-01", [{"StockCode": "BBCA", "Close": 10000}], base_dir=self.timeseries_dir
        )
        write_partition(
            ds, "2026-08-02", [{"StockCode": "BBCA", "Close": 10100}], base_dir=self.timeseries_dir
        )
        write_partition(
            ds, "2026-09-01", [{"StockCode": "BBCA", "Close": 10200}], base_dir=self.timeseries_dir
        )

        # Compact monthly
        res_m = compact_partitions(
            dataset=ds, freq="month", base_dir=self.timeseries_dir, remove_source=False
        )
        self.assertIn(ds, res_m)
        self.assertEqual(res_m[ds]["compacted_partitions"], 2)
        self.assertEqual(res_m[ds]["daily_files_merged"], 3)

        # Compact quarterly
        res_q = compact_partitions(
            dataset=ds, freq="quarter", base_dir=self.timeseries_dir, remove_source=True
        )
        self.assertIn(ds, res_q)
        self.assertEqual(res_q[ds]["compacted_partitions"], 1)
        self.assertEqual(res_q[ds]["daily_files_merged"], 3)

        # Calling compact again when no daily files remain
        res_empty = compact_partitions(dataset=ds, freq="month", base_dir=self.timeseries_dir)
        self.assertEqual(res_empty[ds]["status"], "no_files")
