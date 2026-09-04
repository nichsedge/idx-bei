"""
Vectorized Backtesting & Strategy Simulation Framework for IDX Quantitative Signals.

Evaluates forward performance, holding returns, Sharpe ratios, drawdowns, and benchmark alpha.
"""

import os

import numpy as np
import pandas as pd

from idx.core.currency import get_usd_idr_rate
from idx.core.utils import DATA_DIR, get_logger, load_json
from idx.signals import (
    composite_alpha_ranking,
    compute_technical_indicators,
    foreign_flow_radar,
    sharia_value_screen,
)

log = get_logger("idx.backtest")
PARQUET_DIR = os.path.join(DATA_DIR, "parquet")
DETAILS_FILE = os.path.join(DATA_DIR, "companyDetailsByKodeEmiten.json")


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


def simulate_dividend_arbitrage(
    stock_df: pd.DataFrame | None = None,
    actions_df: pd.DataFrame | None = None,
    details_dict: dict | None = None,
    pre_cum_days: int = 10,
    post_ex_entry_delay: int = 3,
    post_ex_holding_days: int = 10,
    tax_rate: float = 0.10,
    usd_rate: float | None = None,
    min_yield: float = 1.0,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[dict, pd.DataFrame]:
    """Simulates 3 dividend strategies across historical distributions:

    - Strategy A (Naive Hold): Buy 10 days before Cum Date, hold through Ex-Date,
      collect cash dividend, net of 10% tax.
    - Strategy B (Pre-Cum Exit): Buy 10 days before Cum Date, sell on Cum Date close,
      dodging the Ex-Date drawdown entirely.
    - Strategy C (Post-Ex Rebuy): Rebuy 3-5 sessions after Ex-Date when panic selling
      exhausts, holding for post_ex_holding_days sessions.

    Returns:
        tuple (metrics_dict, combined_trades_df)
    """
    if stock_df is None:
        stock_df, _, actions_df = _load_data()
    if details_dict is None:
        details_dict = load_json(DETAILS_FILE) if os.path.exists(DETAILS_FILE) else {}
    if usd_rate is None or usd_rate <= 0:
        usd_rate = get_usd_idr_rate()

    if len(stock_df) == 0 or not details_dict:
        log.warning("Insufficient data for dividend arbitrage simulation.")
        return {}, pd.DataFrame()

    df = stock_df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    if start_date:
        df = df[df["Date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["Date"] <= pd.to_datetime(end_date)]

    # Collect dividend events from details_dict
    events = []
    for ticker, info in details_dict.items():
        ticker_upper = str(ticker).upper().strip()
        divs = info.get("Dividen", [])
        if not isinstance(divs, list):
            continue
        for d in divs:
            cum_raw = d.get("TanggalCum")
            ex_raw = d.get("TanggalExRegulerDanNegosiasi")
            if not cum_raw or not ex_raw:
                continue
            cum_dt = pd.to_datetime(str(cum_raw)[:10], errors="coerce")
            ex_dt = pd.to_datetime(str(ex_raw)[:10], errors="coerce")
            if pd.isna(cum_dt) or pd.isna(ex_dt):
                continue

            dps_raw = float(d.get("CashDividenPerSaham", 0.0) or 0.0)
            dps_mu = str(d.get("CashDividenPerSahamMU", "")).upper().strip()
            total_div = float(d.get("CashDividenTotal", 0.0) or 0.0)
            total_mu = str(d.get("CashDividenTotalMU", "")).upper().strip()

            dps_idr = 0.0
            if dps_raw > 0:
                dps_idr = dps_raw * (usd_rate if dps_mu == "USD" else 1.0)
            elif total_div > 0:
                dps_idr = total_div * (usd_rate if total_mu == "USD" else 1.0) / 1e9

            if dps_idr <= 0:
                continue

            events.append(
                {
                    "StockCode": ticker_upper,
                    "CumDate": cum_dt,
                    "ExDate": ex_dt,
                    "DPS": dps_idr,
                }
            )

    if not events:
        log.warning("No dividend events found for simulation.")
        return {}, pd.DataFrame()

    trades_a = []
    trades_b = []
    trades_c = []

    events = sorted(events, key=lambda x: x["CumDate"])

    for ev in events:
        ticker = ev["StockCode"]
        cum_dt = ev["CumDate"]
        ex_dt = ev["ExDate"]
        dps = ev["DPS"]

        sub = df[df["StockCode"] == ticker].sort_values("Date").reset_index(drop=True)
        if len(sub) < 5:
            continue

        cum_sessions = sub[sub["Date"] <= cum_dt]
        if cum_sessions.empty:
            continue
        cum_idx = cum_sessions.index[-1]
        cum_session_dt = sub.loc[cum_idx, "Date"]

        ex_sessions = sub[sub["Date"] >= ex_dt]
        if ex_sessions.empty:
            continue
        ex_idx = ex_sessions.index[0]
        ex_session_dt = sub.loc[ex_idx, "Date"]

        entry_idx = max(0, cum_idx - pre_cum_days)
        entry_price = float(sub.loc[entry_idx, "Close"])
        if entry_price <= 0:
            continue

        yield_pct = (dps / entry_price) * 100.0
        if yield_pct < min_yield:
            continue

        # Strategy A (Naive Hold): Hold through Ex-Date, collect dividend net of 10% tax
        exit_price_a = float(sub.loc[ex_idx, "Close"])
        net_dps = dps * (1.0 - tax_rate)
        ret_a = (exit_price_a - entry_price + net_dps) / entry_price
        trades_a.append(
            {
                "Strategy": "Strategy A (Naive Hold)",
                "StockCode": ticker,
                "EntryDate": sub.loc[entry_idx, "Date"].strftime("%Y-%m-%d"),
                "ExitDate": ex_session_dt.strftime("%Y-%m-%d"),
                "CumDate": cum_dt.strftime("%Y-%m-%d"),
                "ExDate": ex_dt.strftime("%Y-%m-%d"),
                "EntryPrice": entry_price,
                "ExitPrice": exit_price_a,
                "DPS": round(dps, 2),
                "NetDividend": round(net_dps, 2),
                "YieldPct": round(yield_pct, 2),
                "ReturnPct": round(ret_a * 100.0, 2),
                "Return": ret_a,
            }
        )

        # Strategy B (Pre-Cum Exit): Sell at Cum Date close, avoid Ex-Date drop
        exit_price_b = float(sub.loc[cum_idx, "Close"])
        ret_b = (exit_price_b - entry_price) / entry_price
        trades_b.append(
            {
                "Strategy": "Strategy B (Pre-Cum Exit)",
                "StockCode": ticker,
                "EntryDate": sub.loc[entry_idx, "Date"].strftime("%Y-%m-%d"),
                "ExitDate": cum_session_dt.strftime("%Y-%m-%d"),
                "CumDate": cum_dt.strftime("%Y-%m-%d"),
                "ExDate": ex_dt.strftime("%Y-%m-%d"),
                "EntryPrice": entry_price,
                "ExitPrice": exit_price_b,
                "DPS": round(dps, 2),
                "NetDividend": 0.0,
                "YieldPct": round(yield_pct, 2),
                "ReturnPct": round(ret_b * 100.0, 2),
                "Return": ret_b,
            }
        )

        # Strategy C (Post-Ex Rebuy): Enter post_ex_entry_delay sessions after Ex-Date
        c_entry_idx = ex_idx + post_ex_entry_delay
        if c_entry_idx < len(sub):
            entry_price_c = float(sub.loc[c_entry_idx, "Close"])
            if entry_price_c > 0:
                c_exit_idx = min(len(sub) - 1, c_entry_idx + post_ex_holding_days)
                exit_price_c = float(sub.loc[c_exit_idx, "Close"])
                ret_c = (exit_price_c - entry_price_c) / entry_price_c
                trades_c.append(
                    {
                        "Strategy": "Strategy C (Post-Ex Rebuy)",
                        "StockCode": ticker,
                        "EntryDate": sub.loc[c_entry_idx, "Date"].strftime("%Y-%m-%d"),
                        "ExitDate": sub.loc[c_exit_idx, "Date"].strftime("%Y-%m-%d"),
                        "CumDate": cum_dt.strftime("%Y-%m-%d"),
                        "ExDate": ex_dt.strftime("%Y-%m-%d"),
                        "EntryPrice": entry_price_c,
                        "ExitPrice": exit_price_c,
                        "DPS": round(dps, 2),
                        "NetDividend": 0.0,
                        "YieldPct": round(yield_pct, 2),
                        "ReturnPct": round(ret_c * 100.0, 2),
                        "Return": ret_c,
                    }
                )

    df_a = pd.DataFrame(trades_a)
    df_b = pd.DataFrame(trades_b)
    df_c = pd.DataFrame(trades_c)

    ret_s_a = df_a["Return"] if len(df_a) > 0 else pd.Series(dtype=float)
    ret_s_b = df_b["Return"] if len(df_b) > 0 else pd.Series(dtype=float)
    ret_s_c = df_c["Return"] if len(df_c) > 0 else pd.Series(dtype=float)

    metrics_a = calculate_metrics(ret_s_a)
    metrics_b = calculate_metrics(ret_s_b)
    metrics_c = calculate_metrics(ret_s_c)

    dfs = [d for d in [df_a, df_b, df_c] if not d.empty]
    combined_trades = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    metrics = {
        "strategy": "dividend_arbitrage",
        "total_events": len(events),
        "strategy_a_naive_hold": metrics_a,
        "strategy_b_precum_exit": metrics_b,
        "strategy_c_postex_rebuy": metrics_c,
        "total_return_pct": metrics_b["total_return_pct"],
        "sharpe_ratio": metrics_b["sharpe_ratio"],
        "win_rate_pct": metrics_b["win_rate_pct"],
        "max_drawdown_pct": metrics_b["max_drawdown_pct"],
        "total_trades": len(combined_trades),
    }

    return metrics, combined_trades


def run_backtest(
    strategy: str = "foreign_flow",
    holding_days: int = 20,
    top_n: int = 10,
    min_turnover_rp: float = 1e9,
    start_date: str | None = None,
    end_date: str | None = None,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    stock_df: pd.DataFrame | None = None,
    ratios_df: pd.DataFrame | None = None,
    actions_df: pd.DataFrame | None = None,
) -> tuple[dict, pd.DataFrame]:
    """Runs a vectorized strategy backtest over historical time-series datasets.

    Args:
        strategy: "foreign_flow" | "bandarmology" | "sharia_value" | "composite_alpha" | "dividend_arbitrage"
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
    if strategy == "dividend_arbitrage":
        return simulate_dividend_arbitrage(
            stock_df=stock_df,
            actions_df=actions_df,
            start_date=start_date,
            end_date=end_date,
        )
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
        selected_tickers: list[str] = []
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
