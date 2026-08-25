"""Tests for idx.signals decision-support screens (pure DataFrame transforms)."""

import pandas as pd
import pytest

from idx.signals import (
    audit_risk_shield,
    dilution_watch,
    foreign_flow_radar,
    pasar_nego_crossing_screen,
    sharia_value_screen,
)


@pytest.fixture
def stock_df():
    return pd.DataFrame(
        {
            "Date": ["2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"] * 3,
            "StockCode": ["AAA"] * 4 + ["BBB"] * 4 + ["CCC"] * 4,
            "Close": [100.0] * 8 + [50.0] * 4,
            "Value": [5e9] * 8 + [1e8] * 4,  # CCC is illiquid
            "TradebleShares": [1e9] * 8 + [1e7] * 4,
            "NetForeignFlow": [30e6] * 4 + [-10e6] * 4 + [0.0] * 4,
            "NonRegularValue": [30e9] * 4 + [0.0] * 8,  # AAA has heavy nego crossing
            "NonRegularVolume": [3e8] * 4 + [0.0] * 8,
            "NonRegularFrequency": [10] * 4 + [0] * 8,
        }
    )


def test_pasar_nego_screen_flags_heavy_crossing(stock_df):
    out = pasar_nego_crossing_screen(stock_df, min_nego_val_rp=50e9, min_nego_pct=70.0)
    assert len(out) == 1
    assert out.iloc[0]["StockCode"] == "AAA"
    # Total nego: 4 * 30B = 120B
    assert out.iloc[0]["NegoValRpB"] == pytest.approx(120.0)
    # Total regular: 4 * 5B = 20B -> Share = 120 / (120 + 20) = 85.7%
    assert out.iloc[0]["NegoSharePct"] == pytest.approx(85.7, rel=1e-2)
    assert out.iloc[0]["NegoTrades"] == 40


def test_screens_handle_empty_input():
    empty = pd.DataFrame()
    assert foreign_flow_radar(empty).empty
    assert audit_risk_shield(empty).empty
    assert dilution_watch(empty).empty
    assert sharia_value_screen(empty).empty
    assert pasar_nego_crossing_screen(empty).empty


def test_radar_flags_accumulation_and_distribution(stock_df):
    out = foreign_flow_radar(stock_df, min_abs_pct_float=0.5)
    by_code = out.set_index("StockCode")

    assert set(out["Signal"]) == {"accumulate", "distribute"}
    # AAA: +120M shares / 1e9 float = 12% -> accumulate
    assert by_code.loc["AAA", "Signal"] == "accumulate"
    assert by_code.loc["AAA", "PctFloat"] == pytest.approx(12.0)
    # BBB: -40M / 1e9 = -4% -> distribute
    assert by_code.loc["BBB", "Signal"] == "distribute"
    assert by_code.loc["BBB", "PctFloat"] == pytest.approx(-4.0)
    # Sorted strongest first
    assert out["PctFloat"].is_monotonic_decreasing


def test_radar_filters_illiquid_and_zero_flow(stock_df):
    out = foreign_flow_radar(stock_df, min_turnover_rp=1e9)
    assert "CCC" not in set(out["StockCode"])  # turnover below floor


def test_radar_window_limits_sessions():
    df = pd.DataFrame(
        {
            "Date": pd.date_range("2026-01-01", periods=10).strftime("%Y-%m-%d"),
            "StockCode": ["AAA"] * 10,
            "Close": [100.0] * 10,
            "Value": [5e9] * 10,
            "TradebleShares": [1e9] * 10,
            "NetForeignFlow": [10e6] * 10,
        }
    )
    out = foreign_flow_radar(df, window_days=3)
    assert out.loc[0, "Sessions"] == 3


def test_audit_shield_flags_only_non_clean_latest_filing():
    ratios = pd.DataFrame(
        {
            "code": ["NEST", "NEST", "AMMN"],
            "stockName": ["A", "A", "C"],
            "fsDate": ["2025-12-31", "2024-12-31", "2025-12-31"],
            "opini": ["WDP", "WTM", "WTM"],
            "roe": [5.0, 4.0, 20.0],
            "per": [8.0, 7.0, 9.0],
        }
    )
    out = audit_risk_shield(ratios)
    # NEST flagged once on its LATEST filing; clean AMMN excluded
    assert list(out["code"]) == ["NEST"]
    assert out.loc[0, "opini"] == "WDP"
    assert str(out.loc[0, "fsDate"])[:10] == "2025-12-31"


def test_dilution_watch_scope_and_lookback():
    actions = pd.DataFrame(
        {
            "KodeEmiten": ["NEW", "OLD", "DIV", "FUT"],
            "TanggalPencatatan": [
                "2026-06-01",
                "2026-01-01",
                "2026-05-20",
                "2027-06-01",
            ],
            "JenisTindakan": [
                "Private Placement",
                "Rights Issue",
                "Dividend",
                "Warrant",
            ],
            "caType": ["PrivatePlacement", "kurangModal", "hmetd", "waran"],
        }
    )
    out = dilution_watch(actions, lookback_days=90, on_date="2026-08-25")
    assert list(out["KodeEmiten"]) == ["NEW"]  # OLD outside window, DIV not dilutive,
    # FUT in the future


def test_sharia_screen_filters_flag_valuation_and_opinion():
    ratios = pd.DataFrame(
        {
            "code": ["GOOD", "NONSHARIA", "EXPENSIVE", "WEAKROE", "RISKY", "STALE"],
            "stockName": ["g", "n", "e", "w", "r", "s"],
            "fsDate": ["2025-12-31"] * 6,
            "sharia": ["S", "-", "S", "S", "S", "S"],
            "per": [8.0, 5.0, 20.0, 5.0, 5.0, 5.0],
            "roe": [30.0, 50.0, 50.0, 5.0, 50.0, 50.0],
            "deRatio": [0.5] * 6,
            "priceBV": [1.0] * 6,
            "opini": ["WTM", "WTM", "WTM", "WTM", "WDP", "TMP"],
        }
    )
    out = sharia_value_screen(ratios)
    assert list(out["code"]) == ["GOOD"]
