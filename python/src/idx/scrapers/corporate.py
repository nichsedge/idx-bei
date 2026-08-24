"""
Corporate Actions scraper module covering all 15 corporate action types.
"""

import os
import time

from idx.core.client import IDXClient
from idx.core.utils import (
    DATA_DIR,
    check_count_anomaly,
    check_schema_drift,
    get_logger,
    save_json,
    validate_schema,
)

log = get_logger("idx.scrapers.corporate")

OUTPUT_FILE = os.path.join(DATA_DIR, "corporateActions.json")

CA_TYPES = [
    "tanpaHmetd",
    "hmetd",
    "stockSplit",
    "reverseStock",
    "sahamBonus",
    "dividenSaham",
    "BuybackSaham",
    "PrivatePlacement",
    "ipo",
    "waran",
    "gabungUsaha",
    "kurangModal",
    "konversiSaham",
    "companyListing",
    "partialDelisting"
]

def fetch_corporate_actions(ca_types=None, client=None):
    """Fetches corporate action records for all or specified ca_types."""
    if client is None:
        client = IDXClient()
    if ca_types is None:
        ca_types = CA_TYPES

    endpoint = "/ListingActivity/GetIssuedHistory"
    all_ca_data = {}
    total_records = 0

    log.info("Fetching corporate actions for %d categories...", len(ca_types))

    for ca_type in ca_types:
        params = {
            "caType": ca_type,
            "dateFrom": "",
            "dateTo": "",
            "start": 0,
            "length": 9999
        }
        data = client.get_json(endpoint, params=params)

        if data and isinstance(data.get("data"), list):
            records = data["data"]
            all_ca_data[ca_type] = {"count": len(records), "data": records}
            total_records += len(records)
            log.info("caType='%s': %d records", ca_type, len(records))

            validate_schema(data, "corporate_action")
            check_schema_drift(f"corporate_action_{ca_type}", data)
        else:
            all_ca_data[ca_type] = {"count": 0, "data": []}

        time.sleep(0.5)

    combined = {"totalRecordsAllTypes": total_records, "categories": all_ca_data}
    save_json(OUTPUT_FILE, combined)
    check_count_anomaly("corporate_actions_total", total_records)
    log.info("Corporate actions finished: %d total records.", total_records)
    return combined
