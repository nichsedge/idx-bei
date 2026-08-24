"""
IDX HTTP Client with exponential backoff, rate limiting, and browser impersonation.
"""

import json
import logging
import time

from curl_cffi import requests

log = logging.getLogger("idx.core.client")

DEFAULT_BASE_URL = "https://www.idx.co.id/primary"

DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.idx.co.id/"
}

class IDXClient:
    """HTTP Client for IDX APIs with built-in retries, rate limiting, and browser impersonation."""

    def __init__(self, base_url=DEFAULT_BASE_URL, headers=None, max_retries=3, delay_seconds=1.0):
        self.base_url = base_url.rstrip("/")
        self.headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds

    def get(self, endpoint, params=None, impersonate="chrome", timeout=30):
        """Executes a GET request with automatic retry on 429/50x and rate limit delays."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"

        retries = 0
        while retries <= self.max_retries:
            try:
                log.debug("GET %s | params=%s (attempt %d/%d)", url, params, retries + 1, self.max_retries + 1)
                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    impersonate=impersonate,
                    timeout=timeout
                )

                status_code = response.status_code

                if status_code == 200:
                    time.sleep(self.delay_seconds)
                    return response

                elif status_code in (429, 500, 502, 503, 504):
                    backoff = (2 ** retries) + (0.5 * retries)
                    log.warning("HTTP %d for %s – retrying in %.1fs...", status_code, url, backoff)
                    time.sleep(backoff)
                    retries += 1
                else:
                    log.error("HTTP %d for %s – stopping retries.", status_code, url)
                    return response

            except Exception as exc:
                backoff = (2 ** retries) + 1.0
                log.warning("Request error for %s: %s – retrying in %.1fs...", url, exc, backoff)
                time.sleep(backoff)
                retries += 1

        log.error("Max retries exceeded for %s", url)
        return None

    def get_json(self, endpoint, params=None):
        """Executes a GET request and parses response JSON safely."""
        response = self.get(endpoint, params=params)
        if response and response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError as exc:
                log.error("Failed to decode JSON from %s: %s", endpoint, exc)
        return None
