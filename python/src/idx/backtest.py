"""
Vectorized Backtesting & Strategy Simulation Framework for IDX Quantitative Signals.

Evaluates forward performance, holding returns, Sharpe ratios, drawdowns, and benchmark alpha.
"""

import os

import numpy as np
import pandas as pd

from idx.core.utils import DATA_DIR, get_logger
from idx.signals import (
    composite_alpha_ranking,
    compute_technical_indicators,
    foreign_flow_radar,
    sharia_value_screen,
)

log = get_logger("idx.backtest")
PARQUET_DIR = os.path.join(DATA_DIR, "parquet")


def _load_data():
    """Loads Parquet datasets required for simulation."""
    stock_path = os.path.join(PARQUET_DIR, "stock_summary.parquet")
    ratios_path = os.path.join(PARQUET_DIR, "financial_ratios.parquet")
    actions_path = os.path.join(PARQUET_DIR, "corporate_actions.parquet")

    stock = pd.read_parquet(stock_path) if os.path.exists(stock_path) else pd.DataFrame()
    ratios = pd.read_parquet(ratios_path) if os.path.exists(ratios_path) else pd.DataFrame()
    actions = pd.read_parquet(actions_path) if os.path.exists(actions_path) else pd.DataFrame()
    return stock, ratios, actions


def calculate_metrics(
    returns: pd.Series, benchmark_returns: pd.Series = None, risk_free_rate: float = 0.055
) -> dict:
    """Calculates standardized quantitative performance statistics."""
    if len(returns) == 0:
        return {
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "total_trades": 0,
            "avg_trade_return_pct": 0.0,
            "benchmark_return_pct": 0.0,
            "alpha_pct": 0.0,
        }

    clean_returns = returns.dropna()
    total_trades = len(clean_returns)
    if total_trades == 0:
        return {"total_trades": 0}

    pos_returns = clean_returns[clean_returns > 0]
    neg_returns = clean_returns[clean_returns < 0]
    win_rate = (len(pos_returns) / total_trades) * 100.0 if total_trades > 0 else 0.0

    gross_profit = pos_returns.sum()
    gross_loss = abs(neg_returns.sum())
    profit_factor = (
        (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    )

    # Cumulative equity curve
    equity_curve = (1.0 + clean_returns).cumprod()
    total_return = (equity_curve.iloc[-1] - 1.0) * 100.0 if len(equity_curve) > 0 else 0.0

    # Drawdown
    running_max = equity_curve.cummax()
    drawdowns = (equity_curve - running_max) / (running_max + 1e-9)
    max_drawdown = abs(drawdowns.min()) * 100.0 if len(drawdowns) > 0 else 0.0

    # Annualization factor (assume 252 sessions/year)
    mean_ret = clean_returns.mean()
    std_ret = clean_returns.std()
    downside_std = clean_returns[clean_returns < 0].std()

    daily_rf = (1.0 + risk_free_rate) ** (1.0 / 252) - 1.0
    sharpe = ((mean_ret - daily_rf) / (std_ret + 1e-9)) * np.sqrt(252) if std_ret > 0 else 0.0
    sortino = (
        ((mean_ret - daily_rf) / (downside_std + 1e-9)) * np.sqrt(252) if downside_std > 0 else 0.0
    )

    # Benchmark & Alpha
    bench_ret_pct = 0.0
    if benchmark_returns is not None and len(benchmark_returns) > 0:
        bench_clean = benchmark_returns.dropna()
        if len(bench_clean) > 0:
            bench_equity = (1.0 + bench_clean).cumprod()
            bench_ret_pct = (bench_equity.iloc[-1] - 1.0) * 100.0

    alpha = total_return - bench_ret_pct

    return {
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(total_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "total_trades": total_trades,
        "avg_trade_return_pct": round(clean_returns.mean() * 100.0, 2),
        "benchmark_return_pct": round(bench_ret_pct, 2),
        "alpha_pct": round(alpha, 2),
    }


def run_backtest(
    strategy: str = "foreign_flow",
    holding_days: int = 20,
    top_n: int = 10,
    min_turnover_rp: float = 1e9,
    start_date: str = None,
    end_date: str = None,
    stop_loss_pct: float = None,
    take_profit_pct: float = None,
    stock_df: pd.DataFrame = None,
    ratios_df: pd.DataFrame = None,
    actions_df: pd.DataFrame = None,
) -> tuple[dict, pd.DataFrame]:
    """Runs a vectorized strategy backtest over historical time-series datasets.

    Args:
        strategy: "foreign_flow" | "bandarmology" | "sharia_value" | "composite_alpha"
        holding_days: forward holding period in trading sessions
        top_n: number of stocks picked per rebalancing session
        min_turnover_rp: minimum average daily turnover filter
        start_date: optional starting date filter (YYYY-MM-DD)
        end_date: optional ending date filter (YYYY-MM-DD)
        stop_loss_pct: optional stop loss percentage e.g. 7.0 for -7%
        take_profit_pct: optional take profit percentage e.g. 15.0 for +15%
        stock_df, ratios_df, actions_df: optional custom DataFrames

    Returns:
        tuple (metrics_dict, trades_dataframe)
    """
    if stock_df is None or ratios_df is None:
        stock_df, ratios_df, actions_df = _load_data()

    if len(stock_df) == 0:
        log.warning("No stock summary data for backtest.")
        return {}, pd.DataFrame()

    df = stock_df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    if start_date:
        df = df[df["Date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["Date"] <= pd.to_datetime(end_date)]

    unique_dates = sorted(df["Date"].dropna().unique())
    if len(unique_dates) <= holding_days:
        log.warning(
            "Insufficient dates (%d) for holding period (%d)", len(unique_dates), holding_days
        )
        return {}, pd.DataFrame()

    log.info(
        "Starting backtest: strategy=%s, holding=%d, sessions=%d, dates=[%s → %s]",
        strategy,
        holding_days,
        len(unique_dates),
        unique_dates[0].strftime("%Y-%m-%d"),
        unique_dates[-1].strftime("%Y-%m-%d"),
    )

    trades = []
    # Rebalance every `holding_days` sessions
    for i in range(0, len(unique_dates) - holding_days, holding_days):
        entry_date = unique_dates[i]
        exit_date = unique_dates[i + holding_days]

        # Slices up to entry_date
        history_slice = df[df["Date"] <= entry_date]

        # Generate candidates based on strategy
        selected_tickers = []
        if strategy == "foreign_flow":
            radar = foreign_flow_radar(
                history_slice, window_days=min(10, i + 1), min_turnover_rp=min_turnover_rp
            )
            selected_tickers = radar.head(top_n)["StockCode"].tolist() if len(radar) > 0 else []

        elif strategy == "sharia_value":
            sharia = sharia_value_screen(ratios_df)
            selected_tickers = sharia.head(top_n)["code"].tolist() if len(sharia) > 0 else []

        elif strategy == "composite_alpha":
            alpha = composite_alpha_ranking(
                history_slice,
                ratios_df,
                actions=actions_df,
                min_turnover_rp=min_turnover_rp,
                top_n=top_n,
            )
            selected_tickers = alpha.head(top_n)["StockCode"].tolist() if len(alpha) > 0 else []

        elif strategy == "bandarmology":
            tech = compute_technical_indicators(history_slice)
            if len(tech) > 0:
                latest_tech = tech[tech["Date"] == entry_date]
                bullish = latest_tech[
                    latest_tech["TrendRegime"].isin(["STRONG_BULLISH", "BULLISH"])
                ]
                selected_tickers = (
                    bullish.sort_values("VolRatio20", ascending=False)
                    .head(top_n)["StockCode"]
                    .tolist()
                )

        if not selected_tickers:
            continue

        # Evaluate performance for each selected ticker between entry_date and exit_date
        for ticker in selected_tickers:
            ticker_slice = df[
                (df["StockCode"] == ticker) & (df["Date"] >= entry_date) & (df["Date"] <= exit_date)
            ].sort_values("Date")
            if len(ticker_slice) < 2:
                continue

            entry_price = float(ticker_slice.iloc[0]["Close"])
            if entry_price <= 0:
                continue

            exit_price = float(ticker_slice.iloc[-1]["Close"])
            ret = (exit_price - entry_price) / entry_price

            # Apply Stop Loss / Take Profit if specified
            if stop_loss_pct or take_profit_pct:
                for _, session_row in ticker_slice.iloc[1:].iterrows():
                    curr_c = float(session_row["Close"])
                    curr_ret = (curr_c - entry_price) / entry_price
                    if stop_loss_pct and curr_ret <= -(stop_loss_pct / 100.0):
                        ret = -(stop_loss_pct / 100.0)
                        exit_price = entry_price * (1.0 + ret)
                        break
                    if take_profit_pct and curr_ret >= (take_profit_pct / 100.0):
                        ret = take_profit_pct / 100.0
                        exit_price = entry_price * (1.0 + ret)
                        break

            trades.append(
                {
                    "EntryDate": entry_date.strftime("%Y-%m-%d"),
                    "ExitDate": exit_date.strftime("%Y-%m-%d"),
                    "StockCode": ticker,
                    "EntryPrice": entry_price,
                    "ExitPrice": exit_price,
                    "ReturnPct": round(ret * 100.0, 2),
                    "Return": ret,
                }
            )

    trades_df = pd.DataFrame(trades)
    returns_series = trades_df["Return"] if len(trades_df) > 0 else pd.Series(dtype=float)
    metrics = calculate_metrics(returns_series)
    metrics["strategy"] = strategy
    metrics["holding_days"] = holding_days

    return metrics, trades_df
