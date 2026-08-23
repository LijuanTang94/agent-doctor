#!/usr/bin/env bash
# Runs automatically inside every new OpenClaw managed worktree for this repo.
# Without it, .venv/ is gitignored and absent, so agents cannot run pytest.
# A nonzero exit aborts worktree creation - that is intentional: a worker must
# never start in an environment where it cannot verify its own work.
set -euo pipefail

echo "[worktree-setup] $(pwd)"
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -e ".[dev]"

# prove the baseline is green before any agent touches the code
./.venv/bin/python -m pytest -q -p no:cacheprovider
echo "[worktree-setup] baseline green"
