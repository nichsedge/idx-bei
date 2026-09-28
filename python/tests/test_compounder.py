"""
Unit tests for Forensic Quality & Sector-Aware Compounder Engine.
"""

from idx.compounder import (
    calculate_dca_compounder_score,
    calculate_justified_pbv,
    enrich_company_intellect,
    evaluate_forensics,
    evaluate_sector_valuation,
    is_cyclical_sector,
    is_financial_sector,
)


def test_financial_sector_detection():
    assert is_financial_sector("Financials", "Banks") is True
    assert is_financial_sector("Energy", "Oil, Gas & Coal") is False
    assert is_financial_sector(None, "Bank Syariah") is True


def test_cyclical_sector_detection():
    assert is_cyclical_sector("Energy", "Coal") is True
    assert is_cyclical_sector("Basic Materials", "Mining") is True
    assert is_cyclical_sector("Consumer Non-Cyclicals", "Food") is False


def test_forensic_detects_one_off_trap():
    # LPKR scenario: Net profit (18k) >> Sales (9k), NPM 194%
    lpkr_mock = {
        "code": "LPKR",
        "sector": "Properties & Real Estate",
        "sales": 9250.0,
        "ebt": 19000.0,
        "profitPeriod": 18600.0,
        "npm": 194.0,
        "roe": 58.0,
        "equity": 30000.0,
        "opini": "WTP",
    }
    forensics = evaluate_forensics(lpkr_mock)
    assert forensics["is_value_trap"] is True
    assert "VALUE_TRAP_ONE_OFF" in forensics["flags"]

    valuation = evaluate_sector_valuation(lpkr_mock, forensics)
    assert valuation["status"] == "VALUE_TRAP"
    assert valuation["is_undervalued"] is False

    score = calculate_dca_compounder_score(lpkr_mock, forensics, valuation)
    assert score["verdict"] == "VALUE_TRAP"
    assert score["score"] <= 15.0


def test_justified_pbv_for_banks():
    # Bank Mandiri (BMRI) scenario: ROE 19.25%, Ke 10.5%, g 5.0%
    justified = calculate_justified_pbv(19.25, cost_of_equity=0.105, growth_rate=0.05)
    assert justified >= 2.4  # Justified PBV around 2.5x

    bmri_mock = {
        "code": "BMRI",
        "sector": "Financials",
        "subSector": "Banks",
        "pbv": 1.77,
        "roe": 19.25,
        "is_blue_chip": True,
        "equity": 300000.0,
    }
    forensics = evaluate_forensics(bmri_mock)
    assert forensics["is_value_trap"] is False

    valuation = evaluate_sector_valuation(bmri_mock, forensics)
    assert valuation["status"] == "SECTOR_UNDERVALUED"
    assert valuation["is_undervalued"] is True
    assert valuation["justified_pbv"] is not None

    score = calculate_dca_compounder_score(
        bmri_mock, forensics, valuation, trading_value=50_000_000_000
    )
    assert score["verdict"] == "PRIME_DCA"
    assert score["score"] >= 75.0


def test_enrich_company_intellect():
    asii_mock = {
        "code": "ASII",
        "name": "Astra International Tbk",
        "sector": "Industrials",
        "sales": 246000.0,
        "ebt": 40000.0,
        "profitPeriod": 33000.0,
        "npm": 13.8,
        "roe": 13.0,
        "pbv": 0.76,
        "per": 5.83,
        "deRatio": 0.79,
        "yield": 7.5,
        "is_blue_chip": True,
        "equity": 262000.0,
    }
    enriched = enrich_company_intellect(asii_mock, trading_value=20_000_000_000)
    assert enriched["is_value_trap"] is False
    assert enriched["is_undervalued"] is True
    assert enriched["compounder_score"] >= 70.0
    assert "ai_thesis" in enriched
    assert len(enriched["intellect_badges"]) > 0


def test_cli_compounder_parser():
    from idx.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["compounder", "--top", "15"])
    assert args.command == "compounder"
    assert args.top == 15
    assert args.ticker is None
    assert args.show_traps is False

    args_ticker = parser.parse_args(["compounder", "BBRI"])
    assert args_ticker.command == "compounder"
    assert args_ticker.ticker == "BBRI"

    args_traps = parser.parse_args(["compounder", "--show-traps"])
    assert args_traps.command == "compounder"
    assert args_traps.show_traps is True
