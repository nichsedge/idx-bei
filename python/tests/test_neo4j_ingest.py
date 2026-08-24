import sys
from unittest.mock import MagicMock

# Mock dependencies that are not installed in the environment
# This allows us to test the logic in neo4j_ingest.py without having to install all dependencies
sys.modules["pandas"] = MagicMock()
sys.modules["neo4j"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

import unittest
from io import StringIO
from unittest.mock import patch

import neo4j_ingest


class TestNeo4jIngest(unittest.TestCase):
    def test_ingest_all_stock_profiles_file_not_found(self):
        """Test that ingest_all_stock_profiles handles FileNotFoundError gracefully."""
        # Using a path that definitely doesn't exist
        dummy_path = "non_existent_file_12345.json"

        # Capture stdout to verify the error message
        with patch('sys.stdout', new=StringIO()) as fake_out:
            # The function should catch FileNotFoundError and return None
            result = neo4j_ingest.ingest_all_stock_profiles(data_path=dummy_path)

            output = fake_out.getvalue().strip()
            self.assertIn(f"Error: Data file not found at {dummy_path}", output)
            self.assertIsNone(result)

    def test_ingest_all_stock_summaries_file_not_found(self):
        """Test that ingest_all_stock_summaries handles FileNotFoundError gracefully."""
        # Using a path that definitely doesn't exist
        dummy_path = "non_existent_file_12345.json"

        # Capture stdout to verify the error message
        with patch('sys.stdout', new=StringIO()) as fake_out:
            # The function should catch FileNotFoundError and return None
            result = neo4j_ingest.ingest_all_stock_summaries(data_path=dummy_path)

            output = fake_out.getvalue().strip()
            self.assertIn(f"Error: Data file not found at {dummy_path}", output)
            self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
