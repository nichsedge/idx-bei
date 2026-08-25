"""
SQL query layer over the partitioned Parquet time-series store via DuckDB.

Queries run directly against data/timeseries/<dataset>/date=*.parquet without
materializing anything in memory beyond the result set.

Usage:
    from idx.core.query import query_dataset
    df = query_dataset("stock_summary", start="2026-01-01", where="StockCode = 'BBCA'")
"""

import glob
import os

import duckdb

from idx.core import timeseries as ts
from idx.core.utils import get_logger

log = get_logger("idx.core.query")


def sql(query):
    """Runs arbitrary SQL against DuckDB. Returns a pandas DataFrame."""
    return duckdb.sql(query).df()


def _dataset_glob(dataset, base_dir=None):
    """Glob pattern covering all partitions of a dataset; raises if none exist."""
    pattern = os.path.join(ts.dataset_dir(dataset, base_dir), "date=*.parquet")
    if not glob.glob(pattern):
        raise FileNotFoundError(f"No partitions found for dataset '{dataset}' under {pattern}")
    return pattern


def query_dataset(
    dataset, start=None, end=None, where=None, columns="*", limit=None, base_dir=None
):
    """Queries one time-series dataset with optional filters.

    Args:
        dataset:  Dataset name (e.g. 'stock_summary')
        start:    Inclusive partition date filter, YYYY-MM-DD (on filename Date)
        end:      Inclusive partition date filter, YYYY-MM-DD
        where:    Optional SQL predicate applied to record columns
        columns:  Column list string, defaults to '*'
        limit:    Optional row cap applied last
        base_dir: Optional store root override (for tests)

    Returns:
        pandas DataFrame of matching rows.
    """
    pattern = _dataset_glob(dataset, base_dir)

    conds = []
    if start:
        conds.append(f"regexp_extract(filename, 'date=(.*)\\.parquet', 1) >= '{start}'")
    if end:
        conds.append(f"regexp_extract(filename, 'date=(.*)\\.parquet', 1) <= '{end}'")
    if where:
        conds.append(f"({where})")
    where_clause = f"WHERE {' AND '.join(conds)}" if conds else ""
    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    query = f"""
        SELECT {columns}
        FROM read_parquet(['{pattern}'], filename = true)
        {where_clause}
        ORDER BY 1
        {limit_clause}
    """
    log.debug("DuckDB query: %s", " ".join(query.split()))
    return sql(query)


def available_datasets():
    """Returns datasets that have at least one partition on disk."""
    return [ds for ds in ts.DATASETS if ts.existing_dates(ds)]
