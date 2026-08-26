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
