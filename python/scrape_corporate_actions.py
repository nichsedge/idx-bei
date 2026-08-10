"""Scrapes Corporate Actions across all 15 categories from IDX API."""

from idx.scrapers.corporate import fetch_corporate_actions

if __name__ == "__main__":
    fetch_corporate_actions()
