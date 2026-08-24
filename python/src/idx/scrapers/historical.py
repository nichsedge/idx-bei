"""
Historical data backfill scraper.

Fetches stock summaries, broker summaries, and index summaries over a date range,
building time-series datasets for quantitative analysis and backtesting.

Usage:
    from idx.scrapers.historical import backfill_stock_summary
    backfill_stock_summary("20260101", "20260807")
"""

import datetime
import json
import os

from idx.core.client import IDXClient
from idx.core.utils import DATA_DIR, ensure_data_dir, get_logger

log = get_logger("idx.scrapers.historical")

TIMESERIES_DIR = os.path.join(DATA_DIR, "timeseries")


def _parse_date(d):
    """Accepts 'YYYYMMDD' or 'YYYY-MM-DD' and returns a date object."""
    if isinstance(d, datetime.date):
        return d
    d = d.replace("-", "")
    return datetime.datetime.strptime(d, "%Y%m%d").date()


def _trading_days(start, end):
    """Generates weekday dates between start and end (inclusive).

    IDX trades Mon-Fri. National holidays are NOT filtered here — the API
    simply returns an empty data list for non-trading days, which we skip
    during persistence.
    """
    current = _parse_date(start)
    end_dt = _parse_date(end)
    while current <= end_dt:
        if current.weekday() < 5:  # Mon=0 .. Fri=4
            yield current
        current += datetime.timedelta(days=1)


def _load_existing_records(filepath):
    """Loads existing JSON array from a timeseries file, returns dict keyed by date string."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, encoding="utf-8") as f:
            records = json.load(f)
        if isinstance(records, list):
            index = {}
            for rec in records:
                key = rec.get("Date", "")[:10]  # 'YYYY-MM-DD'
                if key not in index:
                    index[key] = []
                index[key].append(rec)
            return index
        return {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_timeseries(filepath, date_index):
    """Flattens date_index back to a sorted list and saves."""
    ensure_data_dir()
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    all_records = []
    for date_key in sorted(date_index.keys()):
        all_records.extend(date_index[date_key])

    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2)
    os.replace(tmp, filepath)
    return len(all_records)


def backfill_stock_summary(start_date, end_date, client=None, save_every=5):
    """Fetches OHLCV + foreign flow for every trading day in [start_date, end_date].

    Data is appended to data/timeseries/stock_summary.json incrementally.
    Already-fetched dates are skipped automatically (idempotent).

    Args:
        start_date: 'YYYYMMDD' or 'YYYY-MM-DD'
        end_date:   'YYYYMMDD' or 'YYYY-MM-DD'
        client:     Optional IDXClient instance
        save_every: Persist to disk every N dates (safeguard against crashes)

    Returns:
        dict with 'dates_fetched', 'dates_skipped', 'total_records', 'file'
    """
    if client is None:
        client = IDXClient()

    filepath = os.path.join(TIMESERIES_DIR, "stock_summary.json")
    date_index = _load_existing_records(filepath)
    existing_dates = set(date_index.keys())

    dates = list(_trading_days(start_date, end_date))
    fetched = 0
    skipped = 0
    errors = 0

    log.info("Backfill stock summary: %d trading days (%s → %s), %d already cached",
             len(dates), dates[0] if dates else "?", dates[-1] if dates else "?",
             len(existing_dates))

    for i, dt in enumerate(dates):
        date_str = dt.strftime("%Y-%m-%d")
        date_api = dt.strftime("%Y%m%d")

        if date_str in existing_dates:
            skipped += 1
            continue

        endpoint = "/TradingSummary/GetStockSummary"
        params = {"date": date_api, "start": 0, "length": 9999}

        try:
            data = client.get_json(endpoint, params=params)
        except Exception as exc:
            log.warning("Error fetching %s: %s", date_api, exc)
            errors += 1
            continue

        if data and isinstance(data.get("data"), list) and len(data["data"]) > 0:
            records = data["data"]
            date_index[date_str] = records
            fetched += 1
            log.info("[%d/%d] %s: %d stocks", i + 1, len(dates), date_str, len(records))
        else:
            skipped += 1
            log.debug("[%d/%d] %s: no data (holiday?)", i + 1, len(dates), date_str)
            continue

        # Periodic save
        if fetched > 0 and fetched % save_every == 0:
            total = _save_timeseries(filepath, date_index)
            log.info("Checkpoint saved: %d total records across %d dates", total, len(date_index))

    # Final save
    total = _save_timeseries(filepath, date_index)
    log.info("Backfill complete: fetched=%d, skipped=%d, errors=%d, total_records=%d",
             fetched, skipped, errors, total)

    return {
        "dates_fetched": fetched,
        "dates_skipped": skipped,
        "errors": errors,
        "total_records": total,
        "file": filepath,
    }


def backfill_broker_summary(start_date, end_date, client=None, save_every=5):
    """Fetches broker transaction summaries for every trading day in [start_date, end_date].

    Data is appended to data/timeseries/broker_summary.json incrementally.
    """
    if client is None:
        client = IDXClient()

    filepath = os.path.join(TIMESERIES_DIR, "broker_summary.json")
    date_index = _load_existing_records(filepath)
    existing_dates = set(date_index.keys())

    dates = list(_trading_days(start_date, end_date))
    fetched = 0
    skipped = 0

    log.info("Backfill broker summary: %d trading days, %d cached",
             len(dates), len(existing_dates))

    for i, dt in enumerate(dates):
        date_str = dt.strftime("%Y-%m-%d")
        date_api = dt.strftime("%Y%m%d")

        if date_str in existing_dates:
            skipped += 1
            continue

        data = client.get_json("/TradingSummary/GetBrokerSummary",
                               params={"date": date_api, "start": 0, "length": 9999})

        if data and isinstance(data.get("data"), list) and len(data["data"]) > 0:
            date_index[date_str] = data["data"]
            fetched += 1
            log.info("[%d/%d] %s: %d brokers", i + 1, len(dates), date_str, len(data["data"]))
        else:
            skipped += 1
            continue

        if fetched > 0 and fetched % save_every == 0:
            _save_timeseries(filepath, date_index)

    total = _save_timeseries(filepath, date_index)
    log.info("Broker summary backfill done: fetched=%d, skipped=%d, total=%d",
             fetched, skipped, total)
    return {"dates_fetched": fetched, "dates_skipped": skipped, "total_records": total, "file": filepath}


def backfill_index_summary(start_date, end_date, client=None, save_every=5):
    """Fetches index summaries (IHSG, LQ45, sectoral) for every trading day."""
    if client is None:
        client = IDXClient()

    filepath = os.path.join(TIMESERIES_DIR, "index_summary.json")
    date_index = _load_existing_records(filepath)
    existing_dates = set(date_index.keys())

    dates = list(_trading_days(start_date, end_date))
    fetched = 0
    skipped = 0

    log.info("Backfill index summary: %d trading days, %d cached",
             len(dates), len(existing_dates))

    for i, dt in enumerate(dates):
        date_str = dt.strftime("%Y-%m-%d")
        date_api = dt.strftime("%Y%m%d")

        if date_str in existing_dates:
            skipped += 1
            continue

        data = client.get_json("/TradingSummary/GetIndexSummary",
                               params={"date": date_api, "start": 0, "length": 9999})

        if data and isinstance(data.get("data"), list) and len(data["data"]) > 0:
            date_index[date_str] = data["data"]
            fetched += 1
            log.info("[%d/%d] %s: %d indices", i + 1, len(dates), date_str, len(data["data"]))
        else:
            skipped += 1
            continue

        if fetched > 0 and fetched % save_every == 0:
            _save_timeseries(filepath, date_index)

    total = _save_timeseries(filepath, date_index)
    log.info("Index summary backfill done: fetched=%d, skipped=%d, total=%d",
             fetched, skipped, total)
    return {"dates_fetched": fetched, "dates_skipped": skipped, "total_records": total, "file": filepath}
