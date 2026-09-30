#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install -r "$ROOT/backend/requirements.txt"
export PYTHONPATH="$ROOT/backend"
exec "$VENV/bin/uvicorn" app.main:app --app-dir "$ROOT/backend" --host 127.0.0.1 --port "${PORT:-5087}" --reload
