"""
Corporate-action adjusted closes from the stored IDX stock summary.

IDX resets a stock's reference price on ex-dates (splits, reverse splits, rights issues, bonus
shares): that day's ``Previous`` is the theoretical price, not the prior close. The ratio
``Previous / prior Close`` is the adjustment factor; multiplying every earlier close by the
cumulative product of later factors gives a continuous price series (same approach as Yahoo's
split/rights adjustment). Cash dividends do not reset the reference price and are not adjusted.
"""

import pandas as pd

TOLERANCE = 0.005  # Previous within 0.5% of the prior close = no corporate action


def adjustment_events(prices: pd.DataFrame, tol: float = TOLERANCE) -> pd.DataFrame:
    """Ex-dates found in the data: columns StockCode, Date, prior_close, previous, factor."""
    cols = ["StockCode", "Date", "prior_close", "previous", "factor"]
    if "Previous" not in prices.columns:
        return pd.DataFrame(columns=cols)
    df = prices[["StockCode", "Date", "Close", "Previous"]].copy()
    df["Date"] = pd.to_datetime(df["Date"].astype(str).str[:10])
    df = df[df["Close"] > 0].sort_values(["StockCode", "Date"])
    df["prior_close"] = df.groupby("StockCode")["Close"].shift(1)
    df["previous"] = df["Previous"]
    df["factor"] = df["previous"] / df["prior_close"]
    ev = df[(df["prior_close"] > 0) & (df["previous"] > 0) & ((df["factor"] - 1).abs() > tol)]
    return ev[cols].reset_index(drop=True)


def adjusted_closes(prices: pd.DataFrame, tol: float = TOLERANCE) -> pd.DataFrame:
    """Date × StockCode matrix of closes adjusted for every ex-date in the data.

    prices: columns StockCode, Date, Close and (for adjustment) Previous. Without a Previous
    column the raw closes are returned.
    """
    df = prices[["StockCode", "Date", "Close"]].copy()
    df["Date"] = pd.to_datetime(df["Date"].astype(str).str[:10])
    df = df[df["Close"] > 0]
    px = df.pivot_table(index="Date", columns="StockCode", values="Close").sort_index()
    ev = adjustment_events(prices, tol)
    if ev.empty:
        return px
    ratio = (
        ev.pivot_table(index="Date", columns="StockCode", values="factor", aggfunc="prod")
        .reindex(index=px.index, columns=px.columns)
        .fillna(1.0)
    )
    # factor applied to date t = product of the ratios of all later ex-dates
    later = ratio.iloc[::-1].cumprod().iloc[::-1].shift(-1).fillna(1.0)
    return px * later
