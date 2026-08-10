# IDX-BEI Python SDK & Data Pipelines

Comprehensive documentation for running scrapers, historical backfill, daily scheduled ingestion, Parquet exports, and schema drift monitoring.

---

## 🛠️ Environment Setup

Ensure you have `uv` installed, then synchronize dependencies:

```bash
cd python
uv sync
```

---

## 📁 Package Architecture (`src/idx/`)

```text
python/
├── src/
│   └── idx/
│       ├── __init__.py             # SDK Exports
│       ├── core/                   # Engine Core
│       │   ├── client.py           # HTTP Client (Retries, Backoff, Rate Limits, Impersonation)
│       │   └── utils.py            # Validation, Drift Fingerprinting, Anomaly Tracking, File I/O
│       ├── scrapers/               # Domain Scrapers
│       │   ├── company.py          # Company Profiles & Details
│       │   ├── financial.py        # Financial Ratios & Fundamentals
│       │   ├── trading.py          # Stock Summary (OHLCV), Broker Summary & Index Summary
│       │   ├── corporate.py        # Corporate Actions (15 caTypes)
│       │   ├── members.py          # Exchange Members & Broker Directory
│       │   ├── news.py             # Market News & Company Disclosures (PDF Filings)
│       │   └── historical.py      # Historical Time-Series Backfill Engine
│       └── pipelines/              # Data Pipelines
│           ├── parquet.py          # Parquet Export Pipeline (Snappy, Quant Features)
│           └── daily.py            # Daily Cron Scheduled Ingestion
├── cli.py                          # Unified Command-Line Interface
├── pyproject.toml                  # Package Configuration (src-layout)
├── API_VERIFICATION_SPEC.md       # Empirical API Verification Specification
└── tests/                          # Pytest Suite
```

---

## 🛡️ Robust Core Engine (`idx.core`)

All scrapers in this repository use `idx.core.utils` to protect against upstream IDX Web API changes.

### 1. Contract Schema Validation
Enforces top-level required keys and nested item fields (`validate_schema`).
- Logs warnings when unexpected structural changes occur.
- Supports `strict=True` to fail fast during CI/CD.

### 2. Structural Drift Fingerprinting
Generates recursive type fingerprints for response payloads (`check_schema_drift`).
- Baselines are saved automatically in `data/.schema_snapshots.json`.
- Detects added, removed, or altered fields.

### 3. Record Count Anomaly Monitoring
Tracks total record counts across runs in `data/.scrape_stats.json` (`check_count_anomaly`).
- Flags anomalies if record counts swing by >15%.

### 4. Raw Response Archiving
If schema drift, validation failure, or JSON parse errors occur, the raw HTTP response is saved to `data/.raw_archive/<endpoint>_<timestamp>.json` for offline debugging.

---

## 🚀 Unified CLI Usage (`cli.py`)

Run any task using the unified CLI:

```bash
# Snapshot Scrapers
uv run python cli.py company        # Listed company profiles
uv run python cli.py financial      # Financial ratios & statistics
uv run python cli.py corporate      # Corporate actions (all 15 types)
uv run python cli.py brokers        # Exchange member directory
uv run python cli.py trading        # Stock summary, broker summary, index summary
uv run python cli.py news           # News headlines
uv run python cli.py announcements  # Disclosures & PDF filings
uv run python cli.py all            # Run all snapshot scrapers

# Historical Backfill (Time-Series)
uv run python cli.py backfill --start 20260101 --end 20260807

# Parquet Export
uv run python cli.py parquet

# Daily Scheduled Ingestion
uv run python cli.py daily [YYYYMMDD]
```

---

## ⚡ Quant Data Format (Parquet)

The `idx.pipelines.parquet` pipeline converts raw JSON to Snappy-compressed Parquet files, reducing file size by 10-50x while embedding pre-computed quantitative signals:

- **`NetForeignFlow`**: `ForeignBuy - ForeignSell`
- **`Return`**: `(Close - Previous) / Previous`
- **`VWAP`**: `Value / Volume`

Exposed Parquet datasets in `data/parquet/`:
- `stock_summary.parquet`
- `broker_summary.parquet`
- `index_summary.parquet`
- `financial_ratios.parquet`
- `corporate_actions.parquet`

---

## 🧪 Running Tests

Execute the automated test suite:

```bash
uv run pytest tests/ -v
```

---

## 📈 Quantitative Endpoint Reference

For detailed empirical specs, headers, and payload structures, see [API_VERIFICATION_SPEC.md](API_VERIFICATION_SPEC.md).
