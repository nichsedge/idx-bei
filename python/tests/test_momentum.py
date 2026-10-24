"""
Tests for the momentum rank board (idx.momentum) with synthetic daily prices.
"""

import json

import pandas as pd
from fastapi.testclient import TestClient

import idx.momentum as momentum
from idx.api import _TTL_CACHE, app
from idx.momentum import build_board, compute_momentum


def _prices():
    dates = pd.bdate_range("2025-10-01", periods=260)
    rows = []
    for i, d in enumerate(dates):
        rows += [
            {
                "StockCode": "UPUP",
                "Date": d,
                "Close": 100 * (1.01**i),
                "Value": 1e9 if i < 240 else 3e9,
            },
            {"StockCode": "DOWN", "Date": d, "Close": 1000 * (0.995**i), "Value": 1e9},
            {"StockCode": "FLAT", "Date": d, "Close": 500.0, "Value": 1e9},
            # one-day 60% drop (an unadjusted rights-issue ex-date) on day 230
            {"StockCode": "RITE", "Date": d, "Close": 400.0 if i < 230 else 160.0, "Value": 1e9},
            # 1:5 split on day 240: IDX sets Previous to the adjusted reference price
            {
                "StockCode": "SPLT",
                "Date": d,
                "Close": 1000.0 if i < 240 else 200.0,
                "Previous": 200.0 if i == 240 else (1000.0 if i < 240 else 200.0),
                "Value": 1e9,
            },
        ]
        if i < 100:  # stopped trading long ago → excluded
            rows.append({"StockCode": "GONE", "Date": d, "Close": 50.0, "Value": 1e8})
    index = [
        {"IndexCode": "COMPOSITE", "Date": d, "Close": 7000.0 * (0.999**i)}
        for i, d in enumerate(dates)
    ]
    return pd.DataFrame(rows), pd.DataFrame(index)


def test_compute_momentum_metrics_and_ranks():
    prices, index = _prices()
    m, market = compute_momentum(prices, index)

    assert set(m.index) == {"UPUP", "DOWN", "FLAT", "RITE", "SPLT"}  # GONE is stale
    assert market["universe"] == 5 and market["trading_days"] == 260
    assert round(m.loc["UPUP", "r1M"], 4) == round(1.01**21 - 1, 4)
    assert m.loc["FLAT", "r3M"] == 0
    assert round(m.loc["UPUP", "xs3M"], 4) == round((1.01**63 - 1) - (0.999**63 - 1), 4)
    assert m.loc["UPUP", "from_high"] == 0 and m.loc["UPUP", "above_ma20"]
    assert m.loc["DOWN", "from_high"] < 0 and not m.loc["DOWN", "above_ma50"]
    assert (
        round(m.loc["UPUP", "value_20_60"], 2) == 1.8
    )  # last 20d at 3e9 vs 60d (20×3e9 + 40×1e9)/60
    assert m.loc["RITE", "adj_warning"] and not m.loc["UPUP", "adj_warning"]
    # the split is adjusted away: flat price, no warning, ex-date reported
    assert m.loc["SPLT", "r3M"] == 0 and m.loc["SPLT", "from_high"] == 0
    assert not m.loc["SPLT", "adj_warning"]
    assert m.loc["SPLT", "last_adjustment"] == {
        "date": prices["Date"].unique()[240].date().isoformat(),
        "factor": 0.2,
    }
    assert m.loc["RITE", "last_adjustment"] is None
    assert m.loc["UPUP", "market_rank"] == 1 and m["score"].idxmax() == "UPUP"
    assert m.loc["DOWN", "score"] < m.loc["FLAT", "score"]


def test_build_board_groups_and_json_safe():
    prices, index = _prices()
    m, market = compute_momentum(prices, index)
    deals = [
        {
            "target_ticker": "DOWN",
            "deal_type": "acquisition",
            "current_stage": "tender_offer",
            "status": "active",
            "backdoor": {"score": 40},
        },
        {
            "target_ticker": "GONE",
            "deal_type": "acquisition",
            "current_stage": "negotiation",
            "status": "active",
        },
    ]
    screen = {
        "date_from": "2025-01-01",
        "date_to": "2026-10-23",
        "candidates": [
            {
                "ticker": "FLAT",
                "signals": ["CC", "TO"],
                "stage": "tender offer",
                "score_ma": 8,
                "score_capital": 0,
                "last": "2026-10-01",
            },
            {
                "ticker": "UPUP",
                "signals": ["RI"],
                "stage": "",
                "score_ma": 0,
                "score_capital": 4,
                "last": "2026-09-01",
            },
        ],
    }
    rights = [{"ticker": "DOWN", "type": "rights_issue", "stage": "plan", "status": "watch"}]
    board = build_board(m, market, deals, screen, top=10, rights=rights)
    json.dumps(board)  # numpy types converted

    groups = {g["key"]: g for g in board["groups"]}
    assert [r["code"] for r in groups["rights"]["rows"]] == ["DOWN"]
    assert groups["rights"]["rows"][0]["context"] == "rights_issue · plan · watch"
    assert [r["code"] for r in groups["deals"]["rows"]] == [
        "DOWN",
        "GONE",
    ]  # no-price rows sort last
    assert groups["deals"]["rows"][0]["deal_score"] == 40 and groups["deals"]["rows"][1]["no_price"]
    assert [r["code"] for r in groups["screen_ma"]["rows"]] == ["FLAT"]
    assert groups["screen_ma"]["rows"][0]["context"] == "CC TO · tender offer"
    assert [r["code"] for r in groups["screen_capital"]["rows"]] == ["UPUP"]
    assert board["screen_period"] == "2025-01-01..2026-10-23"


def test_momentum_endpoint(monkeypatch):
    _TTL_CACHE.pop("momentum_board_5", None)
    calls = []

    def fake_load_board(deals, top, rights=None):
        calls.append(top)
        return {"market": {"as_of": "2026-10-22"}, "screen_period": None, "groups": []}

    monkeypatch.setattr(momentum, "load_board", fake_load_board)
    client = TestClient(app)
    assert client.get("/api/momentum/board?top=5").json()["market"]["as_of"] == "2026-10-22"
    client.get("/api/momentum/board?top=5")
    assert calls == [5]  # second call served from cache
    assert client.get("/api/momentum/board?top=0").status_code == 422
    _TTL_CACHE.pop("momentum_board_5", None)
