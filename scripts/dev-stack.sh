#!/usr/bin/env bash
# Si ./scripts/dev-stack.sh falla con "Permission denied": chmod +x scripts/dev-stack.sh
#   o ejecuta: bash scripts/dev-stack.sh
# Crea/actualiza el venv, instala dependencias, hace seed, arranca provider (:8001),
# manufacturer (:8000) y la UI Streamlit (:8501). La UI queda en primer plano; al
# cerrarla (Ctrl+C) se detienen también las APIs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PIDS=()

cleanup() {
  echo ""
  echo "Deteniendo APIs (provider + manufacturer)…"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
}

trap cleanup EXIT INT TERM

require_port_free() {
  local port="$1"
  if ss -tln 2>/dev/null | grep -qE ":${port}\\s"; then
    echo "El puerto ${port} ya está en uso. Cierra el otro proceso y vuelve a ejecutar el script." >&2
    exit 1
  fi
}

require_port_free 8000
require_port_free 8001
require_port_free 8501

if [ ! -d "$REPO_ROOT/venv" ]; then
  echo "Creando entorno virtual en venv/…"
  python3 -m venv "$REPO_ROOT/venv"
fi

# shellcheck source=/dev/null
source "$REPO_ROOT/venv/bin/activate"

echo "Instalando dependencias (provider + manufacturer)…"
pip install -q -r "$REPO_ROOT/provider/requirements.txt" -r "$REPO_ROOT/manufacturer/requirements.txt"

echo "Sembrando base de datos del provider…"
pushd "$REPO_ROOT/provider" >/dev/null
python -m app.seed
popd >/dev/null

echo "Sembrando base de datos del manufacturer…"
pushd "$REPO_ROOT/manufacturer" >/dev/null
python -m app.seed
popd >/dev/null

echo "Arrancando provider en http://127.0.0.1:8001 …"
pushd "$REPO_ROOT/provider" >/dev/null
uvicorn app.api:app --host 127.0.0.1 --port 8001 &
PIDS+=($!)
popd >/dev/null

echo "Arrancando manufacturer en http://127.0.0.1:8000 …"
pushd "$REPO_ROOT/manufacturer" >/dev/null
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
PIDS+=($!)
popd >/dev/null

echo "Esperando a que las APIs respondan…"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8001/health" >/dev/null && curl -sf "http://127.0.0.1:8000/health" >/dev/null; then
    break
  fi
  sleep 0.3
done

if ! curl -sf "http://127.0.0.1:8000/health" >/dev/null; then
  echo "Advertencia: el manufacturer no respondió a /health a tiempo." >&2
fi

echo ""
echo "────────────────────────────────────────────────────────────"
echo "  Provider API:     http://localhost:8001/docs"
echo "  Manufacturer API: http://localhost:8000/docs"
echo "  Dashboard (UI):   http://localhost:8501"
echo "────────────────────────────────────────────────────────────"
echo "  Cierra la UI con Ctrl+C para detener también las APIs."
echo ""

pushd "$REPO_ROOT/manufacturer" >/dev/null
streamlit run app/ui.py --server.port 8501 --server.address 127.0.0.1
popd >/dev/null
