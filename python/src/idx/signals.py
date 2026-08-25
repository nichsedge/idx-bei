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

    return df[cols].sort_values("roe", ascending=False).reset_index(drop=True)


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

    if len(stock) > 0:
        trade_date = pd.to_datetime(stock["Date"]).max()
        trade_date = trade_date.strftime("%Y-%m-%d")
    else:
        trade_date = date or datetime.date.today().isoformat()
    label = date or trade_date

    sections = [
        (
            "Foreign Flow Radar",
            f"net foreign flow vs free float, last "
            f"{min(window_days, radar['Sessions'].max() if len(radar) else window_days)} sessions,"
            f" turnover > Rp{min_turnover_rp / 1e9:.0f}B/day, |flow| > {min_abs_pct_float}% float",
            radar.head(10),
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
                "foreign_flow_radar": radar.head(10).to_dict("records"),
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
        "radar_rows": len(radar),
        "shield_rows": len(shield),
        "dilution_rows": len(watch),
        "sharia_rows": len(sharia),
        "nego_rows": len(nego),
        "markdown": md_path,
        "json": json_path,
    }
    log.info(
        "Briefing %s: radar=%d shield=%d dilution=%d sharia=%d nego=%d",
        label,
        result["radar_rows"],
        result["shield_rows"],
        result["dilution_rows"],
        result["sharia_rows"],
        result["nego_rows"],
    )

    if webhook_url:
        send_webhook_briefing(webhook_url, result)

    return result
