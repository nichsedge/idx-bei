"""Tests for idx.core.timeseries – partitioned Parquet time-series store."""

import json
import os

import pytest

from idx.core import timeseries as ts


@pytest.fixture
def base_dir(tmp_path):
    return str(tmp_path)


def _write_two_partitions(base_dir):
    ts.write_partition("stock_summary", "2026-01-05",
                       [{"Date": "2026-01-05T00:00:00", "StockCode": "BBCA", "Close": 9000},
                        {"Date": "2026-01-05T00:00:00", "StockCode": "BBRI", "Close": 4200}],
                       base_dir)
    ts.write_partition("stock_summary", "2026-01-06",
                       [{"Date": "2026-01-06T00:00:00", "StockCode": "BBCA", "Close": 9100}],
                       base_dir)


class TestWritePartition:
    def test_creates_partition_file(self, base_dir):
        path = ts.write_partition("stock_summary", "2026-01-05",
                                  [{"Date": "2026-01-05", "StockCode": "BBCA"}], base_dir)
        assert os.path.exists(path)

    def test_rejects_empty_records(self, base_dir):
        with pytest.raises(ValueError):
            ts.write_partition("stock_summary", "2026-01-05", [], base_dir)

    def test_overwrite_is_idempotent(self, base_dir):
        records = [{"Date": "2026-01-05", "StockCode": "BBCA"}]
        ts.write_partition("stock_summary", "2026-01-05", records, base_dir)
        ts.write_partition("stock_summary", "2026-01-05", records, base_dir)
        assert set(ts.existing_dates("stock_summary", base_dir)) == {"2026-01-05"}


class TestExistingDates:
    def test_empty_dataset(self, base_dir):
        assert ts.existing_dates("stock_summary", base_dir) == {}

    def test_lists_written_dates(self, base_dir):
        _write_two_partitions(base_dir)
        assert set(ts.existing_dates("stock_summary", base_dir)) == {"2026-01-05", "2026-01-06"}


class TestReadDataset:
    def test_reads_all(self, base_dir):
        _write_two_partitions(base_dir)
        df = ts.read_dataset("stock_summary", base_dir=base_dir)
        assert len(df) == 3

    def test_date_filter(self, base_dir):
        _write_two_partitions(base_dir)
        df = ts.read_dataset("stock_summary", start="2026-01-06", end="2026-01-06",
                             base_dir=base_dir)
        assert len(df) == 1
        assert df.iloc[0]["StockCode"] == "BBCA"

    def test_no_data_returns_empty(self, base_dir):
        assert len(ts.read_dataset("stock_summary", base_dir=base_dir)) == 0


class TestMigrateJson:
    def _write_legacy(self, base_dir, dataset="broker_summary"):
        legacy = [
            {"Date": "2026-01-05T00:00:00", "IDFirm": "AB"},
            {"Date": "2026-01-06T00:00:00", "IDFirm": "AC"},
        ]
        path = ts.legacy_json_path(dataset, base_dir)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(legacy, f)
        return path

    def test_migrates_all_dates_and_backs_up(self, base_dir):
        legacy = self._write_legacy(base_dir)
        result = ts.migrate_json("broker_summary", base_dir=base_dir)
        assert result["migrated_dates"] == 2
        assert result["total_records"] == 2
        assert set(ts.existing_dates("broker_summary", base_dir)) == {"2026-01-05", "2026-01-06"}
        assert not os.path.exists(legacy)
        assert os.path.exists(legacy + ".migrated")

    def test_idempotent_rerun(self, base_dir):
        self._write_legacy(base_dir)
        ts.migrate_json("broker_summary", base_dir=base_dir)
        # Re-create legacy file with an already-partitioned date only
        path = ts.legacy_json_path("broker_summary", base_dir)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"Date": "2026-01-05T00:00:00", "IDFirm": "AB"}], f)
        result = ts.migrate_json("broker_summary", base_dir=base_dir)
        assert result["migrated_dates"] == 0
        assert result["skipped_dates"] == 1

    def test_noop_when_no_legacy_file(self, base_dir):
        result = ts.migrate_json("broker_summary", base_dir=base_dir)
        assert result["migrated_dates"] == 0
        assert result["source"] is None
