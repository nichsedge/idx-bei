"""
Unit tests for Bandar / Institutional Flow Anomaly Notifier & Background Daemon.
"""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from starlette.testclient import TestClient

from idx.api import app
from idx.bandar_notifier import (
    BandarAnomalyAlert,
    BandarAnomalyDaemon,
    detect_bandar_anomalies,
    send_telegram_alert,
)
from idx.bandar_notifier import (
    test_telegram_connection as check_telegram_connection,
)


class TestBandarNotifier(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _create_mock_stock_data(self):
        """Creates 21 sessions of stock data where session 21 exhibits anomalies."""
        dates = pd.date_range("2026-08-01", periods=21, freq="B")
        rows = []

        # Baseline 20 sessions for 3 stocks:
        # WHAL: Low volume baseline (10M shares, Rp 10B value, NFF ~0)
        # TRAP: Medium baseline (20M shares)
        # NORM: Normal baseline (15M shares)
        for i in range(20):
            d = dates[i].strftime("%Y-%m-%d")
            # WHAL
            rows.append(
                {
                    "Date": d,
                    "StockCode": "WHAL",
                    "StockName": "PT Whale Absorption Tbk",
                    "Close": 1000.0,
                    "Previous": 1000.0,
                    "Volume": 10_000_000.0,
                    "Value": 10_000_000_000.0,
                    "ForeignBuy": 2_000_000.0,
                    "ForeignSell": 2_000_000.0,
                }
            )
            # TRAP
            rows.append(
                {
                    "Date": d,
                    "StockCode": "TRAP",
                    "StockName": "PT Retail Trap Tbk",
                    "Close": 500.0,
                    "Previous": 500.0,
                    "Volume": 10_000_000.0,
                    "Value": 5_000_000_000.0,
                    "ForeignBuy": 3_000_000.0,
                    "ForeignSell": 3_000_000.0,
                }
            )

        # Session 21: Extreme Spikes
        d_last = dates[20].strftime("%Y-%m-%d")

        # WHAL: Massive Volume Spike (100M shares, +900%), flat price (1005 vs 1000, +0.5%), 75% Foreign Buy
        rows.append(
            {
                "Date": d_last,
                "StockCode": "WHAL",
                "StockName": "PT Whale Absorption Tbk",
                "Close": 1005.0,
                "Previous": 1000.0,
                "Volume": 100_000_000.0,
                "Value": 100_000_000_000.0,
                "ForeignBuy": 75_000_000.0,
                "ForeignSell": 5_000_000.0,
            }
        )

        # TRAP: Volume Spike (80M shares), Price pumped +15% (575 vs 500), but Foreign is heavily net selling (ForeignBuy 5M vs ForeignSell 50M)
        rows.append(
            {
                "Date": d_last,
                "StockCode": "TRAP",
                "StockName": "PT Retail Trap Tbk",
                "Close": 575.0,
                "Previous": 500.0,
                "Volume": 80_000_000.0,
                "Value": 46_000_000_000.0,
                "ForeignBuy": 5_000_000.0,
                "ForeignSell": 50_000_000.0,
            }
        )

        return pd.DataFrame(rows)

    def test_alert_object_and_telegram_formatting(self):
        alert = BandarAnomalyAlert(
            ticker="BBCA",
            company_name="Bank Central Asia Tbk",
            date="2026-09-01",
            price=10200.0,
            price_change_pct=0.25,
            volume=150_000_000.0,
            turnover_rp=1_530_000_000_000.0,
            net_foreign_flow_rp=450_000_000_000.0,
            foreign_buy_ratio_pct=78.5,
            z_vol=3.85,
            z_val=3.92,
            z_nff=4.10,
            z_composite=4.10,
            anomaly_type="INSTITUTIONAL_ABSORPTION",
            wyckoff_phase="Phase C — Silent Absorption",
            smart_money_delta=4.5,
            headline="Whale Absorption on BBCA",
            playbook="Do not panic sell into whale absorption.",
        )

        d = alert.to_dict()
        self.assertEqual(d["ticker"], "BBCA")
        self.assertEqual(d["anomaly_type"], "INSTITUTIONAL_ABSORPTION")
        self.assertEqual(d["z_composite"], 4.10)

        msg = alert.format_telegram_message()
        self.assertIn("BANDAR ANOMALY NOTIFIER", msg)
        self.assertIn("BBCA", msg)
        self.assertIn("INSTITUTIONAL ABSORPTION", msg)
        self.assertIn("4.1σ", msg)
        self.assertIn("Rp 10,200", msg)

    def test_detect_bandar_anomalies_classification(self):
        df = self._create_mock_stock_data()
        anomalies = detect_bandar_anomalies(stock_df=df, sigma_threshold=3.0)

        self.assertTrue(len(anomalies) >= 2)
        anomaly_map = {a.ticker: a for a in anomalies}

        # WHAL must be classified as INSTITUTIONAL_ABSORPTION
        self.assertIn("WHAL", anomaly_map)
        whal_alert = anomaly_map["WHAL"]
        self.assertEqual(whal_alert.anomaly_type, "INSTITUTIONAL_ABSORPTION")
        self.assertGreaterEqual(whal_alert.z_composite, 3.0)
        self.assertGreaterEqual(whal_alert.foreign_buy_ratio_pct, 60.0)
        self.assertLessEqual(abs(whal_alert.price_change_pct), 1.5)

        # TRAP must be classified as RETAIL_TRAP_DISTRIBUTION
        self.assertIn("TRAP", anomaly_map)
        trap_alert = anomaly_map["TRAP"]
        self.assertEqual(trap_alert.anomaly_type, "RETAIL_TRAP_DISTRIBUTION")
        self.assertGreaterEqual(trap_alert.z_composite, 3.0)
        self.assertGreater(trap_alert.price_change_pct, 0.5)

    @patch("urllib.request.urlopen")
    def test_send_telegram_alert_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = send_telegram_alert(
            "Test alert message", bot_token="12345:TOKEN", chat_id="-100123456"
        )
        self.assertTrue(res)
        self.assertTrue(mock_urlopen.called)

    def test_send_telegram_alert_missing_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            res = send_telegram_alert("Test", bot_token=None, chat_id=None)
            self.assertFalse(res)

    @patch("idx.bandar_notifier.send_telegram_alert", return_value=True)
    def test_telegram_connection_fn(self, mock_send):
        res = check_telegram_connection(bot_token="test_tok", chat_id="test_chat")
        self.assertTrue(res["ok"])
        self.assertEqual(res["chat_id"], "test_chat")

    def test_bandar_daemon_cooldown_and_dryrun(self):
        daemon = BandarAnomalyDaemon(sigma_threshold=3.0, cooldown_seconds=3600, dry_run=True)

        with patch("idx.bandar_notifier.detect_bandar_anomalies") as mock_detect:
            # Create sample alert
            alert = BandarAnomalyAlert(
                ticker="TEST",
                company_name="Test Tbk",
                date="2026-09-01",
                price=1000.0,
                price_change_pct=0.0,
                volume=1e8,
                turnover_rp=1e11,
                net_foreign_flow_rp=5e10,
                foreign_buy_ratio_pct=75.0,
                z_vol=4.0,
                z_val=4.0,
                z_nff=4.0,
                z_composite=4.0,
                anomaly_type="INSTITUTIONAL_ABSORPTION",
                wyckoff_phase="Phase C",
                smart_money_delta=3.5,
                headline="Test Headline",
                playbook="Test Playbook",
            )
            mock_detect.return_value = [alert]

            # Pass 1: Alert should be dispatched
            pass1 = daemon.scan_and_notify()
            self.assertEqual(len(pass1), 1)

            # Pass 2: Suppressed by cooldown
            pass2 = daemon.scan_and_notify()
            self.assertEqual(len(pass2), 0)

    def test_api_bandar_endpoints(self):
        # 1. Anomalies endpoint
        resp = self.client.get("/api/bandar/anomalies?threshold=2.0")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

        # 2. Test notification GET endpoint
        resp_test = self.client.get("/api/bandar/notify-test")
        self.assertEqual(resp_test.status_code, 200)
        self.assertIn("ok", resp_test.json())


if __name__ == "__main__":
    unittest.main()
