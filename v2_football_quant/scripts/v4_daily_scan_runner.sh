#!/bin/bash
set -u

ROOT="/Users/liudehua/.openclaw/workspace/v2_football_quant"
LOG_DIR="$ROOT/data/runtime/logs"
DATE_KEY="$(date +%Y%m%d)"

mkdir -p "$LOG_DIR"
cd "$ROOT" || exit 1

exec /usr/bin/python3 "$ROOT/tools/run_v4_durable_daily_scan.py" \
  --scheduled \
  --date "$DATE_KEY" \
  --notify \
  --timeout-seconds 7200
