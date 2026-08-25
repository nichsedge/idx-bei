# Repository Guidelines

## Project Structure & Module Organization
This repository is organized as a unified Python quantitative data pipeline, MCP server, and decision-support engine.

- `python/src/idx/`: core package (`src-layout`)
  - `core/`: HTTP client (`curl_cffi`), schema validation, DuckDB time-series query layer, KSEI ownership engine.
  - `scrapers/`: domain scrapers (company profiles, financial ratios, corporate actions, members, news, announcements).
  - `pipelines/`: daily ingestion, time-series partitioning, Parquet columnar exports.
  - `mcp/`: Model Context Protocol stdio server for AI assistants.
  - `signals.py`: 5 decision-support screens (Foreign Flow, Audit Risk, Dilution Watch, Sharia Value, Pasar Nego).
  - `cli.py`: unified CLI entrypoint for `idx` command.
- `python/tests/`: automated pytest suite (65 passing unit tests).
- `data/`: local datasets (partitioned time-series, Parquet exports, daily briefings, and KSEI ownership CSVs).
- `dashboard/`: interactive Smart Money & Network Alpha visual dashboard.
- `docker-compose/`: local Neo4j graph & PostgreSQL database definitions.
- `.github/workflows/`: automated CI lint/test workflow (`tests.yml`).

## Build, Test, and Development Commands
Run all commands from the repository root using modern `uv`:

- `uv sync`: install and sync workspace dependencies.
- `docker compose up -d`: start local services (Neo4j on `bolt://localhost:7687`).
- `uv run idx all`: run all snapshot scrapers (company, financials, corporate actions, brokers, trading).
- `uv run idx company --all-details`: backfill full boards, shareholders, and dividends across all 952 tickers.
- `uv run idx daily`: run daily market-close ingestion.
- `uv run idx parquet`: rebuild Snappy-compressed Parquet datasets.
- `uv run idx signals`: generate 5-screen daily decision-support briefing (`data/briefings/`).
- `uv run idx dashboard --port 8080`: launch visual network dashboard.
- `uv run idx mcp`: start Model Context Protocol (MCP) server for AI assistants.
- `uv run pytest python/tests`: run full 65-test automated pytest suite.
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
- Run `uv run pytest python/tests` before committing changes.

## Commit & Pull Request Guidelines
- Follow **Conventional Commits** (`feat:`, `fix:`, `refactor:`, `chore:`, `ci:`, `docs:`).
- Keep commits atomic and logically separated.
- Mention data shape, schema impacts, or new CLI commands in the commit message.
