from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from .contracts import Event, MemoryState, utc_now_iso
from .reducer import reduce_events
from .retrieval import eligibility_score


class S3MemoryLabService:
    """AWS-backed memory lab runtime for deployed lambdas."""

    def __init__(
        self,
        *,
        events_bucket: str,
        state_bucket: str,
        vector_bucket: str,
        vector_index_name: str,
        region: str = "us-east-1",
    ) -> None:
        self.events_bucket = events_bucket
        self.state_bucket = state_bucket
        self.vector_bucket = vector_bucket
        self.vector_index_name = vector_index_name
        import boto3

        self.s3 = boto3.client("s3", region_name=region)

    def _event_key(self, memory_id: str, sequence: int, event_id: str) -> str:
        return f"events/raw/{memory_id}/{sequence:020d}-{event_id}.json"

    def _state_key(self, status: str, memory_id: str) -> str:
        return f"state/{status}/{memory_id}.json"

    def _vector_key(self) -> str:
        return f"vectors/{self.vector_index_name}.json"

    def ingest_event(
        self,
        *,
        memory_id: str,
        sequence: int,
        event_type: str,
        payload: dict[str, Any],
        source: str,
    ) -> bool:
        event = Event(
            event_id=str(uuid4()),
            sequence=sequence,
            event_type=event_type,
            memory_id=memory_id,
            payload=payload,
            source=source,
            timestamp=utc_now_iso(),
        )
        event.validate()
        key = self._event_key(memory_id, sequence, event.event_id)
        self.s3.put_object(
            Bucket=self.events_bucket,
            Key=key,
            Body=json.dumps(asdict(event), sort_keys=True).encode("utf-8"),
            ContentType="application/json",
        )
        self._materialize()
        return True

    def _list_events(self) -> list[Event]:
        paginator = self.s3.get_paginator("list_objects_v2")
        rows: list[Event] = []
        for page in paginator.paginate(Bucket=self.events_bucket, Prefix="events/raw/"):
            for obj in page.get("Contents", []):
                payload = self.s3.get_object(Bucket=self.events_bucket, Key=obj["Key"])
                raw = json.loads(payload["Body"].read().decode("utf-8"))
                rows.append(Event(**raw))
        rows.sort(key=lambda e: (e.memory_id, e.sequence, e.event_id))
        return rows

    def _materialize(self) -> None:
        states = reduce_events(self._list_events())
        for mem in states.values():
            self.s3.put_object(
                Bucket=self.state_bucket,
                Key=self._state_key(mem.status, mem.memory_id),
                Body=json.dumps(asdict(mem), sort_keys=True).encode("utf-8"),
                ContentType="application/json",
            )

        # Store vector metadata document in S3 as retrieval-plane materialization.
        vector_rows = []
        for mem in states.values():
            vector_rows.append(
                {
                    "memory_id": mem.memory_id,
                    "status": mem.status,
                    "source_event_id": mem.source_event_id,
                    "source_payload_hash": mem.source_payload_hash,
                    "source_trust": mem.trust_score,
                    "confidence": mem.confidence,
                    "decay_score": mem.decay_score,
                    "has_conflicts": bool(mem.conflicts),
                    "claim": mem.claim,
                }
            )
        self.s3.put_object(
            Bucket=self.vector_bucket,
            Key=self._vector_key(),
            Body=json.dumps({"records": vector_rows}, sort_keys=True).encode("utf-8"),
            ContentType="application/json",
        )

    def retrieve(self, *, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        del query  # scoring currently uses metadata-only signals
        states = self.beliefs_current_raw()
        ranked = []
        for state in states.values():
            if state.status in {"quarantined", "deleted"}:
                continue
            score = eligibility_score(1.0, state)
            if score > 0:
                ranked.append((state.memory_id, score))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def beliefs_current_raw(self) -> dict[str, MemoryState]:
        paginator = self.s3.get_paginator("list_objects_v2")
        out: dict[str, MemoryState] = {}
        for page in paginator.paginate(Bucket=self.state_bucket, Prefix="state/"):
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith(".json"):
                    continue
                payload = self.s3.get_object(Bucket=self.state_bucket, Key=obj["Key"])
                raw = json.loads(payload["Body"].read().decode("utf-8"))
                out[raw["memory_id"]] = MemoryState(**raw)
        return out

    def beliefs_current(self) -> dict[str, dict]:
        return {k: asdict(v) for k, v in self.beliefs_current_raw().items()}

    def memory_lineage(self, memory_id: str) -> list[dict]:
        rows = [asdict(e) for e in self._list_events() if e.memory_id == memory_id]
        return rows
