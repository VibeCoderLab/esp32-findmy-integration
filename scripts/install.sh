#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" == '--help' || "${1:-}" == '-h' ]]; then
  echo 'Usage: scripts/install.sh --port /dev/ttyUSB0 [--name NAME] [--emoji EMOJI] [--verify-ble] [--fresh-protection | --template-protection]'
  echo 'Runs dependency setup, board backup, Apple login, registration, build, upload and verification.'
  echo 'Fresh PCS envelopes without accessory templates are the default. --template-protection enables legacy mode.'
  exit 0
fi
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
if [[ $# -eq 0 ]]; then
  echo 'USB port required. Example: scripts/install.sh --port /dev/ttyUSB0' >&2
  exit 2
fi
"$PROJECT_ROOT/scripts/setup.sh"
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/host/install.py" "$@"
