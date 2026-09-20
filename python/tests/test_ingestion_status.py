"""
Tests for Data Ingestion Status, Gap Detection, and Backfill Recommendations.
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from idx.api import app
from idx.ingestion import (
    calculate_backfill_recommendations,
    detect_timeseries_gaps,
    get_dataset_inventory,
    get_full_ingestion_status,
    get_idx_holidays,
    run_async_ingestion_job,
)


class TestIngestionStatus(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_dataset_inventory(self):
        inv = get_dataset_inventory()
        self.assertIn("timeseries", inv)
        self.assertIn("stock_summary", inv["timeseries"])
        self.assertIn("broker_summary", inv["timeseries"])
        self.assertIn("index_summary", inv["timeseries"])
        self.assertIn("parquet_exports", inv)
        self.assertIn("fundamental_snapshots", inv)
        self.assertIn("total_listed_companies", inv["fundamental_snapshots"])
        self.assertIn("ksei_drift", inv)
        self.assertIn("system", inv)

    def test_detect_timeseries_gaps(self):
        res = detect_timeseries_gaps(
            dataset="stock_summary",
            start_date="2026-01-01",
            end_date="2026-09-08",
        )
        self.assertEqual(res["dataset"], "stock_summary")
        self.assertGreater(res["total_calendar_weekdays"], 150)
        self.assertGreater(res["official_holidays_count"], 10)
        self.assertIsInstance(res["official_holidays"], list)
        self.assertIsInstance(res["true_missing_trading_days"], list)
        self.assertGreaterEqual(res["coverage_percentage"], 0.0)
        self.assertLessEqual(res["coverage_percentage"], 100.0)

    def test_calculate_backfill_recommendations(self):
        recs = calculate_backfill_recommendations(current_date="2026-09-08")
        self.assertIn("summary", recs)
        self.assertIn("tiers", recs)
        self.assertEqual(len(recs["tiers"]), 4)

        tier_ids = [t["id"] for t in recs["tiers"]]
        self.assertIn("tier_1_immediate_gap_repair", tier_ids)
        self.assertIn("tier_2_one_year_baseline", tier_ids)
        self.assertIn("tier_3_three_year_multicycle", tier_ids)
        self.assertIn("tier_4_five_year_macro", tier_ids)

        tier2 = next(t for t in recs["tiers"] if t["tier"] == 2)
        self.assertEqual(tier2["priority"], "RECOMMENDED (BEST VALUE)")
        self.assertGreater(tier2["trading_days_to_fetch"], 200)
        self.assertIn("uv run idx backfill", tier2["recommended_cli_commands"][0])

    def test_get_full_ingestion_status(self):
        full = get_full_ingestion_status()
        self.assertIn(full["status"], ["healthy", "warning", "critical"])
        self.assertIsInstance(full["health_score"], (int, float))
        self.assertGreaterEqual(full["health_score"], 0)
        self.assertLessEqual(full["health_score"], 100)
        self.assertIn("inventory", full)
        self.assertIn("gaps", full)
        self.assertIn("recommendations", full)

    def test_api_ingestion_status_endpoint(self):
        resp = self.client.get("/api/system/ingestion-status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)
        self.assertIn("health_score", data)
        self.assertIn("inventory", data)
        self.assertIn("gaps", data)
        self.assertIn("recommendations", data)

    def test_api_trigger_ingestion_and_jobs_list(self):
        resp = self.client.post(
            "/api/system/trigger-ingestion",
            json={"job_type": "daily", "date": "20260908"},
        )
        self.assertEqual(resp.status_code, 200)
        job_data = resp.json()
        self.assertIn("job_id", job_data)
        self.assertEqual(job_data["status"], "scheduled")

        # Query recent jobs
        jobs_resp = self.client.get("/api/system/jobs")
        self.assertEqual(jobs_resp.status_code, 200)
        self.assertIsInstance(jobs_resp.json(), list)

        # Query specific job
        job_detail = self.client.get(f"/api/system/jobs/{job_data['job_id']}")
        self.assertEqual(job_detail.status_code, 200)
        self.assertEqual(job_detail.json()["job_id"], job_data["job_id"])

    def test_api_get_invalid_job(self):
        resp = self.client.get("/api/system/jobs/nonexistent-job-9999")
        self.assertEqual(resp.status_code, 404)

    @patch("idx.pipelines.daily.ingest_daily", return_value={"status": "ok"})
    def test_run_async_ingestion_job_daily(self, mock_ingest):
        import asyncio

        callback = AsyncMock()
        res = asyncio.run(
            run_async_ingestion_job(
                job_id="test-job-1",
                job_type="daily",
                params={"date": "20260908"},
                broadcast_callback=callback,
            )
        )
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["progress_pct"], 100)
    def test_get_idx_holidays(self):
        holidays_all = get_idx_holidays()
        self.assertIsInstance(holidays_all, dict)
        self.assertIn("2026-01-01", holidays_all)
        self.assertIn("2026-08-17", holidays_all)

        holidays_2026 = get_idx_holidays(year=2026)
        self.assertTrue(all(d.startswith("2026-") for d in holidays_2026.keys()))


if __name__ == "__main__":
    unittest.main()
