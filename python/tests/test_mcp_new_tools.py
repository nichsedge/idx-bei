"""
Tests for expanded MCP tools (broker flow, technical signals, compare peers, announcements, SQL).
"""

import json
import unittest
from unittest.mock import patch

from idx.mcp.server import TOOLS, handle_tool_call


class TestMCPNewTools(unittest.TestCase):
    def test_tools_list_contains_new_tools(self):
        tool_names = [t["name"] for t in TOOLS]
        self.assertIn("idx_query_broker_flow", tool_names)
        self.assertIn("idx_get_technical_signals", tool_names)
        self.assertIn("idx_compare_peers", tool_names)
        self.assertIn("idx_search_announcements", tool_names)
        self.assertIn("idx_execute_sql", tool_names)
        self.assertIn("idx_screen_stealth_accumulation", tool_names)
        self.assertIn("idx_run_backtest", tool_names)

    @patch("idx.signals.detect_stealth_accumulation")
    def test_screen_stealth_accumulation_tool(self, mock_stealth):
        import pandas as pd

        mock_stealth.return_value = {
            "summary": "Stealth accumulation detected in 1 stock",
            "signal": "STEALTH_ACCUMULATION",
            "smart_money_delta": 4.5,
            "anomalies_df": pd.DataFrame([{"StockCode": "BBCA", "Signal": "STEALTH_ACCUMULATION", "WyckoffPhase": "Phase C"}]),
        }
        res = handle_tool_call("idx_screen_stealth_accumulation", {"lookback_days": 5})
        data = json.loads(res)
        self.assertEqual(data["signal"], "STEALTH_ACCUMULATION")
        self.assertEqual(data["smart_money_delta"], 4.5)
        self.assertEqual(len(data["anomalies"]), 1)
        self.assertEqual(data["anomalies"][0]["StockCode"], "BBCA")

    @patch("idx.backtest.run_backtest")
    def test_run_backtest_tool(self, mock_bt):
        import pandas as pd

        mock_bt.return_value = (
            {"strategy": "foreign_flow", "total_return_pct": 14.2, "sharpe_ratio": 1.8},
            pd.DataFrame([{"StockCode": "BBCA", "ReturnPct": 14.2, "Weight": 0.5}]),
        )
        res = handle_tool_call("idx_run_backtest", {"strategy": "foreign_flow", "holding_days": 20})
        data = json.loads(res)
        self.assertEqual(data["metrics"]["strategy"], "foreign_flow")
        self.assertEqual(data["metrics"]["total_return_pct"], 14.2)
        self.assertEqual(data["total_trades"], 1)

    def test_execute_sql_guardrails(self):
        # Disallow unsafe queries
        res = handle_tool_call("idx_execute_sql", {"sql": "DROP TABLE test"})
        self.assertIn("Only read-only SELECT queries are allowed", res)

        res2 = handle_tool_call("idx_execute_sql", {"sql": "DELETE FROM test"})
        self.assertIn("Only read-only SELECT queries are allowed", res2)

    def test_execute_sql_valid_query(self):
        res = handle_tool_call("idx_execute_sql", {"sql": "SELECT 42 AS answer, 'IDX' AS exchange"})
        data = json.loads(res)
        self.assertEqual(data[0]["answer"], 42)
        self.assertEqual(data[0]["exchange"], "IDX")

    @patch("idx.signals.compute_technical_indicators")
    def test_get_technical_signals(self, mock_tech):
        import pandas as pd

        mock_tech.return_value = pd.DataFrame(
            [{"StockCode": "BBCA", "Date": "2026-08-01", "RSI14": 58.5, "TrendRegime": "BULLISH"}]
        )
        res = handle_tool_call("idx_get_technical_signals", {"ticker": "BBCA"})
        data = json.loads(res)
        self.assertEqual(data["StockCode"], "BBCA")
        self.assertEqual(data["RSI14"], 58.5)

    def test_unknown_tool(self):
        res = handle_tool_call("idx_non_existent", {})
        self.assertIn("Unknown tool", res)


if __name__ == "__main__":
    unittest.main()
