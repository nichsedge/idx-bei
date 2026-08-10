# IDX-BEI Data & Quantitative Analysis Toolkit

Toolkit for scraping, storing, and analyzing data from the Indonesia Stock Exchange (IDX / Bursa Efek Indonesia). Covers market data, company fundamentals, corporate actions, and broker flows — with time-series storage, Parquet export, and graph analysis pipelines.

![Neo4j Network Analysis](neo4j-network-analysis.png)

## Quick Start

```bash
git clone https://github.com/yourusername/idx-bei.git
cd idx-bei/python
uv sync
```

### Scrape Everything

```bash
uv run python cli.py all
```

### Historical Backfill (for backtesting)

```bash
uv run python cli.py backfill --start 20260101 --end 20260807
```

### Export to Parquet

```bash
uv run python cli.py parquet
```

### Daily Ingestion (cron)

```bash
# Run manually
uv run python cli.py daily

# Crontab entry (16:45 WIB every weekday)
# 45 16 * * 1-5 cd /path/to/python && uv run python -m idx.pipelines.daily
```

## Repository Structure

```text
idx-bei/
├── python/                        # Python package & scripts
│   ├── src/idx/                   # Core package (src-layout)
│   │   ├── core/                  # HTTP client, schema validation, drift detection
│   │   ├── scrapers/              # Domain scrapers (company, trading, corporate, etc.)
│   │   └── pipelines/             # Parquet export, daily ingestion, analysis
│   ├── cli.py                     # Unified CLI
│   ├── tests/                     # Pytest suite
│   ├── neo4j_ingest.py            # Neo4j graph ingestion
│   ├── neo4j.ipynb                # Graph analysis notebook
│   └── pyproject.toml             # Package config (uv/setuptools)
├── data/                          # Generated datasets (gitignored)
│   ├── timeseries/                # Historical OHLCV, broker, index JSON
│   └── parquet/                   # Columnar exports for fast analytics
├── docker-compose/                # Neo4j & PostgreSQL service configs
└── index.html                     # Smart Money Synergy Score dashboard
```

## Tech Stack

| Layer | Tools |
|-------|-------|
| Language | Python 3.13+ |
| Package Manager | [uv](https://github.com/astral-sh/uv) |
| HTTP Client | `curl_cffi` (browser impersonation, Cloudflare bypass) |
| Storage | JSON → Parquet (via `pyarrow`) |
| Databases | Neo4j (graph), PostgreSQL (relational) |
| Analytics | `pandas`, `scikit-learn`, `matplotlib`, `seaborn` |
| Infrastructure | Docker Compose |

## API Coverage

| Endpoint | Data | Status |
|----------|------|--------|
| `GetStockSummary` | Daily OHLCV, foreign flow, bid/offer | 🟢 |
| `GetBrokerSummary` | Broker transaction volume & value | 🟢 |
| `GetIndexSummary` | IHSG, LQ45, sectoral indices | 🟢 |
| `GetCompanyProfiles` | Listed company directory | 🟢 |
| `GetCompanyProfilesDetail` | Board, shareholders, subsidiaries | 🟢 |
| `GetApiDataPaginated` | P/E, P/B, ROA, ROE, EPS, NPM | 🟢 |
| `GetIssuedHistory` | Corporate actions (15 categories) | 🟢 |
| `GetBrokerSearch` | Exchange member directory | 🟢 |
| `GetNewsSearch` | Market news & headlines | 🟢 |
| `GetAllAnnouncement` | Company disclosures & PDF filings | 🟢 |

See [API_VERIFICATION_SPEC.md](python/API_VERIFICATION_SPEC.md) for full endpoint documentation.

## License

MIT — see [LICENSE](LICENSE).

---
*Disclaimer: For educational and research purposes only. Comply with IDX terms of service.*
