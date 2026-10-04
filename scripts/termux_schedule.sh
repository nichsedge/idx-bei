#!/data/data/com.termux/files/usr/bin/bash
# Termux Daily Ingestion Wrapper for idx-sync
set -euo pipefail

# Acquire wake lock if running in Termux to prevent OS sleep mid-sync
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi

cleanup() {
    if command -v termux-wake-unlock >/dev/null 2>&1; then
        termux-wake-unlock
    fi
}
trap cleanup EXIT

NOTIFY_HELPER="$HOME/Projects/_scheduled_jobs/mobile_runners/notify_telegram.sh"
if [[ -f "$NOTIFY_HELPER" ]]; then
    # shellcheck disable=SC1090
    source "$NOTIFY_HELPER"
fi

handle_error() {
    local exit_code=$?
    echo "❌ [$(date -Iseconds)] Ingestion failed with exit code $exit_code" >&2
    if command -v notify_job_failure >/dev/null 2>&1; then
        notify_job_failure "IDX Daily Ingestion" "idx-sync failed with exit code $exit_code" "idx-sync.log"
    fi
}
trap handle_error ERR

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN_PATH="$REPO_DIR/bin/idx-sync-android-arm64"
if [ ! -f "$BIN_PATH" ]; then
    BIN_PATH="$REPO_DIR/bin/idx-sync"
fi

if [ ! -f "$BIN_PATH" ]; then
    echo "ERROR: idx-sync binary not found in $REPO_DIR/bin." >&2
    echo "Build with: cd $REPO_DIR/tools/idx-sync && go build -o ../../bin/idx-sync ." >&2
    exit 1
fi

START_TS=$(date +%s)
echo "== [$(date -Iseconds)] Starting Termux Daily IDX Ingestion =="
"$BIN_PATH" -data-dir "$REPO_DIR/data" "$@"
DURATION=$(( $(date +%s) - START_TS ))

echo "== [$(date -Iseconds)] Ingestion finished successfully in ${DURATION}s =="

TODAY=$(date +%F)
if command -v notify_job_success >/dev/null 2>&1; then
    notify_job_success \
        "IDX Daily Ingestion" \
        "Data ${TODAY} ingested successfully in ${DURATION}s." \
        "📈 <b>IDX-BEI Daily Ingestion Completed</b> [Mobile Runner]

• <b>Date:</b> ${TODAY}
• <b>Duration:</b> ${DURATION}s
• <b>Target:</b> <code>idx-bei/data/</code>
Time: $(date +'%Y-%m-%d %H:%M:%S WIB')"
fi

