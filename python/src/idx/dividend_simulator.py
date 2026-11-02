"""
Indonesian Dividend Reinvestment & Tax Drag Sovereign Runway Simulator.

Models the unique tax mechanics under UU Harmonisasi Peraturan Perpajakan (UU HPP No. 7/2021)
and UU Cipta Kerja (PMK No. 18/PMK.03/2021):
- Domestic Individual Taxpayers (WPOP DN):
  Dividends are EXEMPT from Income Tax (PPh Final 0% instead of 10%)
  if reinvested in qualified Indonesian instruments within 3 tax years
  and held for at least 3 consecutive fiscal years.
- Standard Tax Drag (10% PPh Final):
  Deducted if not reinvested within the statutory deadline.
- Foreign Taxpayers (WPLN):
  20% statutory withholding under PPh Pasal 26 or treaty rate.

Calculates the 'Sovereign Runway' (years/months of dividend-funded living expenses)
and quantifies the cumulative 'Tax Drag Gap' for premier IDX cash cows
(BBCA, BBRI, ASII, ADRO, BMRI, TLKM, PTBA, ICBP, BBNI).
"""

from __future__ import annotations

import datetime
import os
from typing import Any, cast

import pandas as pd

from idx.core.currency import get_usd_idr_rate
from idx.core.utils import DATA_DIR, get_logger, load_json

log = get_logger("idx.dividend_simulator")

DETAILS_FILE = os.path.join(DATA_DIR, "companyDetailsByKodeEmiten.json")
PARQUET_DIR = os.path.join(DATA_DIR, "parquet")

# Statutory Tax Rates
UU_CIPTA_KERJA_TAX_RATE = 0.00  # 0% PPh Final exemption if reinvested
STANDARD_WPOP_TAX_RATE = 0.10  # 10% PPh Final if unreinvested
FOREIGN_WPLN_TAX_RATE = 0.20  # 20% PPh Pasal 26 standard foreign withholding
CORPORATE_BADAN_TAX_RATE = 0.00  # 0% Corporate dividend exemption (UU Cipta Kerja)

# Curated Indonesian Dividend Cash Cows benchmark profiles
BENCHMARK_CASH_COWS: dict[str, dict[str, Any]] = {
    "BBCA": {
        "name": "Bank Central Asia Tbk",
        "sector": "Financials",
        "subsector": "Private Banking",
        "benchmark_yield_pct": 3.4,
        "historical_dpr_pct": 55.0,
        "dividend_cagr_pct": 11.5,
        "payout_frequency": "Semi-Annual (Interim + Final)",
        "moat": "Indonesia's largest private transaction bank; CASA dominance >80%; fortress balance sheet.",
        "sovereign_tier": "CORE_COMPOUNDER",
    },
    "BBRI": {
        "name": "Bank Rakyat Indonesia (Persero) Tbk",
        "sector": "Financials",
        "subsector": "State Microfinance",
        "benchmark_yield_pct": 6.8,
        "historical_dpr_pct": 80.0,
        "dividend_cagr_pct": 8.0,
        "payout_frequency": "Semi-Annual (Interim + Final)",
        "moat": "Microfinance & rural banking monopoly via Kupedes/KUR; highest dividend payout ratio among SOEs.",
        "sovereign_tier": "HIGH_YIELD_ENGINE",
    },
    "BMRI": {
        "name": "Bank Mandiri (Persero) Tbk",
        "sector": "Financials",
        "subsector": "State Wholesale & Commercial",
        "benchmark_yield_pct": 5.6,
        "historical_dpr_pct": 60.0,
        "dividend_cagr_pct": 9.2,
        "payout_frequency": "Annual Final",
        "moat": "Largest consolidated bank assets in Indonesia; corporate supply chain and retail digital expansion.",
        "sovereign_tier": "CORE_COMPOUNDER",
    },
    "ASII": {
        "name": "Astra International Tbk",
        "sector": "Industrials & Conglomerate",
        "subsector": "Diversified Holdings",
        "benchmark_yield_pct": 7.4,
        "historical_dpr_pct": 50.0,
        "dividend_cagr_pct": 6.0,
        "payout_frequency": "Semi-Annual (Interim + Final)",
        "moat": "Automotive market share >50%; diversified industrial powerhouse across United Tractors and Astra Agro.",
        "sovereign_tier": "VALUE_CASH_COW",
    },
    "ADRO": {
        "name": "Alamtri Resources Indonesia (Adaro) Tbk",
        "sector": "Energy",
        "subsector": "Thermal Coal & Green Energy",
        "benchmark_yield_pct": 12.5,
        "historical_dpr_pct": 65.0,
        "dividend_cagr_pct": 4.0,
        "payout_frequency": "Semi-Annual (Interim + Final)",
        "moat": "Ultra-low-cost thermal coal operator; massive free cash flow yields transitioning to green aluminium.",
        "sovereign_tier": "SUPER_CYCLICAL_YIELD",
    },
    "TLKM": {
        "name": "Telkom Indonesia (Persero) Tbk",
        "sector": "Communication Services",
        "subsector": "Telecommunications",
        "benchmark_yield_pct": 5.8,
        "historical_dpr_pct": 75.0,
        "dividend_cagr_pct": 4.5,
        "payout_frequency": "Annual Final",
        "moat": "Nationwide fiber backbone and mobile network infrastructure with defensible recurring cash flow.",
        "sovereign_tier": "DEFENSIVE_INCOME",
    },
    "PTBA": {
        "name": "Bukit Asam Tbk",
        "sector": "Energy",
        "subsector": "State Coal Mining",
        "benchmark_yield_pct": 14.2,
        "historical_dpr_pct": 95.0,
        "dividend_cagr_pct": 3.0,
        "payout_frequency": "Annual Final",
        "moat": "State-owned mineral asset with 75-100% statutory DPR to state budget; peak dividend payouts.",
        "sovereign_tier": "SUPER_CYCLICAL_YIELD",
    },
    "ICBP": {
        "name": "Indofood CBP Sukses Makmur Tbk",
        "sector": "Consumer Non-Cyclicals",
        "subsector": "Packaged Food",
        "benchmark_yield_pct": 3.6,
        "historical_dpr_pct": 50.0,
        "dividend_cagr_pct": 8.5,
        "payout_frequency": "Annual Final",
        "moat": "Global instant noodle franchise (Indomie) with virtually inelastic demand and pricing power.",
        "sovereign_tier": "DEFENSIVE_INCOME",
    },
    "BBNI": {
        "name": "Bank Negara Indonesia (Persero) Tbk",
        "sector": "Financials",
        "subsector": "State Corporate Banking",
        "benchmark_yield_pct": 5.2,
        "historical_dpr_pct": 50.0,
        "dividend_cagr_pct": 9.0,
        "payout_frequency": "Annual Final",
        "moat": "Corporate banking transformation and international branch network with ROE turnaround.",
        "sovereign_tier": "CORE_COMPOUNDER",
    },
}

QUALIFIED_REINVESTMENT_INSTRUMENTS = [
    {
        "category": "Indonesian Equities (BEI / IDX)",
        "instruments": "Shares of companies listed on the Indonesia Stock Exchange (IDX)",
        "pmk_basis": "PMK-18/PMK.03/2021 Pasal 35 ayat (1) huruf d",
    },
    {
        "category": "Government Securities (SBN / SBSN)",
        "instruments": "Surat Berharga Negara (ORI, Sukuk Ritel SR, PBS, FR, INDON)",
        "pmk_basis": "PMK-18/PMK.03/2021 Pasal 35 ayat (1) huruf a",
    },
    {
        "category": "Corporate Bonds & Sukuk",
        "instruments": "Bonds or sukuk issued by Indonesian companies supervised by OJK",
        "pmk_basis": "PMK-18/PMK.03/2021 Pasal 35 ayat (1) huruf b",
    },
    {
        "category": "Mutual Funds & ETFs",
        "instruments": "Reksadana Saham/Pendapatan Tetap & Exchange-Traded Funds on BEI",
        "pmk_basis": "PMK-18/PMK.03/2021 Pasal 35 ayat (1) huruf e",
    },
    {
        "category": "Bank Deposits & Sharia Savings",
        "instruments": "Time deposits in commercial banks in Indonesia in Rupiah or Foreign Currency",
        "pmk_basis": "PMK-18/PMK.03/2021 Pasal 35 ayat (1) huruf h",
    },
    {
        "category": "Direct Equity Investment",
        "instruments": "Direct equity investment in non-listed Indonesian limited liability companies (PT)",
        "pmk_basis": "PMK-18/PMK.03/2021 Pasal 35 ayat (1) huruf k",
    },
]


def calculate_statutory_deadlines(
    receipt_date: datetime.date | str | None = None,
) -> dict[str, Any]:
    """Calculates statutory tax reinvestment & reporting deadlines under PMK-18/PMK.03/2021.

    Args:
        receipt_date: Date dividend was paid / received into RDN (default: today).

    Returns:
        Structured statutory schedule including reinvestment deadline, holding period,
        and annual e-Reporting submission milestones.
    """
    if receipt_date is None:
        rec_dt = datetime.date.today()
    elif isinstance(receipt_date, str):
        try:
            rec_dt = datetime.date.fromisoformat(receipt_date[:10])
        except Exception:
            rec_dt = datetime.date.today()
    elif isinstance(receipt_date, datetime.datetime):
        rec_dt = receipt_date.date()
    else:
        rec_dt = receipt_date

    tax_year = rec_dt.year

    # Statutory deadline: End of 3rd month after the tax year dividend is received (March 31 of Year T+1)
    reinvest_deadline = datetime.date(tax_year + 1, 3, 31)

    # Statutory holding period: Must be maintained for at least 3 consecutive tax years
    # Holding lock expires on December 31 of Year T+3
    holding_release_date = datetime.date(tax_year + 3, 12, 31)

    # e-Reporting Investasi (Laporan Realisasi Investasi via DJP Online) must be submitted annually
    # concurrent with SPT Tahunan (March 31 of each year for 3 consecutive years)
    reporting_deadlines = [
        {
            "report_period": f"Year {tax_year} Realization (SPT Tahunan {tax_year})",
            "submission_deadline": f"{tax_year + 1}-03-31",
            "requirement": "Initial investment proof & asset categorization via DJP Online e-Reporting",
        },
        {
            "report_period": f"Year {tax_year + 1} Monitoring (SPT Tahunan {tax_year + 1})",
            "submission_deadline": f"{tax_year + 2}-03-31",
            "requirement": "Holding maintenance verification (assets must remain invested in ID)",
        },
        {
            "report_period": f"Year {tax_year + 2} Final Lockout (SPT Tahunan {tax_year + 2})",
            "submission_deadline": f"{tax_year + 3}-03-31",
            "requirement": "Completion of 3-year statutory holding; lock-in releases permanently",
        },
    ]

    return {
        "tax_year_received": tax_year,
        "receipt_date": rec_dt.isoformat(),
        "reinvestment_deadline": reinvest_deadline.isoformat(),
        "holding_release_date": holding_release_date.isoformat(),
        "statutory_holding_years": 3,
        "annual_reporting_deadlines": reporting_deadlines,
        "governing_regulations": [
            "UU No. 7 Tahun 2021 (Harmonisasi Peraturan Perpajakan / UU HPP)",
            "UU No. 11 Tahun 2020 / UU No. 6 Tahun 2023 (UU Cipta Kerja Pasal 111)",
            "Peraturan Menteri Keuangan (PMK) No. 18/PMK.03/2021 Pasal 34 - 40",
        ],
        "qualified_instruments": QUALIFIED_REINVESTMENT_INSTRUMENTS,
    }


def get_cash_cow_profiles(
    tickers: list[str] | None = None,
    usd_rate: float | None = None,
) -> list[dict[str, Any]]:
    """Loads and enriches Indonesian dividend cash cow profiles.

    Merges static qualitative profiles with local Parquet market data and company details.
    """
    if tickers is None:
        target_tickers = list(BENCHMARK_CASH_COWS.keys())
    else:
        target_tickers = [t.upper().strip() for t in tickers]

    if usd_rate is None or usd_rate <= 0:
        usd_rate = get_usd_idr_rate()

    # Load details and parquet
    details = load_json(DETAILS_FILE) if os.path.exists(DETAILS_FILE) else {}
    stock_df = pd.DataFrame()
    ratios_df = pd.DataFrame()

    stock_path = os.path.join(PARQUET_DIR, "stock_summary.parquet")
    if os.path.exists(stock_path):
        try:
            stock_df = pd.read_parquet(
                stock_path,
                columns=["Date", "StockCode", "Close", "ListedShares"],
            )
        except Exception as e:
            log.warning("Could not load stock_summary.parquet: %s", e)

    ratios_path = os.path.join(PARQUET_DIR, "financial_ratios.parquet")
    if os.path.exists(ratios_path):
        try:
            ratios_df = pd.read_parquet(ratios_path)
        except Exception as e:
            log.warning("Could not load financial_ratios.parquet: %s", e)

    profiles: list[dict[str, Any]] = []

    for ticker in target_tickers:
        bench = BENCHMARK_CASH_COWS.get(
            ticker,
            {
                "name": ticker,
                "sector": "General",
                "subsector": "General",
                "benchmark_yield_pct": 5.0,
                "historical_dpr_pct": 50.0,
                "dividend_cagr_pct": 6.0,
                "payout_frequency": "Annual",
                "moat": "IDX-listed company",
                "sovereign_tier": "CORE_COMPOUNDER",
            },
        )

        # Fetch latest price & listed shares
        current_price = 0.0
        listed_shares = 0.0
        if not stock_df.empty and "StockCode" in stock_df.columns:
            s_rows = stock_df[stock_df["StockCode"] == ticker]
            if not s_rows.empty:
                last_s = s_rows.sort_values("Date").iloc[-1]
                current_price = float(last_s.get("Close", 0.0))
                listed_shares = float(last_s.get("ListedShares", 0.0))

        # Fetch fundamentals
        roe = 0.0
        per = 0.0
        pbv = 0.0
        if not ratios_df.empty and "code" in ratios_df.columns:
            r_rows = ratios_df[ratios_df["code"] == ticker]
            if not r_rows.empty:
                last_r = r_rows.iloc[-1]
                roe = float(last_r.get("roe", 0.0) or 0.0)
                per = float(last_r.get("per", 0.0) or 0.0)
                pbv = float(last_r.get("priceBV", 0.0) or 0.0)

        # Compute DPS
        dps_idr = 0.0
        comp_details = details.get(ticker, {})
        divs = comp_details.get("Dividen", [])
        if divs:
            latest_div = divs[0]
            dps_raw = float(latest_div.get("CashDividenPerSaham", 0.0) or 0.0)
            dps_mu = str(latest_div.get("CashDividenPerSahamMU", "")).upper().strip()
            total_div = float(latest_div.get("CashDividenTotal", 0.0) or 0.0)
            total_mu = str(latest_div.get("CashDividenTotalMU", "")).upper().strip()

            if total_div > 0 and listed_shares > 0:
                tot_idr = total_div * (usd_rate if total_mu == "USD" else 1.0)
                dps_idr = tot_idr / listed_shares
            elif dps_raw > 0:
                dps_idr = dps_raw * (usd_rate if dps_mu == "USD" else 1.0)

        # Fallback to benchmark yield if data not yet synced
        yield_pct = (
            (dps_idr / current_price * 100.0)
            if (current_price > 0 and dps_idr > 0)
            else bench["benchmark_yield_pct"]
        )
        if dps_idr <= 0 and current_price > 0:
            dps_idr = current_price * (yield_pct / 100.0)

        profiles.append(
            {
                "ticker": ticker,
                "name": bench["name"],
                "sector": bench["sector"],
                "subsector": bench["subsector"],
                "current_price": round(current_price, 2),
                "dps_idr": round(dps_idr, 2),
                "dividend_yield_pct": round(yield_pct, 2),
                "historical_dpr_pct": round(bench["historical_dpr_pct"], 1),
                "dividend_cagr_pct": round(bench["dividend_cagr_pct"], 1),
                "payout_frequency": bench["payout_frequency"],
                "roe_pct": round(roe, 1),
                "per": round(per, 1),
                "pbv": round(pbv, 2),
                "moat": bench["moat"],
                "sovereign_tier": bench["sovereign_tier"],
            }
        )

    return profiles


def simulate_sovereign_runway(
    starting_capital: float = 1_000_000_000.0,
    monthly_living_expense: float = 15_000_000.0,
    expense_inflation_pct: float = 4.0,
    projection_years: int = 20,
    portfolio_weights: dict[str, float] | None = None,
    custom_yield_pct: float | None = None,
    custom_dividend_cagr_pct: float | None = None,
    usd_rate: float | None = None,
) -> dict[str, Any]:
    """Simulates dividend compounding and sovereign runway under 3 Indonesian tax regimes:

    1. UU Cipta Kerja (0% Tax Drag): Dividends reinvested gross within statutory 3-year deadline.
    2. Standard WPOP (10% Tax Drag): 10% PPh Final deducted on each distribution.
    3. Foreign Taxpayer (20% Tax Drag): 20% PPh Pasal 26 foreign withholding deducted.

    Args:
        starting_capital: Initial portfolio value in IDR (e.g. Rp 1,000,000,000).
        monthly_living_expense: Desired baseline monthly living expense in IDR.
        expense_inflation_pct: Annual inflation rate for living expenses (default: 4.0%).
        projection_years: Number of simulation years (1 to 40).
        portfolio_weights: Dict of {ticker: weight} (weights normalized to 1.0).
        custom_yield_pct: Optional override for portfolio initial dividend yield.
        custom_dividend_cagr_pct: Optional override for annual dividend growth rate.
        usd_rate: USD/IDR exchange rate.

    Returns:
        Comprehensive multi-scenario projection dataset, tax drag metrics,
        and sovereign runway milestone calculations.
    """
    if starting_capital <= 0:
        starting_capital = 100_000_000.0
    if monthly_living_expense <= 0:
        monthly_living_expense = 10_000_000.0
    if projection_years < 1:
        projection_years = 1
    if projection_years > 40:
        projection_years = 40

    # Default balanced basket if not provided
    if not portfolio_weights:
        portfolio_weights = {
            "BBCA": 0.30,
            "BBRI": 0.30,
            "BMRI": 0.15,
            "ASII": 0.15,
            "ADRO": 0.10,
        }

    # Normalize weights
    total_w = sum(portfolio_weights.values())
    if total_w > 0:
        norm_weights = {k: v / total_w for k, v in portfolio_weights.items()}
    else:
        norm_weights = {"BBCA": 0.5, "BBRI": 0.5}

    # Retrieve profiles for selected basket
    profiles = get_cash_cow_profiles(list(norm_weights.keys()), usd_rate=usd_rate)
    prof_map = {p["ticker"]: p for p in profiles}

    # Calculate weighted average yield and dividend CAGR
    if custom_yield_pct is not None and custom_yield_pct > 0:
        weighted_yield_pct = custom_yield_pct
    else:
        weighted_yield_pct = sum(
            prof_map.get(t, {}).get("dividend_yield_pct", 5.0) * w for t, w in norm_weights.items()
        )

    if custom_dividend_cagr_pct is not None and custom_dividend_cagr_pct >= 0:
        weighted_cagr_pct = custom_dividend_cagr_pct
    else:
        weighted_cagr_pct = sum(
            prof_map.get(t, {}).get("dividend_cagr_pct", 6.0) * w for t, w in norm_weights.items()
        )

    # Assumed long-term capital appreciation aligns with retained earnings (~4.0% real growth)
    capital_appreciation_pct = 4.5

    # Run multi-regime annual progression
    regimes = {
        "uu_cipta_kerja_0pct": {
            "name": "UU Cipta Kerja Exemption (0% Tax)",
            "tax_rate": UU_CIPTA_KERJA_TAX_RATE,
            "description": "Dividends fully reinvested within statutory 3-year deadline under PMK-18/PMK.03/2021.",
        },
        "standard_tax_drag_10pct": {
            "name": "Unreinvested Standard (10% Tax Drag)",
            "tax_rate": STANDARD_WPOP_TAX_RATE,
            "description": "10% PPh Final haircut paid each year (unreinvested or spent as lifestyle dividend).",
        },
        "foreign_tax_drag_20pct": {
            "name": "Foreign Investor (20% Withholding)",
            "tax_rate": FOREIGN_WPLN_TAX_RATE,
            "description": "20% statutory PPh Pasal 26 withholding tax on gross dividends.",
        },
    }

    results: dict[str, Any] = {
        "parameters": {
            "starting_capital_idr": starting_capital,
            "monthly_living_expense_idr": monthly_living_expense,
            "annual_living_expense_initial_idr": monthly_living_expense * 12.0,
            "expense_inflation_pct": expense_inflation_pct,
            "projection_years": projection_years,
            "weighted_initial_yield_pct": round(weighted_yield_pct, 2),
            "weighted_dividend_cagr_pct": round(weighted_cagr_pct, 2),
            "assumed_capital_growth_pct": capital_appreciation_pct,
            "portfolio_weights": norm_weights,
            "cash_cow_profiles": profiles,
        },
        "regimes": {},
    }

    current_year = datetime.date.today().year

    for regime_key, reg_info in regimes.items():
        tax_rate = cast(float, reg_info["tax_rate"])
        schedule: list[dict[str, Any]] = []

        port_val = starting_capital
        cum_tax_paid = 0.0
        cum_gross_div = 0.0
        cum_net_div = 0.0
        year_freedom_reached: int | None = None

        for yr in range(1, projection_years + 1):
            calendar_year = current_year + yr - 1
            living_exp_year = (monthly_living_expense * 12.0) * (
                (1.0 + expense_inflation_pct / 100.0) ** (yr - 1)
            )

            # Dividend generated at start of year based on current yield & growth
            growth_factor = (1.0 + weighted_cagr_pct / 100.0) ** (yr - 1)
            eff_yield_pct = weighted_yield_pct * growth_factor
            # Cap effective yield growth realistically so it doesn't exceed 25%
            eff_yield_pct = min(25.0, eff_yield_pct)

            gross_div = port_val * (eff_yield_pct / 100.0)
            tax_paid = gross_div * tax_rate
            net_div = gross_div - tax_paid

            cum_gross_div += gross_div
            cum_tax_paid += tax_paid
            cum_net_div += net_div

            # Sovereign Runway Coverage Ratio: Net Dividend / Annual Living Expenses
            coverage_ratio = net_div / living_exp_year if living_exp_year > 0 else 0.0
            is_sovereign_independent = coverage_ratio >= 1.0

            if is_sovereign_independent and year_freedom_reached is None:
                year_freedom_reached = yr

            # In accumulation mode, 100% of net dividend is reinvested into portfolio
            # plus capital appreciation on underlying holdings
            port_val_end = (port_val + net_div) * (1.0 + capital_appreciation_pct / 100.0)

            # Months of runway if portfolio and dividends were liquidated for expenses
            runway_months = (port_val / (living_exp_year / 12.0)) if living_exp_year > 0 else 0.0

            schedule.append(
                {
                    "simulation_year": yr,
                    "calendar_year": calendar_year,
                    "portfolio_value_start_idr": round(port_val, 2),
                    "portfolio_value_end_idr": round(port_val_end, 2),
                    "gross_dividend_idr": round(gross_div, 2),
                    "tax_paid_idr": round(tax_paid, 2),
                    "net_dividend_idr": round(net_div, 2),
                    "annual_living_expense_idr": round(living_exp_year, 2),
                    "monthly_living_expense_idr": round(living_exp_year / 12.0, 2),
                    "coverage_ratio": round(coverage_ratio, 3),
                    "sovereign_independent": is_sovereign_independent,
                    "runway_months": round(runway_months, 1),
                    "cum_tax_paid_idr": round(cum_tax_paid, 2),
                    "cum_net_dividend_idr": round(cum_net_div, 2),
                }
            )

            # Next year start
            port_val = port_val_end

        results["regimes"][regime_key] = {
            "name": reg_info["name"],
            "tax_rate_pct": round(tax_rate * 100.0, 1),
            "description": reg_info["description"],
            "final_portfolio_value_idr": round(schedule[-1]["portfolio_value_end_idr"], 2),
            "total_gross_dividend_idr": round(cum_gross_div, 2),
            "total_tax_paid_idr": round(cum_tax_paid, 2),
            "total_net_dividend_idr": round(cum_net_div, 2),
            "final_annual_net_dividend_idr": round(schedule[-1]["net_dividend_idr"], 2),
            "final_coverage_ratio": round(schedule[-1]["coverage_ratio"], 2),
            "year_sovereign_freedom_reached": year_freedom_reached,
            "schedule": schedule,
        }

    # Calculate comparative Tax Drag Gap
    uu_final = results["regimes"]["uu_cipta_kerja_0pct"]["final_portfolio_value_idr"]
    std_final = results["regimes"]["standard_tax_drag_10pct"]["final_portfolio_value_idr"]
    tax_drag_wealth_gap = uu_final - std_final
    tax_drag_tax_saved = results["regimes"]["standard_tax_drag_10pct"]["total_tax_paid_idr"]

    yr_uu = results["regimes"]["uu_cipta_kerja_0pct"]["year_sovereign_freedom_reached"]
    yr_std = results["regimes"]["standard_tax_drag_10pct"]["year_sovereign_freedom_reached"]
    time_saved_years = (yr_std - yr_uu) if (yr_std is not None and yr_uu is not None) else None

    results["comparison"] = {
        "tax_drag_wealth_gap_idr": round(tax_drag_wealth_gap, 2),
        "total_tax_saved_via_uu_cipta_kerja_idr": round(tax_drag_tax_saved, 2),
        "wealth_multiplier": round(uu_final / (std_final + 1e-9), 3),
        "time_to_freedom_uu_cipta_kerja_years": yr_uu,
        "time_to_freedom_standard_10pct_years": yr_std,
        "years_saved_by_reinvestment": time_saved_years,
        "verdict": (
            f"By utilizing the UU Cipta Kerja 0% dividend reinvestment exemption, you save "
            f"Rp {tax_drag_tax_saved:,.0f} in direct taxes and compound an additional "
            f"Rp {tax_drag_wealth_gap:,.0f} into your wealth runway."
        ),
    }

    # Add statutory calendar milestones for current year
    results["statutory_calendar"] = calculate_statutory_deadlines()

    return results
