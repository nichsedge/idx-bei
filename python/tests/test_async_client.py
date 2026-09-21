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

    @patch("curl_cffi.requests.AsyncSession.get")
    async def test_async_retry_and_error(self, mock_get):
        mock_resp_429 = MagicMock(status_code=429)
        mock_resp_200 = MagicMock(status_code=200)
        mock_resp_200.json.return_value = {"ok": True}
        mock_get.side_effect = [mock_resp_429, mock_resp_200]

        client = AsyncIDXClient(max_retries=1, delay_seconds=0.0)
        with patch("asyncio.sleep"):
            res = await client.get("/test/retry")
            self.assertEqual(res.status_code, 200)

        # Non-retryable 404
        mock_resp_404 = MagicMock(status_code=404)
        mock_get.side_effect = [mock_resp_404]
        res_404 = await client.get("/test/404")
        self.assertEqual(res_404.status_code, 404)

        with self.assertRaises(IDXRequestError):
            await client.get_json("/test/404", raise_on_error=True)

    @patch("curl_cffi.requests.AsyncSession.get")
    async def test_async_retry_403_rotates_impersonation(self, mock_get):
        mock_resp_403 = MagicMock(status_code=403)
        mock_resp_200 = MagicMock(status_code=200)
        mock_resp_200.json.return_value = {"ok": True}
        mock_get.side_effect = [mock_resp_403, mock_resp_200]

        client = AsyncIDXClient(max_retries=1, delay_seconds=0.0)
        with patch("asyncio.sleep"):
            res = await client.get("/test/waf_retry", impersonate="chrome")
            self.assertEqual(res.status_code, 200)

        self.assertEqual(mock_get.call_count, 2)
        first_call = mock_get.call_args_list[0]
        second_call = mock_get.call_args_list[1]
        self.assertEqual(first_call.kwargs.get("impersonate"), "chrome")
        self.assertEqual(second_call.kwargs.get("impersonate"), "chrome124")


class TestSyncIDXClient(unittest.TestCase):
    @patch("curl_cffi.requests.get")
    def test_sync_get_success_and_retry(self, mock_get):
        from idx.core.client import IDXClient

        client = IDXClient(max_retries=1, delay_seconds=0.0)

        # 200 Success
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"data": [1, 2, 3]}
        mock_get.return_value = mock_resp
        res = client.get_json("/test/sync")
        self.assertEqual(res, {"data": [1, 2, 3]})

        # 429 Retry then success
        mock_429 = MagicMock(status_code=429)
        mock_get.side_effect = [mock_429, mock_resp]
        with patch("time.sleep"):
            res_retry = client.get_json("/test/retry")
            self.assertEqual(res_retry, {"data": [1, 2, 3]})

        # 404 Error
        mock_404 = MagicMock(status_code=404)
        mock_get.side_effect = [mock_404]
        self.assertIsNone(client.get_json("/test/notfound"))
        with self.assertRaises(IDXRequestError):
            client.get_json("/test/notfound", raise_on_error=True)

        # JSON Decode Error
        mock_bad = MagicMock(status_code=200)
        mock_bad.json.side_effect = json.JSONDecodeError("err", "doc", 0)
        mock_get.side_effect = [mock_bad]
        self.assertIsNone(client.get_json("/test/bad"))
        with self.assertRaises(IDXRequestError):
            client.get_json("/test/bad", raise_on_error=True)

    @patch("curl_cffi.requests.get")
    def test_sync_retry_403_rotates_impersonation(self, mock_get):
        from idx.core.client import IDXClient

        client = IDXClient(max_retries=1, delay_seconds=0.0)
        mock_resp_403 = MagicMock(status_code=403)
        mock_resp_200 = MagicMock(status_code=200)
        mock_resp_200.json.return_value = {"data": ["ok"]}
        mock_get.side_effect = [mock_resp_403, mock_resp_200]

        with patch("time.sleep"):
            res = client.get("/test/waf_sync", impersonate="chrome")
            self.assertEqual(res.status_code, 200)

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_get.call_args_list[0].kwargs.get("impersonate"), "chrome")
        self.assertEqual(mock_get.call_args_list[1].kwargs.get("impersonate"), "chrome124")


if __name__ == "__main__":
    unittest.main()
