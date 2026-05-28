#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$SCRIPT_DIR"

if [ ! -d "$REPO_ROOT/venv" ]; then
  python3 -m venv "$REPO_ROOT/venv"
fi

# shellcheck source=/dev/null
exec "$REPO_ROOT/venv/bin/python" -m app.cli "$@"
