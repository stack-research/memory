from __future__ import annotations

import json

from memory_lab.handlers.api_handler import handler as api_handler
from memory_lab.handlers.sleep_handler import handler as sleep_handler


class FakeCloudService:
    def __init__(self, **_kwargs):
        self._lineage = []

    def ingest_event(self, *, memory_id, sequence, event_type, payload, source):
        self._lineage.append(
            {
                "event_id": f"{memory_id}-{sequence}",
                "memory_id": memory_id,
                "event_type": event_type,
                "payload": payload,
                "source": source,
            }
        )
        return True

    def retrieve(self, *, query, top_k=10):
        del query, top_k
        return [("m1", 0.9)]

    def beliefs_current(self):
        return {"m1": {"memory_id": "m1", "claim": "blue sky"}}

    def memory_lineage(self, memory_id):
        return [row for row in self._lineage if row["memory_id"] == memory_id]

    def _materialize(self):
        return None


def test_api_handler_ingest_and_retrieve(monkeypatch) -> None:
    import memory_lab.handlers.api_handler as api_mod

    monkeypatch.setattr(api_mod, "S3MemoryLabService", FakeCloudService)
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


def test_sleep_handler_runs(monkeypatch) -> None:
    import memory_lab.handlers.sleep_handler as sleep_mod

    monkeypatch.setattr(sleep_mod, "S3MemoryLabService", FakeCloudService)
    result = sleep_handler({}, None)
    assert result["ok"] is True
