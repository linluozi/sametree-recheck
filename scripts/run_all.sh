#!/usr/bin/env bash
# Reproduce every report in reports/.  Run from the repository root.
set -euo pipefail

PYTHON="${PYTHON:-python3}"

for case in cases/attrs-1660.json cases/croniter-298.json cases/jsonpatch-274.json; do
  echo "=== ${case} ==="
  PYTHONPATH=src "${PYTHON}" -m sametree_recheck run \
    --case "${case}" --out-dir reports --python "${PYTHON}" --tmp "${TMPDIR:-/tmp}"
done
