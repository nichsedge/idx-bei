"""
Tests for the deal tracker and rights-issue tracker (idx.deals) and their API endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from idx.api import _TTL_CACHE, app
from idx.deals import (
    backdoor_score,
    build_capital_raises,
    list_deals,
    list_rights,
    ticker_corporate_actions,
    tracked_tickers,
)


def _row(id_, ticker, date_, added, after, kind="hmetd"):
    return {
        "id": id_,
        "KodeEmiten": ticker,
        "TanggalPencatatan": f"{date_}T00:00:00",
        "JenisTindakan": kind,
        "JumlahSaham": added,
        "JumlahSahamSetelahTindakan": after,
    }


ACTIONS = {
    "totalRecordsAllTypes": 7,
    "categories": {
        "hmetd": {
            "count": 5,
            "data": [
                # AAAA: one issue listed in two chained batches (1000 → 1500 → 2000)
                _row(1, "AAAA", "2025-01-10", 500, 1500),
                _row(2, "AAAA", "2025-01-20", 500, 2000),
                # AAAA: second issue a year later → serial issuer
                _row(3, "AAAA", "2026-01-15", 2000, 4000),
                # BBBB: inconsistent IDX row (added ≥ after) is skipped
                _row(4, "BBBB", "1994-05-31", 900, 900),
                _row(5, " cccc ", "2026-03-01", 100, 1100),
            ],
        },
        "tanpaHmetd": {
            "count": 1,
            "data": [_row(6, "DDDD", "2026-02-01", 300, 1300, "tanpaHmetd")],
        },
        "stockSplit": {
            "count": 1,
            "data": [_row(7, "AAAA", "2024-06-01", 500, 1000, "stockSplit")],
        },
    },
}


def test_build_capital_raises_merges_batches_and_flags():
    raises = build_capital_raises(ACTIONS)
    by_id = {r["id"]: r for r in raises}

    assert [r["listing_date"] for r in raises] == sorted(
        (r["listing_date"] for r in raises), reverse=True
    )
    assert 4 not in by_id  # skipped
    assert 2 not in by_id  # merged into 1

    first = by_id[1]
    assert first["tranches"] == 2
    assert first["new_shares"] == 1000
    assert first["shares_before"] == 1000
    assert first["shares_after"] == 2000
    assert first["last_listing_date"] == "2025-01-20"
    assert first["dilution_pct"] == 50
    assert first["flags"] == ["LARGE"]

    second = by_id[3]
    assert second["raises_in_36m"] == 2
    assert second["flags"] == ["LARGE", "SERIAL"]

    assert by_id[5]["ticker"] == "CCCC"
    assert by_id[5]["flags"] == []

    placement = by_id[6]
    assert placement["type"] == "private_placement"
    assert placement["size_vs_old_pct"] == 30
    assert placement["flags"] == ["PP_OVER_10"]


def test_unchained_batches_are_not_merged():
    actions = {
        "categories": {
            "hmetd": {
                "data": [
                    _row(1, "EEEE", "2025-01-10", 10, 110),
                    _row(2, "EEEE", "2025-01-12", 10, 500),
                ]
            }
        }
    }
    assert len(build_capital_raises(actions)) == 2


def test_ticker_corporate_actions():
    history = ticker_corporate_actions(ACTIONS, "aaaa")
    assert [h["category"] for h in history] == ["hmetd", "hmetd", "hmetd", "stockSplit"]
    assert history[0]["listing_date"] == "2026-01-15"


def test_backdoor_score_labels():
    assert backdoor_score(None)["score"] == 0
    possible = backdoor_score({"control_change": True, "business_change_plan": True})
    assert (possible["score"], possible["label"]) == (40, "Possible")
    assert sum(s["fired"] for s in possible["signals"]) == 2
    likely = backdoor_score(
        {
            "control_change": True,
            "business_change_plan": True,
            "different_sector": True,
            "shell_like_target": True,
        }
    )
    assert (likely["score"], likely["label"]) == (70, "Likely backdoor")
    assert (
        backdoor_score(
            {
                k: True
                for k in (
                    "control_change",
                    "different_sector",
                    "shell_like_target",
                    "business_change_plan",
                    "large_capital_injection",
                    "jumbo_ng_trades",
                    "price_spike",
                )
            }
        )["score"]
        == 100
    )


def test_list_deals_enriches_and_sorts():
    deals_file = {
        "updated_at": "2026-10-23",
        "deals": [
            {"id": "old", "announced_at": "2024-01-01", "events": [{"event_date": "2024-01-01"}]},
            {
                "id": "new",
                "pre_announcement_price": 100,
                "signals": {"control_change": True},
                "events": [
                    {"event_date": "2025-10-22", "stake_pct": 60, "review_status": "pending"},
                    {"event_date": "2025-11-01", "tender_price": 122, "review_status": "approved"},
                ],
            },
        ],
    }
    res = list_deals(deals_file)
    assert [d["id"] for d in res["deals"]] == ["new", "old"]
    new = res["deals"][0]
    assert round(new["tender_premium_pct"], 6) == 22
    assert new["last_event_date"] == "2025-11-01"
    assert new["pending_review"] == 1
    assert new["backdoor"]["score"] == 20
    assert res["deals"][1]["tender_premium_pct"] is None


def test_list_rights_terms_and_tracked_tickers():
    rights_file = {
        "updated_at": "2026-10-23",
        "rights": [
            {
                "id": "FORU-RI-I",
                "ticker": "FORU",
                "status": "completed",
                "terms": {
                    "ratio_old": 100,
                    "ratio_new": 46235,
                    "exercise_price": 126,
                    "cum_price": 2560,
                },
                "events": [{"event_date": "2026-09-14", "review_status": "pending"}],
            },
            {
                "id": "YELO-W",
                "ticker": "YELO",
                "status": "watch",
                "announced_at": "2026-10-02",
                "events": [],
            },
        ],
    }
    res = list_rights(rights_file)
    assert [r["id"] for r in res["rights"]] == ["YELO-W", "FORU-RI-I"]
    foru = res["rights"][1]
    assert foru["new_per_old"] == 462.35
    assert round(foru["terp"], 2) == round((100 * 2560 + 46235 * 126) / 46335, 2)  # ~131.25
    assert foru["pending_review"] == 1
    assert res["rights"][0]["terp"] is None and res["rights"][0]["last_event_date"] == "2026-10-02"

    deals_file = {
        "deals": [
            {"target_ticker": "NAYZ", "status": "active"},
            {"target_ticker": "OLD", "status": "completed"},
        ]
    }
    assert tracked_tickers(deals_file, rights_file) == ["NAYZ", "YELO"]


def test_api_endpoints():
    client = TestClient(app)
    _TTL_CACHE.pop("rights_issues", None)
    with (
        patch("idx.deals.load_corporate_actions", return_value=ACTIONS),
        patch("idx.deals.load_deals", return_value={"updated_at": "x", "deals": []}),
        patch("idx.deals.load_rights", return_value={"updated_at": "y", "rights": []}),
    ):
        rights = client.get("/api/rights-issues").json()
        assert len(rights["raises"]) == 4
        assert "SERIAL" in rights["flag_labels"]
        assert client.get("/api/corporate-actions/DDDD").json()[0]["category"] == "tanpaHmetd"
        assert client.get("/api/deals").json() == {"updated_at": "x", "deals": []}
        assert client.get("/api/rights-pipeline").json() == {"updated_at": "y", "rights": []}
    _TTL_CACHE.pop("rights_issues", None)
