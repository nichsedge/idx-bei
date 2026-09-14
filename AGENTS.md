# Repository Guidelines

## Project Structure & Module Organization
This repository is organized as a unified Python quantitative data pipeline, MCP server, and decision-support engine.

- `python/src/idx/`: core package (`src-layout`)
  - `core/`: HTTP client (`curl_cffi` sync & `AsyncIDXClient`), schema validation, DuckDB query layer, KSEI ownership & drift engine.
  - `scrapers/`: domain scrapers (company profiles, financial ratios, corporate actions, members, news, announcements, async backfillers).
  - `pipelines/`: daily ingestion, time-series partitioning, incremental Parquet columnar exports.
  - `mcp/`: Model Context Protocol stdio server with 11 quantitative tools for AI assistants.
  - `dividend.py`: Dividend decision engine, Dividend Trap Risk scoring (0–100), and Buy/Hold/Sell analyzer.
  - `ingestion.py`: dataset inventory inspection, calendar gap detection, 4-tier quantitative backfill recommendations, and async background task runner.
  - `backtest.py`: vectorized strategy simulator, drawdown calculation, Sharpe/Sortino ratios, and benchmark alpha.
  - `graph.py`: Neo4j UBO tree resolution, circular cross-holding detection, and board centrality.
  - `api.py`: high-performance async FastAPI REST & WebSocket microservice.
  - `signals.py`: 7 decision-support screens (Composite Alpha, Foreign Flow, Bandarmology Broker Dominance, Audit Risk, Dilution Watch, Sharia Value, Pasar Nego).
  - `cli.py`: unified CLI entrypoint for `idx` command.
- `python/tests/`: automated pytest suite (165 passing unit tests, >=85% coverage).
- `data/`: local datasets (partitioned time-series, Parquet exports, daily briefings, dynamic USD/IDR rate cache, and KSEI ownership CSVs).
- `frontend/`: Modern React 19 + TypeScript + Vite single-page application (SPA) with TradingView Lightweight Charts v5 (candlesticks, EMA-20/50, Bollinger Bands, Foreign Flow sub-panel), Vis.js relationship graphs, Bandarmology & Stealth Accumulation radar, Dividend Decision & Trap Radar, Data Ingestion & Backfill Horizon Status page, Interactive Strategy Backtester, Lucide icons, and live WebSocket streaming.
- `dashboard/`: Vanilla HTML/CSS/JS reference dashboard.
- `docker-compose/`: local Neo4j graph & PostgreSQL database definitions.

## Build, Test, and Development Commands
Run all commands from the repository root using modern `uv`:

- `uv sync`: install and sync workspace dependencies.
- `docker compose up -d`: start local services (Neo4j on `bolt://localhost:7687`).
- `uv run idx all`: run all snapshot scrapers (company, financials, corporate actions, brokers, trading).
- `uv run idx status`: inspect dataset inventory, 2026 calendar gaps, missing trading sessions, and tiered backfill recommendations.
- `uv run idx company --all-details --concurrency 8`: concurrent async backfill of company profiles, boards, and shareholders.
- `uv run idx daily`: run daily market-close ingestion.
- `uv run idx backfill --start 20260101 --end 20260807 --concurrency 8`: concurrent historical backfill.
- `uv run idx parquet`: rebuild Snappy-compressed Parquet datasets (supports `--incremental`).
- `uv run idx compact`: compact daily timeseries partitions into monthly partitions (`year=YYYY/month=MM.parquet`).
- `uv run idx dividend BBCA`: analyze dividend decision and trap risk for a specific stock.
- `uv run idx dividend --screen --min-yield 4.0`: screen and rank dividend opportunities across the market.
- `uv run idx signals`: generate 7-screen daily decision-support briefing (`data/briefings/`).
- `uv run idx bandarmology`: inspect Top-N broker concentration ratios and retail vs institutional flow.
- `uv run idx bandarmology --stealth`: scan for stealth institutional accumulation vs retail traps across top stocks.
- `uv run idx backtest --strategy foreign_flow --holding 20`: simulate strategy performance & calculate Sharpe/Drawdown.
- `uv run idx backtest --strategy dividend_arbitrage`: simulate and compare Strategy A (Naive Hold), B (Pre-Cum Exit), and C (Post-Ex Rebuy).
- `uv run idx graph --ubo BBCA`: resolve multi-hop Ultimate Beneficial Ownership (UBO) hierarchy.
- `uv run idx graph --centrality`: rank corporate board powerbrokers by network centrality.
- `uv run idx graph --ingest`: batch ingest company profiles and summaries into Neo4j graph.
- `uv run idx drift --latest`: track month-over-month KSEI shareholder and tycoon position changes.
- `uv run idx drift --ingest <path_or_url>`: ingest, clean, standardize, and compute drift deltas from KSEI shareholder reports.
- `cd frontend && bun install && bun run build`: compile modern React 19 / TypeScript SPA to `frontend/dist`.
- `uv run idx serve --port 8000`: start unified Web Dashboard (serves `frontend/dist` with fallback to `dashboard/`), FastAPI REST API & WebSocket server.
- `uv run idx dashboard --port 8000`: start unified Web Dashboard, FastAPI REST API & WebSocket server.
- `uv run idx mcp`: start Model Context Protocol (MCP) server for AI assistants.
- `uv run pytest python/tests`: run full 165-test automated pytest suite with >=85% coverage enforcement.
- `uv run mypy python/src/idx`: run Mypy static type checker.
- `uv run ruff check python/src python/tests`: run Ruff linter.
- `uv run ruff format python/src python/tests`: format Python codebase.

## Coding Style & Naming Conventions
- Target **Python 3.13+** using standard language features and modern `uv` workflows.
- Strict **No Backward Compatibility**: do not create or maintain deprecated wrappers, legacy `scrape_*.py` shims, or fallback aliases.
- 4-space indentation, UTF-8 files, type annotations, and descriptive docstrings.
- `snake_case` for functions/variables/files, `UPPER_SNAKE_CASE` for constants.
- Standardize all file access through absolute `DATA_DIR` from `idx.core.utils`.
- Never use `uv run python <script.py>` — always use `uv run <script.py>` or `uv run idx <command>`.

## Testing Guidelines
- Automated tests live in `python/tests/` named `test_<module>.py`.
- Keep unit tests deterministic and isolated by mocking network requests with `unittest.mock` or testing pure DataFrame/parsing transformations.
- Run `uv run pytest python/tests` and `uv run mypy python/src/idx` before committing changes.

## Commit & Pull Request Guidelines
- Follow **Conventional Commits** (`feat:`, `fix:`, `refactor:`, `chore:`, `ci:`, `docs:`).
- Keep commits atomic and logically separated.
- Mention data shape, schema impacts, or new CLI commands in the commit message.
