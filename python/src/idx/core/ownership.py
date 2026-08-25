"""
KSEI >1% Ownership analytics and delta computation engine.

Processes KSEI daily/monthly ownership publications, parses Indonesian number
formats, and tracks position deltas for tycoons, super-insiders, and institutions.
"""

import os

import pandas as pd

from idx.core.utils import DATA_DIR, get_logger

log = get_logger("idx.core.ownership")

DEFAULT_OWNERSHIP_CSV = os.path.join(DATA_DIR, "1%ownership-2025-03-04.csv")

NOTABLE_TYCOONS = {
    "LO KHENG HONG": "Lo Kheng Hong",
    "PRAJOGO": "Prajogo Pangestu",
    "GARIBALDI THOHIR": "Garibaldi (Boy) Thohir",
    "SALIM": "Salim Group / Anthony Salim",
    "PERMADI RACHMAT": "Theodore Permadi Rachmat",
    "HAIYANTO": "Haiyanto",
    "DJONI": "Djoni",
    "SURONO SUBEKTI": "Surono Subekti",
}


def parse_indonesian_float(val) -> float:
    """Parses Indonesian formatted numbers e.g. '41,10' or '3.200.142.830'."""
    if val is None or pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return 0.0
    # Remove thousand-separator periods and replace comma with decimal point
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_ownership_csv(path=DEFAULT_OWNERSHIP_CSV) -> pd.DataFrame:
    """Loads and standardizes a KSEI >1% ownership CSV file."""
    if not os.path.exists(path):
        log.warning("Ownership file not found at %s", path)
        return pd.DataFrame()

    df = pd.read_csv(path)
    required_cols = [
        "DATE",
        "SHARE_CODE",
        "ISSUER_NAME",
        "INVESTOR_NAME",
        "TOTAL_HOLDING_SHARES",
        "PERCENTAGE",
    ]
    for col in required_cols:
        if col not in df.columns:
            log.error("Missing required column '%s' in %s", col, path)
            return pd.DataFrame()

    df["Pct"] = df["PERCENTAGE"].apply(parse_indonesian_float)
    df["Shares"] = df["TOTAL_HOLDING_SHARES"].apply(parse_indonesian_float)
    df["InvestorUpper"] = df["INVESTOR_NAME"].fillna("").astype(str).str.strip().str.upper()
    df["ShareCode"] = df["SHARE_CODE"].fillna("").astype(str).str.strip().str.upper()
    return df


def compute_ownership_deltas(
    prev_df: pd.DataFrame,
    curr_df: pd.DataFrame,
    min_pct_delta: float = 0.05,
) -> pd.DataFrame:
    """Computes changes in position between two KSEI ownership snapshots.

    Args:
        prev_df: older ownership snapshot DataFrame.
        curr_df: newer ownership snapshot DataFrame.
        min_pct_delta: minimum absolute percentage point change to report.

    Returns:
        DataFrame with columns [ShareCode, InvestorName, PrevPct, CurrPct,
        PctDelta, PrevShares, CurrShares, SharesDelta, Action].
    """
    if len(prev_df) == 0 or len(curr_df) == 0:
        return pd.DataFrame(
            columns=[
                "ShareCode",
                "InvestorName",
                "PrevPct",
                "CurrPct",
                "PctDelta",
                "SharesDelta",
                "Action",
            ]
        )

    p = (
        prev_df.groupby(["ShareCode", "InvestorUpper"])
        .agg(
            PrevPct=("Pct", "sum"),
            PrevShares=("Shares", "sum"),
            InvestorName=("INVESTOR_NAME", "first"),
        )
        .reset_index()
    )

    c = (
        curr_df.groupby(["ShareCode", "InvestorUpper"])
        .agg(
            CurrPct=("Pct", "sum"),
            CurrShares=("Shares", "sum"),
            InvestorName=("INVESTOR_NAME", "first"),
        )
        .reset_index()
    )

    merged = pd.merge(
        p, c, on=["ShareCode", "InvestorUpper"], how="outer", suffixes=("_prev", "_curr")
    )
    merged["InvestorName"] = merged["InvestorName_curr"].combine_first(merged["InvestorName_prev"])
    merged["PrevPct"] = merged["PrevPct"].fillna(0.0)
    merged["CurrPct"] = merged["CurrPct"].fillna(0.0)
    merged["PrevShares"] = merged["PrevShares"].fillna(0.0)
    merged["CurrShares"] = merged["CurrShares"].fillna(0.0)

    merged["PctDelta"] = (merged["CurrPct"] - merged["PrevPct"]).round(3)
    merged["SharesDelta"] = merged["CurrShares"] - merged["PrevShares"]

    def classify_action(row):
        if row["PrevPct"] == 0.0 and row["CurrPct"] > 0:
            return "NEW_POSITION"
        elif row["CurrPct"] == 0.0 and row["PrevPct"] > 0:
            return "FULL_EXIT"
        elif row["PctDelta"] > 0:
            return "ACCUMULATING"
        elif row["PctDelta"] < 0:
            return "DISTRIBUTING"
        return "UNCHANGED"

    merged["Action"] = merged.apply(classify_action, axis=1)
    filtered = merged[merged["PctDelta"].abs() >= min_pct_delta].copy()
    filtered = filtered.sort_values("PctDelta", ascending=False, ignore_index=True)
    return filtered[
        ["ShareCode", "InvestorName", "PrevPct", "CurrPct", "PctDelta", "SharesDelta", "Action"]
    ]


def get_tycoon_holdings(df: pd.DataFrame, tycoons: dict = None) -> pd.DataFrame:
    """Extracts all holdings belonging to notable individual investors/tycoons."""
    if len(df) == 0:
        return pd.DataFrame()
    tycoons = tycoons or NOTABLE_TYCOONS

    matches = []
    for pattern, label in tycoons.items():
        sub = df[df["InvestorUpper"].str.contains(pattern, case=False, na=False)].copy()
        if len(sub) > 0:
            sub["TycoonLabel"] = label
            matches.append(sub)

    if not matches:
        return pd.DataFrame()

    out = pd.concat(matches, ignore_index=True)
    return out[
        [
            "TycoonLabel",
            "ShareCode",
            "ISSUER_NAME",
            "InvestorUpper",
            "Pct",
            "Shares",
            "LOCAL_FOREIGN",
            "INVESTOR_TYPE",
        ]
    ].sort_values(["TycoonLabel", "Pct"], ascending=[True, False], ignore_index=True)


def get_multi_holding_individuals(df: pd.DataFrame, min_tickers: int = 2) -> pd.DataFrame:
    """Finds individual investors who hold >1% stakes across multiple listed companies."""
    if len(df) == 0:
        return pd.DataFrame()

    # Filter individual investor type ('ID')
    individuals = df[df["INVESTOR_TYPE"] == "ID"].copy()
    if len(individuals) == 0:
        individuals = df

    g = (
        individuals.groupby("InvestorUpper")
        .agg(
            TickerCount=("ShareCode", "nunique"),
            Tickers=("ShareCode", lambda x: ", ".join(sorted(x.unique()))),
            MaxPct=("Pct", "max"),
            TotalShares=("Shares", "sum"),
        )
        .reset_index()
    )

    g = g[g["TickerCount"] >= min_tickers].sort_values(
        "TickerCount", ascending=False, ignore_index=True
    )
    return g
