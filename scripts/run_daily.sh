#!/bin/bash
# ============================================================
# IntelFlow Daily Pipeline — AI-first wrapper
#
# Replaces the 19-step bash pipeline with a single Python call.
# All logic lives in scripts/run_pipeline.py.
#
# Usage:
#   ./scripts/run_daily.sh                    # today, daily report
#   TODAY=2026-03-11 ./scripts/run_daily.sh   # specific date
#   REPORT_TYPE=weekly ./scripts/run_daily.sh # weekly report
# ============================================================

set -e

# Prevent Mac sleep during pipeline
if [ -z "$CAFFEINATED" ] && command -v caffeinate &>/dev/null; then
    export CAFFEINATED=1
    exec caffeinate -s -i "$0" "$@"
fi

# Paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Date and type
DATE="${TODAY:-$(date +%Y-%m-%d)}"
REPORT_TYPE="${REPORT_TYPE:-daily}"
OUTPUT_DIR="output/$DATE"

# Python: prefer .venv if present
PYTHON="${PYTHON:-python3}"
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
fi

# Load .env if present
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Lock file — prevent concurrent runs
STATE_DIR="$PROJECT_DIR/state"
LOCK_FILE="$STATE_DIR/.daily_lock"
mkdir -p "$STATE_DIR" "$OUTPUT_DIR"

cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

if [ -f "$LOCK_FILE" ]; then
    echo "ERROR: Pipeline already running (lock exists). Remove $LOCK_FILE to force." >&2
    exit 1
fi
echo "$$" > "$LOCK_FILE"

echo "=== IntelFlow Pipeline — $DATE ($REPORT_TYPE) ==="
$PYTHON scripts/run_pipeline.py \
    --date "$DATE" \
    --output "$OUTPUT_DIR" \
    --type "$REPORT_TYPE" \
    "$@"
echo "=== Done ==="
