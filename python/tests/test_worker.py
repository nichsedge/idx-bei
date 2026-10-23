"""
Tests for the scheduled worker (idx.worker): schedules, failure alerting, state and run log, API status.
"""

import json
from datetime import date, datetime
from datetime import time as dtime

import pytest
from fastapi.testclient import TestClient

import idx.worker as worker
from idx.api import app
from idx.pipelines.announcements import WIB
from idx.worker import DailyAt, Every, Job, is_trading_day, run_job, tick

HOLIDAYS = {"2026-08-17": "Hari Kemerdekaan"}


def at(day: str, hm: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{hm}:00").replace(tzinfo=WIB)


@pytest.fixture(autouse=True)
def tmp_worker_files(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "STATE_FILE", str(tmp_path / "worker" / "state.json"))
    monkeypatch.setattr(worker, "RUNS_FILE", str(tmp_path / "worker" / "runs.jsonl"))


def test_is_trading_day():
    assert is_trading_day(date(2026, 10, 23), HOLIDAYS)  # Friday
    assert not is_trading_day(date(2026, 10, 24), HOLIDAYS)  # Saturday
    assert not is_trading_day(date(2026, 8, 17), HOLIDAYS)  # holiday


def test_every_schedule():
    s = Every(minutes=10, start=dtime(6, 0), end=dtime(23, 0), off_minutes=60)
    now = at("2026-10-23", "10:00")
    assert s.due(now, None, None, trading=True)
    assert not s.due(now, at("2026-10-23", "09:55"), None, trading=True)
    assert s.due(now, at("2026-10-23", "09:50"), None, trading=True)
    # outside hours or on a non-trading day: hourly
    assert not s.due(at("2026-10-23", "23:30"), at("2026-10-23", "23:00"), None, trading=True)
    assert s.due(at("2026-10-24", "10:00"), at("2026-10-24", "09:00"), None, trading=False)
    assert not Every(minutes=10, off_minutes=None).due(now, None, None, trading=False)


def test_daily_schedule_with_retry():
    s = DailyAt(dtime(18, 30), until=dtime(23, 0), retry_minutes=30)
    day = "2026-10-23"
    assert not s.due(at(day, "18:00"), None, None, trading=True)  # too early
    assert s.due(at(day, "18:30"), None, None, trading=True)
    assert not s.due(
        at(day, "19:00"), at(day, "18:30"), at(day, "18:30"), trading=True
    )  # done today
    # failed at 18:30 → retry only after 30 min
    assert not s.due(at(day, "18:45"), at(day, "18:30"), None, trading=True)
    assert s.due(at(day, "19:00"), at(day, "18:30"), None, trading=True)
    assert not s.due(at(day, "23:30"), at(day, "19:00"), None, trading=True)  # past cut-off
    assert not s.due(at("2026-10-24", "19:00"), None, None, trading=False)  # weekend
    # yesterday's success does not block today
    assert s.due(at("2026-10-26", "18:31"), at(day, "18:30"), at(day, "18:30"), trading=True)
    # a manual run earlier the same day (idx worker --once) does not replace the scheduled run
    assert s.due(at(day, "18:30"), at(day, "11:28"), at(day, "11:28"), trading=True)


def test_run_job_records_success_failure_and_alert():
    state: dict = {}
    ok = Job("ok", Every(10), lambda now: "fine")
    assert run_job(ok, at("2026-10-23", "10:00"), state)["status"] == "ok"

    def boom(now):
        raise RuntimeError("IDX 403")

    bad = Job("bad", Every(10), boom)
    for i in range(3):
        e = run_job(bad, at("2026-10-23", f"10:{10 * i:02d}"), state)
    assert e["status"] == "failed" and e["consecutive_failures"] == 3 and e["alert"]
    assert "IDX 403" in e["message"]
    e = run_job(Job("bad", Every(10), lambda now: "recovered"), at("2026-10-23", "11:00"), state)
    assert (e["status"], e["consecutive_failures"], e["alert"]) == ("ok", 0, False)

    with open(worker.RUNS_FILE, encoding="utf-8") as f:
        runs = [json.loads(line) for line in f]
    assert [r["job"] for r in runs] == ["ok", "bad", "bad", "bad", "bad"]


def test_tick_runs_only_due_jobs_and_saves_state():
    calls = []
    jobs = [
        Job(
            "ann",
            Every(10, start=dtime(6, 0), end=dtime(23, 0), off_minutes=60),
            lambda now: calls.append("ann") or "a",
        ),
        Job("prices", DailyAt(dtime(18, 30)), lambda now: calls.append("prices") or "p"),
    ]
    state: dict = {"jobs": {}}
    assert tick(jobs, state, now=at("2026-10-23", "10:00"), holidays=HOLIDAYS) == ["ann"]
    assert tick(jobs, state, now=at("2026-10-23", "10:05"), holidays=HOLIDAYS) == []
    assert tick(jobs, state, now=at("2026-10-23", "18:31"), holidays=HOLIDAYS) == ["ann", "prices"]
    assert calls == ["ann", "ann", "prices"]
    saved = worker.load_state()
    assert saved["jobs"]["prices"]["status"] == "ok" and saved["updated_at"].startswith(
        "2026-10-23T18:31"
    )


def test_prices_job_fails_only_when_everything_fails(monkeypatch):
    import idx.pipelines.daily as daily

    monkeypatch.setattr(
        daily,
        "ingest_daily",
        lambda date, export_parquet: {
            "stock_summary": {"status": "ok"},
            "broker_summary": {"status": "error"},
            "index_summary": {"status": "ok"},
        },
    )
    assert "broker error" in worker.job_prices(at("2026-10-23", "18:30"))
    monkeypatch.setattr(
        daily,
        "ingest_daily",
        lambda date, export_parquet: {
            k: {"status": "error"} for k in ("stock_summary", "broker_summary", "index_summary")
        },
    )
    with pytest.raises(RuntimeError):
        worker.job_prices(at("2026-10-23", "18:30"))


def test_worker_status_endpoint():
    state: dict = {"jobs": {}}
    run_job(
        Job("announcements", Every(10), lambda now: "ok: 1 pages, 3 new"), worker.now_wib(), state
    )
    state["updated_at"] = worker.now_wib().isoformat()
    worker.save_state(state)

    body = TestClient(app).get("/api/system/worker?runs=5").json()
    assert body["jobs"]["announcements"]["status"] == "ok"
    assert body["recent_runs"][0]["message"] == "ok: 1 pages, 3 new"
    assert body["stale"] is False
