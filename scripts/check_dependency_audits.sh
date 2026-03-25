#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[dependency-audit] Installing frontend dependencies from lockfile"
(
  cd "$repo_root/frontend"
  npm ci
)

echo "[dependency-audit] Auditing frontend production dependencies"
(
  cd "$repo_root/frontend"
  npm audit --omit=dev --audit-level=moderate
)

echo "[dependency-audit] Ensuring pip-audit is available"
python -m pip install pip-audit

echo "[dependency-audit] Auditing Python dependencies"
(
  cd "$repo_root"
  pip-audit -r requirements.txt
)
