#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start-gitbash.sh  —  Arranca el stack complet des de Git Bash (Windows)
#
# Ús:
#   bash start-gitbash.sh           # arrenca provider + manufacturer + retailer
#   bash start-gitbash.sh --reset   # esborra les BBDD i torna a sembrar
#
# Atura-ho tot amb Ctrl+C
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

RESET=false
if [[ "${1:-}" == "--reset" ]]; then
  RESET=true
fi

PIDS=()

cleanup() {
  echo ""
  echo "Aturant serveis..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  echo "Fet."
}
trap cleanup EXIT INT TERM

# ── Comprova ports ───────────────────────────────────────────────────────────
check_port() {
  local port="$1"
  if netstat -an 2>/dev/null | grep -qE "[:.]${port}[[:space:]].*LISTENING"; then
    echo "ERROR: el port ${port} ja està en ús. Tanca l'altre procés i torna a executar." >&2
    exit 1
  fi
}
check_port 8001
check_port 8002
check_port 8003
check_port 8501

# ── Entorn virtual ───────────────────────────────────────────────────────────
if [ ! -f "$REPO_ROOT/venv/Scripts/python" ] && [ ! -f "$REPO_ROOT/venv/bin/python" ]; then
  echo "Creant entorn virtual..."
  python -m venv "$REPO_ROOT/venv"
fi

# Git Bash pot tenir venv/Scripts o venv/bin
if [ -f "$REPO_ROOT/venv/Scripts/activate" ]; then
  source "$REPO_ROOT/venv/Scripts/activate"
else
  source "$REPO_ROOT/venv/bin/activate"
fi

# ── Dependències ─────────────────────────────────────────────────────────────
echo "Instal·lant dependències..."
pip install -q \
  -r "$REPO_ROOT/provider/requirements.txt" \
  -r "$REPO_ROOT/manufacturer/requirements.txt" \
  -r "$REPO_ROOT/retailer/requirements.txt"

# ── Reset opcional ───────────────────────────────────────────────────────────
if $RESET; then
  echo "Esborrant bases de dades..."
  rm -f "$REPO_ROOT/provider/provider.db"
  rm -f "$REPO_ROOT/manufacturer/manufacturer.db" "$REPO_ROOT/manufacturer/simulator.db"
  rm -f "$REPO_ROOT/retailer/retailer.db"
fi

# ── Seed ─────────────────────────────────────────────────────────────────────
echo "Inicialitzant provider..."
(cd "$REPO_ROOT/provider" && python -m app.seed)

echo "Inicialitzant manufacturer..."
(cd "$REPO_ROOT/manufacturer" && python -m app.seed)

echo "Inicialitzant retailer..."
(cd "$REPO_ROOT/retailer" && python -m app.seed)

# ── Arrenca APIs ─────────────────────────────────────────────────────────────
echo "Arrencant provider   → http://127.0.0.1:8001"
(cd "$REPO_ROOT/provider" && uvicorn app.api:app --host 127.0.0.1 --port 8001 --log-level warning) &
PIDS+=($!)

echo "Arrencant manufacturer → http://127.0.0.1:8002"
(cd "$REPO_ROOT/manufacturer" && uvicorn app.main:app --host 127.0.0.1 --port 8002 --log-level warning) &
PIDS+=($!)

echo "Arrencant retailer   → http://127.0.0.1:8003"
(cd "$REPO_ROOT/retailer" && APP_CONFIG="$REPO_ROOT/retailer/config.json" uvicorn app.api:app --host 127.0.0.1 --port 8003 --log-level warning) &
PIDS+=($!)

echo "Arrencant Streamlit  → http://127.0.0.1:8501"
(cd "$REPO_ROOT/manufacturer" && PRINTER_SIM_API_URL=http://127.0.0.1:8002 python -m streamlit run app/ui.py \
  --server.port 8501 \
  --server.address 127.0.0.1 \
  --server.headless true \
  --logger.level error) &
PIDS+=($!)

# ── Espera que estiguin a punt ────────────────────────────────────────────────
echo "Esperant que les APIs responguin..."
for i in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1 \
  && curl -sf http://127.0.0.1:8002/health >/dev/null 2>&1 \
  && curl -sf http://127.0.0.1:8003/health >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Dashboard (UI):    http://localhost:8501"
echo "  Provider API:      http://localhost:8001/docs"
echo "  Manufacturer API:  http://localhost:8002/docs"
echo "  Retailer API:      http://localhost:8003/docs"
echo ""
echo "  Per avançar un dia (nova terminal):"
echo "    source venv/Scripts/activate"
echo "    python scripts/turn_engine.py --scenario scenarios/week7.json --days 1"
echo ""
echo "  Ctrl+C per aturar tot"
echo "═══════════════════════════════════════════════════════"

# Manté el procés viu
wait
