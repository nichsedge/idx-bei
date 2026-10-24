# Running with Docker

The whole toolkit — dashboard, API, collectors, OCR — runs in one image. No local Python, Node, Bun or Go is needed.

| Service | Container | What it does |
|---|---|---|
| `app` | `idx-toolkit-app` | FastAPI + React dashboard on http://localhost:8000/dashboard/ |
| `worker` | `idx-toolkit-worker` | Scheduled jobs: announcements, prices, screen, deal dossiers, weekly cleanup |
| `neo4j` (profile `graph`) | `idx-neo4j` | Graph database for UBO / network features (optional) |

`app` and `worker` share one image (`idx-bei-app`): a Bun stage builds the frontend, the runtime stage is Python 3.13 with `uv` and Tesseract OCR (Indonesian + English).

## Quick start

```bash
cp .env.example .env            # optional: every setting has a default
docker compose up -d --build    # dashboard + worker
docker compose --profile graph up -d   # also start Neo4j
```

First data load (optional — the worker keeps things current from the moment it starts):

```bash
docker compose exec app uv run idx corporate                                   # corporate actions (rights issues tab)
docker compose exec app uv run idx backfill --start 20251001 --end 20261023 --type stock --concurrency 2 --delay 1.0
docker compose exec app uv run idx backfill --start 20251001 --end 20261023 --type index --concurrency 2 --delay 1.0
docker compose exec app uv run idx announcements --from 2025-01-01 --no-download  # ~1,200 pages, ~45 min
docker compose exec app uv run idx screen --no-fetch
```

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `IDX_DATA_DIR` | `./data` | Host folder mounted at `/app/data`. Keep it out of OneDrive/Dropbox, e.g. `D:/idx-data`. |
| `APP_PORT` | `8000` | Dashboard / API port on the host |
| `IDX_IMAGE` | `idx-bei-app` | Image name shared by `app` and `worker` |
| `NEO4J_IMAGE`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATA_DIR` | `neo4j:latest`, `neo4j`, `password`, `./neo4j_data` | Pin `NEO4J_IMAGE` once you have data |
| `WORKER_ANN_MINUTES` / `WORKER_ANN_OFF_MINUTES` | `10` / `60` | Announcement polling on trading days 06:00–23:00 / otherwise |
| `WORKER_PRICES_AT`, `WORKER_SCREEN_AT`, `WORKER_DOSSIERS_AT` | `18:30`, `19:00`, `20:00` | Daily jobs (WIB); retried until 23:00 on failure |
| `WORKER_CLEANUP_AT` | `03:00` | Weekly cleanup, Sundays |
| `WORKER_SCREEN_FROM`, `WORKER_DOSSIER_FROM` | `2025-01-01` | Start dates for the screen and deal dossiers |

Runtime data never enters the image: `.dockerignore` excludes `data/`, `neo4j_data/`, `.git/`, caches and `node_modules`, which keeps the build context to ~2 MB.

## Scheduled worker

All times are Asia/Jakarta (WIB); weekends and IDX holidays (`idx/ingestion.py`, `data/idx_holidays.json`) are skipped where noted.

| Job | Schedule | Action |
|---|---|---|
| `announcements` | every 10 min 06:00–23:00 on trading days, hourly otherwise | Incremental collection of all filings (titles only); flagged ALERT after 3 failures in a row |
| `prices` | 18:30 trading days | Stock / broker / index summary for the day |
| `screen` | 19:00 trading days | Rebuild the M&A / capital-raising screen (feeds the Momentum tab) |
| `dossiers` | 20:00 trading days | Refresh digests of open entries in `data/deals.json` and `data/rights.json` (new PDFs + OCR only; both files stay local, not in git) |
| `cleanup` | Sundays 03:00 | Compress closed months, prune PDFs > 90 days not used by a deal, keep 7 digests/screens, trim logs |

Daily jobs only count as done once they succeed at or after their scheduled time, and a worker that starts late catches up on the day's missed jobs until 23:00.

```bash
docker compose exec worker uv run idx worker --status          # job status
docker compose exec worker uv run idx worker --once prices     # run a job now
docker compose exec app uv run idx cleanup                     # cleanup dry run (add --apply to act)
docker compose logs -f worker
```

The dashboard's **Data Ingestion** tab shows the same status (`GET /api/system/worker`) and turns red on an ALERT or when the worker has been idle for more than 2 hours.

## Updating

```bash
git pull
docker compose up -d --build     # rebuilds the shared image, restarts app + worker
```

## Troubleshooting

**Build hangs or is slow** — check that `.dockerignore` exists; without it the whole `data/` folder is sent to Docker on every build.

**Docker Desktop: `service command exited with code 1 … io: read/write on closed pipe`** — the engine failed to start inside its WSL VM. Read `%LOCALAPPDATA%\Docker\log\vm\init.log`:

- `Couldn't create reference store repository: invalid character '\x00'` means Docker's own image index was corrupted (typically after an unclean shutdown). Docker Desktop → Troubleshoot → *Clean / Purge data* fixes it; it deletes images, containers and volumes **inside Docker only** — everything under `IDX_DATA_DIR` is on the host and is not touched. Then run `docker compose up -d --build`.
- WSL itself can be checked with `wsl -l -v` and `wsl -d docker-desktop -e echo ok`.

**Shrinking Docker's virtual disk (Windows)** — Docker Desktop compacts automatically past its threshold. To compact by hand, quit Docker Desktop and in an *Administrator* PowerShell:

```powershell
wsl --shutdown
Optimize-VHD -Path "<DockerDesktopWSL>\disk\docker_data.vhdx" -Mode Full
```

**Prices look wrong after a rights issue or split** — prices are not adjusted for corporate actions; the Momentum tab marks such tickers `ADJ?`.
