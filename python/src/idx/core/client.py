"""
IDX HTTP Client with exponential backoff, rate limiting, and browser impersonation.
"""

import asyncio
import json
import logging
import random
import time

from curl_cffi import requests

log = logging.getLogger("idx.core.client")


def _backoff_with_jitter(retries, base=2.0, linear=0.5, jitter_frac=0.25):
    """Exponential backoff with random jitter to avoid thundering-herd retries."""
    nominal = (base**retries) + (linear * retries)
    return nominal * (1.0 + random.uniform(0, jitter_frac))


DEFAULT_BASE_URL = "https://www.idx.co.id/primary"

DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.idx.co.id/",
}


class IDXRequestError(Exception):
    """Raised when a request ultimately fails (max retries exceeded or non-retryable HTTP error)."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


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
                log.debug(
                    "GET %s | params=%s (attempt %d/%d)",
                    url,
                    params,
                    retries + 1,
                    self.max_retries + 1,
                )
                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    impersonate=impersonate,
                    timeout=timeout,
                )

                status_code = response.status_code

                if status_code == 200:
                    time.sleep(self.delay_seconds)
                    return response

                elif status_code in (429, 500, 502, 503, 504):
                    backoff = _backoff_with_jitter(retries)
                    log.warning("HTTP %d for %s – retrying in %.1fs...", status_code, url, backoff)
                    time.sleep(backoff)
                    retries += 1
                else:
                    log.error("HTTP %d for %s – stopping retries.", status_code, url)
                    return response

            except Exception as exc:
                backoff = _backoff_with_jitter(retries, base=1.0)
                log.warning("Request error for %s: %s – retrying in %.1fs...", url, exc, backoff)
                time.sleep(backoff)
                retries += 1

        log.error("Max retries exceeded for %s", url)
        return None

    def get_json(self, endpoint, params=None, raise_on_error=False):
        """Executes a GET request and parses response JSON safely.

        Args:
            endpoint: API path or absolute URL
            params:   Query parameters
            raise_on_error: If True, raises IDXRequestError on HTTP failure or
                invalid JSON instead of returning None. Useful for callers that
                need to distinguish "not found" from "decode failure".

        Returns:
            Parsed JSON, or None on failure when raise_on_error is False.
        """
        response = self.get(endpoint, params=params)
        if response is None:
            message = f"Max retries exceeded for {endpoint}"
            if raise_on_error:
                raise IDXRequestError(message)
            return None
        if response.status_code != 200:
            message = f"HTTP {response.status_code} for {endpoint}"
            if raise_on_error:
                raise IDXRequestError(message, status_code=response.status_code)
            return None
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            message = f"Failed to decode JSON from {endpoint}: {exc}"
            if raise_on_error:
                raise IDXRequestError(message, status_code=200) from exc
            log.error("%s", message)
            return None


class AsyncIDXClient:
    """Asynchronous HTTP Client for IDX APIs using curl_cffi with concurrency throttling."""

    def __init__(
        self,
        base_url=DEFAULT_BASE_URL,
        headers=None,
        max_retries=3,
        delay_seconds=0.2,
        concurrency=5,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        self.concurrency = concurrency
        self._semaphore = None
        self._session = None

    async def __aenter__(self):
        self._session = requests.AsyncSession(headers=self.headers)
        self._semaphore = asyncio.Semaphore(self.concurrency)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
            self._session = None

    def _get_semaphore(self):
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.concurrency)
        return self._semaphore

    async def get(self, endpoint, params=None, impersonate="chrome", timeout=30):
        """Executes an async GET request with concurrency throttling and retry."""
        import asyncio

        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        sem = self._get_semaphore()

        async with sem:
            session = self._session
            should_close = False
            if session is None:
                session = requests.AsyncSession(headers=self.headers)
                should_close = True

            try:
                retries = 0
                while retries <= self.max_retries:
                    try:
                        log.debug(
                            "Async GET %s | params=%s (attempt %d/%d)",
                            url,
                            params,
                            retries + 1,
                            self.max_retries + 1,
                        )
                        response = await session.get(
                            url,
                            params=params,
                            headers=self.headers,
                            impersonate=impersonate,
                            timeout=timeout,
                        )

                        status_code = response.status_code

                        if status_code == 200:
                            if self.delay_seconds > 0:
                                await asyncio.sleep(self.delay_seconds)
                            return response

                        elif status_code in (429, 500, 502, 503, 504):
                            backoff = _backoff_with_jitter(retries)
                            log.warning(
                                "Async HTTP %d for %s – retrying in %.1fs...",
                                status_code,
                                url,
                                backoff,
                            )
                            await asyncio.sleep(backoff)
                            retries += 1
                        else:
                            log.error("Async HTTP %d for %s – stopping retries.", status_code, url)
                            return response

                    except Exception as exc:
                        backoff = _backoff_with_jitter(retries, base=1.0)
                        log.warning(
                            "Async request error for %s: %s – retrying in %.1fs...",
                            url,
                            exc,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        retries += 1

                log.error("Async max retries exceeded for %s", url)
                return None
            finally:
                if should_close:
                    await session.close()

    async def get_json(self, endpoint, params=None, raise_on_error=False):
        """Executes an async GET request and parses response JSON safely."""
        response = await self.get(endpoint, params=params)
        if response is None:
            message = f"Max retries exceeded for {endpoint}"
            if raise_on_error:
                raise IDXRequestError(message)
            return None
        if response.status_code != 200:
            message = f"HTTP {response.status_code} for {endpoint}"
            if raise_on_error:
                raise IDXRequestError(message, status_code=response.status_code)
            return None
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            message = f"Failed to decode JSON from {endpoint}: {exc}"
            if raise_on_error:
                raise IDXRequestError(message, status_code=200) from exc
            log.error("%s", message)
            return None
