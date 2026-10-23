"""
Offline tests for the announcements collector (idx.pipelines.announcements) and the MCP search tool.

Fixtures are two real pages of /NewsAnnouncement/GetAllAnnouncement (keywords='pengambilalihan',
pageSize=3) recorded on 2026-10-23. No network calls.
"""

import copy
import hashlib
import json
import os

import pytest

import idx.pipelines.announcements as ann
import idx.scrapers.news as news
from idx.core.utils import validate_schema
from idx.mcp.server import handle_tool_call
from idx.pipelines.announcements import AnnouncementStore, collect, normalise, search, to_idx_date

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _page(n):
    with open(os.path.join(FIXTURES, f"announcements_page{n}.json"), encoding="utf-8") as f:
        return json.load(f)


PAGE1, PAGE2 = _page(1), _page(2)
EMPTY = {**PAGE1, "Items": [], "PageNumber": 3}


class FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": "application/pdf"}


class FakeClient:
    """Serves the recorded pages and fake PDFs; records every call."""

    def __init__(self, pages=None, fail_on_page=None):
        self.pages = pages or {1: PAGE1, 2: PAGE2}
        self.fail_on_page = fail_on_page
        self.json_calls = []
        self.downloads = []

    def get_json(self, endpoint, params=None):
        self.json_calls.append(dict(params))
        page = params["pageNumber"]
        if page == self.fail_on_page:
            return None
        return copy.deepcopy(self.pages.get(page, EMPTY))

    def get(self, url):
        self.downloads.append(url)
        return FakeResponse(b"%PDF-1.4 " + url.encode())


@pytest.fixture(autouse=True)
def no_snapshot_writes(monkeypatch):
    """Keep schema-drift snapshots out of the real data folder."""
    monkeypatch.setattr(ann, "check_schema_drift", lambda *a, **k: False)
    monkeypatch.setattr(news, "check_schema_drift", lambda *a, **k: False)


@pytest.fixture
def store(tmp_path):
    return AnnouncementStore(base_dir=str(tmp_path / "announcements"))


def _all_urls(*pages):
    return {a["FullSavePath"] for p in pages for i in p["Items"] for a in i["Attachments"]}


def test_to_idx_date():
    assert to_idx_date("2024-01-01") == "20240101"
    assert to_idx_date("20240101") == "20240101"
    assert to_idx_date(None) is None
    with pytest.raises(ValueError):
        to_idx_date("2024-13-01")


def test_normalise():
    item = PAGE1["Items"][0]
    row = normalise(item, "2026-10-23T01:00:00+07:00")
    assert row["id"] == item["Id"]
    assert row["ticker"] == "STRK"  # IDX pads Code with spaces
    assert row["publish_time"] == item["PublishDate"]
    assert row["fetched_at"] == "2026-10-23T01:00:00+07:00"
    assert [a["url"] for a in row["attachments"]] == [
        a["FullSavePath"] for a in item["Attachments"]
    ]
    assert row["attachments"][1]["is_attachment"] is True
    assert row["raw"] == item


def test_schema_validation_covers_item_keys():
    assert validate_schema(PAGE1, "all_announcement") == []
    drifted = copy.deepcopy(PAGE1)
    del drifted["Items"][0]["PublishDate"]
    warnings = validate_schema(drifted, "all_announcement")
    assert len(warnings) == 1 and "PublishDate" in warnings[0]


def test_backfill_persists_items_and_attachments(store):
    client = FakeClient()
    res = collect(keywords="pengambilalihan", date_from="2026-09-01", client=client, store=store)

    assert res.status == "ok" and res.mode == "backfill"
    assert (res.pages, res.new_items) == (3, 6)
    assert client.json_calls[0]["dateFrom"] == "20260901"
    assert "dateTo" not in client.json_calls[0]

    rows = list(store.iter_rows())
    assert len(rows) == 6
    assert {r["publish_time"][:7] for r in rows} == {"2026-09", "2026-10"}
    assert sorted(os.listdir(store.items_dir)) == ["2026-09.jsonl", "2026-10.jsonl"]

    urls = _all_urls(PAGE1, PAGE2)
    assert sorted(client.downloads) == sorted(urls)
    assert res.attachments_downloaded == len(urls)
    for row in rows:
        for att in row["attachments"]:
            content = b"%PDF-1.4 " + att["url"].encode()
            assert att["sha256"] == hashlib.sha256(content).hexdigest()
            assert att["size"] == len(content)
            with open(os.path.join(store.base_dir, att["path"]), "rb") as f:
                assert f.read() == content

    assert store.cursor("pengambilalihan") is None  # backfill never moves the incremental cursor
    assert store.recent_runs()[-1]["new_items"] == 6


def test_rerun_is_idempotent(store):
    collect(keywords="x", date_from="20260901", client=FakeClient(), store=store)
    client = FakeClient()
    res = collect(
        keywords="x", date_from="20260901", client=client, store=AnnouncementStore(store.base_dir)
    )
    assert res.new_items == 0
    assert client.downloads == []
    assert len(list(store.iter_rows())) == 6


def test_no_download_flag(store):
    client = FakeClient()
    res = collect(date_from="20260901", download=False, client=client, store=store)
    assert res.new_items == 6 and client.downloads == []
    assert "sha256" not in next(store.iter_rows())["attachments"][0]


def test_first_incremental_run_looks_back_and_sets_cursor(store):
    client = FakeClient()
    res = collect(keywords="k", client=client, store=store)
    assert res.mode == "incremental" and res.status == "ok"
    assert len(client.json_calls[0]["dateFrom"]) == 8
    assert store.cursor("k") == PAGE1["Items"][0]["PublishDate"]


def test_incremental_stops_at_cursor(store):
    # Cursor at the newest page-2 item: page-2 items ≥ cursor − 24h are re-seen; older ones end the run.
    newest_p2 = PAGE2["Items"][0]["PublishDate"]  # 2026-09-16T19:05:59
    store.set_cursor("k", newest_p2)
    client = FakeClient()
    res = collect(keywords="k", client=client, store=store, download=False)

    assert res.status == "ok"
    assert "dateFrom" not in client.json_calls[0]
    assert [c["pageNumber"] for c in client.json_calls] == [1, 2]
    stored = {r["publish_time"] for r in store.iter_rows()}
    assert "2026-09-08T17:39:29" not in stored  # older than cursor − 24h: not collected
    assert newest_p2 in stored
    assert store.cursor("k") == PAGE1["Items"][0]["PublishDate"]


def test_failed_run_keeps_items_but_not_cursor(store):
    store.set_cursor("k", "2026-01-01T00:00:00")
    res = collect(keywords="k", client=FakeClient(fail_on_page=2), store=store, download=False)
    assert res.status == "failed" and "page 2" in res.error
    assert res.new_items == 3
    assert store.cursor("k") == "2026-01-01T00:00:00"
    assert store.recent_runs()[-1]["status"] == "failed"


def test_max_pages_is_partial(store):
    store.set_cursor("k", "2026-01-01T00:00:00")
    res = collect(keywords="k", max_pages=1, client=FakeClient(), store=store, download=False)
    assert (res.status, res.pages) == ("partial", 1)
    assert store.cursor("k") == "2026-01-01T00:00:00"


def test_schema_warnings_recorded(store):
    drifted = copy.deepcopy(PAGE1)
    for item in drifted["Items"]:
        del item["Title"]
    res = collect(
        date_from="20260901", client=FakeClient(pages={1: drifted}), store=store, download=False
    )
    assert res.schema_warnings and "Title" in res.schema_warnings[0]


def test_latency_uses_wib(store, monkeypatch):
    item = PAGE1["Items"][0]  # published 2026-10-22T11:58:33 WIB (naive)
    one_page = {1: {**PAGE1, "Items": [item], "PageCount": 1}}
    monkeypatch.setattr(ann, "_now", lambda: "2026-10-22T05:58:33+00:00")  # = 12:58:33 WIB
    res = collect(client=FakeClient(pages=one_page), store=store, download=False)
    assert res.median_latency_s == 3600
    assert next(store.iter_rows())["fetched_at"] == "2026-10-22T05:58:33+00:00"

    backfill = collect(date_from="20260901", client=FakeClient(), store=store, download=False)
    assert backfill.median_latency_s is None  # item age, not collector latency


def test_search(store):
    collect(date_from="20260901", client=FakeClient(), store=store, download=False)
    assert [r["ticker"] for r in search(ticker="strk", store=store)] == ["STRK"]
    hits = search(query="pengambilalihan", limit=2, store=store)
    assert len(hits) == 2 and "raw" not in hits[0]
    assert hits[0]["publish_time"] >= hits[1]["publish_time"]
    assert search(query="no-such-text", store=store) == []


def test_mcp_search_uses_store_then_live_items(store, tmp_path, monkeypatch):
    collect(date_from="20260901", client=FakeClient(), store=store, download=False)
    monkeypatch.setattr(ann, "AnnouncementStore", lambda: AnnouncementStore(store.base_dir))

    stored = json.loads(handle_tool_call("idx_search_announcements", {"ticker": "STRK"}))
    assert [r["ticker"] for r in stored] == ["STRK"]

    # Empty store → live query; the response key is "Items", not "data".
    monkeypatch.setattr(
        ann, "AnnouncementStore", lambda: AnnouncementStore(str(tmp_path / "empty"))
    )
    monkeypatch.setattr(news, "fetch_all_announcements", lambda **kw: copy.deepcopy(PAGE2))
    live = json.loads(
        handle_tool_call("idx_search_announcements", {"ticker": PAGE2["Items"][0]["Code"].strip()})
    )
    assert live and live[0]["id"] == PAGE2["Items"][0]["Id"]
    assert "raw" not in live[0]
