#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"
PROFILE="${AWS_PROFILE:-stack-research}"

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
  echo "Usage: scripts/cdk.sh {bootstrap|synth|deploy|destroy|preflight}"
  exit 1
fi

cd "$INFRA_DIR"

if [[ ! -d ".venv" ]]; then
  uv venv .venv
fi
source .venv/bin/activate
uv pip install -r requirements.txt >/dev/null

case "$cmd" in
  preflight)
    "$ROOT_DIR/.venv/bin/python" -m pytest -q
    AWS_PROFILE="$PROFILE" cdk synth
    ;;
  bootstrap)
    AWS_PROFILE="$PROFILE" cdk bootstrap
    ;;
  synth)
    AWS_PROFILE="$PROFILE" cdk synth
    ;;
  deploy)
    required_vars=(AWS_REGION AWS_EVENTS_BUCKET_NAME AWS_STATE_BUCKET_NAME AWS_ANALYTICS_BUCKET_NAME AWS_VECTOR_BUCKET_NAME AWS_VECTOR_INDEX_NAME)
    missing=()
    for var in "${required_vars[@]}"; do
      if [[ -z "${!var:-}" ]]; then
        missing+=("$var")
      fi
    done
    if (( ${#missing[@]} > 0 )); then
      echo "Missing required environment vars for deploy: ${missing[*]}"
      exit 1
    fi
    AWS_PROFILE="$PROFILE" cdk deploy --all
    ;;
  destroy)
    AWS_PROFILE="$PROFILE" cdk destroy --all
    ;;
  *)
    echo "Unknown command: $cmd"
    exit 1
    ;;
esac
