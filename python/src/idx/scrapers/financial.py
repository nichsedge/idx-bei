"""
Financial ratios and statistics scraper module.
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

log = get_logger("idx.scrapers.financial")

BASE_URL = "https://www.idx.co.id/primary/DigitalStatistic/GetApiDataPaginated"

QUERY_PARAMS = {
    "urlName": "LINK_FINANCIAL_DATA_RATIO",
    "periodQuarter": 4,
    "periodYear": 2024,
    "type": "yearly",
    "isPrint": "false",
    "cumulative": "false",
    "pageSize": 100,
    "orderBy": "",
    "search": "",
}

OUTPUT_FILE = os.path.join(DATA_DIR, "financial_ratio.json")


def fetch_financial_ratios(year=2024, quarter=4, client=None, page_size=100):
    """Fetches paginated financial data and ratios across all companies."""
    if client is None:
        client = IDXClient()

    endpoint = "/DigitalStatistic/GetApiDataPaginated"
    base_params = {
        **QUERY_PARAMS,
        "periodQuarter": quarter,
        "periodYear": year,
        "pageSize": page_size,
    }

    all_records = []
    page_number = 1
    has_more = True

    log.info("Fetching financial ratios for year %d quarter %d...", year, quarter)

    while has_more:
        params = {**base_params, "pageNumber": page_number}
        data = client.get_json(endpoint, params=params)

        if data and data.get("data") and len(data["data"]) > 0:
            records = data["data"]
            all_records.extend(records)
            log.info(
                "Retrieved %d records from page %d. Total: %d",
                len(records),
                page_number,
                len(all_records),
            )

            if page_number == 1:
                validate_schema(data, "financial_ratio_page")
                check_schema_drift("financial_ratio_page", data)

            page_number += 1
            time.sleep(1.0)
        else:
            has_more = False

    if all_records:
        result = {"totalRecords": len(all_records), "data": all_records}
        save_json(OUTPUT_FILE, result)
        check_count_anomaly("financial_ratio", len(all_records))
        log.info("Financial ratios collection finished: %d records.", len(all_records))
        return result

    log.warning("No financial ratio records collected.")
    return None
