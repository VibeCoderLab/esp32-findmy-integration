#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/host/key_header.py"
exec "$PROJECT_ROOT/.venv/bin/python" -m platformio run -d "$PROJECT_ROOT/firmware" "$@"
