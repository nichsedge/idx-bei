"""
News & Announcements scraper module.
"""

from idx.core.client import IDXClient
from idx.core.utils import (
    get_logger,
    validate_schema,
    check_schema_drift,
)

log = get_logger("idx.scrapers.news")

def fetch_news_search(page_number=1, page_size=100, locale="id-id", client=None):
    """Fetches news and market headlines."""
    if client is None:
        client = IDXClient()

    endpoint = "/NewsAnnouncement/GetNewsSearch"
    params = {"pageNumber": page_number, "pageSize": page_size, "locale": locale}

    log.info("Fetching news search page %d...", page_number)
    data = client.get_json(endpoint, params=params)

    if data:
        validate_schema(data, "news_search")
        check_schema_drift("news_search", data)
        return data
    return None

def fetch_all_announcements(keywords="", page_number=1, page_size=100, lang="id", client=None):
    """Fetches company disclosures and PDF filings."""
    if client is None:
        client = IDXClient()

    endpoint = "/NewsAnnouncement/GetAllAnnouncement"
    params = {
        "keywords": keywords,
        "pageNumber": page_number,
        "pageSize": page_size,
        "lang": lang
    }

    log.info("Fetching company announcements (keywords='%s', page=%d)...", keywords, page_number)
    data = client.get_json(endpoint, params=params)

    if data:
        validate_schema(data, "all_announcement")
        check_schema_drift("all_announcement", data)
        return data
    return None
