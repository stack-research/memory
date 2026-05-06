#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/4] Synth stacks"
"$ROOT_DIR/scripts/cdk.sh" synth

echo "[2/4] Check API contract file exists"
test -f "$ROOT_DIR/docs/API_CONTRACT.md"

echo "[3/4] Check handlers exist"
test -f "$ROOT_DIR/src/memory_lab/handlers/api_handler.py"
test -f "$ROOT_DIR/src/memory_lab/handlers/sleep_handler.py"

echo "[4/4] Run unit tests"
"$ROOT_DIR/.venv/bin/python" -m pytest -q

echo "Infra smoke checks passed."
