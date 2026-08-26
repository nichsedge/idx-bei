"""
Tests for FastAPI REST & WebSocket Microservice endpoints.
"""

import unittest

from fastapi.testclient import TestClient

from idx.api import app


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "idx-bei-api")

    def test_sql_guardrails(self):
        response = self.client.post("/api/query/sql", json={"sql": "DROP TABLE test"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only read-only SELECT queries are allowed", response.json()["detail"])

    def test_sql_valid_query(self):
        response = self.client.post(
            "/api/query/sql", json={"sql": "SELECT 100 AS num, 'IDX' AS exchange"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[0]["num"], 100)
        self.assertEqual(data[0]["exchange"], "IDX")

    def test_get_ubo(self):
        response = self.client.get("/api/graph/ubo/BBCA")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "BBCA")


if __name__ == "__main__":
    unittest.main()
