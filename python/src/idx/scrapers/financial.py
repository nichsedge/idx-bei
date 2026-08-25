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


def build_url(page_number, year=2024, quarter=4, page_size=100):
    """Builds full URL with query parameters for financial ratio API."""
    from urllib.parse import urlencode

    params = {
        **QUERY_PARAMS,
        "periodQuarter": quarter,
        "periodYear": year,
        "pageSize": page_size,
        "pageNumber": page_number,
    }
    return f"{BASE_URL}?{urlencode(params)}"


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


def fetch_historical_financial_ratios(
    years=(2022, 2023, 2024),
    quarters=(4,),
    client=None,
    delay=1.0,
):
    """Fetches financial ratios across multiple historical periods and consolidates them.

    Args:
        years: sequence of years to scrape (e.g. [2022, 2023, 2024]).
        quarters: sequence of quarters (e.g. [1, 2, 3, 4] or [4] for annuals).
        client: optional IDXClient instance.
        delay: delay in seconds between period fetches.

    Returns:
        dict with totalRecords and list of combined records.
    """
    if client is None:
        client = IDXClient()

    all_historical = []
    for y in years:
        for q in quarters:
            log.info("--- Scraping Financial Ratios for %d-Q%d ---", y, q)
            res = fetch_financial_ratios(year=y, quarter=q, client=client)
            if res and res.get("data"):
                all_historical.extend(res["data"])
            time.sleep(delay)

    if all_historical:
        combined_result = {"totalRecords": len(all_historical), "data": all_historical}
        save_json(OUTPUT_FILE, combined_result)
        log.info("Historical financial ratios consolidated: %d total records.", len(all_historical))
        return combined_result

    return None
