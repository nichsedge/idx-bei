"""
Unit tests for the KSEI ownership parsing and delta engine.
"""

import pandas as pd
import pytest

from idx.core.ownership import (
    compute_ownership_deltas,
    get_multi_holding_individuals,
    get_tycoon_holdings,
    parse_indonesian_float,
)


def test_parse_indonesian_float():
    assert parse_indonesian_float("41,10") == 41.10
    assert parse_indonesian_float("3.200.142.830") == 3200142830.0
    assert parse_indonesian_float("0,05") == 0.05
    assert parse_indonesian_float(12.34) == 12.34
    assert parse_indonesian_float(None) == 0.0
    assert parse_indonesian_float("") == 0.0


def test_compute_ownership_deltas():
    prev_data = pd.DataFrame(
        [
            {
                "SHARE_CODE": "ABMM",
                "INVESTOR_NAME": "LO KHENG HONG",
                "InvestorUpper": "LO KHENG HONG",
                "ShareCode": "ABMM",
                "Pct": 5.0,
                "Shares": 100000000,
            },
            {
                "SHARE_CODE": "BBCA",
                "INVESTOR_NAME": "TYCOON A",
                "InvestorUpper": "TYCOON A",
                "ShareCode": "BBCA",
                "Pct": 2.0,
                "Shares": 50000000,
            },
        ]
    )

    curr_data = pd.DataFrame(
        [
            {
                "SHARE_CODE": "ABMM",
                "INVESTOR_NAME": "LO KHENG HONG",
                "InvestorUpper": "LO KHENG HONG",
                "ShareCode": "ABMM",
                "Pct": 5.62,
                "Shares": 112400000,
            },
            {
                "SHARE_CODE": "GJTL",
                "INVESTOR_NAME": "LO KHENG HONG",
                "InvestorUpper": "LO KHENG HONG",
                "ShareCode": "GJTL",
                "Pct": 6.02,
                "Shares": 209000000,
            },
        ]
    )

    deltas = compute_ownership_deltas(prev_data, curr_data, min_pct_delta=0.01)
    assert len(deltas) == 3

    # Check GJTL is NEW_POSITION
    gjtl = deltas[deltas["ShareCode"] == "GJTL"].iloc[0]
    assert gjtl["Action"] == "NEW_POSITION"
    assert gjtl["CurrPct"] == 6.02
    assert gjtl["PrevPct"] == 0.0

    # Check ABMM is ACCUMULATING
    abmm = deltas[deltas["ShareCode"] == "ABMM"].iloc[0]
    assert abmm["Action"] == "ACCUMULATING"
    assert abmm["PctDelta"] == pytest.approx(0.62)

    # Check BBCA is FULL_EXIT
    bbca = deltas[deltas["ShareCode"] == "BBCA"].iloc[0]
    assert bbca["Action"] == "FULL_EXIT"
    assert bbca["PctDelta"] == pytest.approx(-2.0)


def test_get_tycoon_holdings():
    df = pd.DataFrame(
        [
            {
                "SHARE_CODE": "ABMM",
                "ShareCode": "ABMM",
                "ISSUER_NAME": "ABM Investama",
                "INVESTOR_NAME": "LO KHENG HONG",
                "InvestorUpper": "LO KHENG HONG",
                "Pct": 5.62,
                "Shares": 154835300,
                "LOCAL_FOREIGN": "L",
                "INVESTOR_TYPE": "ID",
            },
            {
                "SHARE_CODE": "UNVR",
                "ShareCode": "UNVR",
                "ISSUER_NAME": "Unilever Indonesia",
                "INVESTOR_NAME": "OTHER INVESTOR",
                "InvestorUpper": "OTHER INVESTOR",
                "Pct": 10.0,
                "Shares": 500000000,
                "LOCAL_FOREIGN": "A",
                "INVESTOR_TYPE": "CP",
            },
        ]
    )

    tycoons = get_tycoon_holdings(df)
    assert len(tycoons) == 1
    assert tycoons.iloc[0]["ShareCode"] == "ABMM"
    assert tycoons.iloc[0]["TycoonLabel"] == "Lo Kheng Hong"


def test_get_multi_holding_individuals():
    df = pd.DataFrame(
        [
            {
                "SHARE_CODE": "TICK1",
                "ShareCode": "TICK1",
                "InvestorUpper": "MULTI INVESTOR",
                "INVESTOR_TYPE": "ID",
                "Pct": 2.0,
                "Shares": 100,
            },
            {
                "SHARE_CODE": "TICK2",
                "ShareCode": "TICK2",
                "InvestorUpper": "MULTI INVESTOR",
                "INVESTOR_TYPE": "ID",
                "Pct": 3.0,
                "Shares": 200,
            },
            {
                "SHARE_CODE": "TICK1",
                "ShareCode": "TICK1",
                "InvestorUpper": "SINGLE INVESTOR",
                "INVESTOR_TYPE": "ID",
                "Pct": 4.0,
                "Shares": 300,
            },
        ]
    )

    multi = get_multi_holding_individuals(df, min_tickers=2)
    assert len(multi) == 1
    assert multi.iloc[0]["InvestorUpper"] == "MULTI INVESTOR"
    assert multi.iloc[0]["TickerCount"] == 2
