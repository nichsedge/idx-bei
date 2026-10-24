"""
Scheduled worker: keeps announcements, prices, the screen and deal dossiers up to date.

Runs as its own process (``idx worker``, Docker service ``worker``) and checks every 30 s which jobs are due,
in Asia/Jakarta time (WIB). Jobs run one at a time; a failing job never stops the loop.

Jobs (defaults, overridable with env vars):

- ``announcements``  every 10 min on trading days 06:00–23:00, hourly otherwise — incremental collection of the
  full announcement feed (titles only). After 3 consecutive failures the job is flagged ``alert``.
- ``prices``         18:30 on trading days, retried every 30 min until 23:00 — stock / broker / index summary.
- ``screen``         19:00 on trading days — rebuild the title screen (feeds the momentum board).
- ``dossiers``       20:00 on trading days — refresh digests of active Deal Tracker tickers.
- ``cleanup``        Sundays 03:00 — retention and compaction (``idx cleanup --apply``, see pipelines/cleanup.py).

State: ``data/worker/state.json`` (per job: last run, last success, status, consecutive failures, message);
history: ``data/worker/runs.jsonl``.
"""

import json
import os
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as dtime

from idx.core.utils import DATA_DIR, get_logger, load_json, save_json
from idx.pipelines.announcements import WIB

log = get_logger("idx.worker")

WORKER_DIR = os.path.join(DATA_DIR, "worker")
STATE_FILE = os.path.join(WORKER_DIR, "state.json")
RUNS_FILE = os.path.join(WORKER_DIR, "runs.jsonl")
TICK_SECONDS = 30
ALERT_AFTER_FAILURES = 3


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_time(name: str, default: str) -> dtime:
    h, m = os.environ.get(name, default).split(":")
    return dtime(int(h), int(m))


def now_wib() -> datetime:
    return datetime.now(WIB)


def is_trading_day(d, holidays: dict[str, str] | None = None) -> bool:
    if holidays is None:
        from idx.ingestion import get_idx_holidays

        holidays = get_idx_holidays()
    return d.weekday() < 5 and d.isoformat() not in holidays


# ---------- schedules ----------


@dataclass
class Every:
    """Every `minutes` inside [start, end) on trading days; every `off_minutes` otherwise (None = not at all)."""

    minutes: int
    start: dtime = dtime(0, 0)
    end: dtime = dtime(23, 59, 59)
    off_minutes: int | None = None

    def due(
        self, now: datetime, last_run: datetime | None, last_ok: datetime | None, trading: bool
    ) -> bool:
        active = trading and self.start <= now.time() < self.end
        minutes = self.minutes if active else self.off_minutes
        if minutes is None:
            return False
        return last_run is None or now - last_run >= timedelta(minutes=minutes)

    def describe(self) -> str:
        off = f", every {self.off_minutes} min otherwise" if self.off_minutes else ""
        return f"every {self.minutes} min {self.start:%H:%M}-{self.end:%H:%M} on trading days{off}"


@dataclass
class DailyAt:
    """Once per trading day from `at`; failed attempts retried every `retry_minutes` until `until`."""

    at: dtime
    until: dtime = dtime(23, 0)
    retry_minutes: int = 30
    trading_only: bool = True
    weekdays: tuple[int, ...] | None = None  # e.g. (6,) = Sundays only (Monday = 0)

    def due(
        self, now: datetime, last_run: datetime | None, last_ok: datetime | None, trading: bool
    ) -> bool:
        if self.trading_only and not trading:
            return False
        if self.weekdays is not None and now.weekday() not in self.weekdays:
            return False
        t = now.time()
        if not (self.at <= t <= self.until):
            return False
        if last_ok is not None and last_ok.date() == now.date() and last_ok.time() >= self.at:
            return False  # already done today (a manual run earlier in the day does not count)
        if last_run is not None and last_run.date() == now.date() and last_run.time() >= self.at:
            return now - last_run >= timedelta(minutes=self.retry_minutes)
        return True

    def describe(self) -> str:
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if self.weekdays is not None:
            days = "/".join(names[d] for d in self.weekdays)
            return f"weekly {days} {self.at:%H:%M}, retry every {self.retry_minutes} min until {self.until:%H:%M}"
        days = "trading days" if self.trading_only else "every day"
        return f"daily {self.at:%H:%M} on {days}, retry every {self.retry_minutes} min until {self.until:%H:%M}"


# ---------- jobs ----------


def job_announcements(now: datetime) -> str:
    from idx.pipelines.announcements import collect

    res = collect(keywords="", download=False)
    if res.status == "failed":
        raise RuntimeError(res.error or "collection failed")
    return f"{res.status}: {res.pages} pages, {res.new_items} new" + (
        f", {len(res.schema_warnings)} schema warnings" if res.schema_warnings else ""
    )


def job_prices(now: datetime) -> str:
    from idx.pipelines.daily import ingest_daily

    res = ingest_daily(date=now.strftime("%Y%m%d"), export_parquet=False)
    parts, failed = [], []
    for name in ("stock_summary", "broker_summary", "index_summary"):
        r = res.get(name) or {}
        status = r.get("status", "?")
        parts.append(f"{name.split('_')[0]} {status}")
        if status == "error":
            failed.append(name)
    if failed and len(failed) == 3:
        raise RuntimeError("all summaries failed: " + "; ".join(parts))
    return ", ".join(parts)


def job_screen(now: datetime) -> str:
    from idx.pipelines.screen import build_screen

    md = build_screen(date_from=os.environ.get("WORKER_SCREEN_FROM", "2025-01-01"), fetch=False)
    return md.splitlines()[1] if md else "done"


def job_dossiers(now: datetime) -> str:
    from idx.deals import load_deals, load_rights, tracked_tickers
    from idx.pipelines.dossier import build_dossier

    tickers = tracked_tickers(load_deals(), load_rights())
    done, failed = [], []
    for t in tickers:
        try:
            build_dossier(t, date_from=os.environ.get("WORKER_DOSSIER_FROM", "2025-01-01"))
            done.append(t)
        except Exception as exc:  # one bad ticker must not stop the rest
            log.warning("dossier %s failed: %s", t, exc)
            failed.append(t)
    if failed and not done:
        raise RuntimeError(f"all dossiers failed: {', '.join(failed)}")
    return f"{len(done)} refreshed ({', '.join(done)})" + (
        f"; failed: {', '.join(failed)}" if failed else ""
    )


def job_cleanup(now: datetime) -> str:
    from idx.pipelines.cleanup import run_cleanup

    return run_cleanup(apply=True, now=now).summary()


@dataclass
class Job:
    name: str
    schedule: Every | DailyAt
    run: Callable[[datetime], str]


def default_jobs() -> list[Job]:
    return [
        Job(
            "announcements",
            Every(
                minutes=_env_int("WORKER_ANN_MINUTES", 10),
                start=dtime(6, 0),
                end=dtime(23, 0),
                off_minutes=_env_int("WORKER_ANN_OFF_MINUTES", 60),
            ),
            job_announcements,
        ),
        Job("prices", DailyAt(_env_time("WORKER_PRICES_AT", "18:30")), job_prices),
        Job("screen", DailyAt(_env_time("WORKER_SCREEN_AT", "19:00")), job_screen),
        Job(
            "dossiers",
            DailyAt(_env_time("WORKER_DOSSIERS_AT", "20:00"), retry_minutes=60),
            job_dossiers,
        ),
        Job(
            "cleanup",
            DailyAt(
                _env_time("WORKER_CLEANUP_AT", "03:00"),
                until=dtime(6, 0),
                retry_minutes=60,
                trading_only=False,
                weekdays=(6,),
            ),
            job_cleanup,
        ),
    ]


# ---------- state ----------


def _parse(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts) if ts else None


def load_state(path: str | None = None) -> dict:
    return load_json(path or STATE_FILE, {"jobs": {}})


def save_state(state: dict, path: str | None = None) -> None:
    path = path or STATE_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_json(path, state)


def run_job(job: Job, now: datetime, state: dict, runs_file: str | None = None) -> dict:
    """Run one job, update its entry in `state` in place, append to the run log. Returns the entry."""
    runs_file = runs_file or RUNS_FILE
    entry = state.setdefault("jobs", {}).setdefault(job.name, {"consecutive_failures": 0})
    started = time.monotonic()
    try:
        message = job.run(now)
        entry.update(status="ok", last_ok=now.isoformat(), consecutive_failures=0, alert=False)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        log.error("job %s failed: %s\n%s", job.name, message, traceback.format_exc())
        failures = entry.get("consecutive_failures", 0) + 1
        entry.update(
            status="failed", consecutive_failures=failures, alert=failures >= ALERT_AFTER_FAILURES
        )
        if entry["alert"]:
            log.warning("ALERT: job %s failed %d times in a row", job.name, failures)
    entry.update(
        last_run=now.isoformat(),
        duration_s=round(time.monotonic() - started, 1),
        message=message[:500],
        schedule=job.schedule.describe(),
    )
    os.makedirs(os.path.dirname(runs_file), exist_ok=True)
    with open(runs_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({"job": job.name, **entry}, ensure_ascii=False) + "\n")
    return entry


def due_jobs(jobs: list[Job], now: datetime, state: dict, trading: bool) -> list[Job]:
    out = []
    for job in jobs:
        e = state.get("jobs", {}).get(job.name, {})
        if job.schedule.due(now, _parse(e.get("last_run")), _parse(e.get("last_ok")), trading):
            out.append(job)
    return out


def tick(
    jobs: list[Job],
    state: dict,
    now: datetime | None = None,
    holidays: dict[str, str] | None = None,
) -> list[str]:
    """Run every due job once and save state after each. Returns the names of jobs that ran."""
    now = now or now_wib()
    trading = is_trading_day(now.date(), holidays)
    ran = []
    for job in due_jobs(jobs, now, state, trading):
        log.info("running job %s", job.name)
        run_job(job, now, state)
        ran.append(job.name)
        state["updated_at"] = now.isoformat()
        save_state(state)
    return ran


def run_forever(jobs: list[Job] | None = None) -> None:
    jobs = jobs or default_jobs()
    state = load_state()
    state["started_at"] = now_wib().isoformat()
    state["schedules"] = {j.name: j.schedule.describe() for j in jobs}
    save_state(state)
    log.info("worker started: %s", "; ".join(f"{k}: {v}" for k, v in state["schedules"].items()))
    while True:
        try:
            # Re-read each tick so manual `idx worker --once` runs in another process are not overwritten.
            tick(jobs, load_state())
        except Exception as exc:  # never let the loop die
            log.error("worker tick failed: %s", exc)
        time.sleep(TICK_SECONDS)


def run_once(names: list[str]) -> dict:
    """Run the named jobs now regardless of schedule (CLI: idx worker --once JOB)."""
    jobs = {j.name: j for j in default_jobs()}
    state = load_state()
    for name in names:
        if name not in jobs:
            raise SystemExit(f"unknown job {name!r}; choose from {', '.join(jobs)}")
        run_job(jobs[name], now_wib(), state)
    state["updated_at"] = now_wib().isoformat()
    save_state(state)
    return state
