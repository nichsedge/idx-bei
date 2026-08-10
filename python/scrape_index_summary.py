"""Scrapes Index Summary (IHSG, LQ45, Sectoral benchmarks) from IDX API."""

from idx.scrapers.trading import fetch_index_summary

if __name__ == "__main__":
    fetch_index_summary()
