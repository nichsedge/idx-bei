"""
Tests for AsyncIDXClient and asynchronous scrapers.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from idx.core.client import AsyncIDXClient, IDXRequestError
from idx.scrapers.company import async_fetch_company_detail


class TestAsyncIDXClient(unittest.IsolatedAsyncioTestCase):
    async def test_async_client_init_and_context(self):
        client = AsyncIDXClient(concurrency=3, delay_seconds=0.0)
        self.assertEqual(client.concurrency, 3)

        async with client as c:
            self.assertIsNotNone(c._session)
            self.assertIsNotNone(c._semaphore)

        self.assertIsNone(client._session)

    @patch("curl_cffi.requests.AsyncSession.get")
    async def test_async_get_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"StockCode": "BBCA"}]}
        mock_get.return_value = mock_resp

        client = AsyncIDXClient(delay_seconds=0.0)
        data = await client.get_json("/test/endpoint")
        self.assertEqual(data, {"data": [{"StockCode": "BBCA"}]})

    @patch("curl_cffi.requests.AsyncSession.get")
    async def test_async_get_json_decode_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("Bad JSON", "doc", 0)
        mock_get.return_value = mock_resp

        client = AsyncIDXClient(delay_seconds=0.0)
        res = await client.get_json("/test/badjson")
        self.assertIsNone(res)

        with self.assertRaises(IDXRequestError):
            await client.get_json("/test/badjson", raise_on_error=True)

    @patch("idx.core.client.AsyncIDXClient.get_json")
    async def test_async_fetch_company_detail(self, mock_get_json):
        mock_get_json.return_value = {"Profiles": [{"NamaEmiten": "Bank Central Asia"}]}
        res = await async_fetch_company_detail("BBCA")
        self.assertIn("Profiles", res)
        self.assertEqual(res["Profiles"][0]["NamaEmiten"], "Bank Central Asia")


if __name__ == "__main__":
    unittest.main()
