"""
Tests for corporate-action adjusted closes (idx.core.adjust).
"""

import pandas as pd

from idx.core.adjust import adjusted_closes, adjustment_events


def _rows(code, closes, previous):
    dates = pd.bdate_range("2026-09-14", periods=len(closes))
    return [
        {"StockCode": code, "Date": d.strftime("%Y-%m-%dT00:00:00"), "Close": c, "Previous": p}
        for d, c, p in zip(dates, closes, previous, strict=True)
    ]


def test_rights_issue_and_split_adjusted():
    # FORU-like rights issue: cum 2560, ex-date reference 131, then two later sessions
    rights = _rows("RITE", [4650, 2560, 176, 108], [4220, 4650, 131, 176])
    # two splits (1:5 then 1:2), plus a normal move on the last day
    split = _rows("SPLT", [1000, 200, 100, 110], [1000, 200, 100, 100])
    plain = _rows("PLAN", [50, 52, 51, 53], [49, 50, 52, 51])
    prices = pd.DataFrame(rights + split + plain)

    ev = adjustment_events(prices)
    assert sorted(ev["StockCode"]) == ["RITE", "SPLT", "SPLT"]
    assert round(float(ev.loc[ev.StockCode == "RITE", "factor"].iloc[0]), 4) == round(131 / 2560, 4)

    adj = adjusted_closes(prices)
    f = 131 / 2560
    assert list(adj["RITE"].round(4)) == [round(4650 * f, 4), 131.0, 176.0, 108.0]
    assert list(adj["SPLT"]) == [100.0, 100.0, 100.0, 110.0]
    assert list(adj["PLAN"]) == [50, 52, 51, 53]


def test_without_previous_returns_raw():
    prices = pd.DataFrame(_rows("RAW", [10, 20], [10, 10])).drop(columns="Previous")
    assert adjustment_events(prices).empty
    assert list(adjusted_closes(prices)["RAW"]) == [10, 20]
