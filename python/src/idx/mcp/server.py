"""
Model Context Protocol (MCP) Server for the IDX-BEI Data Pipeline.

Provides tools for AI assistants (Antigravity, Claude, Cursor, etc.) to query:
- Daily decision-support briefings & signals
- OHLCV & time-series data via DuckDB
- Company profiles, directors, shareholders & dividends
- Super-insider / tycoon ownership holdings
- Sharia & fundamental screens
"""

import json
import os
import sys

import pandas as pd

from idx.core.ownership import get_tycoon_holdings, load_ownership_csv
from idx.core.query import query_dataset
from idx.core.utils import DATA_DIR, get_logger, load_json
from idx.signals import build_briefing, sharia_value_screen

log = get_logger("idx.mcp.server")

TOOLS = [
    {
        "name": "idx_get_signals",
        "description": "Fetch the latest IDX daily signal briefing (Foreign Flow Radar, Audit Risk Shield, Dilution Watch, Sharia Value Screen, and Pasar Nego Crossings).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Optional trading date filter (YYYY-MM-DD). Defaults to latest.",
                },
                "window_days": {
                    "type": "integer",
                    "description": "Foreign flow aggregation window in sessions (default 20).",
                },
            },
        },
    },
    {
        "name": "idx_query_stock",
        "description": "Query recent daily OHLCV, VWAP, Net Foreign Flow, and Negotiated Block volume for a specific stock ticker.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "4-letter IDX stock code, e.g. 'BBCA', 'TINS', 'AADI'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of recent sessions to return (default 20).",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "idx_get_company_profile",
        "description": "Retrieve comprehensive company profile including Board of Directors, Commissioners, Major Shareholders (>5%), Subsidiaries, and Dividend history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "4-letter IDX stock code, e.g. 'AADI', 'BBCA'.",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "idx_screen_sharia_value",
        "description": "Screen for high-quality, undervalued Sharia-compliant Indonesian stocks with low leverage and clean audit opinions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_per": {
                    "type": "number",
                    "description": "Maximum Price-to-Earnings Ratio (default 12.0).",
                },
                "min_roe": {
                    "type": "number",
                    "description": "Minimum Return on Equity percentage (default 12.0).",
                },
                "max_der": {
                    "type": "number",
                    "description": "Maximum Debt-to-Equity Ratio (default 2.0).",
                },
            },
        },
    },
    {
        "name": "idx_get_super_insiders",
        "description": "Query holdings of notable Indonesian tycoons and super-investors (e.g. Lo Kheng Hong, Prajogo Pangestu, Garibaldi Thohir, Salim Group).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tycoon_query": {
                    "type": "string",
                    "description": "Optional search term for tycoon name (e.g. 'LO KHENG HONG' or 'PRAJOGO').",
                },
            },
        },
    },
    {
        "name": "idx_query_broker_flow",
        "description": "Query broker market share, top buyer/seller concentration ratios (CR1, CR3, CR5), and institutional vs retail footprint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Optional date filter (YYYY-MM-DD). Defaults to latest session.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of top brokers to return (default 10).",
                },
            },
        },
    },
    {
        "name": "idx_get_technical_signals",
        "description": "Compute technical indicators (RSI-14, EMA 20/50/200, Bollinger Bands, ATR-14, Volume Spikes, Trend Regime) for a specific stock.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "4-letter IDX stock code, e.g. 'BBCA', 'ASII', 'TLKM'.",
                },
                "rsi_period": {
                    "type": "integer",
                    "description": "RSI period (default 14).",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "idx_compare_peers",
        "description": "Compare valuation metrics (PER, PBV, ROE, DER, Market Cap) for a ticker against all peers in the same industry sector.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "4-letter IDX stock code, e.g. 'BBRI', 'ICBP', 'ADRO'.",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "idx_search_announcements",
        "description": "Search corporate disclosures, RUPS notices, dividend distributions, and public filings with direct IDX PDF links.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword, e.g. 'dividen', 'RUPS', 'akuisisi', 'laporan keuangan'.",
                },
                "ticker": {
                    "type": "string",
                    "description": "Optional 4-letter stock code filter.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of disclosures to return (default 15).",
                },
            },
        },
    },
    {
        "name": "idx_execute_sql",
        "description": "Execute a safe read-only SQL query over the IDX Parquet datasets (stock_summary, financial_ratios, corporate_actions, broker_summary, index_summary) using DuckDB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL SELECT query string to execute. Example: SELECT StockCode, AVG(Close) FROM 'data/parquet/stock_summary.parquet' GROUP BY StockCode LIMIT 10",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return (default 50).",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "idx_analyze_dividend",
        "description": "Analyze an announced or historical dividend for an IDX stock to decide whether to BUY, HOLD, or SELL before Cum Date, including Dividend Trap Risk scoring and after-tax considerations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "4-letter IDX stock code, e.g. 'BBCA', 'PTBA', 'AALI'.",
                },
            },
            "required": ["ticker"],
        },
    },
]


def handle_tool_call(name, args):
    """Executes a tool call and returns the text response."""
    try:
        if name == "idx_get_signals":
            date = args.get("date")
            window_days = args.get("window_days", 20)
            res = build_briefing(date=date, window_days=window_days)
            briefing_file = res.get("json")
            if os.path.exists(briefing_file):
                data = load_json(briefing_file)
                return json.dumps(data, indent=2)
            return json.dumps(res, indent=2)

        elif name == "idx_query_stock":
            ticker = args.get("ticker", "").strip().upper()
            limit = args.get("limit", 20)
            df = query_dataset("stock_summary", where=f"StockCode = '{ticker}'", limit=limit)
            if len(df) == 0:
                return f"No records found for ticker '{ticker}'."
            return df.to_json(orient="records", date_format="iso", indent=2)

        elif name == "idx_get_company_profile":
            ticker = args.get("ticker", "").strip().upper()
            details_path = os.path.join(DATA_DIR, "companyDetailsByKodeEmiten.json")
            if os.path.exists(details_path):
                details = load_json(details_path)
                if ticker in details:
                    return json.dumps(details[ticker], indent=2)
            return f"Company details for ticker '{ticker}' not found in local store."

        elif name == "idx_analyze_dividend":
            ticker = args.get("ticker", "").strip().upper()
            from idx.dividend import analyze_stock_dividend

            res = analyze_stock_dividend(ticker)
            return json.dumps(res, indent=2)

        elif name == "idx_screen_sharia_value":
            max_per = args.get("max_per", 12.0)
            min_roe = args.get("min_roe", 12.0)
            max_der = args.get("max_der", 2.0)
            ratios_path = os.path.join(DATA_DIR, "parquet", "financial_ratios.parquet")
            if os.path.exists(ratios_path):
                df = pd.read_parquet(ratios_path)
                hits = sharia_value_screen(df, max_per=max_per, min_roe=min_roe, max_der=max_der)
                return hits.to_json(orient="records", indent=2)
            return "Financial ratios parquet export not found. Run `cli.py parquet` first."

        elif name == "idx_get_super_insiders":
            query = args.get("tycoon_query")
            df = load_ownership_csv()
            if len(df) == 0:
                return "KSEI ownership data not found."
            holdings = get_tycoon_holdings(df)
            if query:
                holdings = holdings[holdings["InvestorUpper"].str.contains(query.upper(), na=False)]
            return holdings.to_json(orient="records", indent=2)

        elif name == "idx_query_broker_flow":
            date = args.get("date")
            top_k = args.get("top_k", 10)
            broker_path = os.path.join(DATA_DIR, "parquet", "broker_summary.parquet")
            if not os.path.exists(broker_path):
                from idx.core.timeseries import read_dataset

                df_broker = read_dataset("broker_summary")
            else:
                df_broker = pd.read_parquet(broker_path)

            if len(df_broker) == 0:
                return "No broker summary data available. Run `cli.py daily` or backfill first."

            from idx.signals import broker_concentration_screen

            summary, top_df = broker_concentration_screen(df_broker, on_date=date, top_k=top_k)
            return json.dumps(
                {"summary": summary, "top_brokers": top_df.to_dict("records")}, indent=2
            )

        elif name == "idx_get_technical_signals":
            ticker = args.get("ticker", "").strip().upper()
            rsi_period = args.get("rsi_period", 14)
            stock_path = os.path.join(DATA_DIR, "parquet", "stock_summary.parquet")
            if not os.path.exists(stock_path):
                from idx.core.timeseries import read_dataset

                df_stock = read_dataset("stock_summary")
            else:
                df_stock = pd.read_parquet(stock_path)

            if len(df_stock) == 0:
                return "No stock summary data available."

            from idx.signals import compute_technical_indicators

            tech = compute_technical_indicators(df_stock, ticker=ticker, rsi_period=rsi_period)
            if len(tech) == 0:
                return f"No records found for ticker '{ticker}'."
            latest = tech.tail(1).to_dict("records")[0]
            return json.dumps(latest, default=str, indent=2)

        elif name == "idx_compare_peers":
            ticker = args.get("ticker", "").strip().upper()
            ratios_path = os.path.join(DATA_DIR, "parquet", "financial_ratios.parquet")
            all_comp_path = os.path.join(DATA_DIR, "allCompanies.json")

            if not os.path.exists(ratios_path):
                return "Financial ratios parquet not found. Run `cli.py parquet` first."

            ratios_df = pd.read_parquet(ratios_path)
            sector = None
            if os.path.exists(all_comp_path):
                comp_data = load_json(all_comp_path)
                data_list = comp_data.get("data", []) if isinstance(comp_data, dict) else comp_data
                for c in data_list:
                    if c.get("KodeEmiten") == ticker:
                        sector = c.get("Sektor") or c.get("SubSektor")
                        break

            if "Sektor" in ratios_df.columns and sector:
                peers = ratios_df[ratios_df["Sektor"] == sector]
            else:
                peers = ratios_df

            peers = peers.sort_values("fsDate").groupby("code").last().reset_index()
            cols = [
                c
                for c in ["code", "stockName", "per", "priceBV", "roe", "roa", "deRatio", "npm"]
                if c in peers.columns
            ]
            return peers[cols].to_json(orient="records", indent=2)

        elif name == "idx_search_announcements":
            query = (args.get("query") or "").lower()
            ticker = (args.get("ticker") or "").upper()
            limit = args.get("limit", 15)

            ann_path = os.path.join(DATA_DIR, "announcements.json")
            results = []
            if os.path.exists(ann_path):
                raw = load_json(ann_path)
                items = (
                    raw.get("data", [])
                    if isinstance(raw, dict)
                    else (raw if isinstance(raw, list) else [])
                )
                for item in items:
                    t = (item.get("KodeEmiten") or item.get("StockCode") or "").upper()
                    title = (item.get("JudulPengumuman") or item.get("Title") or "").lower()
                    if ticker and ticker not in t:
                        continue
                    if query and query not in title:
                        continue
                    results.append(item)
                    if len(results) >= limit:
                        break

            if not results:
                from idx.scrapers.news import fetch_all_announcements

                data = fetch_all_announcements(keywords=query or ticker)
                if data and "data" in data:
                    results = data["data"][:limit]

            return json.dumps(results[:limit], indent=2, default=str)

        elif name == "idx_execute_sql":
            sql = args.get("sql", "").strip()
            limit = args.get("limit", 50)
            if not sql:
                return "Error: SQL statement cannot be empty."

            # Safety guardrails: Read-only check
            disallowed = [
                "insert ",
                "update ",
                "delete ",
                "drop ",
                "create ",
                "alter ",
                "truncate ",
                "replace ",
                "attach ",
                "copy ",
            ]
            if any(word in sql.lower() for word in disallowed):
                return "Error: Only read-only SELECT queries are allowed."

            import duckdb

            con = duckdb.connect(database=":memory:")
            # Register parquet tables as views for convenience
            for name in [
                "stock_summary",
                "financial_ratios",
                "corporate_actions",
                "broker_summary",
                "index_summary",
            ]:
                p_file = os.path.join(DATA_DIR, "parquet", f"{name}.parquet")
                if os.path.exists(p_file):
                    con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{p_file}')")

            res_df = con.execute(sql).fetchdf()
            if len(res_df) > limit:
                res_df = res_df.head(limit)
            return res_df.to_json(orient="records", date_format="iso", indent=2)

        else:
            return f"Unknown tool '{name}'."

    except Exception as e:
        log.exception("Error executing tool %s: %s", name, e)
        return f"Error executing tool {name}: {str(e)}"


def run_mcp_server():
    """Runs a standard stdio JSON-RPC MCP Server."""
    log.info("Starting IDX MCP Server on stdio...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "idx-bei-mcp", "version": "0.2.0"},
                        "capabilities": {"tools": {}},
                    },
                }
            elif method == "notifications/initialized":
                continue
            elif method == "ping":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            elif method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                result_text = handle_tool_call(tool_name, tool_args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}],
                        "isError": False,
                    },
                }
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"},
                }

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": req.get("id") if "req" in locals() else None,
                "error": {"code": -32603, "message": str(e)},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_mcp_server()
