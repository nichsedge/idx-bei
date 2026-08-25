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
