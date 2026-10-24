"""
Tests for retention and compaction (idx.pipelines.cleanup) and the weekly worker schedule.
"""

import json
import os
from datetime import datetime
from datetime import time as dtime

from idx.pipelines.announcements import WIB, AnnouncementStore
from idx.pipelines.cleanup import run_cleanup
from idx.worker import DailyAt

NOW = datetime(2026, 10, 25, 3, 0, tzinfo=WIB)  # a Sunday


def _row(i, ticker, published, urls=()):
    return {
        "id": f"id{i}",
        "ticker": ticker,
        "title": f"t{i}",
        "publish_time": published,
        "fetched_at": published + "+07:00",
        "attachments": [{"url": u} for u in urls],
        "raw": {"Id": f"id{i}", "Title": f"t{i}"},
    }


def _setup(tmp_path):
    data = tmp_path / "data"
    store = AnnouncementStore(str(data / "announcements"))
    store.add(_row(1, "AAAA", "2026-09-10T10:00:00", ["u-old-deal"]))
    store.add(
        _row(2, "BBBB", "2026-09-11T10:00:00", ["u-old", "u-old-scan", "u-old-notext", "u-shared"])
    )
    store.add(_row(3, "BBBB", "2026-10-20T10:00:00", ["u-new"]))
    store.add(_row(4, "AAAA", "2026-09-12T10:00:00", ["u-shared-deal"]))
    store.add(_row(5, "CCCC", "2026-09-13T10:00:00", ["u-old-rights"]))

    def pdf(url, fetched, text=None, ocr=None, path=None):
        rec = store.save_attachment(url, f"%PDF {url}".encode(), "application/pdf", fetched)
        if path:  # simulate two URLs with identical content (same content-addressed file)
            rec = {**rec, "path": path}
            with open(store.attachments_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        stem = os.path.splitext(os.path.join(store.base_dir, rec["path"]))[0]
        if text is not None:
            open(stem + ".txt", "w", encoding="utf-8").write(text)
        if ocr is not None:
            open(stem + ".ocr.txt", "w", encoding="utf-8").write(ocr)
        return rec

    long_text = "Nilai transaksi sebesar Rp113.500.000.000 untuk pengalihan aset dan usaha."
    old = "2026-06-01T10:00:00+07:00"
    pdf("u-old-deal", old, text=long_text)  # deal ticker → kept
    pdf("u-old-rights", old, text=long_text)  # rights-tracker ticker → kept
    pdf("u-old", old, text=long_text)  # old, text cached → removed
    pdf("u-old-scan", old, text="", ocr=long_text)  # old scan with OCR text → removed
    pdf("u-old-notext", old)  # old, no text cached → kept
    pdf("u-new", "2026-10-20T10:00:00+07:00", text=long_text)  # young → kept
    shared = pdf("u-shared", old, text=long_text)
    pdf(
        "u-shared-deal", old, text=long_text, path=shared["path"]
    )  # same file also used by a deal → kept

    (data / "deals.json").write_text(
        json.dumps({"deals": [{"target_ticker": "AAAA"}]}), encoding="utf-8"
    )
    (data / "rights.json").write_text(
        json.dumps({"rights": [{"ticker": "CCCC"}]}), encoding="utf-8"
    )

    dossiers = data / "dossiers"
    dossiers.mkdir()
    for d in range(1, 10):
        p = dossiers / f"AAAA_202610{d:02d}.md"
        p.write_text("x" * 100)
        os.utime(p, (1_700_000_000 + d, 1_700_000_000 + d))
    screens = data / "screens"
    screens.mkdir()
    for d in range(1, 10):
        for ext in (".md", ".json"):
            p = screens / f"screen_2025-01-01_2026-10-{d:02d}{ext}"
            p.write_text("y" * 100)
            os.utime(p, (1_700_000_000 + d, 1_700_000_000 + d))

    with open(store.runs_file, "w", encoding="utf-8") as f:
        f.writelines(f'{{"run": {i}}}\n' for i in range(20))
    return data, store


def test_dry_run_changes_nothing(tmp_path):
    data, store = _setup(tmp_path)
    before = sorted(str(p) for p in data.rglob("*"))
    rep = run_cleanup(apply=False, data_dir=str(data), now=NOW, log_lines=10)
    assert sorted(str(p) for p in data.rglob("*")) == before
    assert rep.counts == {
        "months compressed": 1,
        "PDFs removed": 2,  # u-old, u-old-scan (u-shared shares its file with a deal PDF)
        "old outputs removed": 6,  # 2 dossiers + 2 screen md/json pairs
        "logs trimmed": 1,
    }
    assert rep.freed > 0 and "dry run" in rep.summary()


def test_apply_compresses_prunes_and_trims(tmp_path):
    data, store = _setup(tmp_path)
    rows_before = sorted(r["id"] for r in store.iter_rows())

    run_cleanup(apply=True, data_dir=str(data), now=NOW, log_lines=10)

    items = sorted(os.listdir(store.items_dir))
    assert items == [
        "2026-09.jsonl.gz",
        "2026-10.jsonl",
    ]  # closed month compressed, current month plain
    fresh = AnnouncementStore(store.base_dir)
    assert sorted(r["id"] for r in fresh.iter_rows()) == rows_before
    assert (
        fresh.has("id2")
        and next(r for r in fresh.iter_rows() if r["id"] == "id2")["raw"]["Title"] == "t2"
    )

    def exists(url):
        rec = fresh.attachment(url)
        return os.path.exists(os.path.join(fresh.base_dir, rec["path"]))

    assert not exists("u-old") and not exists("u-old-scan")
    assert (
        exists("u-old-deal")
        and exists("u-old-rights")
        and exists("u-old-notext")
        and exists("u-new")
        and exists("u-shared")
    )
    # text stays cached for digests
    assert os.path.exists(
        os.path.splitext(os.path.join(fresh.base_dir, fresh.attachment("u-old")["path"]))[0]
        + ".txt"
    )

    assert sorted(os.listdir(data / "dossiers")) == [f"AAAA_202610{d:02d}.md" for d in range(3, 10)]
    assert len(os.listdir(data / "screens")) == 14  # 7 md/json pairs
    with open(store.runs_file, encoding="utf-8") as f:
        assert [json.loads(line)["run"] for line in f] == list(range(10, 20))


def test_late_rows_for_compressed_month_are_merged(tmp_path):
    data, store = _setup(tmp_path)
    run_cleanup(apply=True, data_dir=str(data), now=NOW)
    store = AnnouncementStore(store.base_dir)
    store.add(_row(9, "CCCC", "2026-09-30T10:00:00"))  # late backfill row
    assert sorted(os.listdir(store.items_dir)) == [
        "2026-09.jsonl",
        "2026-09.jsonl.gz",
        "2026-10.jsonl",
    ]
    assert "id9" in {r["id"] for r in AnnouncementStore(store.base_dir).iter_rows()}

    run_cleanup(apply=True, data_dir=str(data), now=NOW)
    assert sorted(os.listdir(store.items_dir)) == ["2026-09.jsonl.gz", "2026-10.jsonl"]
    assert len(list(AnnouncementStore(store.base_dir).iter_rows())) == 6


def test_weekly_schedule():
    s = DailyAt(dtime(3, 0), until=dtime(6, 0), retry_minutes=60, trading_only=False, weekdays=(6,))
    assert s.due(datetime(2026, 10, 25, 3, 0, tzinfo=WIB), None, None, trading=False)  # Sunday
    assert not s.due(datetime(2026, 10, 26, 3, 0, tzinfo=WIB), None, None, trading=True)  # Monday
    assert not s.due(
        datetime(2026, 10, 25, 7, 0, tzinfo=WIB), None, None, trading=False
    )  # after cut-off
    assert s.describe().startswith("weekly Sun 03:00")
