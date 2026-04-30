#!/usr/bin/env bash
# Wrapper en la raíz del repo (por si ./scripts/dev-stack.sh da "Permission denied").
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/dev-stack.sh" "$@"
