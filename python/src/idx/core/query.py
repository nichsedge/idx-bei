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
import re

import duckdb
import pandas as pd

from idx.core import timeseries as ts
from idx.core.utils import get_logger

log = get_logger("idx.core.query")


def sql(query):
    """Runs arbitrary SQL against DuckDB. Returns a pandas DataFrame."""
    res = duckdb.sql(query)
    return res.df() if res is not None else pd.DataFrame()


def _dataset_glob(dataset, base_dir=None):
    """Glob pattern covering all partitions of a dataset; raises if none exist."""
    d_dir = ts.dataset_dir(dataset, base_dir)
    pattern = os.path.join(d_dir, "**", "*.parquet")
    if not glob.glob(pattern, recursive=True):
        # Fallback to consolidated parquet if available
        consolidated = os.path.join(os.path.dirname(d_dir), "parquet", f"{dataset}.parquet")
        if os.path.exists(consolidated):
            return consolidated
        raise FileNotFoundError(f"No partitions found for dataset '{dataset}' under {d_dir}")
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

    # Sanitize and validate basic inputs
    if start and not re.match(r"^\d{4}-?\d{2}-?\d{2}$", str(start)):
        raise ValueError(f"Invalid start date format: {start}")
    if end and not re.match(r"^\d{4}-?\d{2}-?\d{2}$", str(end)):
        raise ValueError(f"Invalid end date format: {end}")
    if columns != "*" and any(c in columns for c in (";", "--", "/*")):
        raise ValueError(f"Invalid character in column specification: {columns}")

    conds = []
    if start:
        conds.append(
            f"(Date >= '{start}' OR regexp_extract(filename, 'date=(.*)\\.parquet', 1) >= '{start}')"
        )
    if end:
        conds.append(
            f"(Date <= '{end}' OR regexp_extract(filename, 'date=(.*)\\.parquet', 1) <= '{end}')"
        )
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
