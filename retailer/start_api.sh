#!/bin/bash
# Start the retailer API server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

CONFIG="${1:-config.json}"
PORT=$(python3 -c "import json; d=json.load(open('$CONFIG')); print(d['retailer'].get('port', 8003))" 2>/dev/null || echo 8003)

echo "🛒 Starting retailer API..."
echo ""

if [ ! -d "$REPO_ROOT/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$REPO_ROOT/venv"
fi

source "$REPO_ROOT/venv/bin/activate"

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Initializing database..."
python -m app.seed

echo ""
echo "Starting server on http://localhost:${PORT}"
echo "API docs available at http://localhost:${PORT}/docs"
echo ""

APP_CONFIG="$CONFIG" uvicorn app.api:app --host 0.0.0.0 --port "$PORT" --reload
