#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
for tool in uv git curl 7z; do
  command -v "$tool" >/dev/null || { echo "Missing: $tool (see README.md)" >&2; exit 1; }
done
UPSTREAM_REV=374d83854f657a7fdca45f813387d99d491db0e2
mkdir -p .deps
if [[ ! -d .deps/os-findmy-e ]]; then
  git clone https://github.com/sacca97/os-findmy-e.git .deps/os-findmy-e
  git -C .deps/os-findmy-e checkout --detach "$UPSTREAM_REV"
fi
[[ "$(git -C .deps/os-findmy-e rev-parse HEAD)" == "$UPSTREAM_REV" ]] || { echo 'Unexpected upstream version; stopping.' >&2; exit 1; }
for patch_name in auth-output.patch cooldown.patch; do
  if git -C .deps/os-findmy-e apply --check "$PROJECT_ROOT/patches/$patch_name" 2>/dev/null; then
    git -C .deps/os-findmy-e apply "$PROJECT_ROOT/patches/$patch_name"
  elif ! git -C .deps/os-findmy-e apply --reverse --check "$PROJECT_ROOT/patches/$patch_name" 2>/dev/null; then
    echo "Patch $patch_name does not apply; review upstream changes first." >&2
    exit 1
  fi
done
if [[ ! -x .venv/bin/python ]]; then uv venv --python 3.12 .venv; fi
uv pip install --python .venv/bin/python -r requirements.txt
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/host/fetch_coreadi.py"
echo 'Setup complete. Next step: scripts/login.sh'
