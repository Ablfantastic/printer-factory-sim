#!/usr/bin/env bash
# Smoke-test: provider (8001) + manufacturer (8000) over REST.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d "$REPO_ROOT/venv" ]; then
  echo "Missing venv at $REPO_ROOT/venv — create it first." >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$REPO_ROOT/venv/bin/activate"

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT
PIDS=()

require_port_free() {
  local port="$1"
  if ss -tln 2>/dev/null | grep -qE ":${port}\\s"; then
    echo "Port ${port} is already in use. Stop the other process (e.g. uvicorn) and retry." >&2
    exit 1
  fi
}

require_port_free 8000
require_port_free 8001

echo "Seeding provider..."
pushd "$REPO_ROOT/provider" >/dev/null
python -m app.seed >/dev/null
popd >/dev/null

echo "Seeding manufacturer..."
pushd "$REPO_ROOT/manufacturer" >/dev/null
pip install -q -r requirements.txt
python -m app.seed >/dev/null
popd >/dev/null

echo "Starting provider :8001 ..."
pushd "$REPO_ROOT/provider" >/dev/null
uvicorn app.api:app --host 127.0.0.1 --port 8001 &
PIDS+=($!)
popd >/dev/null

echo "Starting manufacturer :8000 ..."
pushd "$REPO_ROOT/manufacturer" >/dev/null
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
PIDS+=($!)
popd >/dev/null

sleep 2

echo "== provider /health :8001 =="
curl -sf "http://127.0.0.1:8001/health" | python3 -m json.tool

echo "== manufacturer /health :8000 =="
curl -sf "http://127.0.0.1:8000/health" | python3 -m json.tool

echo "== manufacturer -> provider (GET /api/providers) =="
curl -sf "http://127.0.0.1:8000/api/providers" | python3 -m json.tool

echo "== catalog proxy =="
curl -sf "http://127.0.0.1:8000/api/providers/ChipSupply%20Co/catalog" | python3 -c "import json,sys; d=json.load(sys.stdin); assert len(d)>0; print('catalog items:', len(d))"

echo "== purchase (POST) =="
curl -sf -X POST "http://127.0.0.1:8000/api/purchases" \
  -H "Content-Type: application/json" \
  -d '{"supplier_name":"ChipSupply Co","product_name":"pcb","quantity":2}' | python3 -m json.tool

echo "OK — supply chain REST checks passed."
