"""Tests for idx.core.query – DuckDB SQL layer over parquet partitions."""

import pytest

from idx.core import timeseries as ts
from idx.core.query import available_datasets, query_dataset


@pytest.fixture
def ts_dir(tmp_path, monkeypatch):
    path = str(tmp_path / "timeseries")
    ts.write_partition("stock_summary", "2026-01-05",
                       [{"Date": "2026-01-05T00:00:00", "StockCode": "BBCA", "Close": 9000.0},
                        {"Date": "2026-01-05T00:00:00", "StockCode": "BBRI", "Close": 4200.0}],
                       path)
    ts.write_partition("stock_summary", "2026-01-06",
                       [{"Date": "2026-01-06T00:00:00", "StockCode": "BBCA", "Close": 9100.0}],
                       path)
    monkeypatch.setattr(ts, "TIMESERIES_DIR", path)
    return path


def test_query_all(ts_dir):
    assert len(query_dataset("stock_summary")) == 3


def test_query_date_range(ts_dir):
    df = query_dataset("stock_summary", start="2026-01-06")
    assert len(df) == 1
    df = query_dataset("stock_summary", end="2026-01-05")
    assert len(df) == 2


def test_query_where_and_columns(ts_dir):
    df = query_dataset("stock_summary", where="StockCode = 'BBCA'",
                       columns="StockCode, Close")
    assert len(df) == 2
    assert list(df.columns) == ["StockCode", "Close"]
    assert set(df["Close"]) == {9000.0, 9100.0}


def test_query_limit(ts_dir):
    assert len(query_dataset("stock_summary", limit=2)) == 2


def test_missing_dataset_raises(ts_dir):
    with pytest.raises(FileNotFoundError):
        query_dataset("broker_summary")


def test_available_datasets(ts_dir):
    assert available_datasets() == ["stock_summary"]


def test_sql_passthrough(ts_dir):
    pattern = f"{ts_dir}/stock_summary/date=*.parquet"
    from idx.core.query import sql
    df = sql(f"SELECT count(*) AS n FROM read_parquet('{pattern}')")
    assert df.iloc[0]["n"] == 3
