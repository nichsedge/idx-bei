"""
Trading summary scraper module: Stock Summary (OHLCV), Broker Summary, Index Summary.
"""

import datetime
from idx.core.client import IDXClient
from idx.core.utils import (
    get_logger,
    validate_schema,
    check_schema_drift,
)

log = get_logger("idx.scrapers.trading")


def _get_default_date():
    return datetime.datetime.now().strftime("%Y%m%d")


def fetch_stock_summary(date=None, client=None, start=0, length=9999):
    """Fetches stock summary (OHLCV, Bid/Offer, Foreign Flow) for a given date (YYYYMMDD).

    Returns the raw API response dict or None on failure.
    """
    if client is None:
        client = IDXClient()
    if date is None:
        date = _get_default_date()

    endpoint = "/TradingSummary/GetStockSummary"
    params = {"date": date, "start": start, "length": length}

    log.info("Fetching stock summary for date=%s...", date)
    data = client.get_json(endpoint, params=params)

    if data:
        validate_schema(data, "stock_summary")
        check_schema_drift("stock_summary", data)
        return data
    return None


def fetch_broker_summary(date=None, client=None, start=0, length=9999):
    """Fetches broker transaction summary for a given date (YYYYMMDD).

    Returns the raw API response dict or None on failure.
    """
    if client is None:
        client = IDXClient()
    if date is None:
        date = _get_default_date()

    endpoint = "/TradingSummary/GetBrokerSummary"
    params = {"date": date, "start": start, "length": length}

    log.info("Fetching broker summary for date=%s...", date)
    data = client.get_json(endpoint, params=params)

    if data:
        validate_schema(data, "broker_summary")
        check_schema_drift("broker_summary", data)
        return data
    return None


def fetch_index_summary(date=None, client=None, start=0, length=9999):
    """Fetches index summary (IHSG, LQ45, Sectoral) for a given date (YYYYMMDD).

    Returns the raw API response dict or None on failure.
    """
    if client is None:
        client = IDXClient()
    if date is None:
        date = _get_default_date()

    endpoint = "/TradingSummary/GetIndexSummary"
    params = {"date": date, "start": start, "length": length}

    log.info("Fetching index summary for date=%s...", date)
    data = client.get_json(endpoint, params=params)

    if data:
        validate_schema(data, "index_summary")
        check_schema_drift("index_summary", data)
        return data
    return None
