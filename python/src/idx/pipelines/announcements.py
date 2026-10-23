"""
Company announcements (keterbukaan informasi) collector.

Pages through ``/NewsAnnouncement/GetAllAnnouncement`` (newest first), persists every item and
downloads its PDF attachments.

Layout under ``data/announcements/``::

    items/YYYY-MM.jsonl   one normalised row per announcement (raw IDX item kept under "raw")
    files/ab/<sha256>.pdf attachments, content-addressed
    attachments.jsonl     url → sha256, size, content type, path
    state.json            per-keyword cursor (newest publish time fully collected)
    runs.jsonl            one record per run: status, pages, new items, schema warnings, latency

Two modes:

- incremental (no ``date_from``): page until items are older than the stored cursor minus an
  overlap window; already-stored ids are skipped. The first run without a cursor looks back
  ``FIRST_RUN_LOOKBACK_DAYS``.
- backfill (``date_from`` given): uses the endpoint's ``dateFrom``/``dateTo`` filter and pages
  to the last page.

The cursor only advances when a run completes, so a failed run never leaves a gap.
"""

import gzip
import hashlib
import json
import os
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from idx.core.client import IDXClient
from idx.core.utils import (
    DATA_DIR,
    check_schema_drift,
    get_logger,
    load_json,
    save_json,
    validate_schema,
)
from idx.scrapers.news import fetch_all_announcements

log = get_logger("idx.pipelines.announcements")

ANNOUNCEMENTS_DIR = os.path.join(DATA_DIR, "announcements")
WIB = timezone(timedelta(hours=7))  # Asia/Jakarta, no DST
FIRST_RUN_LOOKBACK_DAYS = 7
CURSOR_OVERLAP = timedelta(hours=24)

# Indonesian / English keywords for takeovers, backdoor listings and capital raises (deal tracker plan §5.3).
MA_KEYWORDS = [
    "pengambilalihan",
    "akuisisi",
    "calon pengendali",
    "pengendali baru",
    "perubahan pengendali",
    "penawaran tender",
    "tender offer",
    "negosiasi",
    "backdoor listing",
    "inbreng",
    "perubahan kegiatan usaha",
    "perubahan nama",
    "PMHMETD",
    "HMETD",
    "rights issue",
    "pembeli siaga",
    "prospektus ringkas",
    "PMTHMETD",
    "private placement",
    "transaksi material",
    "go private",
    "delisting",
    "merger",
    "penggabungan",
]


def to_idx_date(value):
    """'2024-01-01' or '20240101' → '20240101' (the only format the endpoint accepts)."""
    if value is None:
        return None
    digits = str(value).replace("-", "")
    datetime.strptime(digits, "%Y%m%d")  # validate
    return digits


def normalise(item, fetched_at):
    """IDX announcement item → flat row. Keeps the raw item for re-processing."""
    attachments = [
        {
            "url": a.get("FullSavePath"),
            "filename": a.get("PDFFilename"),
            "original_filename": a.get("OriginalFilename"),
            "is_attachment": bool(a.get("IsAttachment")),
        }
        for a in item.get("Attachments") or []
        if a.get("FullSavePath")
    ]
    code = (item.get("Code") or "").strip().upper()
    return {
        "id": item["Id"],
        "announcement_no": item.get("AnnouncementNo"),
        "ticker": code or None,
        "title": (item.get("Title") or "").strip(),
        "subject": (item.get("Perihal") or "").strip() or None,
        "jenis": item.get("Jenis"),
        "publish_time": item.get("PublishDate"),
        "fetched_at": fetched_at,
        "attachments": attachments,
        "raw": item,
    }


@dataclass
class RunResult:
    keywords: str
    mode: str
    started_at: str
    finished_at: str | None = None
    status: str = "running"  # ok | partial | failed
    pages: int = 0
    seen: int = 0
    new_items: int = 0
    attachments_downloaded: int = 0
    attachment_errors: int = 0
    schema_warnings: list[str] = field(default_factory=list)
    median_latency_s: float | None = None
    error: str | None = None


class AnnouncementStore:
    """File-backed store for announcement rows, attachments, cursors and run logs."""

    def __init__(self, base_dir=ANNOUNCEMENTS_DIR):
        self.base_dir = base_dir
        self.items_dir = os.path.join(base_dir, "items")
        self.files_dir = os.path.join(base_dir, "files")
        self.attachments_file = os.path.join(base_dir, "attachments.jsonl")
        self.state_file = os.path.join(base_dir, "state.json")
        self.runs_file = os.path.join(base_dir, "runs.jsonl")
        self._ids: set[str] | None = None
        self._attachments: dict[str, dict] | None = None

    # --- rows ---

    def iter_months(self, newest_first=False):
        """Rows per month. Order inside a month is collection order, not publish order.

        A month is ``YYYY-MM.jsonl`` and/or ``YYYY-MM.jsonl.gz`` (closed months compressed by ``idx cleanup``;
        late items for a compressed month land in a new plain file until the next cleanup merges them).
        """
        if not os.path.isdir(self.items_dir):
            return
        months = sorted(
            {
                n.split(".")[0]
                for n in os.listdir(self.items_dir)
                if n.endswith((".jsonl", ".jsonl.gz"))
            },
            reverse=newest_first,
        )
        for month in months:
            rows = []
            for name, opener in ((f"{month}.jsonl.gz", gzip.open), (f"{month}.jsonl", open)):
                path = os.path.join(self.items_dir, name)
                if os.path.exists(path):
                    with opener(path, "rt", encoding="utf-8") as f:
                        rows += [json.loads(line) for line in f if line.strip()]
            yield rows

    def iter_rows(self):
        for rows in self.iter_months():
            yield from rows

    def has(self, item_id):
        if self._ids is None:
            self._ids = {r["id"] for r in self.iter_rows()}
        return item_id in self._ids

    def add(self, row):
        month = (row.get("publish_time") or row["fetched_at"])[:7]
        os.makedirs(self.items_dir, exist_ok=True)
        _append_jsonl(os.path.join(self.items_dir, f"{month}.jsonl"), row)
        if self._ids is not None:
            self._ids.add(row["id"])

    # --- attachments ---

    def attachment(self, url):
        if self._attachments is None:
            self._attachments = {}
            if os.path.exists(self.attachments_file):
                with open(self.attachments_file, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            rec = json.loads(line)
                            self._attachments[rec["url"]] = rec
        return self._attachments.get(url)

    def save_attachment(self, url, content, content_type, fetched_at):
        sha = hashlib.sha256(content).hexdigest()
        rel_path = os.path.join("files", sha[:2], f"{sha}.pdf")
        path = os.path.join(self.base_dir, rel_path)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(content)
            os.replace(tmp, path)
        rec = {
            "url": url,
            "sha256": sha,
            "size": len(content),
            "content_type": content_type,
            "path": rel_path.replace(os.sep, "/"),
            "fetched_at": fetched_at,
        }
        self.attachment(url)  # make sure the index is loaded
        assert self._attachments is not None
        self._attachments[url] = rec
        _append_jsonl(self.attachments_file, rec)
        return rec

    # --- cursor & runs ---

    def cursor(self, keywords):
        return load_json(self.state_file, {}).get("cursors", {}).get(keywords)

    def set_cursor(self, keywords, publish_time):
        state = load_json(self.state_file, {})
        state.setdefault("cursors", {})[keywords] = publish_time
        os.makedirs(self.base_dir, exist_ok=True)
        save_json(self.state_file, state)

    def log_run(self, result):
        os.makedirs(self.base_dir, exist_ok=True)
        _append_jsonl(self.runs_file, asdict(result))

    def recent_runs(self, n=10):
        if not os.path.exists(self.runs_file):
            return []
        with open(self.runs_file, encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        return [json.loads(line) for line in lines[-n:]]


def _append_jsonl(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _now():
    """Current time in WIB with offset; IDX publish times are naive WIB."""
    return datetime.now(WIB).replace(microsecond=0).isoformat()


def _latency_s(published, fetched_at):
    return (
        datetime.fromisoformat(fetched_at) - datetime.fromisoformat(published).replace(tzinfo=WIB)
    ).total_seconds()


def _download_attachments(row, store, client, result):
    for att in row["attachments"]:
        rec = store.attachment(att["url"])
        if rec is None:
            response = client.get(att["url"])
            if response is None or response.status_code != 200:
                log.warning("Attachment download failed: %s", att["url"])
                result.attachment_errors += 1
                continue
            rec = store.save_attachment(
                att["url"],
                response.content,
                response.headers.get("content-type"),
                _now(),
            )
            result.attachments_downloaded += 1
        att.update({k: rec[k] for k in ("sha256", "size", "content_type", "path")})


def collect(
    keywords="",
    date_from=None,
    date_to=None,
    max_pages=None,
    page_size=100,
    download=True,
    client=None,
    store=None,
):
    """Collect announcements into the store. Returns a RunResult (also appended to runs.jsonl)."""
    client = client or IDXClient()
    store = store or AnnouncementStore()
    date_from, date_to = to_idx_date(date_from), to_idx_date(date_to)

    cursor = None
    mode = "backfill" if date_from else "incremental"
    if mode == "incremental":
        cursor = store.cursor(keywords)
        if cursor is None:
            date_from = (datetime.now(WIB) - timedelta(days=FIRST_RUN_LOOKBACK_DAYS)).strftime(
                "%Y%m%d"
            )
    stop_before = (datetime.fromisoformat(cursor) - CURSOR_OVERLAP).isoformat() if cursor else None

    result = RunResult(keywords=keywords, mode=mode, started_at=_now())
    newest = None
    latencies = []
    page = 1
    reached_end = False

    while max_pages is None or page <= max_pages:
        data = fetch_all_announcements(
            keywords=keywords,
            page_number=page,
            page_size=page_size,
            date_from=date_from,
            date_to=date_to,
            client=client,
        )
        if data is None:
            result.status, result.error = "failed", f"no response for page {page}"
            break
        warnings = validate_schema(data, "all_announcement")
        if warnings:
            result.schema_warnings.extend(warnings)
        if page == 1:
            check_schema_drift("all_announcement", data)
        result.pages += 1

        items = data.get("Items") or []
        fetched_at = _now()
        for item in items:
            published = item.get("PublishDate") or ""
            if stop_before and published < stop_before:
                reached_end = True
                break
            result.seen += 1
            if newest is None or published > newest:
                newest = published
            if not item.get("Id") or store.has(item["Id"]):
                continue
            row = normalise(item, fetched_at)
            if download:
                _download_attachments(row, store, client, result)
            store.add(row)
            result.new_items += 1
            if published and mode == "incremental":  # backfill latency is just item age
                latencies.append(_latency_s(published, fetched_at))

        if reached_end or not items or page >= int(data.get("PageCount") or 0):
            reached_end = True
            break
        page += 1

    if result.status == "running":
        result.status = "ok" if reached_end else "partial"  # partial: stopped by max_pages
    # Advance the cursor only after an incremental run that reached already-collected ground.
    if mode == "incremental" and result.status == "ok" and reached_end and newest:
        store.set_cursor(keywords, max(newest, cursor or ""))
    if latencies:
        result.median_latency_s = statistics.median(latencies)
    result.finished_at = _now()
    store.log_run(result)
    log.info(
        "Announcements (%s, keywords=%r): %s – %d pages, %d new, %d PDFs downloaded",
        mode,
        keywords,
        result.status,
        result.pages,
        result.new_items,
        result.attachments_downloaded,
    )
    return result


def search(query="", ticker="", limit=15, store=None):
    """Search stored announcements, newest first, by title/subject keyword and ticker."""
    store = store or AnnouncementStore()
    query, ticker = query.lower(), ticker.upper()
    results = []
    for rows in store.iter_months(newest_first=True):
        matches = [
            {k: v for k, v in row.items() if k != "raw"}
            for row in rows
            if (not ticker or row.get("ticker") == ticker)
            and (not query or query in f"{row.get('title', '')} {row.get('subject') or ''}".lower())
        ]
        results.extend(sorted(matches, key=lambda r: r.get("publish_time") or "", reverse=True))
        if len(results) >= limit:
            break
    return results[:limit]
