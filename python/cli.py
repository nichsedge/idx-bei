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

import argparse
import logging

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

SNAPSHOT_SCRAPERS = {
    "company": ("Scrape all listed company profiles", lambda: fetch_company_profiles()),
    "financial": ("Scrape financial ratios and fundamental statistics", lambda: fetch_financial_ratios()),
    "corporate": ("Scrape corporate actions across all 15 types", lambda: fetch_corporate_actions()),
    "brokers": ("Scrape exchange members & broker search directory", lambda: fetch_broker_search()),
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="IDX BEI Toolkit - Unified CLI for scrapers and analysis pipelines",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Snapshot scrapers with no arguments
    for name, (help_text, _) in SNAPSHOT_SCRAPERS.items():
        sub.add_parser(name, help=help_text)

    sub.add_parser("trading", help="Scrape stock summary (OHLCV), index summary & broker flow")
    sub.add_parser("news", help="Scrape market news & headlines")
    sub.add_parser("announcements", help="Scrape company announcements & PDF filings")

    p_backfill = sub.add_parser("backfill", help="Historical OHLCV backfill over a date range")
    p_backfill.add_argument("--start", required=True, metavar="YYYYMMDD", help="Start date")
    p_backfill.add_argument("--end", required=True, metavar="YYYYMMDD", help="End date")
    p_backfill.add_argument("--type", choices=["stock", "broker", "index", "all"], default="all",
                            help="Which summaries to backfill (default: all)")

    sub.add_parser("parquet", help="Export all datasets to Parquet format")

    p_daily = sub.add_parser("daily", help="Run daily ingestion (today or specific YYYYMMDD)")
    p_daily.add_argument("date", nargs="?", default=None, metavar="YYYYMMDD",
                         help="Optional date override")

    sub.add_parser("all", help="Run all snapshot scrapers sequentially")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    cmd = args.command

    if cmd in SNAPSHOT_SCRAPERS:
        print(f"--- {cmd.capitalize()}: Scraping ---")
        SNAPSHOT_SCRAPERS[cmd][1]()
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
        print(f"=== Historical Backfill: {args.start} → {args.end} (type={args.type}) ===")
        if args.type in ("stock", "all"):
            backfill_stock_summary(args.start, args.end)
        if args.type in ("broker", "all"):
            backfill_broker_summary(args.start, args.end)
        if args.type in ("index", "all"):
            backfill_index_summary(args.start, args.end)
    elif cmd == "parquet":
        print("=== Exporting All Datasets to Parquet ===")
        results = export_all_parquet()
        for name, info in results.items():
            if isinstance(info, dict) and "rows" in info:
                print(f"  {name}: {info['rows']} rows → {info.get('size_mb', '?')} MB")
            else:
                print(f"  {name}: {info}")
    elif cmd == "daily":
        print(f"=== Daily Ingestion ({args.date or 'today'}) ===")
        ingest_daily(date=args.date)
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


if __name__ == "__main__":
    main()
