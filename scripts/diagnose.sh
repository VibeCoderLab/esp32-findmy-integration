#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cleanup() {
  local result=$?
  trap - EXIT
  if ! python3 "$PROJECT_ROOT/host/logout.py" --quiet; then
    echo 'Local logout failed; run scripts/logout.sh again.' >&2
    if [[ "$result" -eq 0 ]]; then result=1; fi
  fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/host/diagnose.py"
