"""
Retention and compaction for collected data (``idx cleanup``; weekly worker job).

Dry run by default: reports what would change and the space freed; ``apply=True`` makes the changes.

1. Compress closed months of announcement rows (``items/YYYY-MM.jsonl`` → ``.jsonl.gz``, raw IDX items kept).
   The current month (WIB) stays plain for appends; late rows for a compressed month are merged in.
2. Delete attachment PDFs older than ``pdf_days`` that no ticker in ``data/deals.json`` or ``data/rights.json`` uses, but only when their
   text is already cached (``.txt``, or ``.ocr.txt`` for scans) — digests keep working and any PDF can be
   re-downloaded from IDX. The attachment index is left as is.
3. Keep the newest ``keep_outputs`` digests per ticker (``data/dossiers``) and screens (``data/screens``).
4. Trim run logs (announcement and worker ``runs.jsonl``) to the last ``log_lines`` lines.
"""

import gzip
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from idx.core.utils import DATA_DIR, get_logger
from idx.pipelines.announcements import WIB, AnnouncementStore

log = get_logger("idx.pipelines.cleanup")

PDF_DAYS = 90
KEEP_OUTPUTS = 7
LOG_LINES = 5000
MIN_TEXT = 40


@dataclass
class Report:
    apply: bool
    actions: list[str] = field(default_factory=list)
    freed: int = 0  # bytes
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, kind: str, text: str, freed: int = 0) -> None:
        self.actions.append(text)
        self.freed += freed
        self.counts[kind] += 1

    def summary(self) -> str:
        mode = "applied" if self.apply else "dry run"
        parts = ", ".join(f"{k}: {v}" for k, v in sorted(self.counts.items())) or "nothing to do"
        return f"cleanup ({mode}): {parts}; space freed {self.freed / 1e6:.1f} MB"


def _size(path: str) -> int:
    return os.path.getsize(path) if os.path.exists(path) else 0


# ---------- 1. compress closed months ----------


def compress_months(store: AnnouncementStore, current_month: str, report: Report) -> None:
    if not os.path.isdir(store.items_dir):
        return
    for name in sorted(os.listdir(store.items_dir)):
        if not name.endswith(".jsonl"):
            continue
        month = name[: -len(".jsonl")]
        if month >= current_month:
            continue  # still receiving rows
        plain = os.path.join(store.items_dir, name)
        gz = plain + ".gz"
        before = _size(plain) + _size(gz)
        if not report.apply:
            # gzip of JSON lines is typically 5-7x smaller; estimate for the dry run
            report.add(
                "months compressed", f"compress {name} ({before / 1e6:.1f} MB)", int(before * 0.83)
            )
            continue
        tmp = gz + ".tmp"
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as out:
            if os.path.exists(gz):  # merge late rows into an already compressed month
                with gzip.open(gz, "rt", encoding="utf-8") as f:
                    for line in f:
                        out.write(line)
            with open(plain, encoding="utf-8") as f:
                for line in f:
                    out.write(line)
        os.replace(tmp, gz)
        os.remove(plain)
        report.add("months compressed", f"compressed {name} → {name}.gz", before - _size(gz))


# ---------- 2. old attachment PDFs ----------


def _deal_tickers(deals_file: str) -> set[str]:
    """Tickers in deals.json and in the rights.json beside it (tracked capital raises)."""
    out: set[str] = set()
    for path, key, ticker_field in (
        (deals_file, "deals", "target_ticker"),
        (os.path.join(os.path.dirname(deals_file), "rights.json"), "rights", "ticker"),
    ):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                out |= {d[ticker_field].upper() for d in json.load(f).get(key, [])}
    return out


def _text_cached(pdf_path: str) -> bool:
    stem = os.path.splitext(pdf_path)[0]
    txt, ocr = stem + ".txt", stem + ".ocr.txt"
    if os.path.exists(txt):
        with open(txt, encoding="utf-8") as f:
            if len(f.read().strip()) >= MIN_TEXT:
                return True
    return os.path.exists(ocr)


def prune_pdfs(
    store: AnnouncementStore, deals_file: str, now: datetime, days: int, report: Report
) -> None:
    if not os.path.exists(store.attachments_file):
        return
    keep_tickers = _deal_tickers(deals_file)
    keep_urls = {
        a["url"]
        for r in store.iter_rows()
        if (r.get("ticker") or "").upper() in keep_tickers
        for a in r.get("attachments", [])
    }
    cutoff = now - timedelta(days=days)
    seen_paths: set[str] = set()
    with open(store.attachments_file, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    # Several URLs can point to the same content-addressed file; keep it if any of them is needed.
    needed_paths = {r["path"] for r in records if r["url"] in keep_urls}
    for rec in records:
        path = rec["path"]
        if path in seen_paths or path in needed_paths:
            continue
        seen_paths.add(path)
        fetched = datetime.fromisoformat(rec["fetched_at"]) if rec.get("fetched_at") else None
        if fetched is None or fetched.astimezone(WIB) > cutoff:
            continue
        pdf = os.path.join(store.base_dir, path)
        if not os.path.exists(pdf) or not _text_cached(pdf):
            continue
        size = _size(pdf)
        if report.apply:
            os.remove(pdf)
        report.add("PDFs removed", f"remove {path} (fetched {rec['fetched_at'][:10]})", size)


# ---------- 3. old digests and screens ----------


def prune_outputs(dossier_dir: str, screen_dir: str, keep: int, report: Report) -> None:
    groups: dict[str, list[str]] = defaultdict(list)
    if os.path.isdir(dossier_dir):
        for name in os.listdir(dossier_dir):
            m = re.match(r"([A-Z0-9]+)_\d{8}\.md$", name)
            if m:
                groups[f"dossier {m[1]}"].append(os.path.join(dossier_dir, name))
    if os.path.isdir(screen_dir):
        for name in os.listdir(screen_dir):
            if name.startswith("screen_") and name.endswith(".md"):
                groups["screen"].append(os.path.join(screen_dir, name))
    for paths in groups.values():
        paths.sort(key=os.path.getmtime, reverse=True)
        for old in paths[keep:]:
            victims = [old] + (
                [old[:-3] + ".json"] if os.path.basename(old).startswith("screen_") else []
            )
            for v in victims:
                if os.path.exists(v):
                    size = _size(v)
                    if report.apply:
                        os.remove(v)
                    report.add("old outputs removed", f"remove {os.path.basename(v)}", size)


# ---------- 4. run logs ----------


def trim_logs(paths: list[str], max_lines: int, report: Report) -> None:
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) <= max_lines:
            continue
        before = _size(path)
        kept = lines[-max_lines:]
        if report.apply:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(kept)
            os.replace(tmp, path)
            freed = before - _size(path)
        else:
            freed = before - sum(len(line.encode()) for line in kept)
        report.add(
            "logs trimmed", f"trim {os.path.basename(path)} {len(lines)} → {max_lines} lines", freed
        )


def run_cleanup(
    apply: bool = False,
    pdf_days: int = PDF_DAYS,
    keep_outputs: int = KEEP_OUTPUTS,
    log_lines: int = LOG_LINES,
    data_dir: str = DATA_DIR,
    now: datetime | None = None,
) -> Report:
    now = now or datetime.now(WIB)
    store = AnnouncementStore(os.path.join(data_dir, "announcements"))
    report = Report(apply=apply)
    compress_months(store, now.strftime("%Y-%m"), report)
    prune_pdfs(store, os.path.join(data_dir, "deals.json"), now, pdf_days, report)
    prune_outputs(
        os.path.join(data_dir, "dossiers"), os.path.join(data_dir, "screens"), keep_outputs, report
    )
    trim_logs([store.runs_file, os.path.join(data_dir, "worker", "runs.jsonl")], log_lines, report)
    log.info(report.summary())
    return report
