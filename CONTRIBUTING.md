# Contributing to IDX-BEI Toolkit

Thank you for your interest in contributing to the **IDX-BEI Quantitative Toolkit**! Whether you are adding new quantitative signals, expanding scrapers, optimizing backtesting performance, or improving the React frontend, we welcome your contributions.

---

## 1. Development Environment Setup

This project uses modern **Python 3.13+**, [uv](https://github.com/astral-sh/uv) as the unified workspace package manager, and [Bun](https://bun.sh) for the modern React 19 SPA frontend.

### Prerequisites

- Python 3.13+
- `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `bun` (for frontend, `curl -fsSL https://bun.sh/install | bash`)
- Docker & Docker Compose (optional, for local Neo4j graph database)

### Setup Steps

```bash
# Clone the repository
git clone https://github.com/yourusername/idx-bei.git
cd idx-bei

# Install and sync workspace virtual environment
uv sync

# (Optional) Install frontend dependencies
cd frontend && bun install && cd ..
```

---

## 2. Code Quality & Testing Standards

All code contributions must meet strict quality standards before merging:

### Automated Test Suite
- Automated tests live in `python/tests/` named `test_<module>.py`.
- Tests must be deterministic and isolated (use mocks for network calls or pure DataFrame transformations).
- Test coverage must remain **>= 85%**:
  ```bash
  uv run pytest python/tests --cov=idx --cov-fail-under=85
  ```

### Static Typing & Linting
- Strict static typing with Mypy:
  ```bash
  uv run mypy python/src/idx
  ```
- Fast linting and formatting with Ruff:
  ```bash
  uv run ruff check python/src python/tests
  uv run ruff format python/src python/tests
  ```

### Frontend Build Check
```bash
cd frontend && bun run build && cd ..
```

---

## 3. Architecture & Design Principles

1. **Target Python 3.13+**: Utilize modern language idioms, pattern matching, type annotations, and standard libraries.
2. **Strict No Deprecations / No Backward Compatibility Wrappers**: Do not maintain deprecated wrappers, legacy shims, or fallback aliases.
3. **Data Access via `DATA_DIR`**: All local file operations must use `DATA_DIR` imported from `idx.core.utils`. Never hardcode relative file paths.
4. **Pure DataFrame Transforms**: Keep quantitative signal modules (e.g. `idx.signals`, `idx.dividend`) as pure DataFrame-in → DataFrame-out transformations for testability.
5. **Modern UV Commands**: Never use `uv run python <script.py>` — always execute `uv run <script.py>` or `uv run idx <command>`.

---

## 4. Git Commit Guidelines

We enforce the **Conventional Commits** standard:

- `feat:` A new feature or quantitative indicator (e.g., `feat(signals): add sector rotation radar`)
- `fix:` A bug fix (e.g., `fix(client): handle non-trading day 403 status`)
- `refactor:` Code restructuring without behavior changes
- `perf:` Performance improvements
- `test:` Adding or updating unit tests
- `docs:` Documentation updates
- `chore:` Tooling, dependency, or workspace updates

---

## 5. Submitting Pull Requests

1. Fork the repository and create a feature branch (`git checkout -b feat/my-new-signal`).
2. Make your changes adhering to code style, type annotations, and docstrings.
3. Verify that all 174+ pytest unit tests pass with >=85% test coverage.
4. Push your branch and open a Pull Request. Fill in the provided PR template.

Thank you for making the IDX quantitative ecosystem better for everyone!
