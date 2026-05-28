#!/bin/bash
# Run the retailer CLI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "$REPO_ROOT/venv" ]; then
    python3 -m venv "$REPO_ROOT/venv"
fi

exec "$REPO_ROOT/venv/bin/python" -m app.cli "$@"
