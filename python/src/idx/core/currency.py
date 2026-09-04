"""
Dynamic USD/IDR Exchange Rate Engine with local caching and resilient fallbacks.

Provides current exchange rates for USD-denominated dividend conversions and financial ratios.
Caches rates in data/usd_idr_rate.json with configurable TTL (default 24 hours).
"""

import json
import os
import time
from typing import Any

from idx.core.utils import DATA_DIR, get_logger

log = get_logger("idx.core.currency")

CACHE_FILE = os.path.join(DATA_DIR, "usd_idr_rate.json")
DEFAULT_USD_IDR_RATE = 16200.0
DEFAULT_CACHE_TTL_SECONDS = 86400  # 24 hours


def _load_cached_rate() -> dict[str, Any] | None:
    """Loads rate from cache file if valid."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "rate" in data and "timestamp" in data:
                return data
    except Exception as exc:
        log.warning("Failed to read exchange rate cache: %s", exc)
    return None


def _save_cached_rate(rate: float, source: str) -> None:
    """Persists rate to local JSON cache."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        payload = {
            "rate": float(rate),
            "timestamp": time.time(),
            "source": source,
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as exc:
        log.warning("Failed to write exchange rate cache: %s", exc)


def fetch_live_usd_idr_rate() -> float | None:
    """Attempts to fetch live USD/IDR exchange rate from Yahoo Finance or public feeds."""
    # Attempt 1: Yahoo Finance via yfinance if available
    try:
        import yfinance as yf

        ticker = yf.Ticker("USDIDR=X")
        fast_info = getattr(ticker, "fast_info", None)
        if fast_info and getattr(fast_info, "last_price", None):
            price = float(fast_info.last_price)
            if 10000.0 <= price <= 30000.0:
                log.info("Fetched USD/IDR rate from Yahoo Finance fast_info: %.2f", price)
                return price

        hist = ticker.history(period="5d")
        if not hist.empty and "Close" in hist.columns:
            price = float(hist["Close"].iloc[-1])
            if 10000.0 <= price <= 30000.0:
                log.info("Fetched USD/IDR rate from Yahoo Finance history: %.2f", price)
                return price
    except Exception as exc:
        log.debug("Yahoo Finance rate fetch failed: %s", exc)

    # Attempt 2: Bank Indonesia or open exchange rate endpoint via urllib
    try:
        import urllib.request

        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            rates = data.get("rates", {})
            if "IDR" in rates:
                price = float(rates["IDR"])
                if 10000.0 <= price <= 30000.0:
                    log.info("Fetched USD/IDR rate from open exchange API: %.2f", price)
                    return price
    except Exception as exc:
        log.debug("Open exchange API fetch failed: %s", exc)

    return None


def get_usd_idr_rate(
    force_refresh: bool = False,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    default_rate: float = DEFAULT_USD_IDR_RATE,
) -> float:
    """Returns the current USD/IDR exchange rate.

    Checks cache first unless `force_refresh` is True or cache is older than `cache_ttl_seconds`.
    Falls back to cached rate or `default_rate` on network failure.
    """
    cached = _load_cached_rate()
    now = time.time()

    if not force_refresh and cached:
        age = now - cached.get("timestamp", 0)
        if age < cache_ttl_seconds:
            rate = float(cached.get("rate", default_rate))
            log.debug("Using cached USD/IDR rate: %.2f (age: %.1f hours)", rate, age / 3600.0)
            return rate

    # Fetch live
    live_rate = fetch_live_usd_idr_rate()
    if live_rate is not None:
        _save_cached_rate(live_rate, source="live_fetch")
        return live_rate

    # Fallback to stale cache if available
    if cached and "rate" in cached:
        stale_rate = float(cached["rate"])
        log.warning("Live rate fetch failed; using stale cached USD/IDR rate: %.2f", stale_rate)
        return stale_rate

    log.warning("No USD/IDR rate available; falling back to default %.2f", default_rate)
    return default_rate
