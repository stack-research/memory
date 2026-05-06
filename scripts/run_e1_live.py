from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def call(method: str, url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url=url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    base_url = os.environ.get("MEMORY_API_BASE_URL")
    if not base_url:
        raise RuntimeError("MEMORY_API_BASE_URL is required")

    call(
        "POST",
        f"{base_url}/v1/events",
        {
            "memory_id": "e1_true_low_trust",
            "sequence": 1,
            "event_type": "observed",
            "payload": {"claim": "The sky is blue.", "trust_score": 0.2, "confidence": 0.9},
            "source": "weak_true_source",
        },
    )
    call(
        "POST",
        f"{base_url}/v1/events",
        {
            "memory_id": "e1_false_high_trust",
            "sequence": 1,
            "event_type": "observed",
            "payload": {"claim": "The sky is green.", "trust_score": 0.9, "confidence": 0.8},
            "source": "trusted_false_source",
        },
    )
    retrieve = call("POST", f"{base_url}/v1/retrieve", {"query": "What color is the sky?", "top_k": 5})
    true_lineage = call("GET", f"{base_url}/v1/memory/e1_true_low_trust/lineage")
    false_lineage = call("GET", f"{base_url}/v1/memory/e1_false_high_trust/lineage")

    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "stack_id": os.environ.get("MEMORY_STACK_ID", "unknown"),
        "git_sha": git_sha(),
        "aws_profile": os.environ.get("AWS_PROFILE", "stack-research"),
        "api_base_url": base_url,
        "retrieve": retrieve,
        "lineage_true": true_lineage,
        "lineage_false": false_lineage,
    }
    out = Path("var/reports/e1_live_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
