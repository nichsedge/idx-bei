"""
Exchange Members & Broker Search scraper module.
"""

import os

from idx.core.client import IDXClient
from idx.core.utils import (
    DATA_DIR,
    check_count_anomaly,
    check_schema_drift,
    get_logger,
    save_json,
    validate_schema,
)

log = get_logger("idx.scrapers.members")

OUTPUT_FILE = os.path.join(DATA_DIR, "brokerSearch.json")

def fetch_broker_search(client=None, option=0, license_type="", start=0, length=9999):
    """Fetches exchange member broker search directory."""
    if client is None:
        client = IDXClient()

    endpoint = "/ExchangeMember/GetBrokerSearch"
    params = {"option": option, "license": license_type, "start": start, "length": length}

    log.info("Fetching exchange member broker directory...")
    data = client.get_json(endpoint, params=params)

    if data:
        validate_schema(data, "broker_search")
        check_schema_drift("broker_search", data)
        save_json(OUTPUT_FILE, data)
        check_count_anomaly("broker_search", len(data.get("data", [])))
        log.info("Broker directory saved: %d firms.", len(data.get("data", [])))
        return data

    return None
