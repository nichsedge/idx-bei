#!/usr/bin/env bash
# Daily IDX-BEI pipeline: ingest -> signals+Discord -> refresh dashboard artifacts
set -euo pipefail
cd ~/Projects/idx-bei

set -a
source .env
set +a

echo "== $(date -Is) uv run idx daily =="
uv run idx daily

echo "== $(date -Is) uv run idx signals --webhook-url =="
uv run idx signals ${DISCORD_WEBHOOK:+--webhook-url "$DISCORD_WEBHOOK"}

echo "== $(date -Is) dashboard artifacts =="
# signals/parquet refresh data/network_alpha_data.* consumed by dashboard/index.html
if ls data/briefings/briefing_$(date +%F).md >/dev/null 2>&1; then
  echo "briefing OK: data/briefings/briefing_$(date +%F).md"
else
  echo "WARN: today's briefing missing" >&2
fi
ls -la data/network_alpha_data.js data/network_alpha_data.json 2>/dev/null || true
echo "== $(date -Is) done =="
