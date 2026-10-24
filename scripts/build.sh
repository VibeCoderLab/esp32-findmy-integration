#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/host/key_header.py"
exec uvx --from platformio==6.2.0 pio run -d "$PROJECT_ROOT/firmware" "$@"
