# %% [markdown]
# # IDX-BEI Quantitative Research & Market Analysis Walkthrough
#
# Welcome to the **IDX-BEI Quantitative Analysis Toolkit**! This notebook provides an end-to-end walkthrough designed for quant researchers, financial analysts, and algorithmic traders interested in the Indonesia Stock Exchange (Bursa Efek Indonesia / IDX).
#
# ### What this notebook covers:
# 1. **High-Performance Data Querying**: Inspecting Parquet datasets with DuckDB.
# 2. **Net Foreign Flow Radar**: Tracking offshore institutional accumulation & distribution vs free float.
# 3. **Bandarmology & Stealth Accumulation**: Broker concentration ($CR_1, CR_3, CR_5$), Smart Money Delta ($\Delta$), and Wyckoff phases.
# 4. **Sector Rotation & Market Regime**: Sector relative strength (Alpha) vs COMPOSITE (IHSG).
# 5. **Dividend Trap Risk & Decision Engine**: Evaluating yield, payout ratio, and 0–100 Dividend Trap Risk.
# 6. **Vectorized Strategy Backtester**: Simulating multi-factor strategies with Sharpe ratios and drawdowns.

# %%
import os
import sys

# Ensure idx package is in Python path
notebook_dir = os.getcwd()
repo_root = os.path.abspath(os.path.join(notebook_dir, ".."))
src_path = os.path.join(repo_root, "python", "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import pandas as pd
from idx.backtest import run_backtest
from idx.core.query import available_datasets, query_dataset
from idx.dividend import analyze_stock_dividend
from idx.signals import (
    broker_concentration_screen,
    detect_stealth_accumulation,
    foreign_flow_radar,
    sector_rotation_radar,
)

# Display fallback for standalone script execution vs interactive notebooks
if "display" not in globals():
    try:
        from IPython.display import display  # type: ignore[no-redef]
    except ImportError:

        def display(*args):  # type: ignore[no-redef]
            for arg in args:
                print(arg)


print("Available datasets in storage:", available_datasets())
print("IDX Quantitative Toolkit initialized successfully!")

# %% [markdown]
# ## 1. High-Speed Columnar DuckDB Querying
#
# Query partitioned historical time-series datasets (`stock_summary`, `broker_summary`, `index_summary`) using DuckDB without loading full tables into memory.

# %%
# Query recent blue-chip liquidity and turnover
df_top = query_dataset(
    "stock_summary",
    columns="Date, StockCode, Close, Volume, Value, ForeignBuy, ForeignSell, (ForeignBuy - ForeignSell) AS NetForeignFlow",
    where="Value >= 50000000000",
    limit=10,
)
display(df_top)

# %% [markdown]
# ## 2. Foreign Flow Radar: Smart Offshore Money Tracking
#
# Foreign institutions frequently drive major price trends on the IDX. The **Foreign Flow Radar** calculates 5-session net foreign volume accumulated as a percentage of free float ($NFF / FreeFloat$), filtering for liquid tickers ($Turnover > Rp 1B/day$).

# %%
parquet_dir = os.path.join(repo_root, "data", "parquet")
stock_file = os.path.join(parquet_dir, "stock_summary.parquet")

if os.path.exists(stock_file):
    df_stock = pd.read_parquet(stock_file)
    radar_df = foreign_flow_radar(
        df_stock, window_days=5, min_turnover_rp=1e9, min_abs_pct_float=0.5
    )
    print(f"Detected {len(radar_df)} stocks with significant foreign accumulation/distribution:")
    display(radar_df.head(10))
else:
    print("Parquet exports not found. Run `uv run idx parquet` first.")

# %% [markdown]
# ## 3. Bandarmology & Wyckoff Stealth Accumulation
#
# Evaluate local institutional and underwriting syndicate behavior:
# - **Broker Concentration**: Top-1 ($CR_1$), Top-3 ($CR_3$), Top-5 ($CR_5$) market share and institutional-to-retail flow ratios.
# - **Smart Money Delta ($\Delta$)**: Compares institutional broker loading intensity against retail broker flow.
# - **Wyckoff Accumulation Phase**: Identifies whether a stock is in Phase A (Stopping Action), Phase B (Absorption), Phase C (Spring/Test), or Phase D (Markup).

# %%
broker_file = os.path.join(parquet_dir, "broker_summary.parquet")
if os.path.exists(broker_file) and os.path.exists(stock_file):
    df_broker = pd.read_parquet(broker_file)

    # 1. Market-wide broker concentration
    broker_metrics, top_brokers = broker_concentration_screen(df_broker, top_k=5)
    print("Market Broker Concentration:", broker_metrics)
    display(top_brokers)

    # 2. Stealth accumulation anomalies
    stealth_results = detect_stealth_accumulation(df_broker, df_stock)
    print(
        f"\nMarket Signal: {stealth_results['signal']} | Smart Money Delta: {stealth_results['smart_money_delta']:.2f}"
    )
    display(stealth_results["anomalies_df"].head(10))
else:
    print("Broker summary dataset missing.")

# %% [markdown]
# ## 4. Sector Rotation & Market Regime Radar
#
# Identify leading and lagging sectors by calculating Relative Strength Alpha against the benchmark IHSG (`COMPOSITE`) over a 20-session window.

# %%
index_file = os.path.join(parquet_dir, "index_summary.parquet")
if os.path.exists(index_file):
    df_index = pd.read_parquet(index_file)
    regime, sectors = sector_rotation_radar(df_index, window_days=20)
    print(f"Market Macro Regime: {regime['market_regime']}")
    print(f"IHSG Period Return : {regime['benchmark_return_pct']:+.2f}%")
    print("Leading Sectors    :", regime["leading_sectors"])
    print("Lagging Sectors    :", regime["lagging_sectors"])
    display(sectors)
else:
    print("Index summary dataset missing.")

# %% [markdown]
# ## 5. Dividend Decision Engine & Dividend Trap Radar
#
# Indonesian dividend yields often reach double digits (e.g. coal, energy, commodities). However, holding through the **Cum Date** often leads to severe post-ex dividend drops exceeding the dividend payout itself (Dividend Trap).
#
# The **Dividend Engine** computes:
# - Dividend Yield & Payout Ratio (DPR)
# - **Dividend Trap Risk (0–100 Score)**: Evaluates earnings quality, leverage (DER), commodity cyclicality, and post-ex recovery history.
# - **Actionable Verdict**: `BUY`, `HOLD`, or `EXIT_BEFORE_CUM_DATE`.

# %%
# Analyze dividend decisions for notable dividend payers
for ticker in ["PTBA", "BBCA"]:
    div_analysis = analyze_stock_dividend(ticker)
    print(f"\n{'=' * 40}")
    print(f"Dividend Analysis: {ticker}")
    print(f"{'=' * 40}")
    print(f"Recommendation    : {div_analysis.get('recommendation', 'N/A')}")
    print(
        f"Dividend Trap Risk: {div_analysis.get('dividend_trap_risk', 'N/A')}/100 ({div_analysis.get('risk_tier', 'N/A')})"
    )
    print(f"Estimated Yield   : {div_analysis.get('dividend_yield_pct', 'N/A')}%")
    print(f"Payout Ratio (DPR): {div_analysis.get('dpr_pct', 'N/A')}%")

# %% [markdown]
# ## 6. Vectorized Quantitative Strategy Backtesting
#
# Simulate quantitative strategies over historical partitions with realistic transaction costs, stop-loss / take-profit triggers, and volatility parity position sizing.

# %%
# Simulate Foreign Flow Strategy
metrics_ff, trades_ff = run_backtest(
    strategy="foreign_flow",
    holding_days=20,
    top_n=10,
    stop_loss_pct=7.0,
    take_profit_pct=15.0,
)

print("Foreign Flow Strategy Performance:")
for k, v in metrics_ff.items():
    print(f"  {k:22s}: {v}")

if not trades_ff.empty:
    print(f"\nSample Trades Executed ({len(trades_ff)} total):")
    display(trades_ff.head(5))

# %% [markdown]
# ## Next Steps & AI Assistant Integration
#
# - **Web Dashboard & Charts**: Start the interactive React 19 SPA & REST API via `uv run idx dashboard`.
# - **Model Context Protocol (MCP)**: Power Claude, Cursor, or Antigravity with 14 quant tools via `uv run idx mcp`.
# - **Daily Briefings**: Generate market close briefings via `uv run idx signals`.
