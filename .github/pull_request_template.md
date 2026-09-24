## Description

Brief summary of the changes introduced in this pull request and the rationale behind them.

Fixes #(issue)

## Type of Change

- [ ] `feat`: New quantitative indicator, model, scraper, or CLI capability
- [ ] `fix`: Bug fix
- [ ] `refactor`: Code reorganization without behavioral change
- [ ] `perf`: Performance improvement
- [ ] `test`: Unit test additions or improvements
- [ ] `docs`: Documentation update

## Checklist

- [ ] My code adheres to the project coding style (Python 3.13+, 4-space indentation, type annotations).
- [ ] I have run `uv run ruff check` and `uv run ruff format` with no errors.
- [ ] I have run `uv run mypy python/src/idx` with zero type errors.
- [ ] I have added automated unit tests covering the new functionality.
- [ ] All tests pass and project test coverage remains **>= 85%** (`uv run pytest python/tests --cov=idx --cov-fail-under=85`).
- [ ] If frontend changes were made, `bun run build` in `frontend/` succeeds cleanly.
