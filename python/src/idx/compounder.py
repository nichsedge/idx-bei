"""
IDX-BEI Forensic Quality & Sector-Aware Compounder Engine.

Provides institutional-grade intelligence:
1. Forensic Accounting: Detects one-off non-operating earnings (e.g. LPKR Siloam sale),
   divergences, extreme debt, and audit red flags.
2. Sector-Aware Valuation: Implements Justified PBV (Gordon Growth Model) for Banks
   and appropriate multi-factor valuation for non-financials (preventing the naive PBV < 1 trap).
3. DCA / Long-Term Compounder Scoring: Evaluates 0–100 score for long-term "Nabung Saham" suitability.
4. AI/Forensic Theses & Smart Badges for UI presentation.
"""

from typing import Any


def is_financial_sector(sector: str | None, subsector: str | None = None) -> bool:
    """Check if the emiten belongs to Financials / Banking where debt and PBV behave differently."""
    sec = (sector or "").lower()
    sub = (subsector or "").lower()
    return "financial" in sec or "bank" in sec or "bank" in sub or "financing" in sub


def is_cyclical_sector(sector: str | None, subsector: str | None = None) -> bool:
    """Check if the emiten is in highly cyclical commodity sectors."""
    text = f"{sector or ''} {subsector or ''}".lower()
    cyclical_keywords = [
        "energy",
        "coal",
        "oil",
        "gas",
        "mining",
        "basic materials",
        "metal",
        "steel",
    ]
    return any(k in text for k in cyclical_keywords)


def evaluate_forensics(company: dict[str, Any]) -> dict[str, Any]:
    """
    Forensic evaluation of earnings quality and balance sheet health.
    Detects one-off accounting distortions (e.g. LPKR, GGRP).
    """
    flags: list[str] = []
    reasons: list[str] = []

    sales = float(company.get("sales") or 0.0)
    ebt = float(company.get("ebt") or 0.0)
    profit = float(company.get("profitPeriod") or company.get("profitAttrOwner") or 0.0)
    npm = float(company.get("npm") or 0.0)
    der = float(company.get("deRatio") or company.get("der") or 0.0)
    equity = float(company.get("equity") or 0.0)
    opini = str(company.get("opini") or company.get("audit") or "").upper()
    sector = company.get("sector")
    subsector = company.get("subSector") or company.get("subsector")

    is_fin = is_financial_sector(sector, subsector)

    # 1. Forensic Trap Check: Profit > Sales (NPM > 85% for non-financials)
    # When net income exceeds sales or NPM is anomalous, it's almost always a one-off asset sale or restructuring
    if not is_fin and sales > 0:
        if profit > (sales * 0.85) or npm > 80.0:
            flags.append("VALUE_TRAP_ONE_OFF")
            reasons.append(
                "Laba bersih melebihi/hampir setara omset (NPM > 80%) — indikasi kuat laba semu/penjualan aset."
            )
        elif profit > (ebt * 2.0) and ebt > 0:
            flags.append("VALUE_TRAP_ONE_OFF")
            reasons.append(
                "Laba bersih lebih dari 2x lipat laba sebelum pajak — pos luar biasa non-operasional."
            )
        elif profit > (ebt * 1.35) and ebt > 0:
            flags.append("EXTRAORDINARY_EARNINGS")
            reasons.append(
                "Laba bersih melonjak di atas laba operasional/sebelum pajak (keuntungan pajak/pos luar biasa)."
            )

    # 2. Forensic Trap Check: Insolvent / Negative Equity
    if equity < 0:
        flags.append("NEGATIVE_EQUITY")
        reasons.append("Ekuitas negatif / defisiensi modal.")
    elif 0 < equity < 500.0:  # Less than Rp 500 Miliar equity
        flags.append("MICRO_CAP_RISK")
        reasons.append(
            "Skala modal mikro (< Rp 500 Miliar) — likuiditas terbatas dan risiko kelangsungan usaha tinggi."
        )

    # 3. Non-Financial Extreme Debt Check
    if not is_fin and der > 2.5:
        flags.append("HIGH_LEVERAGE_RISK")
        reasons.append(f"Tingkat utang sangat tinggi (DER {der:.2f}x > 2.5x).")

    # 4. Audit Opinion Flag
    if opini in ("WDP", "TMP", "TMTP", "TL"):
        flags.append("AUDIT_FLAG")
        reasons.append(f"Opini audit berisiko ({opini}).")

    # 5. Cyclical Commodity Warning
    if is_cyclical_sector(sector, subsector):
        flags.append("CYCLICAL_COMMODITY")
        reasons.append("Sektor komoditas siklikal — waspada pembalikan siklus harga.")

    is_value_trap = "VALUE_TRAP_ONE_OFF" in flags or "NEGATIVE_EQUITY" in flags

    return {
        "is_value_trap": is_value_trap,
        "flags": flags,
        "reasons": reasons,
    }


def calculate_justified_pbv(
    roe: float, cost_of_equity: float = 0.105, growth_rate: float = 0.05
) -> float:
    """
    Gordon Growth Justified PBV Model:
    Justified PBV = (ROE - g) / (Ke - g)
    """
    roe_decimal = roe / 100.0
    if roe_decimal <= growth_rate:
        return 0.5  # Distressed / Low ROE floor
    justified = (roe_decimal - growth_rate) / (cost_of_equity - growth_rate)
    return round(max(0.5, min(justified, 6.0)), 2)


def evaluate_sector_valuation(company: dict[str, Any], forensics: dict[str, Any]) -> dict[str, Any]:
    """
    Sector-aware valuation model.
    Banks are evaluated via Justified PBV vs ROE.
    Non-banks are evaluated via PBV, PER, and forensic safety.
    """
    pbv = float(company.get("pbv") or company.get("priceBV") or company.get("price_bv") or 0.0)
    per = float(company.get("per") or 0.0)
    roe = float(company.get("roe") or 0.0)
    sector = company.get("sector")
    subsector = company.get("subSector") or company.get("subsector")

    is_fin = is_financial_sector(sector, subsector)
    is_trap = forensics.get("is_value_trap", False)

    justified_pbv: float | None = None
    status = "FAIR_VALUE"
    discount_pct = 0.0

    if is_trap:
        return {
            "status": "VALUE_TRAP",
            "justified_pbv": None,
            "discount_pct": 0.0,
            "is_undervalued": False,
            "verdict_badge": "⚠️ Value Trap (Laba Semu)",
        }

    if is_fin:
        # Justified PBV for banks
        if roe > 0:
            justified_pbv = calculate_justified_pbv(roe)
            if pbv > 0 and justified_pbv > 0:
                discount_pct = round(((justified_pbv - pbv) / justified_pbv) * 100.0, 1)

            if roe >= 12.0 and pbv <= (justified_pbv * 0.85):
                status = "SECTOR_UNDERVALUED"
            elif roe < 8.0 and pbv > 1.0:
                status = "OVERVALUED_BANK"
            elif pbv > (justified_pbv * 1.25):
                status = "PREMIUM_VALUATION"
            else:
                status = "FAIR_VALUE"
        else:
            status = "UNPROFITABLE_BANK"
    else:
        # Non-financial emiten
        if pbv > 0 and pbv < 1.0 and roe >= 8.0:
            status = "DEEP_VALUE"
            discount_pct = round((1.0 - pbv) * 100.0, 1)
        elif 0 < per <= 12.0 and 0 < pbv <= 2.2 and roe >= 12.0:
            status = "SECTOR_UNDERVALUED"
            discount_pct = round(max(0.0, (15.0 - per) / 15.0 * 100.0), 1)
        elif per > 25.0 or (pbv > 4.0 and roe < 15.0):
            status = "OVERVALUED"
        else:
            status = "FAIR_VALUE"

    is_undervalued = status in ("DEEP_VALUE", "SECTOR_UNDERVALUED")

    badge_map = {
        "DEEP_VALUE": "💎 Deep Value (<1x PBV)",
        "SECTOR_UNDERVALUED": "🏦 Undervalued Berkualitas",
        "FAIR_VALUE": "⚖️ Fair Value",
        "PREMIUM_VALUATION": "👑 Premium Quality",
        "OVERVALUED": "⚠️ Valuasi Mahal",
        "OVERVALUED_BANK": "⚠️ Bank Overvalued",
        "VALUE_TRAP": "🚨 Value Trap",
    }

    return {
        "status": status,
        "justified_pbv": justified_pbv,
        "discount_pct": discount_pct,
        "is_undervalued": is_undervalued,
        "verdict_badge": badge_map.get(status, "⚖️ Fair Value"),
    }


def calculate_dca_compounder_score(
    company: dict[str, Any],
    forensics: dict[str, Any],
    valuation: dict[str, Any],
    trading_value: float = 0.0,
) -> dict[str, Any]:
    """
    Computes Long-Term DCA / Nabung Saham Compounder Score (0–100).
    Reward: Sustainable ROE, healthy balance sheet, safe yield, reasonable valuation.
    Penalty: Value trap (instant zero/floor), cyclical peaks, extreme leverage.
    """
    if forensics.get("is_value_trap"):
        return {
            "score": 10.0,
            "verdict": "VALUE_TRAP",
            "dca_rating": "🚨 HINDARI (Value Trap)",
            "badges": ["Value Trap", "Laba Semu"],
            "ai_thesis": "Hindari untuk tabungan jangka panjang. Laba dilaporkan tinggi akibat transaksi non-operasional/penjualan aset sesaat, bukan pertumbuhan bisnis riil.",
        }

    score = 0.0
    roe = float(company.get("roe") or 0.0)
    der = float(company.get("deRatio") or company.get("der") or 0.0)
    div_yield = float(company.get("yield") or company.get("Dividen") or 0.0)
    is_blue_chip = bool(company.get("is_blue_chip") or False)
    sector = company.get("sector")
    subsector = company.get("subSector") or company.get("subsector")
    is_fin = is_financial_sector(sector, subsector)
    flags = forensics.get("flags", [])

    # 1. Profitability & Capital Efficiency (Max: 30 pts)
    if roe >= 20.0:
        score += 30.0
    elif roe >= 15.0:
        score += 25.0
    elif roe >= 10.0:
        score += 18.0
    elif roe >= 6.0:
        score += 10.0

    # 2. Valuation Attractiveness (Max: 25 pts)
    val_status = valuation.get("status")
    if val_status == "DEEP_VALUE":
        score += 25.0
    elif val_status == "SECTOR_UNDERVALUED":
        score += 23.0
    elif val_status == "FAIR_VALUE":
        score += 15.0
    elif val_status == "PREMIUM_VALUATION" and roe >= 18.0:
        score += 12.0  # Bluechip moat allowance (e.g. BBCA)
    elif val_status == "OVERVALUED":
        score += 2.0

    # 3. Balance Sheet & Solvency (Max: 20 pts)
    if is_fin:
        # Banks: solvency evaluated through capital adequacy & ROE
        score += 20.0 if roe >= 12.0 else 10.0
    else:
        if der <= 0.5:
            score += 20.0  # Pristine net-cash / low debt
        elif der <= 1.0:
            score += 16.0
        elif der <= 1.5:
            score += 10.0
        elif der <= 2.5:
            score += 5.0
        else:
            score += 0.0

    # 4. Shareholder Return & Dividend (Max: 15 pts)
    if div_yield >= 5.0:
        score += 15.0
    elif div_yield >= 3.0:
        score += 11.0
    elif div_yield >= 1.5:
        score += 6.0

    # 5. Blue Chip, Scale & Liquidity (Max: 10 pts)
    equity = float(company.get("equity") or 0.0)
    if is_blue_chip or equity >= 20_000.0:  # > 20 Triliun equity
        score += 6.0
    elif equity >= 5_000.0:  # > 5 Triliun equity
        score += 4.0

    if trading_value >= 10_000_000_000:  # > 10 Miliar/day
        score += 4.0
    elif trading_value >= 2_000_000_000:
        score += 2.0

    # Penalties for Forensic, Cyclical & Micro-Cap Risks
    if "CYCLICAL_COMMODITY" in flags:
        score -= 8.0  # Cyclical caution for long-term buy-and-forget
    if "MICRO_CAP_RISK" in flags:
        score -= 22.0  # Micro-caps are not safe long-term compounders
    if "HIGH_LEVERAGE_RISK" in flags:
        score -= 25.0
    if "AUDIT_FLAG" in flags:
        score -= 30.0

    final_score = max(5.0, min(100.0, round(score, 1)))

    # Badges & DCA Rating
    badges: list[str] = []
    if final_score >= 75.0:
        dca_rating = "⭐ PRIME DCA (Sangat Layak Tabung)"
        verdict = "PRIME_DCA"
        badges.append("Layak Tabung")
    elif final_score >= 60.0:
        dca_rating = "✅ ACCUMULATE (Layak Koleksi)"
        verdict = "ACCUMULATE"
        badges.append("Koleksi Bertahap")
    elif final_score >= 45.0:
        dca_rating = "⚖️ NEUTRAL (Wait & See)"
        verdict = "NEUTRAL"
    else:
        dca_rating = "⚠️ SPEKULATIF / BATASI"
        verdict = "SPECULATIVE"

    if val_status in ("DEEP_VALUE", "SECTOR_UNDERVALUED"):
        badges.append("Valuasi Diskon")
    if roe >= 15.0:
        badges.append(f"ROE {roe:.1f}% Prima")
    if is_blue_chip:
        badges.append("LQ45 Core")
    if div_yield >= 5.0:
        badges.append(f"Dividen {div_yield:.1f}%")
    if "CYCLICAL_COMMODITY" in flags:
        badges.append("Komoditas Siklikal")

    # Generate Concise AI Investment Thesis
    ticker = company.get("code") or company.get("StockCode") or ""
    name = company.get("name") or company.get("stockName") or ticker

    if verdict == "PRIME_DCA":
        ai_thesis = (
            f"{name} ({ticker}) merupakan compounder kualitas prima dengan ROE tinggi ({roe:.1f}%), "
            f"neraca keuangan sehat, dan valuasi menarik. Sangat direkomendasikan untuk strategi nabung saham (DCA) jangka panjang."
        )
    elif "CYCLICAL_COMMODITY" in flags and final_score >= 60.0:
        ai_thesis = (
            f"{name} ({ticker}) mencetak profitabilitas tinggi di sektor komoditas dengan dividen menarik, "
            f"namun memiliki siklus bisnis. Layak diakumulasi saat siklus wajar, pantau harga komoditas acuan."
        )
    elif verdict == "ACCUMULATE":
        ai_thesis = (
            f"{name} ({ticker}) memiliki fundamental solid dan valuasi beralasan. Cocok dikoleksi secara berkala "
            f"dengan diversifikasi portofolio yang terukur."
        )
    else:
        ai_thesis = (
            f"{name} ({ticker}) memiliki karakteristik spekulatif atau profil imbal hasil terbatas untuk tabungan primer. "
            f"Pertimbangkan alternatif core compounder."
        )

    return {
        "score": final_score,
        "verdict": verdict,
        "dca_rating": dca_rating,
        "badges": badges[:3],
        "ai_thesis": ai_thesis,
    }


def enrich_company_intellect(company: dict[str, Any], trading_value: float = 0.0) -> dict[str, Any]:
    """
    Enriches a single company dictionary with complete forensic & compounder intelligence.
    """
    forensics = evaluate_forensics(company)
    valuation = evaluate_sector_valuation(company, forensics)
    compounder = calculate_dca_compounder_score(company, forensics, valuation, trading_value)

    res = dict(company)
    res["forensics"] = forensics
    res["is_value_trap"] = forensics["is_value_trap"]
    res["forensic_flags"] = forensics["flags"]
    res["forensic_reasons"] = forensics["reasons"]

    res["valuation_status"] = valuation["status"]
    res["is_undervalued"] = valuation["is_undervalued"]
    res["justified_pbv"] = valuation["justified_pbv"]
    res["valuation_badge"] = valuation["verdict_badge"]

    res["compounder_score"] = compounder["score"]
    res["dca_verdict"] = compounder["verdict"]
    res["dca_rating"] = compounder["dca_rating"]
    res["intellect_badges"] = compounder["badges"]
    res["ai_thesis"] = compounder["ai_thesis"]

    return res
