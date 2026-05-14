#!/usr/bin/env bash
# Smoke-test: provider (8001) + manufacturer (8002) + retailer (8003) over REST.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -x "$REPO_ROOT/venv/bin/python" ]; then
  echo "Creating venv at $REPO_ROOT/venv ..."
  python3 -m venv "$REPO_ROOT/venv"
fi
# shellcheck source=/dev/null
source "$REPO_ROOT/venv/bin/activate"

if ! python -m pip --version >/dev/null 2>&1; then
  echo "The existing venv is incomplete. Recreating venv/ ..."
  deactivate 2>/dev/null || true
  python3 -m venv --clear "$REPO_ROOT/venv"
  # shellcheck source=/dev/null
  source "$REPO_ROOT/venv/bin/activate"
fi

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

require_port_free 8001
require_port_free 8002
require_port_free 8003

echo "Seeding provider..."
pushd "$REPO_ROOT/provider" >/dev/null
python -m app.seed >/dev/null
popd >/dev/null

echo "Seeding manufacturer..."
pushd "$REPO_ROOT/manufacturer" >/dev/null
python -m pip install -q -r requirements.txt
python -m app.seed >/dev/null
popd >/dev/null

echo "Seeding retailer..."
pushd "$REPO_ROOT/retailer" >/dev/null
python -m pip install -q -r requirements.txt
python -m app.seed >/dev/null
popd >/dev/null

echo "Starting provider :8001 ..."
pushd "$REPO_ROOT/provider" >/dev/null
uvicorn app.api:app --host 127.0.0.1 --port 8001 &
PIDS+=($!)
popd >/dev/null

echo "Starting manufacturer :8002 ..."
pushd "$REPO_ROOT/manufacturer" >/dev/null
uvicorn app.main:app --host 127.0.0.1 --port 8002 &
PIDS+=($!)
popd >/dev/null

echo "Starting retailer :8003 ..."
pushd "$REPO_ROOT/retailer" >/dev/null
APP_CONFIG="$REPO_ROOT/retailer/config.json" uvicorn app.api:app --host 127.0.0.1 --port 8003 &
PIDS+=($!)
popd >/dev/null

sleep 2

echo "== provider /health :8001 =="
curl -sf "http://127.0.0.1:8001/health" | python3 -m json.tool

echo "== manufacturer /health :8002 =="
curl -sf "http://127.0.0.1:8002/health" | python3 -m json.tool

echo "== retailer /health :8003 =="
curl -sf "http://127.0.0.1:8003/health" | python3 -m json.tool

echo "== manufacturer -> provider (GET /api/providers) =="
curl -sf "http://127.0.0.1:8002/api/providers" | python3 -m json.tool

echo "== catalog proxy =="
curl -sf "http://127.0.0.1:8002/api/providers/ChipSupply%20Co/catalog" | python3 -c "import json,sys; d=json.load(sys.stdin); assert len(d)>0; print('catalog items:', len(d))"

echo "== manufacturer purchase from provider (POST) =="
curl -sf -X POST "http://127.0.0.1:8002/api/purchases" \
  -H "Content-Type: application/json" \
  -d '{"supplier_name":"ChipSupply Co","product_name":"pcb","quantity":2}' | python3 -m json.tool

echo "== retailer syncs catalog from manufacturer =="
curl -sf -X POST "http://127.0.0.1:8003/api/catalog/sync" | python3 -m json.tool

echo "== retailer purchase from manufacturer (POST) =="
PURCHASE_JSON="$(curl -sf -X POST "http://127.0.0.1:8003/api/purchases" \
  -H "Content-Type: application/json" \
  -d '{"model":"P3D-Mini","quantity":1}')"
printf '%s\n' "$PURCHASE_JSON" | python3 -m json.tool
MANUFACTURER_ORDER_ID="$(printf '%s\n' "$PURCHASE_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['manufacturer_order_id'])")"

echo "== manufacturer received retailer order =="
curl -sf "http://127.0.0.1:8002/api/orders/${MANUFACTURER_ORDER_ID}" | python3 -m json.tool

echo "OK — supply chain REST checks passed."
