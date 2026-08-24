"""Tests for idx.scrapers.historical – backfill loop (mocked client)."""

import pytest

from idx.core import timeseries as ts
from idx.scrapers import historical


class FakeClient:
    """Returns data for requested dates; tracks calls."""

    def __init__(self, empty_dates=(), fail_dates=()):
        self.empty_dates = set(empty_dates)
        self.fail_dates = set(fail_dates)
        self.requested = []

    def get_json(self, endpoint, params=None, **kwargs):
        date = params["date"]
        self.requested.append(date)
        if date in self.fail_dates:
            raise RuntimeError("boom")
        if date in self.empty_dates:
            return {"data": []}
        return {"data": [{"Date": f"{date[:4]}-{date[4:6]}-{date[6:8]}", "n": 1}]}


@pytest.fixture
def ts_dir(tmp_path, monkeypatch):
    path = str(tmp_path / "timeseries")
    monkeypatch.setattr(ts, "TIMESERIES_DIR", path)
    return path


class TestBackfillDataset:
    def test_fetches_trading_days_only(self, ts_dir):
        # Mon 2026-01-05 .. Fri 2026-01-09; Sat/Sun excluded
        result = historical._backfill_dataset(
            "stock_summary",
            "/TradingSummary/GetStockSummary",
            "20260105",
            "20260111",
            client=FakeClient(),
        )
        assert result["dates_fetched"] == 5
        assert result["errors"] == 0
        assert set(ts.existing_dates("stock_summary")) == {
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
            "2026-01-08",
            "2026-01-09",
        }

    def test_skips_holidays_without_partition(self, ts_dir):
        client = FakeClient(empty_dates=["20260106"])
        result = historical._backfill_dataset(
            "stock_summary",
            "/TradingSummary/GetStockSummary",
            "20260105",
            "20260107",
            client=client,
        )
        assert result["dates_fetched"] == 2
        assert result["dates_skipped"] == 1
        assert "2026-01-06" not in ts.existing_dates("stock_summary")

    def test_counts_errors_and_continues(self, ts_dir):
        client = FakeClient(fail_dates=["20260106"])
        result = historical._backfill_dataset(
            "stock_summary",
            "/TradingSummary/GetStockSummary",
            "20260105",
            "20260107",
            client=client,
        )
        assert result["dates_fetched"] == 2
        assert result["errors"] == 1
        assert len(ts.existing_dates("stock_summary")) == 2

    def test_idempotent_rerun_skips_cached(self, ts_dir):
        historical._backfill_dataset(
            "stock_summary",
            "/TradingSummary/GetStockSummary",
            "20260105",
            "20260106",
            client=FakeClient(),
        )
        client = FakeClient()
        result = historical._backfill_dataset(
            "stock_summary",
            "/TradingSummary/GetStockSummary",
            "20260105",
            "20260106",
            client=client,
        )
        assert result["dates_fetched"] == 0
        assert result["dates_skipped"] == 2
        assert client.requested == []  # nothing re-fetched


class TestParseDate:
    def test_accepts_both_formats(self):
        assert str(historical._parse_date("20260105")) == "2026-01-05"
        assert str(historical._parse_date("2026-01-05")) == "2026-01-05"
