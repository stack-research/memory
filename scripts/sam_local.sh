#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"

cmd="${1:-start-api}"
stack="${2:-MemoryComputeStack}"
template="$INFRA_DIR/cdk.out/${stack}.template.json"

cd "$INFRA_DIR"
"$ROOT_DIR/scripts/cdk.sh" synth >/dev/null

case "$cmd" in
  invoke-api)
    sam local invoke MemoryApiLambda -t "$template"
    ;;
  invoke-sleep)
    sam local invoke MemorySleepLambda -t "$template"
    ;;
  start-api)
    sam local start-api -t "$template"
    ;;
  *)
    echo "Usage: scripts/sam_local.sh {start-api|invoke-api|invoke-sleep} [StackName]"
    exit 1
    ;;
esac
