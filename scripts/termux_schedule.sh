#!/data/data/com.termux/files/usr/bin/bash
# Termux Daily Ingestion Wrapper for idx-sync
set -euo pipefail

# Acquire wake lock if running in Termux to prevent OS sleep mid-sync
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi

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

echo "== [$(date -Iseconds)] Starting Termux Daily IDX Ingestion =="
"$BIN_PATH" -data-dir "$REPO_DIR/data" "$@"

if command -v termux-wake-unlock >/dev/null 2>&1; then
    termux-wake-unlock
fi
echo "== [$(date -Iseconds)] Ingestion finished successfully =="
