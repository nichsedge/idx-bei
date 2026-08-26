"""
Company profiles & company details scraper module.
"""

import os
import time

from idx.core.client import IDXClient
from idx.core.utils import (
    DATA_DIR,
    check_records_total_consistency,
    check_schema_drift,
    get_logger,
    load_json,
    save_json,
    validate_schema,
)

log = get_logger("idx.scrapers.company")

DETAILS_FILE = os.path.join(DATA_DIR, "companyDetailsByKodeEmiten.json")
ALL_COMPANIES_FILE = os.path.join(DATA_DIR, "allCompanies.json")


def fetch_company_profiles(client=None, start=0, length=9999):
    """Fetches full list of listed company profiles."""
    if client is None:
        client = IDXClient()

    endpoint = "/ListedCompany/GetCompanyProfiles"
    params = {"start": start, "length": length}

    log.info("Fetching company profiles list...")
    data = client.get_json(endpoint, params=params)

    if data:
        validate_schema(data, "company_profiles_list")
        check_schema_drift("company_profiles_list", data)
        check_records_total_consistency(data, label="company_profiles_list")
        return data
    return None


def fetch_company_detail(kode_emiten, client=None, language="id-id"):
    """Fetches details for a single company ticker."""
    if client is None:
        client = IDXClient()

    endpoint = "/ListedCompany/GetCompanyProfilesDetail"
    params = {"KodeEmiten": kode_emiten, "language": language}

    return client.get_json(endpoint, params=params)


def fetch_all_company_details(
    tickers=None,
    delay=0.1,
    client=None,
    limit=None,
    reset=False,
    output_path=DETAILS_FILE,
):
    """Iteratively fetches details for all listed companies and saves to JSON.

    Args:
        tickers: optional list of ticker strings. Defaults to all companies in allCompanies.json.
        delay: sleep seconds between requests.
        client: optional IDXClient instance.
        limit: optional cap on number of companies to fetch.
        reset: if True, resets existing saved details before scraping.
        output_path: path to save the consolidated JSON dictionary.

    Returns:
        dict of {ticker: company_detail_dict}.
    """
    if client is None:
        client = IDXClient(delay_seconds=0.1)

    if tickers is None:
        if os.path.exists(ALL_COMPANIES_FILE):
            all_comp = load_json(ALL_COMPANIES_FILE)
            if isinstance(all_comp, list):
                tickers = [c.get("KodeEmiten") for c in all_comp if c.get("KodeEmiten")]
            elif isinstance(all_comp, dict) and "data" in all_comp:
                tickers = [c.get("KodeEmiten") for c in all_comp["data"] if c.get("KodeEmiten")]
        else:
            profiles = fetch_company_profiles(client=client)
            if profiles and "data" in profiles:
                tickers = [c.get("KodeEmiten") for c in profiles["data"] if c.get("KodeEmiten")]

    if not tickers:
        log.warning("No tickers found to fetch company details.")
        return {}

    if limit:
        tickers = tickers[:limit]

    # Load existing details for resume/checkpointing unless reset=True
    if reset:
        log.info("Reset requested: starting fresh company details collection.")
        existing = {}
    else:
        existing = load_json(output_path) if os.path.exists(output_path) else {}
        if not isinstance(existing, dict):
            existing = {}

    log.info("Starting company details backfill for %d tickers...", len(tickers))
    count = 0

    try:
        for i, ticker in enumerate(tickers, start=1):
            if ticker in existing and existing[ticker].get("Profiles"):
                continue

            detail = fetch_company_detail(ticker, client=client)
            if detail and isinstance(detail, dict) and detail.get("Profiles"):
                existing[ticker] = detail
                count += 1
                log.info("[%d/%d] Fetched details for %s", i, len(tickers), ticker)
            else:
                log.warning("[%d/%d] Failed/empty details for %s", i, len(tickers), ticker)

            if count > 0 and count % 20 == 0:
                save_json(output_path, existing)

            time.sleep(delay)
    except KeyboardInterrupt:
        log.warning("Backfill interrupted by user. Saving current progress...")
    finally:
        save_json(output_path, existing)
        log.info("Company details saved: %d companies in %s", len(existing), output_path)

    return existing


async def async_fetch_company_detail(kode_emiten, client=None, language="id-id"):
    """Fetches details for a single company ticker asynchronously."""
    if client is None:
        from idx.core.client import AsyncIDXClient

        client = AsyncIDXClient()

    endpoint = "/ListedCompany/GetCompanyProfilesDetail"
    params = {"KodeEmiten": kode_emiten, "language": language}
    return await client.get_json(endpoint, params=params)


async def async_fetch_all_company_details(
    tickers=None,
    concurrency=5,
    client=None,
    limit=None,
    reset=False,
    output_path=DETAILS_FILE,
):
    """Fetches details for all listed companies concurrently and saves to JSON.

    Args:
        tickers: list of tickers, defaults to all companies in allCompanies.json.
        concurrency: number of concurrent requests.
        client: optional AsyncIDXClient instance.
        limit: optional cap on tickers.
        reset: if True, resets existing details.
        output_path: file path to save consolidated JSON.

    Returns:
        dict of {ticker: company_detail_dict}.
    """
    import asyncio

    from idx.core.client import AsyncIDXClient

    if tickers is None:
        if os.path.exists(ALL_COMPANIES_FILE):
            all_comp = load_json(ALL_COMPANIES_FILE)
            if isinstance(all_comp, list):
                tickers = [c.get("KodeEmiten") for c in all_comp if c.get("KodeEmiten")]
            elif isinstance(all_comp, dict) and "data" in all_comp:
                tickers = [c.get("KodeEmiten") for c in all_comp["data"] if c.get("KodeEmiten")]
        else:
            profiles = fetch_company_profiles()
            if profiles and "data" in profiles:
                tickers = [c.get("KodeEmiten") for c in profiles["data"] if c.get("KodeEmiten")]

    if not tickers:
        log.warning("No tickers found to fetch company details.")
        return {}

    if limit:
        tickers = tickers[:limit]

    if reset:
        existing = {}
    else:
        existing = load_json(output_path) if os.path.exists(output_path) else {}
        if not isinstance(existing, dict):
            existing = {}

    to_fetch = [t for t in tickers if not (t in existing and existing[t].get("Profiles"))]
    log.info(
        "Async backfill: %d total tickers (%d already cached, %d to fetch, concurrency=%d)",
        len(tickers),
        len(tickers) - len(to_fetch),
        len(to_fetch),
        concurrency,
    )

    if not to_fetch:
        return existing

    async_client = client or AsyncIDXClient(concurrency=concurrency)
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    saved_count = 0

    async def _worker(ticker, idx, total):
        nonlocal saved_count
        async with sem:
            detail = await async_fetch_company_detail(ticker, client=async_client)
            if detail and isinstance(detail, dict) and detail.get("Profiles"):
                async with lock:
                    existing[ticker] = detail
                    saved_count += 1
                    if saved_count % 25 == 0:
                        save_json(output_path, existing)
                log.info("[%d/%d] Fetched %s", idx, total, ticker)
            else:
                log.warning("[%d/%d] Failed/empty for %s", idx, total, ticker)

    tasks = [_worker(t, i + 1, len(to_fetch)) for i, t in enumerate(to_fetch)]
    try:
        await asyncio.gather(*tasks)
    finally:
        save_json(output_path, existing)
        log.info("Async backfill complete: %d companies in %s", len(existing), output_path)

    return existing
