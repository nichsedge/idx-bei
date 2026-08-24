"""
Historical data backfill scraper.

Fetches stock summaries, broker summaries, and index summaries over a date range,
building partitioned Parquet time-series datasets for quantitative analysis.

Usage:
    from idx.scrapers.historical import backfill_stock_summary
    backfill_stock_summary("20260101", "20260807")
"""

import datetime

from idx.core import timeseries as ts
from idx.core.client import IDXClient
from idx.core.utils import get_logger

log = get_logger("idx.scrapers.historical")


def _parse_date(d):
    """Accepts 'YYYYMMDD' or 'YYYY-MM-DD' and returns a date object."""
    if isinstance(d, datetime.date):
        return d
    d = d.replace("-", "")
    return datetime.datetime.strptime(d, "%Y%m%d").date()


def _trading_days(start, end):
    """Generates weekday dates between start and end (inclusive).

    IDX trades Mon-Fri. National holidays are NOT filtered here — the API
    simply returns an empty data list for non-trading days, which we skip.
    """
    current = _parse_date(start)
    end_dt = _parse_date(end)
    while current <= end_dt:
        if current.weekday() < 5:  # Mon=0 .. Fri=4
            yield current
        current += datetime.timedelta(days=1)


def backfill_stock_summary(start_date, end_date, client=None):
    """Fetches OHLCV + foreign flow for every trading day in [start_date, end_date].

    Data is written as one Parquet partition per date under
    data/timeseries/stock_summary/. Already-fetched dates are skipped (idempotent).

    Args:
        start_date: 'YYYYMMDD' or 'YYYY-MM-DD'
        end_date:   'YYYYMMDD' or 'YYYY-MM-DD'
        client:     Optional IDXClient instance

    Returns:
        dict with 'dates_fetched', 'dates_skipped', 'total_records'
    """
    return _backfill_dataset(
        "stock_summary", "/TradingSummary/GetStockSummary", start_date, end_date, client,
    )


def backfill_broker_summary(start_date, end_date, client=None):
    """Fetches broker transaction summaries for every trading day in [start_date, end_date]."""
    return _backfill_dataset(
        "broker_summary", "/TradingSummary/GetBrokerSummary", start_date, end_date, client,
    )


def backfill_index_summary(start_date, end_date, client=None):
    """Fetches index summaries (IHSG, LQ45, sectoral) for every trading day in range."""
    return _backfill_dataset(
        "index_summary", "/TradingSummary/GetIndexSummary", start_date, end_date, client,
    )


def _backfill_dataset(dataset, endpoint, start_date, end_date, client=None):
    """Generic backfill loop: fetch per trading day and write one partition per date.

    Each date is persisted immediately after fetching — a crash mid-backfill
    loses at most one day of work, and re-runs resume where they stopped.
    """
    if client is None:
        client = IDXClient()

    have = ts.existing_dates(dataset)
    dates = list(_trading_days(start_date, end_date))
    fetched = 0
    skipped = 0
    errors = 0
    total = 0

    log.info("Backfill %s: %d trading days (%s → %s), %d already cached",
             dataset, len(dates), dates[0] if dates else "?",
             dates[-1] if dates else "?", len(have))

    for i, dt in enumerate(dates):
        date_str = dt.strftime("%Y-%m-%d")
        date_api = dt.strftime("%Y%m%d")

        if date_str in have:
            skipped += 1
            continue

        try:
            data = client.get_json(endpoint, params={"date": date_api, "start": 0, "length": 9999})
        except Exception as exc:
            log.warning("Error fetching %s for %s: %s", dataset, date_api, exc)
            errors += 1
            continue

        records = data.get("data") if isinstance(data, dict) else None
        if isinstance(records, list) and len(records) > 0:
            ts.write_partition(dataset, date_str, records)
            fetched += 1
            total += len(records)
            log.info("[%d/%d] %s: %d records", i + 1, len(dates), date_str, len(records))
        else:
            skipped += 1
            log.debug("[%d/%d] %s: no data (holiday?)", i + 1, len(dates), date_str)

    log.info("Backfill %s done: fetched=%d, skipped=%d, errors=%d, total_records=%d",
             dataset, fetched, skipped, errors, total)
    return {
        "dataset": dataset,
        "dates_fetched": fetched,
        "dates_skipped": skipped,
        "errors": errors,
        "total_records": total,
    }
