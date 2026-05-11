#!/bin/sh
set -eu

DATA_ROOT="${MODEL_DATA_ROOT:-/data/datalake}"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 3 15 * *}"
LOG_DIR="$DATA_ROOT/logs"
CRON_LOG="$LOG_DIR/cron.log"
LOCK_FILE="$LOG_DIR/modelo-pred-menm.lock"

mkdir -p "$LOG_DIR" \
    "$DATA_ROOT/Geodata/raster_results" \
    "$DATA_ROOT/img_results" \
    "$DATA_ROOT/models"

printf '%s %s\n' "$CRON_SCHEDULE" "(set -C; : > $LOCK_FILE) 2>/dev/null || exit 0; trap 'rm -f $LOCK_FILE' EXIT; MODEL_DATA_ROOT=$DATA_ROOT /usr/local/bin/python /app/src/main.py >> $CRON_LOG 2>&1" > /tmp/modelo-pred-menm.cron
crontab /tmp/modelo-pred-menm.cron

if [ "${RUN_ON_START:-false}" = "true" ]; then
    if (set -C; : > "$LOCK_FILE") 2>/dev/null; then
        trap 'rm -f "$LOCK_FILE"' EXIT
        MODEL_DATA_ROOT="$DATA_ROOT" /usr/local/bin/python /app/src/main.py >> "$CRON_LOG" 2>&1 || true
    else
        printf '%s\n' "[WARN] Ejecucion ya en curso, se omite RUN_ON_START." >> "$CRON_LOG"
    fi
fi

exec cron -f
