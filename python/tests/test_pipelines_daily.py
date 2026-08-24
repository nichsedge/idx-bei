"""Tests for idx.pipelines.daily – daily ingestion pipeline (mocked client)."""

import os

import pytest

from idx.core import timeseries as ts
from idx.pipelines import daily as daily_mod


class FakeClient:
    """IDXClient stand-in returning canned responses per endpoint."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_json(self, endpoint, params=None, **kwargs):
        self.calls.append((endpoint, params))
        result = self.responses.get(endpoint)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def ts_dir(tmp_path, monkeypatch):
    """Redirect the timeseries store to a temp dir."""
    path = str(tmp_path / "timeseries")
    os.makedirs(path, exist_ok=True)
    monkeypatch.setattr(ts, "TIMESERIES_DIR", path)
    return path


class TestIngestDataset:
    def test_ingests_new_date(self, ts_dir):
        client = FakeClient(
            {
                "/TradingSummary/GetStockSummary": {
                    "data": [{"Date": "2026-01-05", "StockCode": "BBCA"}]
                }
            }
        )
        result = daily_mod._ingest_dataset(
            client, "stock_summary", "/TradingSummary/GetStockSummary", "20260105", "2026-01-05"
        )
        assert result["status"] == "ok"
        assert result["records"] == 1
        assert set(ts.existing_dates("stock_summary")) == {"2026-01-05"}

    def test_skips_existing_date(self, ts_dir):
        ts.write_partition(
            "stock_summary", "2026-01-05", [{"Date": "2026-01-05", "StockCode": "BBCA"}]
        )
        client = FakeClient({})
        result = daily_mod._ingest_dataset(
            client, "stock_summary", "/TradingSummary/GetStockSummary", "20260105", "2026-01-05"
        )
        assert result["status"] == "skipped"
        assert client.calls == []  # no HTTP call for cached dates

    def test_no_data_on_non_trading_day(self, ts_dir):
        client = FakeClient({"/TradingSummary/GetIndexSummary": {"data": []}})
        result = daily_mod._ingest_dataset(
            client, "index_summary", "/TradingSummary/GetIndexSummary", "20260103", "2026-01-03"
        )
        assert result["status"] == "no_data"

    def test_handles_none_response(self, ts_dir):
        client = FakeClient({"/TradingSummary/GetBrokerSummary": None})
        result = daily_mod._ingest_dataset(
            client, "broker_summary", "/TradingSummary/GetBrokerSummary", "20260105", "2026-01-05"
        )
        assert result["status"] == "no_data"


class TestIngestDaily:
    def test_full_run_writes_all_datasets(self, ts_dir, monkeypatch):
        responses = {
            name: {"data": [{"Date": "2026-01-05", f"Key{i}": 1}]}
            for i, name in enumerate(
                [
                    "/TradingSummary/GetStockSummary",
                    "/TradingSummary/GetBrokerSummary",
                    "/TradingSummary/GetIndexSummary",
                ]
            )
        }
        monkeypatch.setattr(daily_mod, "export_parquet_default", False, raising=False)
        results = daily_mod.ingest_daily(
            date="20260105", client=FakeClient(responses), export_parquet=False
        )
        assert all(
            results[ds]["status"] == "ok"
            for ds in ("stock_summary", "broker_summary", "index_summary")
        )
        # Idempotent: re-running the same date skips everything
        results2 = daily_mod.ingest_daily(
            date="20260105", client=FakeClient(responses), export_parquet=False
        )
        assert all(
            results2[ds]["status"] == "skipped"
            for ds in ("stock_summary", "broker_summary", "index_summary")
        )

    def test_migrates_legacy_json(self, ts_dir, tmp_path):
        import json
        import os

        legacy = os.path.join(ts_dir, "index_summary.json")
        with open(legacy, "w") as f:
            json.dump([{"Date": "2025-12-31T00:00:00", "IndexCode": "IHSG"}], f)
        client = FakeClient({})  # no new data anywhere
        daily_mod.ingest_daily(date="20260105", client=client, export_parquet=False)
        assert set(ts.existing_dates("index_summary")) == {"2025-12-31"}
        assert not os.path.exists(legacy)  # renamed to .migrated
