import os
import sys
from unittest.mock import MagicMock

# Mock curl_cffi before importing scrape_financial_ratio
sys.modules["curl_cffi"] = MagicMock()

# Add the parent directory to sys.path to import the module being tested
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from urllib.parse import parse_qs, urlparse

from scrape_financial_ratio import BASE_URL, QUERY_PARAMS, build_url


def test_build_url_page_one():
    """Test build_url with page_number=1"""
    url = build_url(1)

    # Check if BASE_URL is present
    assert url.startswith(BASE_URL)

    # Parse the URL to check query parameters
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query, keep_blank_values=True)

    # Check if all QUERY_PARAMS are present and correct
    for key, value in QUERY_PARAMS.items():
        assert query_params[key][0] == str(value)

    # Check if pageNumber is correctly set
    assert query_params['pageNumber'][0] == '1'

def test_build_url_different_page():
    """Test build_url with a different page_number"""
    page_num = 5
    url = build_url(page_num)

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query, keep_blank_values=True)

    assert query_params['pageNumber'][0] == str(page_num)
