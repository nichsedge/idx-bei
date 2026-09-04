"""
Daily scheduled ingestion pipeline.

Designed to run via cron at market close (~16:30 WIB) to append today's
trading data to the partitioned Parquet time-series store.

Usage:
    # Full daily run (OHLCV + broker + index + parquet export):
    uv run idx daily

    # Crontab entry (16:45 WIB every weekday):
    # 45 16 * * 1-5 uv run idx daily >> /var/log/idx-daily.log 2>&1
"""

import datetime
import logging
import sys

from idx.core import timeseries as ts
from idx.core.client import IDXClient
from idx.core.utils import get_logger

log = get_logger("idx.pipelines.daily")


def _today_str():
    """Returns today's date as YYYYMMDD string."""
    return datetime.datetime.now().strftime("%Y%m%d")


def _ingest_dataset(client, dataset, endpoint, date, date_iso):
    """Fetches one trading-summary dataset for a date and writes its partition.

    Returns:
        dict with 'status' and record counts.
    """
    have = ts.existing_dates(dataset)
    if date_iso in have:
        log.info("%s for %s already exists, skipping", dataset, date_iso)
        return {"status": "skipped"}

    data = client.get_json(endpoint, params={"date": date, "start": 0, "length": 9999})
    records = data.get("data") if isinstance(data, dict) else None

    if not isinstance(records, list) or len(records) == 0:
        log.warning("%s: no data for %s (non-trading day?)", dataset, date_iso)
        return {"status": "no_data"}

    ts.write_partition(dataset, date_iso, records)
    log.info("%s: %d records ingested for %s", dataset, len(records), date_iso)
    return {"status": "ok", "records": len(records)}


def ingest_daily(date=None, client=None, export_parquet=True):
    """Fetches stock/broker/index summaries for a date and appends to the time-series store.

    Args:
        date:            Override date in YYYYMMDD format (for backfill/testing)
        client:          Optional IDXClient instance
        export_parquet:  If True, re-export consolidated Parquet files after ingestion

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

    # One-time migration from legacy monolithic JSON (no-op if already done)
    migrated = ts.migrate_all()
    if any(m["migrated_dates"] for m in migrated.values()):
        results["legacy_migration"] = {k: m["migrated_dates"] for k, m in migrated.items()}

    datasets = [
        ("stock_summary", "/TradingSummary/GetStockSummary"),
        ("broker_summary", "/TradingSummary/GetBrokerSummary"),
        ("index_summary", "/TradingSummary/GetIndexSummary"),
    ]
    for dataset, endpoint in datasets:
        try:
            results[dataset] = _ingest_dataset(client, dataset, endpoint, date, date_iso)
        except Exception as exc:
            log.error("%s ingestion failed: %s", dataset, exc)
            results[dataset] = {"status": "error", "message": str(exc)}

    # Refresh dynamic USD/IDR exchange rate
    try:
        from idx.core.currency import get_usd_idr_rate

        rate = get_usd_idr_rate(force_refresh=True)
        results["usd_idr_rate"] = rate
        log.info("Refreshed USD/IDR exchange rate: %.2f", rate)
    except Exception as exc:
        log.warning("USD/IDR rate refresh skipped: %s", exc)

    # ── Consolidated Parquet Export ────────────────────────────────────────
    if export_parquet:
        try:
            from idx.pipelines.parquet import export_all

            results["parquet_export"] = export_all()
            log.info("Parquet export complete")
        except Exception as exc:
            log.error("Parquet export failed: %s", exc)
            results["parquet_export"] = {"status": "error", "message": str(exc)}

    log.info("=" * 60)
    log.info(
        "Daily ingestion complete: %s",
        {k: (v.get("status", "?") if isinstance(v, dict) else "ok") for k, v in results.items()},
    )
    log.info("=" * 60)

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Accept optional date argument: python -m idx.pipelines.daily 20260807
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    ingest_daily(date=date_arg)
