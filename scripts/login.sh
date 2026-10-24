#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/host/login.py" "$@"
