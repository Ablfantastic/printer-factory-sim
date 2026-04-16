#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEEK6_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$WEEK6_ROOT/.." && pwd)"

cd "$SCRIPT_DIR"

if [ ! -d "$REPO_ROOT/venv" ]; then
  python3 -m venv "$REPO_ROOT/venv"
fi

source "$REPO_ROOT/venv/bin/activate"

echo "Installing manufacturer API dependencies..."
python -m pip install -r requirements.txt

echo "Seeding manufacturer database..."
python -m app.seed

echo "Starting manufacturer API on http://localhost:8002"
exec uvicorn app.api:app --host 0.0.0.0 --port 8002 --reload
