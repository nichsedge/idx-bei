"""
Unified Command-Line Interface (CLI) for IDX Scrapers and Analysis Pipelines.

Usage:
  uv run python cli.py company
  uv run python cli.py financial
  uv run python cli.py corporate
  uv run python cli.py brokers
  uv run python cli.py trading
  uv run python cli.py news
  uv run python cli.py announcements
  uv run python cli.py backfill --start 20260101 --end 20260807
  uv run python cli.py parquet
  uv run python cli.py daily [YYYYMMDD]
  uv run python cli.py all
"""

import logging
import sys

from idx.pipelines.daily import ingest_daily
from idx.pipelines.parquet import export_all as export_all_parquet
from idx.scrapers.company import fetch_company_profiles
from idx.scrapers.corporate import fetch_corporate_actions
from idx.scrapers.financial import fetch_financial_ratios
from idx.scrapers.historical import (
    backfill_broker_summary,
    backfill_index_summary,
    backfill_stock_summary,
)
from idx.scrapers.members import fetch_broker_search
from idx.scrapers.news import fetch_all_announcements, fetch_news_search
from idx.scrapers.trading import fetch_broker_summary, fetch_index_summary, fetch_stock_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def print_help():
    print("""
IDX BEI Toolkit - Unified CLI

Scrapers:
  company        Scrape all listed company profiles
  financial      Scrape financial ratios and fundamental statistics
  corporate      Scrape corporate actions across all 15 types
  brokers        Scrape exchange members & broker search directory
  trading        Scrape stock summary (OHLCV), index summary & broker flow
  news           Scrape market news & headlines
  announcements  Scrape company announcements & PDF filings

Historical & Pipelines:
  backfill       Historical OHLCV backfill over a date range
                   --start YYYYMMDD  --end YYYYMMDD  [--type stock|broker|index|all]
  parquet        Export all datasets to Parquet format
  daily          Run daily ingestion (today or specific YYYYMMDD)

Meta:
  all            Run all snapshot scrapers sequentially
""")

def main():
    if len(sys.argv) < 2:
        print_help()
        return

    cmd = sys.argv[1].lower()

    if cmd == "company":
        print("--- Scraping Company Profiles ---")
        fetch_company_profiles()
    elif cmd == "financial":
        print("--- Scraping Financial Ratios ---")
        fetch_financial_ratios()
    elif cmd == "corporate":
        print("--- Scraping Corporate Actions ---")
        fetch_corporate_actions()
    elif cmd == "brokers":
        print("--- Scraping Broker Search Directory ---")
        fetch_broker_search()
    elif cmd == "trading":
        print("--- Scraping Trading Summaries ---")
        fetch_stock_summary()
        fetch_broker_summary()
        fetch_index_summary()
    elif cmd == "news":
        print("--- Scraping News Search ---")
        fetch_news_search()
    elif cmd == "announcements":
        print("--- Scraping Company Announcements ---")
        fetch_all_announcements()
    elif cmd == "backfill":
        start_date = None
        end_date = None
        backfill_type = "all"
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--start" and i + 1 < len(sys.argv):
                start_date = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--end" and i + 1 < len(sys.argv):
                end_date = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--type" and i + 1 < len(sys.argv):
                backfill_type = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        if not start_date or not end_date:
            print("Error: --start and --end are required for backfill")
            print("  Usage: cli.py backfill --start 20260101 --end 20260807")
            return

        print(f"=== Historical Backfill: {start_date} → {end_date} (type={backfill_type}) ===")
        if backfill_type in ("stock", "all"):
            backfill_stock_summary(start_date, end_date)
        if backfill_type in ("broker", "all"):
            backfill_broker_summary(start_date, end_date)
        if backfill_type in ("index", "all"):
            backfill_index_summary(start_date, end_date)
    elif cmd == "parquet":
        print("=== Exporting All Datasets to Parquet ===")
        results = export_all_parquet()
        for name, info in results.items():
            if isinstance(info, dict) and "rows" in info:
                print(f"  {name}: {info['rows']} rows → {info.get('size_mb', '?')} MB")
            else:
                print(f"  {name}: {info}")
    elif cmd == "daily":
        date_arg = sys.argv[2] if len(sys.argv) > 2 else None
        print(f"=== Daily Ingestion ({date_arg or 'today'}) ===")
        ingest_daily(date=date_arg)
    elif cmd == "all":
        print("=== Running All Snapshot Scrapers ===")
        fetch_company_profiles()
        fetch_financial_ratios()
        fetch_corporate_actions()
        fetch_broker_search()
        fetch_stock_summary()
        fetch_broker_summary()
        fetch_index_summary()
        fetch_news_search()
        fetch_all_announcements()
    else:
        print(f"Unknown command: '{cmd}'")
        print_help()

if __name__ == "__main__":
    main()
