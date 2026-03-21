#!/bin/zsh
set -euo pipefail

PROJECT_DIR="/Users/igor_itmail.ru/Documents/ТГ счетчики юг"
LOG_FILE="/tmp/schetchiki_customer_api.log"

cd "$PROJECT_DIR"

pkill -f 'sync_backend/customer_api.py' >/dev/null 2>&1 || true

nohup python3 sync_backend/customer_api.py >"$LOG_FILE" 2>&1 &

sleep 2

echo "customer_api started"
echo "health: http://127.0.0.1:8787/api/health"
echo "log: $LOG_FILE"
