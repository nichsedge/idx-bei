"""
Parquet export pipeline.

Consolidates the partitioned time-series store (one Parquet file per date) and
snapshot JSON datasets into single columnar Parquet files with derived columns,
for fast analytical queries with pandas/polars.

Usage:
    from idx.pipelines.parquet import export_stock_timeseries, export_all
    export_stock_timeseries()
    export_all()
"""

import json
import os

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from idx.core import timeseries as ts
from idx.core.utils import DATA_DIR, get_logger

log = get_logger("idx.pipelines.parquet")

TIMESERIES_DIR = os.path.join(DATA_DIR, "timeseries")
PARQUET_DIR = os.path.join(DATA_DIR, "parquet")


def _ensure_parquet_dir():
    os.makedirs(PARQUET_DIR, exist_ok=True)


def _load_json(filepath):
    """Loads a JSON file, returns list or dict."""
    if not os.path.exists(filepath):
        log.warning("File not found: %s", filepath)
        return None
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


# ── Stock Summary (OHLCV) Time-Series ─────────────────────────────────────────

STOCK_COLUMNS = [
    "Date",
    "StockCode",
    "StockName",
    "Previous",
    "OpenPrice",
    "High",
    "Low",
    "Close",
    "Change",
    "Volume",
    "Value",
    "Frequency",
    "ForeignBuy",
    "ForeignSell",
    "Bid",
    "BidVolume",
    "Offer",
    "OfferVolume",
    "ListedShares",
    "TradebleShares",
    "NonRegularVolume",
    "NonRegularValue",
    "NonRegularFrequency",
]

STOCK_DTYPES = {
    "StockCode": "string",
    "StockName": "string",
    "Previous": "float64",
    "OpenPrice": "float64",
    "High": "float64",
    "Low": "float64",
    "Close": "float64",
    "Change": "float64",
    "Volume": "float64",
    "Value": "float64",
    "Frequency": "float64",
    "ForeignBuy": "float64",
    "ForeignSell": "float64",
    "Bid": "float64",
    "BidVolume": "float64",
    "Offer": "float64",
    "OfferVolume": "float64",
    "ListedShares": "float64",
    "TradebleShares": "float64",
    "NonRegularVolume": "float64",
    "NonRegularValue": "float64",
    "NonRegularFrequency": "float64",
}


def export_stock_timeseries(output=None, incremental=False):
    """Consolidates stock-summary date partitions → single Parquet file.

    Args:
        output: Path to output Parquet file. Defaults to data/parquet/stock_summary.parquet
        incremental: If True and target exists, only reads partitions newer than latest parquet date.

    Returns:
        dict with rows, columns, file, size_mb
    """
    _ensure_parquet_dir()
    if output is None:
        output = os.path.join(PARQUET_DIR, "stock_summary.parquet")

    start_date = None
    existing_df = None
    if incremental and os.path.exists(output):
        try:
            existing_df = pd.read_parquet(output)
            if len(existing_df) > 0 and "Date" in existing_df.columns:
                max_dt = pd.to_datetime(existing_df["Date"]).max()
                start_date = (max_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception as e:
            log.warning("Incremental read failed (%s), doing full export", e)
            existing_df = None

    new_df = ts.read_dataset("stock_summary", start=start_date)
    if len(new_df) == 0 and existing_df is None:
        log.warning("No stock summary data to export")
        return None
    elif len(new_df) == 0 and existing_df is not None:
        log.info("Incremental export: no newer partitions to append.")
        size_mb = os.path.getsize(output) / (1024 * 1024)
        return {
            "rows": len(existing_df),
            "columns": len(existing_df.columns),
            "file": output,
            "size_mb": round(size_mb, 2),
        }

    # Select and order columns (gracefully handle missing ones)
    available = [c for c in STOCK_COLUMNS if c in new_df.columns]
    df = new_df[available].copy()

    # Parse dates
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Cast numeric columns (skip string columns)
    for col, dtype in STOCK_DTYPES.items():
        if col in df.columns and dtype != "string":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Derive useful quant columns
    if "ForeignBuy" in df.columns and "ForeignSell" in df.columns:
        df["NetForeignFlow"] = df["ForeignBuy"] - df["ForeignSell"]

    if "Close" in df.columns and "Previous" in df.columns:
        df["Return"] = ((df["Close"] - df["Previous"]) / df["Previous"]).round(6)

    if "Value" in df.columns and "Volume" in df.columns:
        df["VWAP"] = (df["Value"] / df["Volume"]).where(df["Volume"] > 0).round(2)

    if existing_df is not None:
        df = pd.concat([existing_df, df], ignore_index=True)
        df.drop_duplicates(subset=["Date", "StockCode"], keep="last", inplace=True)

    # Sort for optimal compression and query patterns
    df.sort_values(["Date", "StockCode"], inplace=True, ignore_index=True)

    # Write Parquet with snappy compression
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, output, compression="snappy")

    size_mb = os.path.getsize(output) / (1024 * 1024)
    log.info(
        "Exported stock_summary.parquet: %d rows × %d cols (%.2f MB)",
        len(df),
        len(df.columns),
        size_mb,
    )

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "file": output,
        "size_mb": round(size_mb, 2),
    }


# ── Broker Summary Time-Series ────────────────────────────────────────────────


def export_broker_timeseries(output=None, incremental=False):
    """Consolidates broker-summary date partitions → single Parquet file."""
    _ensure_parquet_dir()
    if output is None:
        output = os.path.join(PARQUET_DIR, "broker_summary.parquet")

    start_date = None
    existing_df = None
    if incremental and os.path.exists(output):
        try:
            existing_df = pd.read_parquet(output)
            if len(existing_df) > 0 and "Date" in existing_df.columns:
                max_dt = pd.to_datetime(existing_df["Date"]).max()
                start_date = (max_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            existing_df = None

    new_df = ts.read_dataset("broker_summary", start=start_date)
    if len(new_df) == 0 and existing_df is None:
        log.warning("No broker summary data to export")
        return None
    elif len(new_df) == 0 and existing_df is not None:
        size_mb = os.path.getsize(output) / (1024 * 1024)
        return {
            "rows": len(existing_df),
            "columns": len(existing_df.columns),
            "file": output,
            "size_mb": round(size_mb, 2),
        }

    df = new_df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    for col in ["Volume", "Value", "Frequency"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if existing_df is not None:
        df = pd.concat([existing_df, df], ignore_index=True)
        id_col = (
            "IDFirm"
            if "IDFirm" in df.columns
            else ("IDBrokerSummary" if "IDBrokerSummary" in df.columns else None)
        )
        if id_col:
            df.drop_duplicates(subset=["Date", id_col], keep="last", inplace=True)

    sort_col = "IDFirm" if "IDFirm" in df.columns else "Date"
    df.sort_values(["Date", sort_col], inplace=True, ignore_index=True)

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, output, compression="snappy")

    size_mb = os.path.getsize(output) / (1024 * 1024)
    log.info(
        "Exported broker_summary.parquet: %d rows × %d cols (%.2f MB)",
        len(df),
        len(df.columns),
        size_mb,
    )
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "file": output,
        "size_mb": round(size_mb, 2),
    }


# ── Index Summary Time-Series ─────────────────────────────────────────────────


def export_index_timeseries(output=None, incremental=False):
    """Consolidates index-summary date partitions → single Parquet file."""
    _ensure_parquet_dir()
    if output is None:
        output = os.path.join(PARQUET_DIR, "index_summary.parquet")

    start_date = None
    existing_df = None
    if incremental and os.path.exists(output):
        try:
            existing_df = pd.read_parquet(output)
            if len(existing_df) > 0 and "Date" in existing_df.columns:
                max_dt = pd.to_datetime(existing_df["Date"]).max()
                start_date = (max_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            existing_df = None

    new_df = ts.read_dataset("index_summary", start=start_date)
    if len(new_df) == 0 and existing_df is None:
        log.warning("No index summary data to export")
        return None
    elif len(new_df) == 0 and existing_df is not None:
        size_mb = os.path.getsize(output) / (1024 * 1024)
        return {
            "rows": len(existing_df),
            "columns": len(existing_df.columns),
            "file": output,
            "size_mb": round(size_mb, 2),
        }

    df = new_df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    numeric_cols = [
        "Previous",
        "Highest",
        "Lowest",
        "Close",
        "Change",
        "Volume",
        "Value",
        "Frequency",
        "MarketCapital",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Derive index return
    if "Close" in df.columns and "Previous" in df.columns:
        df["Return"] = ((df["Close"] - df["Previous"]) / df["Previous"]).round(6)

    if existing_df is not None:
        df = pd.concat([existing_df, df], ignore_index=True)
        idx_col = "IndexCode" if "IndexCode" in df.columns else "IndexName"
        if idx_col in df.columns:
            df.drop_duplicates(subset=["Date", idx_col], keep="last", inplace=True)

    sort_col = "IndexCode" if "IndexCode" in df.columns else "Date"
    df.sort_values(["Date", sort_col], inplace=True, ignore_index=True)

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, output, compression="snappy")

    size_mb = os.path.getsize(output) / (1024 * 1024)
    log.info(
        "Exported index_summary.parquet: %d rows × %d cols (%.2f MB)",
        len(df),
        len(df.columns),
        size_mb,
    )
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "file": output,
        "size_mb": round(size_mb, 2),
    }


# ── Snapshot Exports ──────────────────────────────────────────────────────────


def export_financial_ratios(source=None, output=None):
    """Converts financial ratios snapshot JSON → Parquet."""
    _ensure_parquet_dir()
    if source is None:
        source = os.path.join(DATA_DIR, "financial_ratio.json")
    if output is None:
        output = os.path.join(PARQUET_DIR, "financial_ratios.parquet")

    data = _load_json(source)
    if data is None:
        return None

    # financial_ratio.json may be a flat list or a dict with 'data' key
    if isinstance(data, dict) and "data" in data:
        records = data["data"]
    elif isinstance(data, list):
        records = data
    else:
        log.warning("Unexpected financial ratio format")
        return None

    if len(records) == 0:
        return None

    df = pd.DataFrame(records)

    numeric_cols = [
        "assets",
        "liabilities",
        "equity",
        "sales",
        "operatingProfit",
        "netIncome",
        "eps",
        "per",
        "pbv",
        "roa",
        "roe",
        "npm",
        "opm",
        "der",
        "currentRatio",
        "marketCap",
        "dividendYield",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.sort_values(["code"], inplace=True, ignore_index=True)

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, output, compression="snappy")

    size_mb = os.path.getsize(output) / (1024 * 1024)
    log.info(
        "Exported financial_ratios.parquet: %d rows × %d cols (%.2f MB)",
        len(df),
        len(df.columns),
        size_mb,
    )
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "file": output,
        "size_mb": round(size_mb, 2),
    }


def export_corporate_actions(source=None, output=None):
    """Flattens corporate actions across all categories → single Parquet table."""
    _ensure_parquet_dir()
    if source is None:
        source = os.path.join(DATA_DIR, "corporateActions.json")
    if output is None:
        output = os.path.join(PARQUET_DIR, "corporate_actions.parquet")

    data = _load_json(source)
    if data is None:
        return None

    all_records = []
    for ca_type, info in data.get("categories", {}).items():
        for rec in info.get("data", []):
            rec["caType"] = ca_type
            all_records.append(rec)

    if not all_records:
        return None

    df = pd.DataFrame(all_records)

    if "TanggalPencatatan" in df.columns:
        df["TanggalPencatatan"] = pd.to_datetime(df["TanggalPencatatan"], errors="coerce")

    df.sort_values(["TanggalPencatatan", "KodeEmiten"], inplace=True, ignore_index=True)

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, output, compression="snappy")

    size_mb = os.path.getsize(output) / (1024 * 1024)
    log.info(
        "Exported corporate_actions.parquet: %d rows × %d cols (%.2f MB)",
        len(df),
        len(df.columns),
        size_mb,
    )
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "file": output,
        "size_mb": round(size_mb, 2),
    }


# ── Export All ────────────────────────────────────────────────────────────────


def export_all():
    """Runs all parquet exports. Returns summary dict."""
    results = {}

    for name, fn in [
        ("stock_timeseries", export_stock_timeseries),
        ("broker_timeseries", export_broker_timeseries),
        ("index_timeseries", export_index_timeseries),
        ("financial_ratios", export_financial_ratios),
        ("corporate_actions", export_corporate_actions),
    ]:
        try:
            result = fn()
            results[name] = result if result else {"status": "no_data"}
        except Exception as exc:
            log.error("Failed to export %s: %s", name, exc)
            results[name] = {"status": "error", "message": str(exc)}

    log.info(
        "Export all complete: %s", {k: v.get("rows", v.get("status")) for k, v in results.items()}
    )
    return results
