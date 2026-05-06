from __future__ import annotations

import json

from memory_lab.handlers.api_handler import handler as api_handler
from memory_lab.handlers.sleep_handler import handler as sleep_handler


def test_api_handler_ingest_and_retrieve(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_ROOT", str(tmp_path / "lab"))
    ingest_event = {
        "httpMethod": "POST",
        "path": "/v1/events",
        "body": json.dumps(
            {
                "memory_id": "m1",
                "sequence": 1,
                "event_type": "observed",
                "payload": {"claim": "blue sky", "trust_score": 0.7},
                "source": "test",
            }
        ),
    }
    resp = api_handler(ingest_event, None)
    assert resp["statusCode"] == 200

    retrieve_event = {
        "httpMethod": "POST",
        "path": "/v1/retrieve",
        "body": json.dumps({"query": "blue sky", "top_k": 5}),
    }
    resp = api_handler(retrieve_event, None)
    assert resp["statusCode"] == 200
    payload = json.loads(resp["body"])
    assert payload["results"]


def test_sleep_handler_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_ROOT", str(tmp_path / "lab"))
    result = sleep_handler({}, None)
    assert result["ok"] is True
