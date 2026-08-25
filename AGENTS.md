# Repository Guidelines

## Project Structure & Module Organization
This repository is organized around Python data pipelines and local database services.

- `python/`: core scripts and notebook (`scrape_*.py`, `neo4j_ingest.py`, `neo4j.ipynb`, `pyproject.toml`).
- `data/`: generated datasets (JSON/CSV) used by scrapers and ingestion jobs.
- `docker-compose/`: service definitions for Neo4j, PostgreSQL, and Metabase.
- `docker-compose.yml`: top-level include file for enabled services.
- `.deprecated/`: legacy code; avoid adding new work here.

Keep new modules in `python/` and store generated outputs under `data/` with descriptive names (example: `companyDetailsByKodeEmiten.json`).

## Build, Test, and Development Commands
Run commands from the repository root unless noted.

- `uv sync`: install/update Python dependencies across workspace.
- `docker compose up -d`: start local services (Neo4j enabled by default).
- `uv run idx all`: fetch all market snapshot data.
- `uv run idx signals`: generate daily decision-support briefing.
- `uv run python/neo4j_ingest.py`: ingest JSON data into Neo4j.
- `uv run jupyter notebook python/neo4j.ipynb`: open analysis notebook.

## Coding Style & Naming Conventions
Follow existing Python style in this repo:

- 4-space indentation, UTF-8 files, and clear function-level docstrings.
- `snake_case` for functions/variables/files, `UPPER_SNAKE_CASE` for constants.
- Keep scripts idempotent where possible (incremental writes, safe retries).
- Use explicit relative paths from script location (see current `os.path.join(..., "../data")` pattern).

No formatter/linter is currently configured. If you introduce one (for example `ruff`), document it in `python/pyproject.toml` and README.

## Testing Guidelines
There is no formal automated test suite yet. For now:

- Validate changes with targeted script runs against small or existing data files.
- For ingestion changes, verify Neo4j connectivity and a sample query result.
- Add new tests under `python/tests/` using `pytest` when adding non-trivial logic.

Name tests `test_<module>.py` and focus on pure transformation logic over network calls.

## Commit & Pull Request Guidelines
Recent history favors Conventional Commit prefixes (`feat:`, `refactor:`, `chore:`). Follow that style with concise, imperative messages.

- One logical change per commit.
- Mention data shape or schema impacts in the commit body.
- PRs should include: purpose, files changed, run commands, and sample output/screenshots (for notebook or Neo4j result changes).
- Link related issues/tasks and note any manual setup needed for reviewers.
