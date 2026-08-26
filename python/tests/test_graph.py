"""
Tests for Neo4j UBO resolution, circular cross-holdings, and board centrality.
"""

import unittest
from unittest.mock import MagicMock, patch

from idx.graph import calculate_board_centrality, detect_cross_holdings, get_ubo_tree


class TestGraph(unittest.TestCase):
    @patch("idx.graph.get_neo4j_driver")
    def test_get_ubo_tree_neo4j(self, mock_get_driver):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_res = MagicMock()
        mock_res.single.return_value = {
            "name": "Bank Central Asia Tbk",
            "ultimate_owners": ["Djarum Group", "Robert Budi Hartono"],
            "key_insiders": ["Jahja Setiaatmadja"],
        }
        mock_session.run.return_value = mock_res
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_get_driver.return_value = mock_driver

        tree = get_ubo_tree("BBCA")
        self.assertEqual(tree["ticker"], "BBCA")
        self.assertEqual(tree["engine"], "neo4j")
        self.assertIn("Djarum Group", tree["ultimate_owners"])

    def test_get_ubo_tree_offline_fallback(self):
        with patch("idx.graph.get_neo4j_driver", return_value=None):
            tree = get_ubo_tree("BBCA")
            self.assertIn("ticker", tree)
            self.assertEqual(tree["ticker"], "BBCA")

    def test_detect_cross_holdings_fallback(self):
        with patch("idx.graph.get_neo4j_driver", return_value=None):
            loops = detect_cross_holdings()
            self.assertIsInstance(loops, list)
            self.assertGreaterEqual(len(loops), 1)

    def test_calculate_board_centrality_fallback(self):
        with patch("idx.graph.get_neo4j_driver", return_value=None):
            df_c = calculate_board_centrality(top_n=10)
            self.assertIn("insider", df_c.columns)
            self.assertIn("board_seats", df_c.columns)


if __name__ == "__main__":
    unittest.main()
