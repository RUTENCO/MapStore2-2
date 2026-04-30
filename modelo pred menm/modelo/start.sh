#!/bin/sh
set -eu

DATA_ROOT="${MODEL_DATA_ROOT:-/data/datalake}"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 0 1 * *}"
LOG_DIR="$DATA_ROOT/logs"
CRON_LOG="$LOG_DIR/cron.log"

mkdir -p "$LOG_DIR" \
    "$DATA_ROOT/Geodata/raster_results" \
    "$DATA_ROOT/img_results" \
    "$DATA_ROOT/models"

printf '%s %s\n' "$CRON_SCHEDULE" "MODEL_DATA_ROOT=$DATA_ROOT /usr/local/bin/python /app/src/main.py >> $CRON_LOG 2>&1" > /tmp/modelo-pred-menm.cron
crontab /tmp/modelo-pred-menm.cron

if [ "${RUN_ON_START:-false}" = "true" ]; then
    MODEL_DATA_ROOT="$DATA_ROOT" /usr/local/bin/python /app/src/main.py >> "$CRON_LOG" 2>&1 || true
fi

exec cron -f
