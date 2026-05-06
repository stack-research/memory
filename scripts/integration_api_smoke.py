from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


def call(method: str, url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url=url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    base_url = os.environ.get("MEMORY_API_BASE_URL")
    if not base_url:
        raise RuntimeError("MEMORY_API_BASE_URL must be set")

    events_url = f"{base_url}/v1/events"
    retrieve_url = f"{base_url}/v1/retrieve"
    beliefs_url = f"{base_url}/v1/beliefs/current"

    call(
        "POST",
        events_url,
        {
            "memory_id": "smoke-m1",
            "sequence": 1,
            "event_type": "observed",
            "payload": {"claim": "smoke test claim", "trust_score": 0.5},
            "source": "integration-smoke",
        },
    )
    retrieve = call("POST", retrieve_url, {"query": "smoke test claim", "top_k": 5})
    beliefs = call("GET", beliefs_url)

    print("retrieve:", retrieve)
    print("beliefs_keys:", list(beliefs.get("beliefs", {}).keys())[:5])


if __name__ == "__main__":
    main()
