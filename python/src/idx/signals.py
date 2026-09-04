"""
Decision-support signals over the exported Parquet datasets.

Each screen answers one concrete money question and is a pure
DataFrame-in → DataFrame-out transform so it stays testable without network:

- foreign_flow_radar:   where is foreign money accumulating / distributing?
- audit_risk_shield:    which listed companies carry non-clean audit opinions?
- dilution_watch:       which companies recently filed dilutive corporate actions?
- sharia_value_screen:  cheap, profitable, sharia-flagged candidates.

build_briefing() runs all screens over data/parquet exports and renders a
markdown + JSON briefing under data/briefings/ for daily consumption.

Usage:
    uv run idx signals
"""

import datetime
import json
import os
from typing import Any

import pandas as pd

from idx.core.utils import DATA_DIR, get_logger

log = get_logger("idx.signals")

# ── Defaults (overridable per call / CLI flags) ───────────────────────────────

PARQUET_DIR = os.path.join(DATA_DIR, "parquet")
BRIEFING_DIR = os.path.join(DATA_DIR, "briefings")

FOREIGN_WINDOW_DAYS = 5  # sessions aggregated per stock
FOREIGN_MIN_TURNOVER_RP = 1e9  # avg daily value filter: Rp1B
FOREIGN_MIN_PCT_FLOAT = 0.5  # |net foreign flow| as % of free float

NEGO_WINDOW_DAYS = 20  # sessions aggregated for off-market crossing
NEGO_MIN_VALUE_RP = 25e9  # min total nego value: Rp25B
NEGO_MIN_PCT = 75.0  # min % of total volume transacted off-market (pasar nego)

RISK_OPINIONS = {"WDP", "TMP", "TMTP", "TL"}  # qualified / disclaimer / adverse
CLEAN_OPINIONS = {"WTM", "WTP", ""}  # Wajar Tanpa Modifikasi/Pengecualian

DILUTIVE_TYPES = frozenset({"PrivatePlacement", "kurangModal", "waran", "konversiSaham"})
DILUTION_LOOKBACK_DAYS = 90

SHARIA_FLAG = "S"
SHARIA_MAX_PER = 12.0
SHARIA_MIN_ROE = 12.0

SHARIA_FLAG = "S"
SHARIA_MAX_PER = 12.0
SHARIA_MIN_ROE = 12.0
SHARIA_MAX_DER = 2.0  # screens out junk-leverage names that inflate ROE


def _load_parquet(name):
    """Loads one consolidated Parquet export; returns empty DataFrame if absent."""
    path = os.path.join(PARQUET_DIR, name)
    if not os.path.exists(path):
        log.warning("Parquet export missing: %s (run `cli.py parquet` first)", path)
        return pd.DataFrame()
    return pd.read_parquet(path)


def _latest_per_code(ratios):
    """Reduces financial-ratios rows to the latest fsDate snapshot per code."""
    df = ratios.copy()
    df["fsDate"] = pd.to_datetime(df["fsDate"], errors="coerce")
    df = df.sort_values("fsDate").drop_duplicates("code", keep="last")
    return df


def _md_table(df, float_fmt="{:.2f}"):
    """Renders a compact pipe-table for the markdown briefing."""
    if len(df) == 0:
        return "_No hits._\n"
    show = df.copy()
    for col in show.columns:
        if pd.api.types.is_float_dtype(show[col]):
            show[col] = show[col].map(lambda v: float_fmt.format(v) if pd.notna(v) else "-")
    header = "| " + " | ".join(show.columns) + " |"
    sep = "|" + "|".join("---" for _ in show.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in r) + " |" for r in show.itertuples(index=False)]
    return "\n".join([header, sep, *rows]) + "\n"


# ── Screen 1: Foreign flow radar ──────────────────────────────────────────────


def foreign_flow_radar(
    stock,
    *,
    window_days=FOREIGN_WINDOW_DAYS,
    min_turnover_rp=FOREIGN_MIN_TURNOVER_RP,
    min_abs_pct_float=FOREIGN_MIN_PCT_FLOAT,
):
    """Aggregates net foreign flow per stock over the last N sessions.

    Args:
        stock: consolidated stock_summary rows (Date, StockCode, Close, Value,
            TradebleShares, NetForeignFlow — or ForeignBuy/ForeignSell).
        window_days: number of most-recent distinct sessions to aggregate.
        min_turnover_rp: keep stocks with mean daily Value above this.
        min_abs_pct_float: keep stocks whose |NFF| exceeds this % of free float.

    Returns:
        DataFrame [StockCode, Close, Sessions, NFF_MSh, PctFloat, AvgValueRpB,
        Signal] sorted by PctFloat descending. NFF_MSh = net foreign flow in
        million shares.
    """
    df = stock.copy()
    if len(df) == 0:
        return pd.DataFrame(
            columns=[
                "StockCode",
                "Close",
                "Sessions",
                "NFF_MSh",
                "PctFloat",
                "AvgValueRpB",
                "Signal",
            ]
        )

    if "NetForeignFlow" not in df.columns:
        df["NetForeignFlow"] = df["ForeignBuy"] - df["ForeignSell"]

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    last_dates = sorted(df["Date"].dropna().unique())[-window_days:]
    df = df[df["Date"].isin(last_dates)]

    g = df.groupby("StockCode").agg(
        Close=("Close", "last"),
        Sessions=("Date", "nunique"),
        NFF_Shares=("NetForeignFlow", "sum"),
        AvgValue=("Value", "mean"),
        TradebleShares=("TradebleShares", "first"),
    )
    g = g[(g["AvgValue"] > min_turnover_rp) & (g["TradebleShares"] > 0)]
    g["PctFloat"] = g["NFF_Shares"] / g["TradebleShares"] * 100.0
    g = g[g["PctFloat"].abs() >= min_abs_pct_float]
    g["Signal"] = g["PctFloat"].map(lambda p: "accumulate" if p > 0 else "distribute")

    out = g.reset_index().rename(columns={"AvgValue": "AvgValueRpB"})
    out["AvgValueRpB"] = out["AvgValueRpB"] / 1e9
    out["NFF_MSh"] = (out["NFF_Shares"] / 1e6).round(2)
    out = out.sort_values("PctFloat", ascending=False, ignore_index=True)
    return out[["StockCode", "Close", "Sessions", "NFF_MSh", "PctFloat", "AvgValueRpB", "Signal"]]


# ── Screen 2: Audit risk shield ───────────────────────────────────────────────


def audit_risk_shield(ratios):
    """Flags latest-snapshot filings whose audit opinion is not clean.

    Args:
        ratios: financial_ratios rows (code, stockName, fsDate, opini, roe, per).

    Returns:
        DataFrame [code, stockName, opini, fsDate, roe, per] for opini in
        {WDP, TMP, TMTP, TL}, latest filing per code, fsDate descending.
    """
    if len(ratios) == 0:
        return pd.DataFrame(columns=["code", "stockName", "opini", "fsDate", "roe", "per"])

    df = _latest_per_code(ratios)
    df = df[df["opini"].isin(RISK_OPINIONS)]
    df = df.sort_values("fsDate", ascending=False)
    out = df[["code", "stockName", "opini", "fsDate", "roe", "per"]].reset_index(drop=True)
    out["fsDate"] = pd.to_datetime(out["fsDate"], errors="coerce").dt.strftime("%Y-%m-%d")
    return out


# ── Screen 3: Dilution watch ──────────────────────────────────────────────────


def dilution_watch(actions, *, lookback_days=DILUTION_LOOKBACK_DAYS, on_date=None):
    """Lists recent dilutive corporate actions within the lookback window.

    Args:
        actions: corporate_actions rows (KodeEmiten, TanggalPencatatan,
            JenisTindakan, caType).
        lookback_days: how far back to scan from on_date.
        on_date: reference date; defaults to today.

    Returns:
        DataFrame [KodeEmiten, caType, TanggalPencatatan, JenisTindakan]
        sorted by date descending.
    """
    cols = ["KodeEmiten", "caType", "TanggalPencatatan", "JenisTindakan"]
    if len(actions) == 0:
        return pd.DataFrame(columns=cols)

    ref = pd.Timestamp(on_date) if on_date else pd.Timestamp.today()
    df = actions.copy()
    df["TanggalPencatatan"] = pd.to_datetime(df["TanggalPencatatan"], errors="coerce")
    cutoff = ref - pd.Timedelta(days=lookback_days)
    df = df[
        df["caType"].isin(DILUTIVE_TYPES)
        & (df["TanggalPencatatan"] >= cutoff)
        & (df["TanggalPencatatan"] <= ref)
    ]
    df = df.sort_values("TanggalPencatatan", ascending=False)

    out = df[cols].reset_index(drop=True)
    out["TanggalPencatatan"] = out["TanggalPencatatan"].dt.strftime("%Y-%m-%d")
    return out


# ── Screen 4: Sharia value screen ─────────────────────────────────────────────


def sharia_value_screen(
    ratios,
    *,
    max_per=SHARIA_MAX_PER,
    min_roe=SHARIA_MIN_ROE,
    max_der=None,
    exclude_risky_opinion=True,
):
    """Screens sharia-flagged stocks with positive PER and strong ROE.

    Args:
        ratios: financial_ratios rows (sharia flag 'S', per, roe, deRatio,
            priceBV, opini).
        max_per: upper PER bound.
        min_roe: lower ROE bound (%).
        max_der: optional DER upper bound; None skips the filter.
        exclude_risky_opinion: drop names with non-clean audit opinions.

    Returns:
        DataFrame [code, stockName, per, roe, deRatio, priceBV] by ROE desc.
    """
    cols = ["code", "stockName", "per", "roe", "deRatio", "priceBV"]
    if len(ratios) == 0:
        return pd.DataFrame(columns=cols)

    df = _latest_per_code(ratios)
    mask = (
        (df["sharia"] == SHARIA_FLAG)
        & (df["per"] > 0)
        & (df["per"] < max_per)
        & (df["roe"] >= min_roe)
    )
    if max_der is not None:
        mask &= df["deRatio"] <= max_der
    if exclude_risky_opinion:
        mask &= ~df["opini"].isin(RISK_OPINIONS)
    df = df[mask]

    avail_cols = [c for c in cols if c in df.columns]
    return df[avail_cols].sort_values("roe", ascending=False).reset_index(drop=True)


# ── Screen 5: Pasar Nego Crossing Radar ───────────────────────────────────────


def pasar_nego_crossing_screen(
    stock,
    *,
    window_days=NEGO_WINDOW_DAYS,
    min_nego_val_rp=NEGO_MIN_VALUE_RP,
    min_nego_pct=NEGO_MIN_PCT,
):
    """Detects massive off-market negotiated board trading (Pasar Negosiasi).

    Large institutional crossing blocks often precede mandatory tender offers,
    strategic M&A, private placements, or major restructuring.

    Args:
        stock: consolidated stock_summary rows (Date, StockCode, Close, Value,
            NonRegularValue, NonRegularVolume, NonRegularFrequency).
        window_days: number of most-recent distinct sessions to aggregate.
        min_nego_val_rp: min aggregate non-regular turnover in IDR (default Rp 25B).
        min_nego_pct: min % share of non-regular value over total value (default 75%).

    Returns:
        DataFrame [StockCode, Close, Sessions, NegoValRpB, RegValRpB, NegoSharePct,
        NegoTrades] sorted by NegoValRpB descending.
    """
    cols = [
        "StockCode",
        "Close",
        "Sessions",
        "NegoValRpB",
        "RegValRpB",
        "NegoSharePct",
        "NegoTrades",
    ]
    if len(stock) == 0:
        return pd.DataFrame(columns=cols)

    df = stock.copy()
    if "NonRegularValue" not in df.columns:
        return pd.DataFrame(columns=cols)

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    last_dates = sorted(df["Date"].dropna().unique())[-window_days:]
    df = df[df["Date"].isin(last_dates)]

    g = df.groupby("StockCode").agg(
        Close=("Close", "last"),
        Sessions=("Date", "nunique"),
        TotalNegoVal=("NonRegularValue", "sum"),
        TotalRegVal=("Value", "sum"),
        NegoTrades=("NonRegularFrequency", "sum"),
    )

    g["TotalCombinedVal"] = g["TotalNegoVal"] + g["TotalRegVal"]
    g["NegoSharePct"] = (g["TotalNegoVal"] / (g["TotalCombinedVal"] + 1e-9)) * 100.0

    g = g[(g["TotalNegoVal"] >= min_nego_val_rp) & (g["NegoSharePct"] >= min_nego_pct)]

    out = g.reset_index()
    out["NegoValRpB"] = (out["TotalNegoVal"] / 1e9).round(2)
    out["RegValRpB"] = (out["TotalRegVal"] / 1e9).round(2)
    out["NegoSharePct"] = out["NegoSharePct"].round(1)
    out["NegoTrades"] = out["NegoTrades"].fillna(0).astype(int)
    out = out.sort_values("NegoValRpB", ascending=False, ignore_index=True)
    return out[cols]


# ── Screen 6: Bandarmology & Broker Concentration Radar ────────────────────────


INSTITUTIONAL_BROKERS = frozenset(
    {"AK", "BK", "ZP", "CS", "KZ", "RX", "CC", "LG", "DX", "AI", "MS", "CG"}
)
RETAIL_BROKERS = frozenset({"YP", "PD", "XC", "NI", "KK", "CP", "AZ", "OD", "SQ", "XL"})


def broker_concentration_screen(broker, *, on_date=None, top_k=5):
    """Calculates Top-N broker concentration (CR_k) and institutional vs retail flow.

    Args:
        broker: broker_summary DataFrame (Date, IDFirm, FirmName, Value, Volume).
        on_date: optional ISO date string. Defaults to latest session in data.
        top_k: top N brokers to evaluate for concentration ratio.

    Returns:
        tuple (summary_dict, top_brokers_df)
    """
    cols = ["Rank", "IDFirm", "FirmName", "ValueRpB", "SharePct", "Category"]
    if len(broker) == 0:
        return {}, pd.DataFrame(columns=cols)

    df = broker.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        if on_date:
            target_dt = pd.to_datetime(on_date)
            df = df[df["Date"] == target_dt]
        else:
            latest_dt = df["Date"].max()
            df = df[df["Date"] == latest_dt]

    if len(df) == 0:
        return {}, pd.DataFrame(columns=cols)

    for c in ("Value", "Volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Group by firm
    grouped = df.groupby(["IDFirm", "FirmName"], as_index=False)["Value"].sum()
    total_val = grouped["Value"].sum()
    if total_val <= 0:
        return {}, pd.DataFrame(columns=cols)

    grouped = grouped.sort_values("Value", ascending=False).reset_index(drop=True)
    grouped["SharePct"] = (grouped["Value"] / total_val * 100.0).round(2)
    grouped["ValueRpB"] = (grouped["Value"] / 1e9).round(2)
    grouped["Rank"] = grouped.index + 1

    def _cat(code):
        if code in INSTITUTIONAL_BROKERS:
            return "Institutional/Foreign"
        if code in RETAIL_BROKERS:
            return "Retail"
        return "General"

    grouped["Category"] = grouped["IDFirm"].apply(_cat)

    cr1 = grouped.head(1)["SharePct"].sum().round(2)
    cr3 = grouped.head(3)["SharePct"].sum().round(2)
    cr5 = grouped.head(5)["SharePct"].sum().round(2)

    inst_val = grouped[grouped["IDFirm"].isin(INSTITUTIONAL_BROKERS)]["Value"].sum()
    retail_val = grouped[grouped["IDFirm"].isin(RETAIL_BROKERS)]["Value"].sum()

    inst_share = round((inst_val / total_val) * 100.0, 2)
    retail_share = round((retail_val / total_val) * 100.0, 2)
    dominance_ratio = round(inst_val / (retail_val + 1e-9), 2)

    summary = {
        "total_market_turnover_rp_b": round(total_val / 1e9, 2),
        "cr1_pct": cr1,
        "cr3_pct": cr3,
        "cr5_pct": cr5,
        "institutional_share_pct": inst_share,
        "retail_share_pct": retail_share,
        "institutional_to_retail_ratio": dominance_ratio,
        "top_dominant_broker": grouped.iloc[0]["IDFirm"] if len(grouped) > 0 else None,
    }

    return summary, grouped.head(top_k)[cols]


STEALTH_SMART_BROKERS = frozenset({"AK", "BK", "ZP", "RX", "CC"})
STEALTH_RETAIL_BROKERS = frozenset({"YP", "PD", "XC", "NI"})


def detect_stealth_accumulation(
    broker: pd.DataFrame,
    stock: pd.DataFrame | None = None,
    *,
    on_date: str | None = None,
    min_smart_delta: float = 3.0,
    max_price_change_pct: float = 1.0,
) -> dict[str, Any]:
    """Detects 'Stealth Accumulation vs Retail Trap' bandarmology anomalies.

    Computes:
        Smart Money Delta = sum(Turnover(AK, BK, ZP, RX, CC)) / sum(Turnover(YP, PD, XC, NI))

    Flags:
        - STEALTH_ACCUMULATION: Price moves < 1% while Smart Money Delta > 3.0
        - RETAIL_TRAP: Price moves > 1% while Smart Money Delta < 0.5 (retail buying into distribution)
        - NEUTRAL otherwise.

    Args:
        broker: broker_summary DataFrame (Date, IDFirm, Value, Volume, optional StockCode)
        stock: stock_summary DataFrame (Date, StockCode, Close, Previous, Value, ForeignBuy, ForeignSell)
        on_date: optional ISO date string
        min_smart_delta: threshold ratio to qualify as smart accumulation (default 3.0)
        max_price_change_pct: max price movement % for stealth accumulation (default 1.0)

    Returns:
        dict with keys: 'summary', 'anomalies_df', 'signal', 'smart_money_delta'
    """
    if len(broker) == 0:
        return {
            "signal": "NO_DATA",
            "smart_money_delta": 0.0,
            "summary": {},
            "anomalies_df": pd.DataFrame(),
        }

    b_df = broker.copy()
    if "Date" in b_df.columns:
        b_df["Date"] = pd.to_datetime(b_df["Date"], errors="coerce")
        if on_date:
            target_dt = pd.to_datetime(on_date)
            b_df = b_df[b_df["Date"] == target_dt]
        else:
            latest_dt = b_df["Date"].max()
            b_df = b_df[b_df["Date"] == latest_dt]

    for c in ("Value", "Volume"):
        if c in b_df.columns:
            b_df[c] = pd.to_numeric(b_df[c], errors="coerce").fillna(0)

    has_stock_code = "StockCode" in b_df.columns

    smart_val = float(b_df[b_df["IDFirm"].isin(STEALTH_SMART_BROKERS)]["Value"].sum())
    retail_val = float(b_df[b_df["IDFirm"].isin(STEALTH_RETAIL_BROKERS)]["Value"].sum())
    overall_delta = round(float(smart_val / (retail_val + 1e-9)), 2)

    records = []
    if has_stock_code:
        for ticker, g in b_df.groupby("StockCode"):
            s_val = float(g[g["IDFirm"].isin(STEALTH_SMART_BROKERS)]["Value"].sum())
            r_val = float(g[g["IDFirm"].isin(STEALTH_RETAIL_BROKERS)]["Value"].sum())
            delta = round(float(s_val / (r_val + 1e-9)), 2)

            price_chg = 0.0
            if stock is not None and len(stock) > 0 and "StockCode" in stock.columns:
                s_rows = stock[stock["StockCode"] == ticker]
                if len(s_rows) > 0:
                    last_s = s_rows.iloc[-1]
                    c_p = float(last_s.get("Close", 0))
                    p_p = float(last_s.get("Previous", c_p))
                    if p_p > 0:
                        price_chg = (c_p - p_p) / p_p * 100.0

            if abs(price_chg) <= max_price_change_pct and delta >= min_smart_delta:
                records.append(
                    {
                        "StockCode": ticker,
                        "PriceChangePct": round(price_chg, 2),
                        "SmartMoneyDelta": delta,
                        "SmartTurnoverRpM": round(s_val / 1e6, 2),
                        "RetailTurnoverRpM": round(r_val / 1e6, 2),
                        "Signal": "STEALTH_ACCUMULATION",
                        "Priority": "HIGH",
                    }
                )
            elif price_chg > 1.0 and delta < 0.5:
                records.append(
                    {
                        "StockCode": ticker,
                        "PriceChangePct": round(price_chg, 2),
                        "SmartMoneyDelta": delta,
                        "SmartTurnoverRpM": round(s_val / 1e6, 2),
                        "RetailTurnoverRpM": round(r_val / 1e6, 2),
                        "Signal": "RETAIL_TRAP",
                        "Priority": "MEDIUM",
                    }
                )
    elif stock is not None and len(stock) > 0 and "StockCode" in stock.columns:
        s_df = stock.copy()
        if "Date" in s_df.columns:
            s_df["Date"] = pd.to_datetime(s_df["Date"], errors="coerce")
            if on_date:
                s_df = s_df[s_df["Date"] == pd.to_datetime(on_date)]
            else:
                s_df = s_df[s_df["Date"] == s_df["Date"].max()]

        for _, row in s_df.iterrows():
            c_p = float(row.get("Close", 0))
            p_p = float(row.get("Previous", c_p))
            if p_p <= 0 or c_p <= 0:
                continue
            price_chg = (c_p - p_p) / p_p * 100.0
            nff = float(row.get("ForeignBuy", 0)) - float(row.get("ForeignSell", 0))
            val = float(row.get("Value", 0))

            if val >= 5e9:
                flow_ratio = nff / val if val > 0 else 0
                if abs(price_chg) <= max_price_change_pct and (
                    overall_delta >= min_smart_delta or flow_ratio > 0.25
                ):
                    records.append(
                        {
                            "StockCode": str(row.get("StockCode")),
                            "PriceChangePct": round(price_chg, 2),
                            "SmartMoneyDelta": overall_delta,
                            "NetForeignFlowRpB": round(nff / 1e9, 2),
                            "TurnoverRpB": round(val / 1e9, 2),
                            "Signal": "STEALTH_ACCUMULATION",
                            "Priority": "HIGH" if overall_delta >= min_smart_delta else "MEDIUM",
                        }
                    )
                elif price_chg > 1.0 and (overall_delta < 0.5 or flow_ratio < -0.25):
                    records.append(
                        {
                            "StockCode": str(row.get("StockCode")),
                            "PriceChangePct": round(price_chg, 2),
                            "SmartMoneyDelta": overall_delta,
                            "NetForeignFlowRpB": round(nff / 1e9, 2),
                            "TurnoverRpB": round(val / 1e9, 2),
                            "Signal": "RETAIL_TRAP",
                            "Priority": "MEDIUM",
                        }
                    )

    anomalies_df = pd.DataFrame(records)
    if not anomalies_df.empty:
        anomalies_df = anomalies_df.sort_values(
            ["Priority", "SmartMoneyDelta"], ascending=[True, False], ignore_index=True
        )

    if overall_delta >= min_smart_delta:
        overall_signal = "STEALTH_ACCUMULATION"
    elif overall_delta < 0.5:
        overall_signal = "RETAIL_TRAP"
    else:
        overall_signal = "NEUTRAL"

    summary = {
        "on_date": on_date
        or (
            b_df["Date"].max().strftime("%Y-%m-%d")
            if "Date" in b_df.columns and not b_df.empty
            else None
        ),
        "smart_money_turnover_rp_b": round(smart_val / 1e9, 2),
        "retail_turnover_rp_b": round(retail_val / 1e9, 2),
        "smart_money_delta": overall_delta,
        "market_signal": overall_signal,
        "anomalies_detected": len(anomalies_df),
    }

    return {
        "summary": summary,
        "signal": overall_signal,
        "smart_money_delta": overall_delta,
        "anomalies_df": anomalies_df,
    }


# ── Technical Indicators & Vectorized Signals ─────────────────────────────────


def compute_technical_indicators(stock, ticker=None, rsi_period=14):
    """Computes vectorized technical indicators (RSI-14, EMA 20/50/200, Bollinger Bands, ATR-14).

    Args:
        stock: stock_summary DataFrame (Date, StockCode, OpenPrice, High, Low, Close, Volume).
        ticker: optional ticker symbol. If None, processes all tickers.
        rsi_period: period for Relative Strength Index.

    Returns:
        DataFrame with computed technical indicator columns.
    """
    if len(stock) == 0:
        return pd.DataFrame()

    df = stock.copy()
    if ticker:
        df = df[df["StockCode"] == ticker.upper()]

    if len(df) == 0:
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ("OpenPrice", "High", "Low", "Close", "Volume", "Previous"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values(["StockCode", "Date"]).reset_index(drop=True)

    def _calc_group(g):
        if len(g) < 2:
            g["RSI14"] = None
            g["EMA20"] = None
            g["EMA50"] = None
            g["EMA200"] = None
            g["BB_Upper"] = None
            g["BB_Lower"] = None
            g["BB_PctB"] = None
            g["ATR14"] = None
            g["VolRatio20"] = None
            g["TrendRegime"] = "INSUFFICIENT_DATA"
            return g

        close = g["Close"]
        # EMAs
        g["EMA20"] = close.ewm(span=20, adjust=False).mean().round(2)
        g["EMA50"] = close.ewm(span=50, adjust=False).mean().round(2)
        g["EMA200"] = close.ewm(span=200, adjust=False).mean().round(2)

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
        avg_loss = loss.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        g["RSI14"] = (100 - (100 / (1 + rs))).round(1)

        # Bollinger Bands (20-day, 2 std)
        sma20 = close.rolling(20, min_periods=5).mean()
        std20 = close.rolling(20, min_periods=5).std()
        g["BB_Upper"] = (sma20 + 2 * std20).round(2)
        g["BB_Lower"] = (sma20 - 2 * std20).round(2)
        band_width = g["BB_Upper"] - g["BB_Lower"]
        g["BB_PctB"] = ((close - g["BB_Lower"]) / (band_width + 1e-9)).round(2)

        # ATR-14
        if "High" in g.columns and "Low" in g.columns and "Previous" in g.columns:
            prev_c = (
                g["Close"].shift(1).fillna(g["OpenPrice"] if "OpenPrice" in g.columns else close)
            )
            tr = pd.concat(
                [
                    (g["High"] - g["Low"]).abs(),
                    (g["High"] - prev_c).abs(),
                    (g["Low"] - prev_c).abs(),
                ],
                axis=1,
            ).max(axis=1)
            g["ATR14"] = tr.ewm(span=14, adjust=False).mean().round(2)
        else:
            g["ATR14"] = None

        # Volume ratio
        if "Volume" in g.columns:
            vol = g["Volume"]
            vol_sma20 = vol.rolling(20, min_periods=5).mean()
            g["VolRatio20"] = (vol / (vol_sma20 + 1e-9)).round(2)
        else:
            g["VolRatio20"] = 1.0

        # Trend regime
        last_c = close.iloc[-1]
        e20 = g["EMA20"].iloc[-1]
        e50 = g["EMA50"].iloc[-1]
        if pd.notna(e20) and pd.notna(e50):
            if last_c > e20 > e50:
                trend = "STRONG_BULLISH"
            elif last_c > e20:
                trend = "BULLISH"
            elif last_c < e20 < e50:
                trend = "STRONG_BEARISH"
            elif last_c < e20:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
        else:
            trend = "NEUTRAL"
        g["TrendRegime"] = trend

        return g

    results = []
    for _, g in df.groupby("StockCode"):
        results.append(_calc_group(g.copy()))

    out = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
    return out


# ── Screen 7: Composite Alpha Ranking Model ───────────────────────────────────


def composite_alpha_ranking(
    stock,
    ratios,
    actions=None,
    *,
    min_turnover_rp=FOREIGN_MIN_TURNOVER_RP,
    top_n=20,
):
    """Combines Value Fundamentals, Foreign Money Accumulation, Technical Trend & Risk factors.

    Returns:
        DataFrame sorted by CompositeAlphaScore descending.
    """
    cols = [
        "StockCode",
        "StockName",
        "Close",
        "AlphaScore",
        "PER",
        "ROE",
        "DER",
        "NetForeignFlow_MSh",
        "RSI14",
        "TrendRegime",
        "AuditOpinion",
    ]
    if len(stock) == 0 or len(ratios) == 0:
        return pd.DataFrame(columns=cols)

    radar = foreign_flow_radar(
        stock, window_days=20, min_turnover_rp=min_turnover_rp, min_abs_pct_float=0.0
    )
    tech = compute_technical_indicators(stock)
    if len(tech) > 0:
        latest_tech = tech.sort_values("Date").groupby("StockCode").last().reset_index()
    else:
        latest_tech = pd.DataFrame(columns=["StockCode", "RSI14", "TrendRegime"])

    lat_ratios = _latest_per_code(ratios).rename(columns={"code": "StockCode"})
    merged = pd.merge(lat_ratios, radar, on="StockCode", how="inner")
    merged = pd.merge(
        merged, latest_tech[["StockCode", "RSI14", "TrendRegime"]], on="StockCode", how="left"
    )

    if len(merged) == 0:
        return pd.DataFrame(columns=cols)

    # Score components (0-100 scale)
    scores = pd.Series(50.0, index=merged.index)

    # 1. Fundamental Value score (ROE, PER, DER)
    roe = (
        pd.to_numeric(merged["roe"], errors="coerce").fillna(0)
        if "roe" in merged.columns
        else pd.Series(0.0, index=merged.index)
    )
    per = (
        pd.to_numeric(merged["per"], errors="coerce").fillna(999)
        if "per" in merged.columns
        else pd.Series(999.0, index=merged.index)
    )
    der = (
        pd.to_numeric(merged["deRatio"], errors="coerce").fillna(999)
        if "deRatio" in merged.columns
        else pd.Series(999.0, index=merged.index)
    )

    scores += (roe.clip(0, 30) / 30.0) * 20.0  # Up to +20 for ROE
    scores += ((per > 0) & (per < 15)).astype(float) * 15.0  # +15 for fair/low PER
    scores -= (der > 3.0).astype(float) * 15.0  # -15 for high debt

    # 2. Foreign Flow factor
    pct_float = (
        pd.to_numeric(merged["PctFloat"], errors="coerce").fillna(0)
        if "PctFloat" in merged.columns
        else pd.Series(0.0, index=merged.index)
    )
    scores += (pct_float.clip(-5, 5) / 5.0) * 25.0  # Up to +25 for heavy accumulation

    # 3. Technical factor (RSI in sweet spot 45-65 & Bullish trend)
    rsi = (
        pd.to_numeric(merged["RSI14"], errors="coerce").fillna(50)
        if "RSI14" in merged.columns
        else pd.Series(50.0, index=merged.index)
    )
    scores += ((rsi >= 45) & (rsi <= 68)).astype(float) * 10.0
    if "TrendRegime" in merged.columns:
        scores += (merged["TrendRegime"].isin(["STRONG_BULLISH", "BULLISH"])).astype(float) * 10.0

    # 4. Audit Risk Penalty
    if "opini" in merged.columns:
        scores -= merged["opini"].isin(RISK_OPINIONS).astype(float) * 40.0

    merged["AlphaScore"] = scores.clip(0, 100).round(1)
    merged["StockName"] = (
        merged["stockName"]
        if "stockName" in merged.columns
        else merged.get("StockName", merged["StockCode"])
    )
    merged["PER"] = per.round(1)
    merged["ROE"] = roe.round(1)
    merged["DER"] = der.round(2)
    merged["NetForeignFlow_MSh"] = merged["NFF_MSh"]
    merged["AuditOpinion"] = merged["opini"].fillna("Clean")

    res = merged.sort_values("AlphaScore", ascending=False).reset_index(drop=True)
    return res[cols].head(top_n)


# ── Webhook Notification Helper ──────────────────────────────────────────────


def send_webhook_briefing(webhook_url, briefing_result, summary_text=None):
    """Sends briefing alerts to a Discord, Slack, or generic webhook endpoint."""
    import urllib.request

    if not webhook_url:
        return False

    payload = {
        "text": summary_text
        or f"IDX Daily Signal Briefing — {briefing_result.get('date', 'Today')}",
        "content": summary_text
        or (
            f"**IDX Daily Signal Briefing — {briefing_result.get('date', 'Today')}**\n"
            f"- Radar Hits: {briefing_result.get('radar_rows', 0)}\n"
            f"- Risk Flags: {briefing_result.get('shield_rows', 0)}\n"
            f"- Dilution Warnings: {briefing_result.get('dilution_rows', 0)}\n"
            f"- Sharia Value: {briefing_result.get('sharia_rows', 0)}\n"
            f"- Pasar Nego Crossings: {briefing_result.get('nego_rows', 0)}"
        ),
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "IDX-BEI/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info("Webhook delivered successfully: HTTP %d", resp.status)
            return True
    except Exception as e:
        log.warning("Failed to deliver webhook alert: %s", e)
        return False


# ── Briefing builder ──────────────────────────────────────────────────────────


def build_briefing(
    *,
    date=None,
    out_dir=BRIEFING_DIR,
    window_days=FOREIGN_WINDOW_DAYS,
    min_turnover_rp=FOREIGN_MIN_TURNOVER_RP,
    min_abs_pct_float=FOREIGN_MIN_PCT_FLOAT,
    dilution_lookback_days=DILUTION_LOOKBACK_DAYS,
    sharia_max_per=SHARIA_MAX_PER,
    sharia_min_roe=SHARIA_MIN_ROE,
    nego_window_days=NEGO_WINDOW_DAYS,
    min_nego_val_rp=NEGO_MIN_VALUE_RP,
    min_nego_pct=NEGO_MIN_PCT,
    webhook_url=None,
):
    """Runs every screen over the Parquet exports and renders a briefing.

    Args:
        date: label/reference date; defaults to the latest session in data.
        out_dir: output directory (default data/briefings).
        webhook_url: optional webhook URL to broadcast summary alert.
        Remaining args: forwarded to the individual screens.

    Returns:
        dict with per-section row counts, trading date, and output file paths.
    """
    window_days = window_days if window_days is not None else FOREIGN_WINDOW_DAYS
    min_turnover_rp = min_turnover_rp if min_turnover_rp is not None else FOREIGN_MIN_TURNOVER_RP
    min_abs_pct_float = (
        min_abs_pct_float if min_abs_pct_float is not None else FOREIGN_MIN_PCT_FLOAT
    )
    dilution_lookback_days = (
        dilution_lookback_days if dilution_lookback_days is not None else DILUTION_LOOKBACK_DAYS
    )
    sharia_max_per = sharia_max_per if sharia_max_per is not None else SHARIA_MAX_PER
    sharia_min_roe = sharia_min_roe if sharia_min_roe is not None else SHARIA_MIN_ROE
    nego_window_days = nego_window_days if nego_window_days is not None else NEGO_WINDOW_DAYS
    min_nego_val_rp = min_nego_val_rp if min_nego_val_rp is not None else NEGO_MIN_VALUE_RP
    min_nego_pct = min_nego_pct if min_nego_pct is not None else NEGO_MIN_PCT
    out_dir = out_dir if out_dir is not None else BRIEFING_DIR

    stock = _load_parquet("stock_summary.parquet")
    ratios = _load_parquet("financial_ratios.parquet")
    actions = _load_parquet("corporate_actions.parquet")
    broker = _load_parquet("broker_summary.parquet")

    radar = foreign_flow_radar(
        stock,
        window_days=window_days,
        min_turnover_rp=min_turnover_rp,
        min_abs_pct_float=min_abs_pct_float,
    )
    shield = audit_risk_shield(ratios)
    watch = dilution_watch(actions, lookback_days=dilution_lookback_days, on_date=date)
    sharia = sharia_value_screen(
        ratios, max_per=sharia_max_per, min_roe=sharia_min_roe, max_der=SHARIA_MAX_DER
    )
    nego = pasar_nego_crossing_screen(
        stock,
        window_days=nego_window_days,
        min_nego_val_rp=min_nego_val_rp,
        min_nego_pct=min_nego_pct,
    )
    broker_sum, top_brokers = broker_concentration_screen(broker, on_date=date, top_k=5)
    stealth_res = detect_stealth_accumulation(broker, stock, on_date=date)
    alpha = composite_alpha_ranking(
        stock, ratios, actions=actions, min_turnover_rp=min_turnover_rp, top_n=10
    )

    if len(stock) > 0:
        trade_date = pd.to_datetime(stock["Date"]).max()
        trade_date = trade_date.strftime("%Y-%m-%d")
    else:
        trade_date = date or datetime.date.today().isoformat()
    label = date or trade_date

    sections = [
        (
            "Composite Alpha Rankings",
            "Multi-factor score (Value + Foreign Flow + Momentum + Clean Audit)",
            alpha.head(10),
        ),
        (
            "Foreign Flow Radar",
            f"net foreign flow vs free float, last "
            f"{min(window_days, radar['Sessions'].max() if len(radar) else window_days)} sessions,"
            f" turnover > Rp{min_turnover_rp / 1e9:.0f}B/day, |flow| > {min_abs_pct_float}% float",
            radar.head(10),
        ),
        (
            "Bandarmology & Broker Dominance",
            f"CR1: {broker_sum.get('cr1_pct', '-')}%, CR3: {broker_sum.get('cr3_pct', '-')}%, "
            f"CR5: {broker_sum.get('cr5_pct', '-')}%, Inst/Retail ratio: {broker_sum.get('institutional_to_retail_ratio', '-')}",
            top_brokers,
        ),
        (
            "Stealth Accumulation vs Retail Trap",
            f"Smart Money Delta: {stealth_res['smart_money_delta']:.2f}, Market Signal: {stealth_res['signal']}",
            stealth_res["anomalies_df"].head(10),
        ),
        (
            "Audit Risk Shield",
            "non-clean audit opinions (WDP/TMP/TMTP/TL), latest filing",
            shield,
        ),
        (
            "Dilution Watch",
            f"dilutive actions ({', '.join(sorted(DILUTIVE_TYPES))})"
            f" in the last {dilution_lookback_days} days",
            watch.head(20),
        ),
        (
            "Sharia Value Screen",
            f"flag S, PER < {sharia_max_per:g}, ROE >= {sharia_min_roe:g}%,"
            f" DER <= {SHARIA_MAX_DER:g}%, clean opinion",
            sharia.head(15),
        ),
        (
            "Pasar Nego Crossing Radar",
            f"stealth off-market block crossings, last {nego_window_days} sessions, "
            f"nego value >= Rp{min_nego_val_rp / 1e9:.0f}B, share >= {min_nego_pct:.0f}% total",
            nego.head(10),
        ),
    ]

    lines = [
        f"# IDX Daily Signal Briefing — {label}",
        "",
        f"_Trading data through **{trade_date}**. Generated by `idx.signals`"
        f" on {datetime.date.today().isoformat()}._",
        "",
    ]
    for title, subtitle, df in sections:
        lines += [f"## {title}", "", f"_{subtitle}_", "", _md_table(df), ""]
    lines += [
        "---",
        "_Educational/research output, not investment advice."
        " Verify against official IDX disclosures before acting._",
        "",
    ]

    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, f"briefing_{label}.md")
    json_path = os.path.join(out_dir, f"briefing_{label}.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": label,
                "trade_date": trade_date,
                "composite_alpha_rankings": alpha.head(10).to_dict("records"),
                "foreign_flow_radar": radar.head(10).to_dict("records"),
                "bandarmology_summary": broker_sum,
                "top_brokers": top_brokers.to_dict("records"),
                "stealth_accumulation": {
                    "summary": stealth_res["summary"],
                    "signal": stealth_res["signal"],
                    "smart_money_delta": stealth_res["smart_money_delta"],
                    "anomalies": stealth_res["anomalies_df"].head(10).to_dict("records"),
                },
                "audit_risk_shield": shield.to_dict("records"),
                "dilution_watch": watch.to_dict("records"),
                "sharia_value_screen": sharia.to_dict("records"),
                "pasar_nego_crossing": nego.head(10).to_dict("records"),
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    result = {
        "date": label,
        "trade_date": trade_date,
        "alpha_rows": len(alpha),
        "radar_rows": len(radar),
        "broker_rows": len(top_brokers),
        "stealth_anomalies": len(stealth_res["anomalies_df"]),
        "shield_rows": len(shield),
        "dilution_rows": len(watch),
        "sharia_rows": len(sharia),
        "nego_rows": len(nego),
        "markdown": md_path,
        "json": json_path,
    }
    log.info(
        "Briefing %s: alpha=%d radar=%d brokers=%d shield=%d dilution=%d sharia=%d nego=%d",
        label,
        result["alpha_rows"],
        result["radar_rows"],
        result["broker_rows"],
        result["shield_rows"],
        result["dilution_rows"],
        result["sharia_rows"],
        result["nego_rows"],
    )

    if webhook_url:
        send_webhook_briefing(webhook_url, result)

    return result
