"""
Unit tests for DuckDB partition compaction and automated KSEI ownership ingestion.
"""

import os
import tempfile
import unittest

from idx.core import timeseries as ts
from idx.core.ownership import ingest_ksei_ownership
from idx.pipelines.parquet import compact_partitions


class TestCompactionAndIngest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_partition_compaction(self):
        base_dir = self.temp_dir.name
        # Write two daily partitions
        records_1 = [{"Date": "2026-08-03", "StockCode": "BBCA", "Close": 10000.0, "Volume": 100}]
        records_2 = [{"Date": "2026-08-04", "StockCode": "BBCA", "Close": 10100.0, "Volume": 200}]

        ts.write_partition("stock_summary", "2026-08-03", records_1, base_dir=base_dir)
        ts.write_partition("stock_summary", "2026-08-04", records_2, base_dir=base_dir)

        # Run compaction
        summary = compact_partitions(
            "stock_summary", freq="month", base_dir=base_dir, remove_source=True
        )
        self.assertEqual(summary["stock_summary"]["compacted_partitions"], 1)
        self.assertEqual(summary["stock_summary"]["daily_files_merged"], 2)

        # Verify compacted file exists
        compacted_file = os.path.join(base_dir, "stock_summary", "year=2026", "month=08.parquet")
        self.assertTrue(os.path.exists(compacted_file))

        # Verify existing_dates recognizes dates from the compacted partition
        dates = ts.existing_dates("stock_summary", base_dir=base_dir)
        self.assertIn("2026-08-03", dates)
        self.assertIn("2026-08-04", dates)

        # Verify read_dataset reads from compacted partition
        df = ts.read_dataset("stock_summary", base_dir=base_dir)
        self.assertEqual(len(df), 2)
        self.assertEqual(list(df["Date"]), ["2026-08-03", "2026-08-04"])

    def test_ksei_ownership_ingestion(self):
        out_dir = self.temp_dir.name

        # Snapshot 1
        csv_content_1 = (
            "DATE,SHARE_CODE,ISSUER_NAME,INVESTOR_NAME,TOTAL_HOLDING_SHARES,PERCENTAGE\n"
            '03-FEB-2025,BBCA,PT BANK CENTRAL ASIA TBK,  LO KHENG HONG  ,10.000.000,"1,50"\n'
            '03-FEB-2025,BBCA,PT BANK CENTRAL ASIA TBK,PT DWIMURIA INVESTAMA,5.000.000.000,"51,00"\n'
        )
        src_path_1 = os.path.join(out_dir, "raw_1.csv")
        with open(src_path_1, "w", encoding="utf-8") as f:
            f.write(csv_content_1)

        res_1 = ingest_ksei_ownership(src_path_1, output_dir=out_dir)
        self.assertEqual(res_1["status"], "ok")
        self.assertEqual(res_1["total_rows"], 2)
        self.assertEqual(res_1["date"], "2025-02-03")
        self.assertTrue(os.path.exists(res_1["output_file"]))

        # Snapshot 2 (Lo Kheng Hong accumulated)
        csv_content_2 = (
            "DATE,SHARE_CODE,ISSUER_NAME,INVESTOR_NAME,TOTAL_HOLDING_SHARES,PERCENTAGE\n"
            '03-MAR-2025,BBCA,PT BANK CENTRAL ASIA TBK,LO KHENG HONG,15.000.000,"2,25"\n'
            '03-MAR-2025,BBCA,PT BANK CENTRAL ASIA TBK,PT DWIMURIA INVESTAMA,5.000.000.000,"51,00"\n'
        )
        src_path_2 = os.path.join(out_dir, "raw_2.csv")
        with open(src_path_2, "w", encoding="utf-8") as f:
            f.write(csv_content_2)

        res_2 = ingest_ksei_ownership(src_path_2, output_dir=out_dir)
        self.assertEqual(res_2["status"], "ok")
        self.assertEqual(res_2["date"], "2025-03-03")
        self.assertEqual(res_2["prev_file"], "1%ownership-2025-02-03.csv")
        self.assertGreater(res_2["deltas_count"], 0)

        # Verify accumulation action
        deltas = res_2["deltas"]
        lkh_row = deltas[deltas["InvestorName"].str.contains("LO KHENG HONG", case=False)]
        self.assertFalse(lkh_row.empty)
        self.assertEqual(lkh_row.iloc[0]["Action"], "ACCUMULATING")
        self.assertEqual(lkh_row.iloc[0]["PctDelta"], 0.75)
