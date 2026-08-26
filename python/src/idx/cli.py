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
    p_company.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Concurrent async request limit (default 5)",
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
    p_backfill.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Concurrent async request limit (default 5)",
    )

    # 4. Parquet & Query
    p_parquet = sub.add_parser("parquet", help="Export all datasets to Parquet format")
    p_parquet.add_argument(
        "--incremental",
        action="store_true",
        help="Incrementally append newer date partitions only",
    )

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

    # 6. Signals & Bandarmology
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

    p_bandar = sub.add_parser("bandarmology", help="Inspect Top-N broker concentration & flow")
    p_bandar.add_argument("--date", default=None, metavar="YYYY-MM-DD", help="Date filter")
    p_bandar.add_argument("--top", type=int, default=10, help="Top N brokers (default 10)")

    # 7. Backtest
    p_bt = sub.add_parser("backtest", help="Vectorized backtesting of quantitative screens")
    p_bt.add_argument(
        "--strategy",
        choices=["foreign_flow", "bandarmology", "sharia_value", "composite_alpha"],
        default="foreign_flow",
        help="Strategy to simulate (default: foreign_flow)",
    )
    p_bt.add_argument(
        "--holding", type=int, default=20, help="Holding period in sessions (default 20)"
    )
    p_bt.add_argument(
        "--top", type=int, default=10, help="Top N stocks picked per session (default 10)"
    )
    p_bt.add_argument("--stop-loss", type=float, default=None, help="Stop loss % e.g. 7.0 for -7%")
    p_bt.add_argument(
        "--take-profit", type=float, default=None, help="Take profit % e.g. 15.0 for +15%"
    )

    # 8. Knowledge Graph & UBO
    p_graph = sub.add_parser("graph", help="Neo4j UBO resolution & corporate network analysis")
    p_graph.add_argument("--ubo", metavar="TICKER", help="Resolve UBO hierarchy for ticker")
    p_graph.add_argument(
        "--centrality", action="store_true", help="Rank board members by network centrality"
    )
    p_graph.add_argument(
        "--cross-holdings", action="store_true", help="Detect circular cross-holding loops"
    )

    # 9. Shareholder Drift
    p_drift = sub.add_parser(
        "drift", help="Track KSEI monthly shareholder & tycoon position deltas"
    )
    p_drift.add_argument("--tycoon", metavar="NAME", help="Filter drift for specific tycoon")
    p_drift.add_argument("--latest", action="store_true", help="Show latest month-over-month drift")

    # 10. FastAPI Microservice
    p_serve = sub.add_parser("serve", help="Start high-performance FastAPI & WebSocket REST server")
    p_serve.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    p_serve.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")

    # 11. MCP Server
    sub.add_parser("mcp", help="Start the Model Context Protocol (MCP) stdio server")

    # 12. Dashboard
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
        subprocess.run(
            [sys.executable, "-m", "http.server", str(args.port), "--directory", root_dir]
        )
    elif cmd == "company":
        print("--- Company Profiles Scraping ---")
        fetch_company_profiles()
        if getattr(args, "all_details", False):
            import asyncio

            from idx.scrapers.company import async_fetch_all_company_details

            print(f"--- Backfilling Full Company Details (concurrency={args.concurrency}) ---")
            asyncio.run(
                async_fetch_all_company_details(
                    concurrency=args.concurrency,
                    limit=args.limit,
                    reset=getattr(args, "reset", False),
                )
            )
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
        print(
            f"=== Historical Backfill: {args.start} → {args.end} (type={args.type}, concurrency={args.concurrency}) ==="
        )
        import asyncio

        from idx.scrapers.historical import (
            async_backfill_broker_summary,
            async_backfill_index_summary,
            async_backfill_stock_summary,
        )

        async def _run_backfill():
            if args.type in ("stock", "all"):
                await async_backfill_stock_summary(
                    args.start, args.end, concurrency=args.concurrency
                )
            if args.type in ("broker", "all"):
                await async_backfill_broker_summary(
                    args.start, args.end, concurrency=args.concurrency
                )
            if args.type in ("index", "all"):
                await async_backfill_index_summary(
                    args.start, args.end, concurrency=args.concurrency
                )

        asyncio.run(_run_backfill())
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
        print(f"  Alpha ranks  : {result.get('alpha_rows', 0)}  (top 10 in briefing)")
        print(f"  Radar hits   : {result['radar_rows']}  (top 10 in briefing)")
        print(f"  Top brokers  : {result.get('broker_rows', 0)}")
        print(f"  Risk flags   : {result['shield_rows']}")
        print(f"  Dilution     : {result['dilution_rows']}")
        print(f"  Sharia value : {result['sharia_rows']}  (top 15 in briefing)")
        print(f"  Pasar Nego   : {result.get('nego_rows', 0)}  (top 10 in briefing)")
        print(f"  Markdown → {result['markdown']}")
        print(f"  JSON     → {result['json']}")

    elif cmd == "bandarmology":
        print(f"=== Bandarmology & Broker Flow ({args.date or 'Latest'}) ===")
        from idx.core.timeseries import read_dataset
        from idx.signals import broker_concentration_screen

        df_b = read_dataset("broker_summary")
        summary, top_df = broker_concentration_screen(df_b, on_date=args.date, top_k=args.top)
        print(f"Total Market Turnover: Rp{summary.get('total_market_turnover_rp_b', '-')}B")
        print(
            f"Concentration Ratios : CR1={summary.get('cr1_pct', '-')}%, CR3={summary.get('cr3_pct', '-')}%, CR5={summary.get('cr5_pct', '-')}%"
        )
        print(
            f"Inst vs Retail Share : Inst={summary.get('institutional_share_pct', '-')}% vs Retail={summary.get('retail_share_pct', '-')}% (Ratio: {summary.get('institutional_to_retail_ratio', '-')})"
        )
        print("\nTop Brokers:")
        with pd.option_context("display.max_columns", None, "display.width", 150):
            print(top_df.to_string(index=False))

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
    elif cmd == "backtest":
        from idx.backtest import run_backtest

        print(
            f"=== Running Strategy Backtest: {args.strategy} (holding={args.holding}d, top={args.top}) ==="
        )
        metrics, trades_df = run_backtest(
            strategy=args.strategy,
            holding_days=args.holding,
            top_n=args.top,
            stop_loss_pct=args.stop_loss,
            take_profit_pct=args.take_profit,
        )
        print(f"  Total Return : {metrics.get('total_return_pct', 0.0)}%")
        print(f"  Sharpe Ratio : {metrics.get('sharpe_ratio', 0.0)}")
        print(f"  Sortino Ratio: {metrics.get('sortino_ratio', 0.0)}")
        print(f"  Max Drawdown : {metrics.get('max_drawdown_pct', 0.0)}%")
        print(
            f"  Win Rate     : {metrics.get('win_rate_pct', 0.0)}% ({metrics.get('total_trades', 0)} trades)"
        )
        print(f"  Profit Factor: {metrics.get('profit_factor', 0.0)}")
        print(f"  Avg Trade Ret: {metrics.get('avg_trade_return_pct', 0.0)}%")
        if len(trades_df) > 0:
            print("\nRecent Completed Trades:")
            with pd.option_context("display.max_columns", None, "display.width", 150):
                print(trades_df.tail(10).to_string(index=False))

    elif cmd == "graph":
        from idx.graph import calculate_board_centrality, detect_cross_holdings, get_ubo_tree

        if args.ubo:
            print(f"=== UBO Hierarchy: {args.ubo.upper()} ===")
            tree = get_ubo_tree(args.ubo)
            import json

            print(json.dumps(tree, indent=2))
        elif args.centrality:
            print("=== Board Network Centrality (Top Powerbrokers) ===")
            df_c = calculate_board_centrality(top_n=15)
            with pd.option_context("display.max_columns", None, "display.width", 150):
                print(df_c.to_string(index=False))
        elif args.cross_holdings:
            print("=== Circular Cross-Holding Loops ===")
            loops = detect_cross_holdings()
            import json

            print(json.dumps(loops, indent=2))
        else:
            print("Specify --ubo <TICKER>, --centrality, or --cross-holdings.")

    elif cmd == "drift":
        from idx.core.ownership import (
            get_latest_shareholder_drift,
        )

        print("=== KSEI Shareholder Drift & Position Changes ===")
        res = get_latest_shareholder_drift()
        if res.get("status") == "ok":
            print(f"Comparing: {res.get('prev_file')} → {res.get('curr_file')}")
            print(f"  Accumulations : {res.get('accumulations')}")
            print(f"  Distributions : {res.get('distributions')}")
            print(f"  New Positions : {res.get('new_entries')}")
            print(f"  Full Exits    : {res.get('exits')}")

            if args.tycoon:
                t_df = pd.DataFrame(res.get("tycoon_drift", []))
                if len(t_df) > 0:
                    t_df = t_df[t_df["InvestorName"].str.contains(args.tycoon.upper(), na=False)]
                print(f"\nDrift for '{args.tycoon}':")
                with pd.option_context("display.max_columns", None, "display.width", 150):
                    print(t_df.to_string(index=False) if len(t_df) > 0 else "No position changes.")
            else:
                top_df = pd.DataFrame(res.get("top_deltas", []))
                print("\nTop Significant Position Changes:")
                with pd.option_context("display.max_columns", None, "display.width", 150):
                    print(top_df.to_string(index=False))
        else:
            print(
                f"Status: {res.get('status')}. Provide at least 2 KSEI ownership snapshots in data directory."
            )

    elif cmd == "serve":
        from idx.api import run_server

        print(f"=== Starting IDX-BEI FastAPI Microservice on http://{args.host}:{args.port} ===")
        print(f"Interactive OpenAPI Swagger Docs: http://{args.host}:{args.port}/docs")
        run_server(host=args.host, port=args.port)

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
