"""
Partitioned Parquet time-series store.

Replaces the legacy "load whole JSON → append → rewrite" pattern with one
Parquet file per date:

    data/timeseries/<dataset>/date=YYYY-MM-DD.parquet

This makes daily ingestion O(1): appending today's data writes a single small
file instead of rewriting the full history. Reads use pyarrow directly and
return pandas DataFrames.

Usage:
    from idx.core.timeseries import (
        existing_dates, write_partition, read_dataset, migrate_json,
    )
    write_partition("stock_summary", "2026-08-07", records)
    df = read_dataset("stock_summary", start="2026-01-01")
"""

import glob
import json
import os
import shutil

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from idx.core.utils import DATA_DIR, get_logger

log = get_logger("idx.core.timeseries")

TIMESERIES_DIR = os.path.join(DATA_DIR, "timeseries")

DATASETS = ("stock_summary", "broker_summary", "index_summary")


def dataset_dir(dataset, base_dir=None):
    """Returns the partition directory for a dataset."""
    root = base_dir or TIMESERIES_DIR
    return os.path.join(root, dataset)


def partition_path(dataset, date_iso, base_dir=None):
    """Returns the partition file path for a dataset and ISO date (YYYY-MM-DD)."""
    return os.path.join(dataset_dir(dataset, base_dir), f"date={date_iso}.parquet")


def compacted_partitions(dataset, base_dir=None):
    """Returns list of monthly/quarterly compacted parquet paths."""
    pattern = os.path.join(dataset_dir(dataset, base_dir), "year=*", "month=*.parquet")
    return sorted(glob.glob(pattern))


def existing_dates(dataset, base_dir=None):
    """Returns the set of ingested dates (ISO strings) for a dataset."""
    dates = {}

    # 1. Compacted monthly partitions: year=YYYY/month=MM.parquet
    for comp_path in compacted_partitions(dataset, base_dir):
        try:
            # Read only the Date column to quickly identify covered dates
            tbl = pq.read_table(comp_path, columns=["Date"])
            col_dates = set(tbl["Date"].to_pylist())
            for d in col_dates:
                if d:
                    d_str = str(d)[:10]
                    dates[d_str] = comp_path
        except Exception as exc:
            log.warning("Could not read dates from compacted partition %s: %s", comp_path, exc)

    # 2. Daily partitions: date=YYYY-MM-DD.parquet (daily overrides if both exist)
    pattern = os.path.join(dataset_dir(dataset, base_dir), "date=*.parquet")
    for path in glob.glob(pattern):
        basename = os.path.basename(path)  # date=YYYY-MM-DD.parquet
        dates[basename[len("date=") : -len(".parquet")]] = path

    return dates


def write_partition(dataset, date_iso, records, base_dir=None):
    """Atomically writes one date partition.

    Args:
        dataset:   Dataset name (e.g. 'stock_summary')
        date_iso:  Date in YYYY-MM-DD format
        records:   List of dict records
        base_dir:  Optional root override (for tests)

    Returns:
        Path of the written parquet file.
    """
    if not isinstance(records, list) or len(records) == 0:
        raise ValueError(f"No records to write for {dataset} {date_iso}")

    out_path = partition_path(dataset, date_iso, base_dir)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    table = pa.Table.from_pylist(records)
    tmp = out_path + ".tmp"
    pq.write_table(table, tmp, compression="snappy")
    os.replace(tmp, out_path)

    log.debug("Wrote %s partition %s (%d records)", dataset, date_iso, len(records))
    return out_path


def read_dataset(dataset, start=None, end=None, base_dir=None):
    """Reads a dataset into a pandas DataFrame, optionally filtered by date range.

    Args:
        dataset:  Dataset name
        start:    Inclusive start date (YYYY-MM-DD), optional
        end:      Inclusive end date (YYYY-MM-DD), optional
        base_dir: Optional root override (for tests)

    Returns:
        pandas DataFrame sorted by Date; empty DataFrame if no data.
    """
    dates = existing_dates(dataset, base_dir)
    selected = sorted(
        d for d, _ in dates.items() if (start is None or d >= start) and (end is None or d <= end)
    )

    if not selected:
        return pd.DataFrame()

    unique_paths = sorted(set(dates[d] for d in selected))
    tables = [pq.read_table(p) for p in unique_paths]
    df = pa.concat_tables(tables).to_pandas()

    # Filter to selected dates
    if "Date" in df.columns:
        df["_d_str"] = df["Date"].astype(str).str[:10]
        selected_set = set(selected)
        df = df[df["_d_str"].isin(selected_set)].copy()
        df.drop(columns=["_d_str"], inplace=True)

    sort_cols = [
        c
        for c in ["Date"] + [c for c in df.columns if c.endswith(("Code", "Firm"))]
        if c in df.columns
    ]
    if sort_cols:
        df.sort_values(
            sort_cols,
            inplace=True,
            ignore_index=True,
        )
    return df


def legacy_json_path(dataset, base_dir=None):
    """Path of the legacy monolithic JSON file for a dataset."""
    root = base_dir or TIMESERIES_DIR
    return os.path.join(root, f"{dataset}.json")


def migrate_json(dataset, base_dir=None, keep_backup=True):
    """Migrates a legacy monolithic JSON time-series file to date partitions.

    Idempotent: dates that already exist as partitions are skipped, and the
    migration does nothing if the legacy JSON is absent.

    Args:
        dataset:     Dataset name
        base_dir:    Optional root override (for tests)
        keep_backup: If True, rename the JSON to <name>.json.migrated instead
                     of deleting it after successful migration.

    Returns:
        dict with 'migrated_dates', 'skipped_dates', 'total_records', 'source'
    """
    source = legacy_json_path(dataset, base_dir)
    result = {"migrated_dates": 0, "skipped_dates": 0, "total_records": 0, "source": None}

    if not os.path.exists(source):
        return result

    try:
        with open(source, encoding="utf-8") as f:
            records = json.load(f)
        if not isinstance(records, list):
            log.warning("Unexpected legacy format in %s, skipping migration", source)
            return result
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Cannot read %s: %s", source, exc)
        return result

    by_date = {}
    for rec in records:
        key = str(rec.get("Date", ""))[:10]
        if key:
            by_date.setdefault(key, []).append(rec)

    have = existing_dates(dataset, base_dir)
    for date_key, date_records in sorted(by_date.items()):
        if date_key in have:
            result["skipped_dates"] += 1
            continue
        write_partition(dataset, date_key, date_records, base_dir)
        result["migrated_dates"] += 1
        result["total_records"] += len(date_records)
        log.info("Migrated %s %s: %d records", dataset, date_key, len(date_records))

    result["source"] = source
    if keep_backup:
        backup = source + ".migrated"
        shutil.move(source, backup)
        log.info("Legacy JSON moved to %s", backup)
    else:
        os.remove(source)

    return result


def migrate_all(base_dir=None):
    """Runs migration for all known datasets. Returns per-dataset results."""
    return {ds: migrate_json(ds, base_dir) for ds in DATASETS}
