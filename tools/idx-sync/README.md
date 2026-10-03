# IDX-Sync: Lightweight Standalone Ingestion for Termux & Embedded Systems

A zero-dependency Go binary built to run on native Android (Termux) or lightweight Linux environments where heavy C++ Python wheels (`duckdb`, `pyarrow`, `curl_cffi`) cannot be compiled.

---

## ⚡ Why Native Termux Python Fails

1. **Bionic libc vs. glibc**: Android does not use standard GNU C (`glibc`). Modern Python data engineering wheels (`pyarrow`, `duckdb`) on PyPI only ship `manylinux` or `musllinux` binaries. On Termux, `pip` falls back to building Arrow and DuckDB C++ from source, which consistently fails or triggers out-of-memory (OOM) kills on mobile devices.
2. **Cloudflare TLS Fingerprint WAF**: The Indonesia Stock Exchange (`idx.co.id`) validates TLS Client Hello fingerprints (JA3/JA4). Standard tools (`curl`, Python `requests`, `urllib`) are instantly blocked with `HTTP 403 Forbidden / Cloudflare challenge`.
3. **The Solution**: `idx-sync` is written in Go using `bogdanfinn/tls-client` (pure-Go `uTLS`). It compiles into a single, statically-linked executable (`CGO_ENABLED=0`) with **zero** external C libraries or runtime dependencies, while reliably impersonating Safari/Chrome TLS handshakes to ingest full market data in seconds.

---

## 🚀 Building `idx-sync`

### Option A: Build directly inside native Termux
```bash
pkg install golang git
cd tools/idx-sync
go build -o ../../bin/idx-sync .
```

### Option B: Cross-compile from your workstation for Android ARM64
```bash
cd tools/idx-sync
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o ../../bin/idx-sync-android-arm64 .
```
Then copy `bin/idx-sync-android-arm64` to your Android device via `scp`, `adb`, or `git`.

---

## 🛠️ Usage

```bash
# Ingest today's market-close trading summaries + USD/IDR exchange rate
./bin/idx-sync -data-dir ./data

# Ingest a specific historical trading day
./bin/idx-sync -data-dir ./data -date 20260401

# Send Discord webhook notification on completion
./bin/idx-sync -data-dir ./data -webhook "https://discord.com/api/webhooks/..."
```

### Ingestion Output
- Stock Summary (OHLCV, Foreign flow): `data/timeseries/stock_summary/date=YYYY-MM-DD.json`
- Broker Summary (Institutional flow): `data/timeseries/broker_summary/date=YYYY-MM-DD.json`
- Index Summary (IHSG & Sector indices): `data/timeseries/index_summary/date=YYYY-MM-DD.json`
- Live USD/IDR Rate: `data/usd_idr_rate.json`

When you pull or sync the data back to your main workstation or server, `idx-bei` automatically detects and converts these `.json` partitions into snappy-compressed `.parquet` files via `timeseries.migrate_all()` or `uv run idx status` / `uv run idx compact`.

---

## ⏰ Scheduling on Native Termux

### 1. Using `cronie` (Standard Cron Daemon)
```bash
# Install cron daemon and wake-lock tools
pkg install cronie termux-api

# Open crontab
crontab -e
```
Add the following line to run at 16:45 WIB (09:45 UTC) every trading day (Monday–Friday):
```cron
45 16 * * 1-5 /data/data/com.termux/files/home/idx-bei/scripts/termux_schedule.sh >> /data/data/com.termux/files/home/idx-sync.log 2>&1
```
Start the cron service:
```bash
crond
```

### 2. Using `termux-job-scheduler` (Android Doze-Resistant)
If Android battery optimization kills background cron processes when the screen is locked:
```bash
pkg install termux-api

# Schedule periodic execution every 24 hours surviving device reboots
termux-job-scheduler \
  --script /data/data/com.termux/files/home/idx-bei/scripts/termux_schedule.sh \
  --period-ms 86400000 \
  --persisted true
```
