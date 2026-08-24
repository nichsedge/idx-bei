"""
Daily scheduled ingestion pipeline.

Designed to run via cron at market close (~16:30 WIB) to append today's
trading data to the time-series store and refresh the Parquet files.

Usage:
    # Full daily run (OHLCV + broker + index + parquet export):
    uv run python -m idx.pipelines.daily

    # Crontab entry (16:45 WIB every weekday):
    # 45 16 * * 1-5 cd /path/to/python && uv run python -m idx.pipelines.daily >> /var/log/idx-daily.log 2>&1
"""

import datetime
import json
import logging
import os
import sys

from idx.core.client import IDXClient
from idx.core.utils import DATA_DIR, get_logger

log = get_logger("idx.pipelines.daily")

TIMESERIES_DIR = os.path.join(DATA_DIR, "timeseries")


def _today_str():
    """Returns today's date as YYYYMMDD string."""
    return datetime.datetime.now().strftime("%Y%m%d")


def _today_iso():
    """Returns today's date as YYYY-MM-DD string."""
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _load_timeseries(filepath):
    """Loads existing time-series JSON. Returns (date_index, raw_list)."""
    if not os.path.exists(filepath):
        return {}, []
    try:
        with open(filepath, encoding="utf-8") as f:
            records = json.load(f)
        index = {}
        for rec in records:
            key = rec.get("Date", "")[:10]
            if key not in index:
                index[key] = []
            index[key].append(rec)
        return index, records
    except (OSError, json.JSONDecodeError):
        return {}, []


def _append_and_save(filepath, date_index, date_key, new_records):
    """Appends new_records for date_key and persists."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    date_index[date_key] = new_records

    all_records = []
    for dk in sorted(date_index.keys()):
        all_records.extend(date_index[dk])

    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2)
    os.replace(tmp, filepath)
    return len(all_records)


def ingest_daily(date=None, client=None, export_parquet=True):
    """Fetches today's stock/broker/index summaries and appends to time-series store.

    Args:
        date:            Override date in YYYYMMDD format (for backfill/testing)
        client:          Optional IDXClient instance
        export_parquet:  If True, re-export Parquet files after ingestion

    Returns:
        Summary dict with ingestion results
    """
    if client is None:
        client = IDXClient()
    if date is None:
        date = _today_str()

    date_iso = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    results = {}

    log.info("=" * 60)
    log.info("Daily ingestion started for %s", date_iso)
    log.info("=" * 60)

    # ── Stock Summary (OHLCV + Foreign Flow) ──────────────────────────────
    stock_file = os.path.join(TIMESERIES_DIR, "stock_summary.json")
    stock_index, _ = _load_timeseries(stock_file)

    if date_iso in stock_index:
        log.info("Stock summary for %s already exists (%d records), skipping",
                 date_iso, len(stock_index[date_iso]))
        results["stock_summary"] = {"status": "skipped", "records": len(stock_index[date_iso])}
    else:
        data = client.get_json("/TradingSummary/GetStockSummary",
                               params={"date": date, "start": 0, "length": 9999})
        if data and isinstance(data.get("data"), list) and len(data["data"]) > 0:
            n = _append_and_save(stock_file, stock_index, date_iso, data["data"])
            log.info("Stock summary: %d stocks ingested (total: %d records)",
                     len(data["data"]), n)
            results["stock_summary"] = {"status": "ok", "records": len(data["data"]), "total": n}
        else:
            log.warning("Stock summary: no data for %s (non-trading day?)", date_iso)
            results["stock_summary"] = {"status": "no_data"}

    # ── Broker Summary ────────────────────────────────────────────────────
    broker_file = os.path.join(TIMESERIES_DIR, "broker_summary.json")
    broker_index, _ = _load_timeseries(broker_file)

    if date_iso in broker_index:
        log.info("Broker summary for %s already exists, skipping", date_iso)
        results["broker_summary"] = {"status": "skipped"}
    else:
        data = client.get_json("/TradingSummary/GetBrokerSummary",
                               params={"date": date, "start": 0, "length": 9999})
        if data and isinstance(data.get("data"), list) and len(data["data"]) > 0:
            n = _append_and_save(broker_file, broker_index, date_iso, data["data"])
            log.info("Broker summary: %d brokers ingested (total: %d records)",
                     len(data["data"]), n)
            results["broker_summary"] = {"status": "ok", "records": len(data["data"]), "total": n}
        else:
            results["broker_summary"] = {"status": "no_data"}

    # ── Index Summary ─────────────────────────────────────────────────────
    index_file = os.path.join(TIMESERIES_DIR, "index_summary.json")
    idx_index, _ = _load_timeseries(index_file)

    if date_iso in idx_index:
        log.info("Index summary for %s already exists, skipping", date_iso)
        results["index_summary"] = {"status": "skipped"}
    else:
        data = client.get_json("/TradingSummary/GetIndexSummary",
                               params={"date": date, "start": 0, "length": 9999})
        if data and isinstance(data.get("data"), list) and len(data["data"]) > 0:
            n = _append_and_save(index_file, idx_index, date_iso, data["data"])
            log.info("Index summary: %d indices ingested (total: %d records)",
                     len(data["data"]), n)
            results["index_summary"] = {"status": "ok", "records": len(data["data"]), "total": n}
        else:
            results["index_summary"] = {"status": "no_data"}

    # ── Parquet Export ────────────────────────────────────────────────────
    if export_parquet:
        try:
            from idx.pipelines.parquet import export_all
            parquet_results = export_all()
            results["parquet_export"] = parquet_results
            log.info("Parquet export complete")
        except Exception as exc:
            log.error("Parquet export failed: %s", exc)
            results["parquet_export"] = {"status": "error", "message": str(exc)}

    log.info("=" * 60)
    log.info("Daily ingestion complete: %s", {k: v.get("status", "?") for k, v in results.items()})
    log.info("=" * 60)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Accept optional date argument: python -m idx.pipelines.daily 20260807
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    ingest_daily(date=date_arg)
