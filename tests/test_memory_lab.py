from __future__ import annotations

from pathlib import Path

from memory_lab.config import Settings, load_dotenv
from memory_lab.audit import AuditAPI
from memory_lab.compaction import compact_events_to_parquet_layout, glue_bootstrap_schema
from memory_lab.contracts import Event, MemoryState, VectorRecord, stable_json_hash, utc_now_iso
from memory_lab.invariants import assert_parquet_row_traceability, assert_state_traceability
from memory_lab.lineage import EventLog
from memory_lab.reducer import reduce_events
from memory_lab.service import MemoryLabService


def test_contracts_and_invariants() -> None:
    event = Event(
        event_id="e1",
        sequence=1,
        event_type="observed",
        memory_id="m1",
        payload={"claim": "x"},
        source="s",
        timestamp=utc_now_iso(),
    )
    event.validate()
    state = MemoryState(
        memory_id="m1",
        claim="x",
        trust_score=0.8,
        confidence=0.8,
        decay_score=1.0,
        last_recalled=None,
        access_count=0,
        source_event_id="e1",
        source_payload_hash=stable_json_hash({"claim": "x"}),
    )
    state.validate()
    assert_state_traceability(state, {"e1"})
    record = VectorRecord(
        memory_id="m1",
        embedding=[0.1, 0.2],
        claim_hash="h",
        source_event_id="e1",
        source_payload_hash=None,
        agent_id="a",
        status="active",
        kind="memory",
        source_trust=0.8,
        confidence=0.7,
        decay_score=0.9,
        last_recalled_ts=None,
        assertion_ts=utc_now_iso(),
        has_conflicts=False,
    )
    record.validate()


def test_dotenv_settings(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "AWS_PROFILE=stack-research",
                "AWS_VECTOR_BUCKET_NAME=test-vectors",
                "AWS_VECTOR_INDEX_NAME=test-index",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("AWS_VECTOR_BUCKET_NAME", raising=False)
    monkeypatch.delenv("AWS_VECTOR_INDEX_NAME", raising=False)
    load_dotenv(env_file)
    settings = Settings.from_env()
    assert settings.aws_profile == "stack-research"
    assert settings.aws_vector_bucket_name == "test-vectors"
    assert settings.aws_vector_index_name == "test-index"


def test_append_only_and_idempotency(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    e1 = Event("e1", 1, "observed", "m1", {"claim": "a"}, "s", utc_now_iso())
    assert log.append(e1) is True
    assert log.append(e1) is False


def test_reducer_and_conflicts(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    now = utc_now_iso()
    log.append(Event("e1", 1, "observed", "m1", {"claim": "a", "trust_score": 0.6}, "s", now))
    log.append(Event("e2", 2, "contradicted", "m1", {"target_memory_id": "m2"}, "s", now))
    log.append(Event("e3", 3, "quarantined", "m1", {"reason": "poison"}, "s", now))
    state = reduce_events(log.list_events())
    assert state["m1"].status == "quarantined"
    assert len(state["m1"].conflicts) == 1


def test_retrieval_gating(tmp_path: Path) -> None:
    service = MemoryLabService(tmp_path)
    service.ingest_event(
        memory_id="m1",
        sequence=1,
        event_type="observed",
        payload={"claim": "sky is blue", "trust_score": 0.7, "confidence": 0.9},
        source="sensor",
    )
    service.ingest_event(
        memory_id="m2",
        sequence=1,
        event_type="observed",
        payload={"claim": "sky is green", "trust_score": 0.9, "confidence": 0.9},
        source="trusted_false_source",
    )
    service.ingest_event(
        memory_id="m2",
        sequence=2,
        event_type="quarantined",
        payload={"reason": "poison"},
        source="guard",
    )
    selected = service.retrieve("What color is the sky?")
    memory_ids = [m for m, _ in selected]
    assert "m2" not in memory_ids


def test_audit_replay_and_compaction(tmp_path: Path) -> None:
    service = MemoryLabService(tmp_path)
    service.ingest_event(
        memory_id="m1",
        sequence=1,
        event_type="observed",
        payload={"claim": "a", "trust_score": 0.5},
        source="s",
    )
    service.ingest_event(
        memory_id="m1",
        sequence=2,
        event_type="recalled",
        payload={},
        source="s",
    )
    assert service.replay_verify() is True
    api = AuditAPI(tmp_path)
    assert api.beliefs_current()["m1"]["access_count"] == 1
    diff = api.diff({"m1": 1}, {"m1": 2})
    assert "m1" in diff

    paths = compact_events_to_parquet_layout(tmp_path)
    assert paths
    assert_parquet_row_traceability(
        {"source_event_id": "e1", "source_payload_hash": ""},
    )
    schema = glue_bootstrap_schema()
    assert schema["table"] == "memory_events"
