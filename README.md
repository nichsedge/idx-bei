# IDX-BEI Data & Quantitative Analysis Toolkit

Toolkit for scraping, storing, and analyzing data from the Indonesia Stock Exchange (IDX / Bursa Efek Indonesia). Covers market data, company fundamentals, corporate actions, and broker flows — with time-series storage, Parquet export, and graph analysis pipelines.

![Neo4j Network Analysis](docs/assets/neo4j-network-analysis.png)

## Quick Start

```bash
git clone https://github.com/yourusername/idx-bei.git
cd idx-bei
uv sync
```

### Scrape & Pipeline Commands

```bash
# 1. Scrape all snapshot datasets (company profiles, financial ratios, corporate actions, brokers)
uv run idx all

# 2. Concurrent async backfill across company boards & shareholders (952 tickers)
uv run idx company --all-details --concurrency 8

# 3. Daily ingestion (today's OHLCV, broker summary & index flow)
uv run idx daily

# 4. Concurrent historical backfill (for backtesting)
uv run idx backfill --start 20260101 --end 20260807 --concurrency 8

# 5. Export all time-series and snapshots to Parquet (supports --incremental)
uv run idx parquet

# 6. Compact daily time-series partitions into monthly Snappy Parquet files
uv run idx compact
```

### Quantitative Backtesting & Strategy Simulator

```bash
# Backtest strategy holding returns, Sharpe ratios, and max drawdowns
uv run idx backtest --strategy foreign_flow --holding 20 --top 10
uv run idx backtest --strategy composite_alpha --holding 20 --stop-loss 7.0 --take-profit 15.0

# Simulate Dividend Arbitrage (Naive Hold vs Pre-Cum Exit vs Post-Ex Rebuy)
uv run idx backtest --strategy dividend_arbitrage
```

### Knowledge Graph & Ultimate Beneficial Ownership (UBO)

```bash
# Resolve multi-hop UBO hierarchy and corporate holding tree
uv run idx graph --ubo BBCA

# Rank top corporate board powerbrokers by network centrality
uv run idx graph --centrality

# Detect circular cross-holding loops between listed companies
uv run idx graph --cross-holdings
```

### KSEI Shareholder Drift & Smart Money Tracking

```bash
# Track month-over-month position accumulation/distribution across all 1% & 5% holders
uv run idx drift --latest

# Ingest and standardize raw KSEI monthly/weekly shareholder reports (file or URL)
uv run idx drift --ingest data/ksei/raw_ksei_202607.csv

# Inspect specific tycoon position changes (e.g. Lo Kheng Hong, Prajogo Pangestu)
uv run idx drift --tycoon "LO KHENG HONG"
```

### Daily Decision-Support Signals & Bandarmology

```bash
# Generate daily 7-screen decision briefing (writes Markdown + JSON into data/briefings/)
uv run idx signals

# Inspect Top-N broker concentration ratios & institutional footprint
uv run idx bandarmology

# Detect stealth institutional accumulation vs retail traps (Smart Money Delta)
uv run idx bandarmology --stealth

# Optional: broadcast briefing summary to Discord/Slack/Telegram webhook
uv run idx signals --webhook-url "https://discord.com/api/webhooks/..."
```

Runs seven quantitative decision-support screens over Parquet exports:
- **Composite Alpha Rankings** — multi-factor ranking (Value + Smart Money Flow + Technical Momentum + Clean Audit)
- **Foreign Flow Radar** — net foreign buying/selling as % of free float (accumulate/distribute)
- **Bandarmology & Broker Dominance** — Top-1 ($CR_1$), Top-3 ($CR_3$), Top-5 ($CR_5$) broker concentration and institutional vs retail footprint
- **Stealth Accumulation vs Retail Trap** — detects flat-price stealth institutional loading ($\Delta > 3.0$) vs retail exit pumps ($\Delta < 0.5$)
- **Audit Risk Shield** — stocks with non-clean audit opinions (`WDP`/`TMP`/`TL`)
- **Dilution Watch** — recent private placements, warrants, and capital reductions
- **Sharia Value Screen** — sharia-flagged, PER < 12, ROE ≥ 12%, DER ≤ 2
- **Pasar Nego Crossing Radar** — stealth off-market block crossings (value > Rp25B, nego share > 75%)

### Dividend Decision Engine & Trap Radar

Resolve whether to **BUY**, **HOLD**, or **SELL BEFORE CUM DATE** when a stock announces a dividend:

```bash
# Deep-dive dividend decision analysis for a specific stock (auto USD/IDR conversion)
uv run idx dividend BBCA
uv run idx dividend PTBA

# Screen high-yield dividend opportunities and rank by Dividend Trap Risk
uv run idx dividend --screen --min-yield 4.0 --limit 20
```

Read the full tactical strategy guide in [docs/DIVIDEND_DECISION_GUIDE.md](docs/DIVIDEND_DECISION_GUIDE.md).

### Interactive Dashboard, REST API & AI Assistant (MCP)

```bash
# Launch Smart Money Dashboard with TradingView candlestick, event markers & live WS updates
uv run idx dashboard --port 8080

# Start high-performance FastAPI REST API & WebSocket server (Swagger docs at /docs)
uv run idx serve --port 8000

# Start Model Context Protocol (MCP) Server for Claude, Cursor, Antigravity
uv run idx mcp
```

The MCP server exposes 11 standard JSON-RPC tools for AI assistants:
- `idx_analyze_dividend`: evaluate dividend announcements (Yield, DPR, Trap Risk 0–100, Buy/Hold/Sell verdict).
- `idx_get_signals`: daily 7-screen briefing summary.
- `idx_query_stock`: OHLCV, Net Foreign Flow & VWAP.
- `idx_get_company_profile`: board directors, commissioners, major shareholders & subsidiaries.
- `idx_query_broker_flow`: Top-N broker market share, $CR_1/CR_3/CR_5$ concentration ratios.
- `idx_get_technical_signals`: RSI-14, EMA 20/50/200, Bollinger Bands, ATR-14 & trend regime.
- `idx_compare_peers`: sector-relative valuation benchmarking.
- `idx_search_announcements`: public disclosures & PDF filing links.
- `idx_screen_sharia_value`: profitable, low-debt Sharia stocks.
- `idx_get_super_insiders`: billionaire/tycoon ownership holdings.
- `idx_execute_sql`: safe read-only DuckDB SQL queries over Parquet datasets.

## Repository Structure

```text
idx-bei/
├── pyproject.toml                 # Root UV workspace configuration
├── uv.lock                        # Consolidated workspace lockfile
├── python/                        # Python package & scripts
│   ├── src/idx/                   # Core package (src-layout)
│   │   ├── core/                  # HTTP client (sync & async), DuckDB query layer, KSEI ownership engine, currency rates
│   │   ├── scrapers/              # Domain scrapers (company, trading, corporate, financial, news, async backfillers)
│   │   ├── pipelines/             # Incremental Parquet export, daily ingestion, compaction
│   │   ├── mcp/                   # Model Context Protocol (MCP) server (11 tools)
│   │   ├── backtest.py            # Vectorized strategy simulator & dividend arbitrage backtester
│   │   ├── graph.py               # Neo4j UBO tree resolution & board centrality
│   │   ├── api.py                 # FastAPI REST microservice & WebSocket broadcast server
│   │   ├── signals.py             # 7 decision-support screens & stealth accumulation model
│   │   └── cli.py                 # CLI implementation
│   ├── cli.py                     # CLI launcher
│   ├── tests/                     # Pytest suite (115 passing unit tests)
│   ├── neo4j_ingest.py            # Neo4j graph ingestion script
│   ├── neo4j.ipynb                # Graph analysis notebook
│   └── pyproject.toml             # Package config (uv/setuptools)
├── data/                          # Generated datasets (gitignored)
│   ├── timeseries/                # Historical OHLCV, broker, index partitions
│   ├── parquet/                   # Columnar exports (daily and monthly compacted)
│   └── briefings/                 # Daily signal briefings (md + json)
├── .github/workflows/             # CI testing (tests.yml) & automated market-close cron (daily_ingest.yml)
├── docker-compose/                # Neo4j & PostgreSQL service configs
└── dashboard/index.html           # Visual dashboard with TradingView Lightweight Charts & live WS
```

## Testing & Code Quality

```bash
# Run automated pytest suite with coverage (115 unit tests)
uv run pytest python/tests --cov=idx --cov-report=term-missing

# Run Mypy static type checker
uv run mypy python/src/idx

# Run Ruff linter and formatter
uv run ruff check python/src python/tests
uv run ruff format python/src python/tests
```

## Neo4j Knowledge Graph Ingestion

```bash
# 1. Start Neo4j container
docker compose up -d

# 2. Ingest full 952-company network (12,000+ insiders, 5,400+ subsidiaries)
uv run python/neo4j_ingest.py

# 3. Open Neo4j Browser UI
# URL: http://localhost:7474 (user: neo4j, password: password)
```

## Tech Stack

| Layer | Tools |
|-------|-------|
| Language | Python 3.13+ |
| Package Manager | [uv](https://github.com/astral-sh/uv) (root workspace) |
| HTTP Client | `curl_cffi` (browser impersonation, Cloudflare bypass) |
| Query & Storage | DuckDB, Parquet (`pyarrow`), JSON |
| Databases | Neo4j (graph), PostgreSQL (relational) |
| Analytics & ML | `pandas`, `scikit-learn`, `matplotlib`, `seaborn` |
| AI Assistant Protocol | Model Context Protocol (MCP stdio) |
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
