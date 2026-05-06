#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"
PROFILE="${AWS_PROFILE:-stack-research}"

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
  echo "Usage: scripts/cdk.sh {bootstrap|synth|deploy|destroy}"
  exit 1
fi

cd "$INFRA_DIR"

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt >/dev/null

case "$cmd" in
  bootstrap)
    AWS_PROFILE="$PROFILE" cdk bootstrap
    ;;
  synth)
    AWS_PROFILE="$PROFILE" cdk synth
    ;;
  deploy)
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
