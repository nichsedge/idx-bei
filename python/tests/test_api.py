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

    def test_stealth_accumulation_endpoint(self):
        response = self.client.get("/api/stealth-accumulation")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("smart_money_delta", data)
        self.assertIn("signal", data)

    def test_broadcast_endpoint(self):
        response = self.client.post("/api/broadcast", json={"type": "test_event", "val": 123})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "broadcast_sent")

    def test_websocket_stream(self):
        with self.client.websocket_connect("/ws/stream") as ws:
            msg = ws.receive_json()
            self.assertEqual(msg["type"], "handshake")
            self.assertEqual(msg["status"], "connected")
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            self.assertEqual(pong["type"], "pong")

    def test_drift_endpoint(self):
        response = self.client.get("/api/drift")
        self.assertEqual(response.status_code, 200)

    def test_dividend_screen_endpoint(self):
        response = self.client.get("/api/dividend?min_yield=1.0")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)


if __name__ == "__main__":
    unittest.main()
