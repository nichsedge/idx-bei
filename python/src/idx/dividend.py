"""
Dividend Decision Engine & Trap Analyzer for IDX-BEI listed stocks.

Provides quantitative decision support for the classic IDX investor dilemma:
When a held stock announces a dividend, should you BUY, HOLD, or SELL before Cum Date?

Evaluates:
1. Dividend Yield & Net After-Tax Return (UU HPP 10% / 0% reinvested).
2. Dividend Payout Ratio (DPR) & Earnings Sustainability (EPS, ROE, DER).
3. Dividend Trap Risk Score (0-100) across 5 risk dimensions.
4. Smart Money Flow (Net Foreign Flow & Institutional Accumulation/Distribution).
5. Technical Regime (20-day run-up euphoria & RSI-14 overbought level).
6. Actionable Recommendation (BUY / HOLD / SELL BEFORE CUM DATE) with tactical execution playbook.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from idx.core.currency import get_usd_idr_rate
from idx.core.utils import DATA_DIR, get_logger, load_json

log = get_logger("idx.dividend")

PARQUET_DIR = os.path.join(DATA_DIR, "parquet")
DETAILS_FILE = os.path.join(DATA_DIR, "companyDetailsByKodeEmiten.json")


def _calculate_rsi(series: pd.Series, period: int = 14) -> float:
    """Calculates Wilder's RSI-14 for a price series."""
    if len(series) < period + 1:
        return 50.0
    delta = series.diff().dropna()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Wilder exponential smoothing
    for i in range(period, len(delta)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    last_gain = avg_gain.iloc[-1]
    last_loss = avg_loss.iloc[-1]
    if pd.isna(last_gain) or pd.isna(last_loss):
        return 50.0
    if last_loss == 0:
        return 100.0 if last_gain > 0 else 50.0
    rs = last_gain / last_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def get_latest_dividend(
    ticker: str, details_dict: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Extracts the latest dividend record for a given ticker."""
    if details_dict is None:
        if os.path.exists(DETAILS_FILE):
            details_dict = load_json(DETAILS_FILE)
        else:
            return None

    comp = details_dict.get(ticker.upper())
    if not comp or not comp.get("Dividen"):
        return None

    divs = comp["Dividen"]
    if not divs:
        return None

    # Return newest dividend record
    return divs[0]


def analyze_stock_dividend(
    ticker: str,
    *,
    window_days: int = 20,
    usd_rate: float | None = None,
    details_dict: dict[str, Any] | None = None,
    stock_df: pd.DataFrame | None = None,
    ratios_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Performs deep quantitative dividend decision analysis on an IDX stock.

    Args:
        ticker: 4-letter IDX stock code (e.g. 'BBCA', 'PTBA', 'AALI').
        window_days: Lookback sessions for flow & momentum calculations.
        usd_rate: Exchange rate for USD-denominated cash dividends. Defaults to dynamic rate.
        details_dict: Optional preloaded company details JSON.
        stock_df: Optional preloaded stock_summary DataFrame.
        ratios_df: Optional preloaded financial_ratios DataFrame.

    Returns:
        Structured analysis dictionary with metrics, risk score, and verdict.
    """
    ticker = ticker.upper().strip()
    if usd_rate is None or usd_rate <= 0:
        usd_rate = get_usd_idr_rate()

    # 1. Load Data
    if details_dict is None:
        details_dict = load_json(DETAILS_FILE) if os.path.exists(DETAILS_FILE) else {}
    if stock_df is None:
        stock_path = os.path.join(PARQUET_DIR, "stock_summary.parquet")
        stock_df = pd.read_parquet(stock_path) if os.path.exists(stock_path) else pd.DataFrame()
    if ratios_df is None:
        ratios_path = os.path.join(PARQUET_DIR, "financial_ratios.parquet")
        ratios_df = pd.read_parquet(ratios_path) if os.path.exists(ratios_path) else pd.DataFrame()

    # Filter for ticker
    comp_info = details_dict.get(ticker, {})
    divs = comp_info.get("Dividen", [])
    if not divs:
        company_name = comp_info.get("Profiles", [{}])[0].get("NamaEmiten") or comp_info.get(
            "Search", {}
        ).get("NamaEmiten", ticker)
        return {
            "ticker": ticker,
            "company_name": company_name,
            "has_dividend": False,
            "message": f"No dividend distribution records found for {ticker}.",
        }

    latest_div = divs[0]
    company_name = (
        latest_div.get("Nama")
        or comp_info.get("Profiles", [{}])[0].get("NamaEmiten")
        or comp_info.get("Search", {}).get("NamaEmiten", ticker)
    )

    # Stock price series
    stock_rows = stock_df[stock_df["StockCode"] == ticker].sort_values("Date")
    if len(stock_rows) == 0:
        return {
            "ticker": ticker,
            "company_name": company_name,
            "has_dividend": True,
            "message": f"Historical price data not found in parquet for {ticker}.",
        }

    last_session = stock_rows.iloc[-1]
    current_price = float(last_session.get("Close", 0.0))
    listed_shares = float(last_session.get("ListedShares", 0.0))

    # Fundamentals
    ratio_rows = ratios_df[ratios_df["code"] == ticker]
    last_ratio = ratio_rows.iloc[-1] if len(ratio_rows) > 0 else None

    eps = (
        float(last_ratio["eps"])
        if last_ratio is not None and pd.notna(last_ratio.get("eps"))
        else 0.0
    )
    roe = (
        float(last_ratio["roe"])
        if last_ratio is not None and pd.notna(last_ratio.get("roe"))
        else 0.0
    )
    der = (
        float(last_ratio["deRatio"])
        if last_ratio is not None and pd.notna(last_ratio.get("deRatio"))
        else 0.0
    )
    per = (
        float(last_ratio["per"])
        if last_ratio is not None and pd.notna(last_ratio.get("per"))
        else 0.0
    )
    pbv = (
        float(last_ratio["priceBV"])
        if last_ratio is not None and pd.notna(last_ratio.get("priceBV"))
        else 0.0
    )
    audit_opinion = str(last_ratio.get("opini", "N/A")) if last_ratio is not None else "N/A"

    # 2. Determine Dividend Per Share (DPS) in IDR
    dps_raw = float(latest_div.get("CashDividenPerSaham", 0.0) or 0.0)
    dps_mu = str(latest_div.get("CashDividenPerSahamMU", "")).upper().strip()
    total_div = float(latest_div.get("CashDividenTotal", 0.0) or 0.0)
    total_mu = str(latest_div.get("CashDividenTotalMU", "")).upper().strip()

    dps_idr = 0.0
    # Prioritize Total Cash Dividend / Listed Shares when total is available
    if total_div > 0 and listed_shares > 0:
        total_idr = total_div * (usd_rate if total_mu == "USD" else 1.0)
        dps_idr = total_idr / listed_shares
    elif dps_raw > 0:
        if dps_mu == "USD":
            # Sanity check: if dps_raw * usd_rate > current_price, dps_raw was likely in cents or total
            raw_converted = dps_raw * usd_rate
            if current_price > 0 and raw_converted > current_price * 0.6:
                dps_idr = raw_converted / 100.0  # cents conversion
            else:
                dps_idr = raw_converted
        else:
            # IDR sanity check
            if current_price > 0 and dps_raw > current_price * 0.7:
                dps_idr = dps_raw / 1000.0
            else:
                dps_idr = dps_raw

    # Yield
    div_yield_pct = (dps_idr / current_price * 100.0) if current_price > 0 else 0.0

    # Dividend Payout Ratio (DPR)
    if eps > 0 and dps_idr > 0:
        dpr_pct = (dps_idr / eps) * 100.0
    elif total_div > 0 and last_ratio is not None and pd.notna(last_ratio.get("profitAttrOwner")):
        profit = float(last_ratio["profitAttrOwner"])
        total_idr = total_div * (usd_rate if total_mu == "USD" else 1.0)
        dpr_pct = (total_idr / profit * 100.0) if profit > 0 else 0.0
    else:
        dpr_pct = 0.0

    # 3. Market Flow & Technical Indicators
    recent_sessions = stock_rows.tail(window_days)
    close_series = stock_rows["Close"].dropna()
    rsi_14 = _calculate_rsi(close_series, 14)

    # 20-day price change (euphoria check)
    start_close = recent_sessions.iloc[0]["Close"] if len(recent_sessions) > 0 else current_price
    runup_20d_pct = (
        ((current_price - start_close) / start_close * 100.0) if start_close > 0 else 0.0
    )

    # Net Foreign Flow (NFF) over 5-day and 20-day
    nff_5d = (
        float(stock_rows.tail(5)["NetForeignFlow"].sum())
        if "NetForeignFlow" in stock_rows.columns
        else 0.0
    )
    nff_20d = (
        float(recent_sessions["NetForeignFlow"].sum())
        if "NetForeignFlow" in stock_rows.columns
        else 0.0
    )
    turnover_20d = (
        float(recent_sessions["Value"].sum()) if "Value" in recent_sessions.columns else 1.0
    )
    nff_share_pct = (nff_20d / turnover_20d * 100.0) if turnover_20d > 0 else 0.0

    # 4. Dates & Schedule
    cum_date = latest_div.get("TanggalCum", "")[:10]
    ex_date = latest_div.get("TanggalExRegulerDanNegosiasi", "")[:10]
    dps_date = latest_div.get("TanggalDPS", "")[:10]
    pay_date = latest_div.get("TanggalPembayaran", "")[:10]
    tahun_buku = latest_div.get("TahunBuku", "N/A")

    # 5. Quantitative Dividend Trap Risk Scoring (0 to 100)
    # Dimension 1: Yield Severity (High yield often = deep ARB gap down on Ex-Date)
    trap_score = 0.0
    risk_factors: list[str] = []

    if div_yield_pct >= 12.0:
        trap_score += 25.0
        risk_factors.append(
            f"Ultra-high yield ({div_yield_pct:.1f}%): severe multi-day Ex-Date ARB risk"
        )
    elif div_yield_pct >= 8.0:
        trap_score += 18.0
        risk_factors.append(f"High yield ({div_yield_pct:.1f}%): expected steep Ex-Date markdown")
    elif div_yield_pct >= 5.0:
        trap_score += 10.0
    else:
        trap_score += 2.0

    # Dimension 2: Payout Sustainability (DPR)
    if dpr_pct > 100.0:
        trap_score += 25.0
        risk_factors.append(f"Unsustainable payout (DPR {dpr_pct:.1f}% > 100%): capital eroding")
    elif dpr_pct > 80.0:
        trap_score += 18.0
        risk_factors.append(f"Aggressive payout (DPR {dpr_pct:.1f}%): vulnerable to earnings slump")
    elif dpr_pct > 60.0:
        trap_score += 8.0

    # Dimension 3: Smart Money Flow Divergence
    if nff_5d < 0 and runup_20d_pct > 5.0:
        trap_score += 20.0
        risk_factors.append(
            "Smart Money Divergence: Foreigners net selling into pre-cum price run-up"
        )
    elif nff_20d < 0:
        trap_score += 10.0
        risk_factors.append(
            f"Foreign outflow: Net selling of Rp{abs(nff_20d) / 1e9:.1f}B over {window_days}d"
        )
    elif nff_20d > 0:
        trap_score -= 5.0  # Smart money accumulation bonus

    # Dimension 4: Technical Euphoria & Overbought
    if rsi_14 >= 75.0 or runup_20d_pct >= 20.0:
        trap_score += 15.0
        risk_factors.append(
            f"Overbought euphoria: RSI-14 is {rsi_14:.1f}, 20d run-up +{runup_20d_pct:.1f}%"
        )
    elif rsi_14 >= 68.0 or runup_20d_pct >= 10.0:
        trap_score += 8.0
        risk_factors.append(f"Elevated momentum: RSI-14 is {rsi_14:.1f}")

    # Dimension 5: Audit & Balance Sheet Solvency
    if audit_opinion in {"WDP", "TMP", "TMTP", "TL"}:
        trap_score += 15.0
        risk_factors.append(f"Non-clean audit opinion: '{audit_opinion}' carries structural risk")
    if der > 2.5 and roe < 10.0:
        trap_score += 10.0
        risk_factors.append(f"High leverage (DER {der:.2f}x) with weak ROE ({roe:.1f}%)")

    trap_score = max(0.0, min(100.0, trap_score))

    # Risk Tier Categorization
    if trap_score <= 30.0:
        trap_risk_tier = "LOW"
    elif trap_score <= 55.0:
        trap_risk_tier = "MODERATE"
    elif trap_score <= 75.0:
        trap_risk_tier = "HIGH"
    else:
        trap_risk_tier = "CRITICAL"

    # 6. Actionable Recommendation (BUY, HOLD, SELL)
    if (
        trap_score >= 60.0
        or (runup_20d_pct > max(div_yield_pct * 1.5, 10.0) and nff_5d < 0)
        or audit_opinion in {"WDP", "TMP", "TMTP", "TL"}
    ):
        verdict = "SELL BEFORE CUM DATE"
        tactical_action = (
            "Take profit 1-2 days before Cum Date or during Cum Date morning session. "
            "Lock in the pre-dividend capital gains without suffering the anticipated Ex-Date markdown. "
            "You avoid the 10% dividend tax and can rebuy after the Ex-Date sell-off settles at a lower cost basis."
        )
    elif trap_score <= 35.0 and nff_20d >= 0 and rsi_14 <= 65.0 and div_yield_pct >= 2.5:
        verdict = "BUY / ACCUMULATE"
        tactical_action = (
            "Accumulate before Cum Date or on healthy pullbacks. "
            "High quality compounder with sustainable payout and institutional backing. "
            "Ex-Date price drop is historically shallow and quickly recovered."
        )
    else:
        verdict = "HOLD"
        tactical_action = (
            "Hold existing position to collect cash dividend. "
            "Reinvest dividend under UU HPP to enjoy 0% income tax exemption. "
            "Do not chase aggressively if price has run up, but do not panic sell on Ex-Date."
        )

    # Ex-Date Expected Drop
    expected_ex_drop_rp = dps_idr
    expected_ex_drop_pct = div_yield_pct

    return {
        "ticker": ticker,
        "company_name": company_name,
        "has_dividend": True,
        "current_price": current_price,
        "dps_idr": round(dps_idr, 2),
        "dividend_yield_pct": round(div_yield_pct, 2),
        "expected_ex_date_drop_rp": round(expected_ex_drop_rp, 2),
        "expected_ex_date_drop_pct": round(expected_ex_drop_pct, 2),
        "dates": {
            "cum_date": cum_date,
            "ex_date": ex_date,
            "dps_date": dps_date,
            "payment_date": pay_date,
            "fiscal_year": tahun_buku,
        },
        "fundamentals": {
            "eps": round(eps, 2),
            "dpr_pct": round(dpr_pct, 2),
            "per": round(per, 2),
            "pbv": round(pbv, 2),
            "roe_pct": round(roe, 2),
            "der": round(der, 2),
            "audit_opinion": audit_opinion,
        },
        "smart_money": {
            "nff_5d_rp": round(nff_5d, 0),
            "nff_20d_rp": round(nff_20d, 0),
            "foreign_share_pct": round(nff_share_pct, 2),
            "runup_20d_pct": round(runup_20d_pct, 2),
            "rsi_14": round(rsi_14, 1),
        },
        "dividend_trap_score": round(trap_score, 1),
        "dividend_trap_tier": trap_risk_tier,
        "risk_factors": risk_factors,
        "verdict": verdict,
        "tactical_action": tactical_action,
    }


def screen_upcoming_dividends(
    *,
    min_yield: float = 2.0,
    max_trap_score: float = 100.0,
    year_filter: str = "2026",
    limit: int = 50,
) -> pd.DataFrame:
    """Screens dividend declarations across the entire listed universe."""
    details_dict = load_json(DETAILS_FILE) if os.path.exists(DETAILS_FILE) else {}
    stock_path = os.path.join(PARQUET_DIR, "stock_summary.parquet")
    stock_df = pd.read_parquet(stock_path) if os.path.exists(stock_path) else pd.DataFrame()
    ratios_path = os.path.join(PARQUET_DIR, "financial_ratios.parquet")
    ratios_df = pd.read_parquet(ratios_path) if os.path.exists(ratios_path) else pd.DataFrame()

    results: list[dict[str, Any]] = []

    for ticker, info in details_dict.items():
        divs = info.get("Dividen", [])
        if not divs:
            continue
        latest = divs[0]
        cum_date = latest.get("TanggalCum", "")[:10]
        if year_filter and not cum_date.startswith(year_filter):
            continue

        analysis = analyze_stock_dividend(
            ticker,
            details_dict=details_dict,
            stock_df=stock_df,
            ratios_df=ratios_df,
        )
        if not analysis.get("has_dividend"):
            continue

        yld = analysis["dividend_yield_pct"]
        trap = analysis["dividend_trap_score"]

        if yld >= min_yield and trap <= max_trap_score:
            results.append(
                {
                    "Ticker": ticker,
                    "Name": analysis["company_name"][:25],
                    "Price": analysis["current_price"],
                    "DPS_IDR": analysis["dps_idr"],
                    "Yield%": yld,
                    "DPR%": analysis["fundamentals"]["dpr_pct"],
                    "CumDate": analysis["dates"]["cum_date"],
                    "ExDate": analysis["dates"]["ex_date"],
                    "TrapScore": trap,
                    "TrapRisk": analysis["dividend_trap_tier"],
                    "Verdict": analysis["verdict"],
                }
            )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).sort_values("Yield%", ascending=False)
    return df.head(limit)


def format_dividend_report(analysis: dict[str, Any]) -> str:
    """Renders a comprehensive terminal report for dividend decision support."""
    if not analysis.get("has_dividend"):
        return f"❌ {analysis.get('message', 'No dividend info found.')}"

    ticker = analysis["ticker"]
    name = analysis["company_name"]
    price = analysis["current_price"]
    dps = analysis["dps_idr"]
    yld = analysis["dividend_yield_pct"]
    dates = analysis["dates"]
    fund = analysis["fundamentals"]
    sm = analysis["smart_money"]
    trap = analysis["dividend_trap_score"]
    tier = analysis["dividend_trap_tier"]
    verdict = analysis["verdict"]
    action = analysis["tactical_action"]
    risks = analysis["risk_factors"]

    # Visual Badge
    if verdict == "BUY / ACCUMULATE":
        verdict_badge = f"\033[92m🟢 {verdict}\033[0m"
    elif verdict == "HOLD":
        verdict_badge = f"\033[94m🔵 {verdict}\033[0m"
    else:
        verdict_badge = f"\033[91m🔴 {verdict}\033[0m"

    # Trap Tier Badge
    if tier == "LOW":
        tier_badge = f"\033[92m{tier} ({trap}/100)\033[0m"
    elif tier == "MODERATE":
        tier_badge = f"\033[93m{tier} ({trap}/100)\033[0m"
    elif tier == "HIGH":
        tier_badge = f"\033[91m{tier} ({trap}/100)\033[0m"
    else:
        tier_badge = f"\033[95m{tier} ({trap}/100)\033[0m"

    lines = [
        "╔══════════════════════════════════════════════════════════════════════════════╗",
        f"║  IDX DIVIDEND DECISION RADAR: {ticker:<6} - {name[:40]:<40} ║",
        "╠══════════════════════════════════════════════════════════════════════════════╣",
        f"║  Current Price   : Rp{price:>10,.0f}      DPS Announced  : Rp{dps:>10,.2f}       ║",
        f"║  Dividend Yield  : {yld:>9.2f}%       Ex-Date Drop   : ~{analysis['expected_ex_date_drop_pct']:>8.2f}%       ║",
        "╟──────────────────────────────────────────────────────────────────────────────╢",
        "║  TIMELINE DATES:                                                             ║",
        f"║  • Cum Date      : {dates['cum_date']:<12} (Last day to buy for dividend eligibility) ║",
        f"║  • Ex Date       : {dates['ex_date']:<12} (Price adjusts down; selling still gets div)║",
        f"║  • Recording DPS : {dates['dps_date']:<12} • Payment Date: {dates['payment_date']:<12}       ║",
        "╟──────────────────────────────────────────────────────────────────────────────╢",
        "║  FUNDAMENTAL HEALTH & SUSTAINABILITY:                                        ║",
        f"║  • Payout Ratio  : {fund['dpr_pct']:>7.1f}%       • EPS (LTM)    : Rp{fund['eps']:>9.2f}       ║",
        f"║  • ROE           : {fund['roe_pct']:>7.1f}%       • DER          : {fund['der']:>9.2f}x       ║",
        f"║  • PER           : {fund['per']:>7.1f}x       • PBV          : {fund['pbv']:>9.2f}x       ║",
        f"║  • Audit Opinion : {fund['audit_opinion']:<12}                                           ║",
        "╟──────────────────────────────────────────────────────────────────────────────╢",
        "║  SMART MONEY & TECHNICAL MOMENTUM:                                           ║",
        f"║  • Foreign Net 5D: Rp{sm['nff_5d_rp'] / 1e9:>8.1f}B     • Foreign Net 20D : Rp{sm['nff_20d_rp'] / 1e9:>8.1f}B     ║",
        f"║  • 20D Run-up    : {sm['runup_20d_pct']:>8.2f}%      • RSI-14 (Trend)  : {sm['rsi_14']:>9.1f}       ║",
        "╟──────────────────────────────────────────────────────────────────────────────╢",
        f"║  DIVIDEND TRAP RISK SCORE: {tier_badge:<50}║",
    ]

    if risks:
        lines.append(
            "║  Identified Risk Factors:                                                    ║"
        )
        for r in risks:
            lines.append(f"║  ⚠️  {r[:72]:<72} ║")

    lines.extend(
        [
            "╟──────────────────────────────────────────────────────────────────────────────╢",
            f"║  DECISION VERDICT : {verdict_badge:<56}║",
            "║  Tactical Execution:                                                         ║",
        ]
    )

    import textwrap

    wrapped = textwrap.wrap(action, width=74)
    for w in wrapped:
        lines.append(f"║  {w:<74} ║")

    lines.append("╚══════════════════════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)
