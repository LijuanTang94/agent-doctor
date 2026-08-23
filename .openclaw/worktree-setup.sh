#!/usr/bin/env bash
# Runs automatically inside every new OpenClaw managed worktree for this repo.
# Without it, .venv/ is gitignored and absent, so agents cannot run pytest.
# A nonzero exit aborts worktree creation - that is intentional: a worker must
# never start in an environment where it cannot verify its own work.
set -euo pipefail

echo "[worktree-setup] $(pwd)"

# pyproject requires Python >=3.10; the system python3 may be older (e.g. 3.9.6),
# which fails `pip install -e .[dev]` before pytest ever runs. Pick the newest
# available interpreter that satisfies the floor, else fail loudly.
PY=""
for c in python3.13 python3.12 python3.11 python3.10; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "[worktree-setup] ERROR: no Python >=3.10 interpreter found (pyproject requires >=3.10)" >&2
  exit 1
fi
echo "[worktree-setup] using $PY ($("$PY" --version 2>&1))"

"$PY" -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -e ".[dev]"

# prove the baseline is green before any agent touches the code
./.venv/bin/python -m pytest -q -p no:cacheprovider
echo "[worktree-setup] baseline green"
