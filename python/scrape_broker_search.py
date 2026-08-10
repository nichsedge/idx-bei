"""Scrapes Exchange Members & Broker Search directory from IDX API."""

from idx.scrapers.members import fetch_broker_search

if __name__ == "__main__":
    fetch_broker_search()