#!/bin/zsh
set -euo pipefail

curl -sS http://127.0.0.1:8787/api/health
echo
