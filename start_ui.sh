#!/bin/bash
# Convenience wrapper: run the manufacturer dashboard from the repository root
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/manufacturer/start_ui.sh" "$@"
