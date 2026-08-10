"""
Scrapes Financial Ratios and fundamental indicators from IDX API.
"""

from idx.scrapers.financial import fetch_financial_ratios, BASE_URL, QUERY_PARAMS

def build_url(page_number):
    """Backward compatibility helper for unit tests."""
    from urllib.parse import urlencode
    params = {**QUERY_PARAMS, "pageNumber": page_number}
    return f"{BASE_URL}?{urlencode(params)}"

if __name__ == "__main__":
    fetch_financial_ratios()