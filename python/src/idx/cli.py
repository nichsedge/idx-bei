"""
Unified Command-Line Interface (CLI) for IDX Scrapers, Pipelines, and Analysis.

Entry point for `idx` executable and `python cli.py`.
"""

import argparse
import logging
import os
import subprocess
import sys

import pandas as pd

from idx.core.query import available_datasets, query_dataset
from idx.core.utils import DATA_DIR
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
from idx.signals import build_briefing

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

SNAPSHOT_SCRAPERS = {
    "financial": (
        "Scrape financial ratios and fundamental statistics",
        lambda: fetch_financial_ratios(),
    ),
    "corporate": (
        "Scrape corporate actions across all 15 types",
        lambda: fetch_corporate_actions(),
    ),
    "brokers": ("Scrape exchange members & broker search directory", lambda: fetch_broker_search()),
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="idx",
        description="IDX BEI Toolkit - Unified CLI for scrapers and analysis pipelines",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # 1. Company
    p_company = sub.add_parser("company", help="Scrape listed company profiles & details")
    p_company.add_argument(
        "--all-details",
        action="store_true",
        help="Backfill full company profiles, boards, and shareholders for all tickers",
    )
    p_company.add_argument(
        "--reset",
        action="store_true",
        help="Reset existing details before scraping",
    )
    p_company.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap on number of companies to fetch details for",
    )

    # 2. Snapshot scrapers
    for name, (help_text, _) in SNAPSHOT_SCRAPERS.items():
        sub.add_parser(name, help=help_text)

    sub.add_parser("trading", help="Scrape stock summary (OHLCV), index summary & broker flow")
    sub.add_parser("news", help="Scrape market news & headlines")
    sub.add_parser("announcements", help="Scrape company announcements & PDF filings")

    # 3. Backfill
    p_backfill = sub.add_parser("backfill", help="Historical OHLCV backfill over a date range")
    p_backfill.add_argument("--start", required=True, metavar="YYYYMMDD", help="Start date")
    p_backfill.add_argument("--end", required=True, metavar="YYYYMMDD", help="End date")
    p_backfill.add_argument(
        "--type",
        choices=["stock", "broker", "index", "all"],
        default="all",
        help="Which summaries to backfill (default: all)",
    )

    # 4. Parquet & Query
    sub.add_parser("parquet", help="Export all datasets to Parquet format")

    p_query = sub.add_parser("query", help="SQL query over partitioned time-series (DuckDB)")
    p_query.add_argument(
        "dataset",
        help=f"Dataset to query ({', '.join(available_datasets()) or 'stock_summary|broker_summary|index_summary'})",
    )
    p_query.add_argument("--start", default=None, metavar="YYYY-MM-DD", help="Inclusive start date")
    p_query.add_argument("--end", default=None, metavar="YYYY-MM-DD", help="Inclusive end date")
    p_query.add_argument("--where", default=None, help="SQL predicate, e.g. \"StockCode = 'BBCA'\"")
    p_query.add_argument("--columns", default="*", help="Column list (default: *)")
    p_query.add_argument("--limit", type=int, default=20, help="Max rows to display (default: 20)")

    # 5. Daily
    p_daily = sub.add_parser("daily", help="Run daily ingestion (today or specific YYYYMMDD)")
    p_daily.add_argument(
        "date", nargs="?", default=None, metavar="YYYYMMDD", help="Optional date override"
    )

    # 6. Signals
    p_signals = sub.add_parser(
        "signals", help="Build daily decision-support briefing from Parquet exports"
    )
    p_signals.add_argument("--date", default=None, metavar="YYYY-MM-DD", help="Label date")
    p_signals.add_argument(
        "--window", type=int, default=None, help="Foreign-flow window in sessions"
    )
    p_signals.add_argument(
        "--min-turnover",
        type=float,
        default=None,
        help="Min avg daily value in Rp (default 1e9)",
    )
    p_signals.add_argument(
        "--min-pct-float", type=float, default=None, help="Min |NFF| %% of float (default 0.5)"
    )
    p_signals.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Dilution-watch lookback in days (default 90)",
    )
    p_signals.add_argument(
        "--outdir", default=None, help="Briefing output directory (default data/briefings)"
    )
    p_signals.add_argument(
        "--webhook-url",
        default=None,
        help="Webhook URL to broadcast briefing summary (Discord/Slack/Telegram)",
    )

    # 7. MCP Server
    sub.add_parser("mcp", help="Start the Model Context Protocol (MCP) stdio server")

    # 8. Dashboard
    p_dash = sub.add_parser("dashboard", help="Start visual Smart Money Dashboard HTTP server")
    p_dash.add_argument("--port", type=int, default=8080, help="Port to bind (default 8080)")

    sub.add_parser("all", help="Run all snapshot scrapers sequentially")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    cmd = args.command

    if cmd == "mcp":
        from idx.mcp.server import run_mcp_server

        run_mcp_server()
    elif cmd == "dashboard":
        root_dir = os.path.abspath(os.path.join(DATA_DIR, ".."))
        print(f"=== Starting Smart Money Dashboard on http://localhost:{args.port}/dashboard/ ===")
        print(f"Serving from {root_dir} (Press Ctrl+C to stop)...")
        subprocess.run([sys.executable, "-m", "http.server", str(args.port), "--directory", root_dir])
    elif cmd == "company":
        print("--- Company Profiles Scraping ---")
        fetch_company_profiles()
        if getattr(args, "all_details", False):
            from idx.scrapers.company import fetch_all_company_details

            print("--- Backfilling Full Company Details ---")
            fetch_all_company_details(limit=args.limit, reset=getattr(args, "reset", False))
    elif cmd in SNAPSHOT_SCRAPERS:
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
    elif cmd == "signals":
        print("=== Building Daily Signal Briefing ===")
        result = build_briefing(
            date=args.date,
            out_dir=args.outdir,
            window_days=args.window,
            min_turnover_rp=args.min_turnover,
            min_abs_pct_float=args.min_pct_float,
            dilution_lookback_days=args.lookback_days,
            webhook_url=args.webhook_url,
        )
        print(f"  Trading date : {result['trade_date']}")
        print(f"  Radar hits   : {result['radar_rows']}  (top 10 in briefing)")
        print(f"  Risk flags   : {result['shield_rows']}")
        print(f"  Dilution     : {result['dilution_rows']}")
        print(f"  Sharia value : {result['sharia_rows']}  (top 15 in briefing)")
        print(f"  Pasar Nego   : {result.get('nego_rows', 0)}  (top 10 in briefing)")
        print(f"  Markdown → {result['markdown']}")
        print(f"  JSON     → {result['json']}")

    elif cmd == "parquet":
        print("=== Exporting All Datasets to Parquet ===")
        results = export_all_parquet()
        for name, info in results.items():
            if isinstance(info, dict) and "rows" in info:
                print(f"  {name}: {info['rows']} rows → {info.get('size_mb', '?')} MB")
            else:
                print(f"  {name}: {info}")
    elif cmd == "query":
        df = query_dataset(
            args.dataset,
            start=args.start,
            end=args.end,
            where=args.where,
            columns=args.columns,
            limit=args.limit,
        )
        print(f"{len(df)} rows (limit {args.limit})")
        if len(df) > 0:
            with pd.option_context("display.max_columns", None, "display.width", 200):
                print(df.to_string(index=False))
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
