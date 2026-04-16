#!/bin/bash
# Convenience wrapper: run the manufacturer API from the repository root
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/manufacturer/start_api.sh" "$@"
