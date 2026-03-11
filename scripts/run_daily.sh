#!/bin/bash
# ============================================
# IntelFlow Daily Pipeline
# Automated data collection, AI analysis, and report generation
#
# Pipeline steps:
#  1. Multi-source data collection (parallel, 10min timeout each)
#  2. Data preprocessing (raw_*.json → briefing.json)
#  3. Split briefing into per-dimension data files
#  4. Section-based parallel report generation + assembly
#  5. Optional: AI cover image generation
#  6. Optional: Multi-platform publishing
#  7. Summary report
#
# Weekend: Weekly deep analysis (aggregates 7 days)
# Month-end: Monthly review (aggregates 4 weeks)
#
# ============================================
# ADDING A NEW DATA SOURCE
# ============================================
# 1. Create scripts/collect_yoursource.py
#    - Accept --date and --output args
#    - Check if its source is enabled via utils.load_sources_config()
#    - Save output as raw_yoursource.json in the output dir
# 2. Add an entry to config/sources.json under builtin_sources or custom_sources
#    - Set "enabled": true, "type", "description", "requires_key"
# 3. Map to dimensions in config/focus.json so the analysis engine knows
#    which report section this data feeds into
# 4. That's it — the pipeline auto-discovers collect_*.py scripts
# ============================================

set -e

# Prevent Mac sleep during pipeline
if [ -z "$CAFFEINATED" ] && command -v caffeinate &>/dev/null; then
    export CAFFEINATED=1
    exec caffeinate -s -i "$0" "$@"
fi

# Project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Date config
TODAY="${TODAY:-$(date +%Y-%m-%d)}"
DAY_OF_WEEK=$(date -j -f "%Y-%m-%d" "$TODAY" +%u 2>/dev/null || date -d "$TODAY" +%u)
DAY_OF_MONTH=$(date -j -f "%Y-%m-%d" "$TODAY" +%d 2>/dev/null || date -d "$TODAY" +%d)
OUTPUT_DIR="$PROJECT_DIR/output/$TODAY"
STATE_DIR="$PROJECT_DIR/state"
LOCK_FILE="$STATE_DIR/.daily_lock"

# Python
PYTHON="${PYTHON:-python3}"
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
fi

# Load .env
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Load config
CONFIG_DIR="$PROJECT_DIR/config"

# ============================================
# Helper functions
# ============================================

log() { echo "[$(date +%H:%M:%S)] $1"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $1" >&2; }

cleanup() {
    rm -f "$LOCK_FILE"
    log "Pipeline finished. Lock released."
}
trap cleanup EXIT

check_lock() {
    if [ -f "$LOCK_FILE" ]; then
        err "Pipeline already running (lock file exists). Remove $LOCK_FILE to force."
        exit 1
    fi
}

run_with_timeout() {
    local timeout=$1
    local label=$2
    shift 2
    log "Starting: $label"
    if timeout "$timeout" "$@" 2>&1; then
        log "Done: $label"
    else
        err "Failed or timed out: $label (continuing...)"
    fi
}

# ============================================
# Pre-flight checks
# ============================================

mkdir -p "$OUTPUT_DIR" "$STATE_DIR" "$CONFIG_DIR"

check_lock
echo "$$" > "$LOCK_FILE"

log "=== IntelFlow Daily Pipeline ==="
log "Date: $TODAY"
log "Output: $OUTPUT_DIR"

# ============================================
# Step 1: Parallel Data Collection
# ============================================

log "=== Step 1: Data Collection (parallel) ==="
log "Auto-discovering collect_*.py scripts (each checks sources.json internally)"

PIDS=()
LABELS=()

# Launch collectors in parallel
launch_collector() {
    local script=$1
    local label=$2
    if [ -f "$SCRIPT_DIR/$script" ]; then
        $PYTHON "$SCRIPT_DIR/$script" --date "$TODAY" --output "$OUTPUT_DIR" &
        PIDS+=($!)
        LABELS+=("$label")
    fi
}

# Auto-discover all collect_*.py scripts instead of hardcoding
for collector in "$SCRIPT_DIR"/collect_*.py; do
    [ -f "$collector" ] || continue
    script_name=$(basename "$collector")
    # Derive a human label from filename: collect_foo_bar.py → "foo bar"
    label=$(echo "$script_name" | sed 's/^collect_//;s/\.py$//;s/_/ /g')
    launch_collector "$script_name" "$label"
done

# Also launch supplementary search scripts
launch_collector "search_news_supplement.py" "SerpAPI Supplement"

# Wait for all collectors (10 min timeout)
TIMEOUT=600
START_TIME=$(date +%s)
for i in "${!PIDS[@]}"; do
    pid=${PIDS[$i]}
    label=${LABELS[$i]}
    ELAPSED=$(( $(date +%s) - START_TIME ))
    REMAINING=$(( TIMEOUT - ELAPSED ))
    if [ $REMAINING -le 0 ]; then
        err "Timeout waiting for: $label (killing)"
        kill "$pid" 2>/dev/null || true
        continue
    fi
    if wait "$pid" 2>/dev/null; then
        log "Collected: $label"
    else
        err "Failed: $label (non-critical, continuing)"
    fi
done

# Count collected files
RAW_COUNT=$(ls "$OUTPUT_DIR"/raw_*.json 2>/dev/null | wc -l | tr -d ' ')
log "Collected $RAW_COUNT raw data files"

if [ "$RAW_COUNT" -eq 0 ]; then
    err "No data collected. Check API keys and network. Aborting."
    exit 1
fi

# ============================================
# Step 2: Preprocessing
# ============================================

log "=== Step 2: Preprocessing ==="
run_with_timeout 300 "Prepare briefing" \
    $PYTHON "$SCRIPT_DIR/prepare_briefing.py" --date "$TODAY" --output "$OUTPUT_DIR"

if [ ! -f "$OUTPUT_DIR/briefing.json" ]; then
    err "briefing.json not created. Aborting."
    exit 1
fi

BRIEFING_SIZE=$(wc -c < "$OUTPUT_DIR/briefing.json" | tr -d ' ')
log "briefing.json: ${BRIEFING_SIZE} bytes"

# ============================================
# Step 3: Split into sections
# ============================================

log "=== Step 3: Split Briefing ==="
run_with_timeout 120 "Split briefing" \
    $PYTHON "$SCRIPT_DIR/split_briefing.py" --date "$TODAY" --output "$OUTPUT_DIR"

SECTIONS_DIR="$OUTPUT_DIR/sections"
SECTION_COUNT=$(ls "$SECTIONS_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
log "Split into $SECTION_COUNT dimension files"

# ============================================
# Step 4: Section-based Report Generation
# ============================================

log "=== Step 4: Report Generation ==="

# Check if Claude Code CLI is available
if ! command -v claude &>/dev/null; then
    err "Claude Code CLI not found. Install: https://docs.anthropic.com/en/docs/claude-code"
    err "Skipping report generation."
else
    # Load focus config for enabled dimensions
    FOCUS_FILE="$CONFIG_DIR/focus.json"
    PROFILE_FILE="$CONFIG_DIR/profile.json"

    # Generate each section in parallel
    SECTION_PIDS=()
    SECTION_LABELS=()

    for section_file in "$SECTIONS_DIR"/*.json; do
        [ -f "$section_file" ] || continue
        section_name=$(basename "$section_file" .json)
        output_md="$SECTIONS_DIR/${section_name}.md"

        log "Generating section: $section_name"

        # Build the prompt for this section
        claude -p "You are an intelligence analyst. Analyze the following data and write a detailed analysis section.

Read the data file: $section_file
Read the editorial voice profile: $PROFILE_FILE

Write your analysis to: $output_md

Requirements:
- Use specific numbers and data points from the source
- Provide your own judgment, not just summaries
- Cross-reference with other domains when relevant
- Write in both English and Chinese sections
- Never fabricate data — if uncertain, skip it
" --timeout 900 &>/dev/null &

        SECTION_PIDS+=($!)
        SECTION_LABELS+=("$section_name")
    done

    # Wait for section generation
    for i in "${!SECTION_PIDS[@]}"; do
        pid=${SECTION_PIDS[$i]}
        label=${SECTION_LABELS[$i]}
        if wait "$pid" 2>/dev/null; then
            log "Generated: $label"
        else
            err "Failed: $label"
            # Retry once
            log "Retrying: $label"
            section_file="$SECTIONS_DIR/${label}.json"
            output_md="$SECTIONS_DIR/${label}.md"
            claude -p "Analyze data from $section_file and write analysis to $output_md" --timeout 900 &>/dev/null || true
        fi
    done

    # Assemble final report
    log "Assembling final report..."
    run_with_timeout 300 "Assemble report" \
        $PYTHON "$SCRIPT_DIR/assemble_report.py" --date "$TODAY" --output "$OUTPUT_DIR" --type daily

    # Check outputs
    for lang in zh en; do
        report="$OUTPUT_DIR/daily_${lang}.md"
        if [ -f "$report" ]; then
            SIZE=$(wc -c < "$report" | tr -d ' ')
            WORDS=$(wc -w < "$report" | tr -d ' ')
            log "daily_${lang}.md: ${SIZE} bytes, ~${WORDS} words"
        else
            err "daily_${lang}.md not generated"
        fi
    done
fi

# ============================================
# Step 5: Publishing (if configured)
# ============================================

log "=== Step 5: Publishing ==="

# WordPress
if [ -n "$WORDPRESS_URL" ] && [ -n "$WORDPRESS_APP_PASSWORD" ]; then
    if [ -f "$OUTPUT_DIR/daily_en.md" ]; then
        run_with_timeout 120 "Publish WordPress" \
            $PYTHON "$SCRIPT_DIR/publish_wordpress.py" --date "$TODAY" --output "$OUTPUT_DIR"
    fi
else
    log "WordPress not configured, skipping."
fi

# Feishu
if [ -n "$FEISHU_WEBHOOK" ]; then
    if [ -f "$OUTPUT_DIR/daily_zh.md" ]; then
        run_with_timeout 120 "Publish Feishu" \
            $PYTHON "$SCRIPT_DIR/publish_feishu.py" --date "$TODAY" --output "$OUTPUT_DIR"
    fi
else
    log "Feishu not configured, skipping."
fi

# ============================================
# Step 6: Weekly / Monthly (if applicable)
# ============================================

if [ "$DAY_OF_WEEK" -eq 7 ]; then
    log "=== Sunday: Generating Weekly Report ==="
    if [ -f "$SCRIPT_DIR/assemble_report.py" ]; then
        run_with_timeout 1200 "Weekly report" \
            $PYTHON "$SCRIPT_DIR/assemble_report.py" --date "$TODAY" --output "$OUTPUT_DIR" --type weekly
    fi
fi

if [ "$DAY_OF_MONTH" -ge 28 ]; then
    NEXT_MONTH_DAY=$(date -j -v+4d -f "%Y-%m-%d" "$TODAY" +%d 2>/dev/null || date -d "$TODAY + 4 days" +%d)
    if [ "$NEXT_MONTH_DAY" -lt 5 ]; then
        log "=== Month-end: Generating Monthly Report ==="
        if [ -f "$SCRIPT_DIR/assemble_report.py" ]; then
            run_with_timeout 1800 "Monthly report" \
                $PYTHON "$SCRIPT_DIR/assemble_report.py" --date "$TODAY" --output "$OUTPUT_DIR" --type monthly
        fi
    fi
fi

# ============================================
# Summary
# ============================================

log "=== Pipeline Complete ==="
log "Date: $TODAY"
log "Output: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"/daily_*.md 2>/dev/null | while read line; do log "  $line"; done
log "Total time: $(( $(date +%s) - START_TIME ))s"
