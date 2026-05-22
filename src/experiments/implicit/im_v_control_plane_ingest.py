"""im_v — CONTROL_PLANE_INGEST falsification suite.

Spec: specs/CONTROL_PLANE_INGEST.md §9.

Five hooks, one per §9 check. All in-memory and deterministic — the
consumer runs against `InMemoryLineageEngine`, no AWS, no wall clock
(a fixed `PhysicalMoment` is passed to every `ingest`). Consistent
with the other implicit suites (`im_f` tests replay determinism the
same loop-free way).

  1. replay equivalence    — capture is deterministic; captured cues
                             round-trip through `cue_from_ingested_event`
                             and `ReplayCueProvider` unchanged.
  2. validation equivalence — a consumer-produced `control_cue_ingested`
                             passes storage-edge `validate_event_v7`,
                             and all five control-plane types are
                             mapping-registered with valid kinds (the
                             Athena predicate derives its sets from the
                             same mapping — Phase 2 equivalence).
  3. idempotency           — a cue delivered twice yields exactly one
                             `control_cue_ingested` and one
                             `control_cue_duplicate_ignored`.
  4. no silent loss        — good -> ingested, malformed -> rejected,
                             system fault -> TransientIngestError (the
                             dead-letter branch); DLQ recovery emits a
                             `control_cue_dlq_*` event.
  5. scope containment     — a foreign-scope cue routes away with no
                             event in this worker's scope, and is not
                             recorded as a rejection.
"""

from __future__ import annotations

from src.epistemic_triangle import (
    ASSERTION_KIND_ENUM,
    RECORD_KIND_ENUM,
    lookup_event_type,
    validate_event_v7,
)
from src.experiments.implicit.common import InMemoryLineageEngine, summarize
from src.heliotime import PhysicalMoment
from src.implicit_memory.cue_ingest import (
    CONTROL_PLANE_EVENT_TYPES,
    Cue,
    CueIngestionConsumer,
    InMemorySeenCueStore,
    TransientIngestError,
    cue_from_ingested_event,
    record_dlq_abandoned,
    record_dlq_recovered,
)
from src.implicit_memory.replay import ReplayCueProvider, rebuild_from_lineage


# Fixed capture moment — replay must be byte-stable; no wall-clock read.
_PM = PhysicalMoment(
    tai_iso="2026-05-13T12:00:00.000", solar_age_myr=4603.0, ecliptic_lon_deg=0.0
)
_AGENT = "lab-agent-1"
_STREAM = "im-v"


def _cue(
    cue_id: str,
    *,
    cue_type: str = "safety_anomaly",
    agent_id: str = _AGENT,
    stream_id: str = _STREAM,
    payload: dict | None = None,
) -> Cue:
    return Cue(
        cue_id=cue_id,
        cue_type=cue_type,
        agent_id=agent_id,
        stream_id=stream_id,
        source_id="im-v-fixture",
        source_class="fixture",
        payload=payload if payload is not None else {"signal": 1},
    )


def _consumer(lineage) -> CueIngestionConsumer:
    return CueIngestionConsumer(
        lineage=lineage,
        agent_id=_AGENT,
        stream_id=_STREAM,
        seen_cues=InMemorySeenCueStore(),
    )


class _FailingEmitter:
    """Emitter that raises a system fault on every emit — drives the
    no-silent-loss transient (dead-letter) branch."""

    def emit(self, **kwargs):
        raise RuntimeError("simulated durable-write failure")


def _hook_replay_equivalence() -> dict:
    cues = [
        _cue("v-rep-1"),
        _cue("v-rep-2", cue_type="scheduled_cue"),
        _cue("v-rep-3", cue_type="recall_directive"),
    ]

    signatures: list[str] = []
    decoded: list[Cue] = []
    for run_index in range(2):
        eng = InMemoryLineageEngine(events=[])
        consumer = _consumer(eng)
        for cue in cues:
            consumer.ingest(cue, tai_moment=_PM)
        signatures.append(rebuild_from_lineage(eng.events)["decision_signature"])
        if run_index == 0:
            ingested = [e for e in eng.events if e["event_type"] == "control_cue_ingested"]
            decoded = [cue_from_ingested_event(e) for e in ingested]
            replayed = ReplayCueProvider(eng.events).pull()

    deterministic = signatures[0] == signatures[1]
    round_trip = len(decoded) == len(cues) and all(
        d.cue_id == o.cue_id and d.cue_type == o.cue_type and d.payload == o.payload
        and d.source_class == o.source_class
        for d, o in zip(decoded, cues)
    )
    replay_count_ok = len(replayed) == len(cues)
    return {
        "hook": "replay_equivalence",
        "pass": deterministic and round_trip and replay_count_ok,
        "deterministic": deterministic,
        "round_trip": round_trip,
        "replay_count_ok": replay_count_ok,
    }


def _hook_validation_equivalence() -> dict:
    eng = InMemoryLineageEngine(events=[])
    _consumer(eng).ingest(_cue("v-val-1"), tai_moment=_PM)
    ingested = [e for e in eng.events if e["event_type"] == "control_cue_ingested"]
    # A consumer-produced event passes storage-edge v7 validation.
    edge_ok = len(ingested) == 1 and validate_event_v7(ingested[0]) is None

    # Every control-plane type is mapping-registered with kinds in the
    # closed enums. The Athena predicate derives its membership/enum
    # sets from this same mapping, so storage-edge acceptance implies
    # canonical-ingestion acceptance (Phase 2 equivalence).
    mapping_ok = True
    for event_type in CONTROL_PLANE_EVENT_TYPES:
        mapping = lookup_event_type(event_type)
        if mapping is None or mapping.record_kind.value not in RECORD_KIND_ENUM:
            mapping_ok = False
            break
        if (
            mapping.assertion_kind is not None
            and mapping.assertion_kind.value not in ASSERTION_KIND_ENUM
        ):
            mapping_ok = False
            break

    return {
        "hook": "validation_equivalence",
        "pass": edge_ok and mapping_ok,
        "edge_ok": edge_ok,
        "mapping_ok": mapping_ok,
    }


def _hook_idempotency() -> dict:
    eng = InMemoryLineageEngine(events=[])
    consumer = _consumer(eng)
    cue = _cue("v-dup-1")
    first = consumer.ingest(cue, tai_moment=_PM)
    second = consumer.ingest(cue, tai_moment=_PM)
    ingested_count = sum(1 for e in eng.events if e["event_type"] == "control_cue_ingested")
    duplicate_count = sum(
        1 for e in eng.events if e["event_type"] == "control_cue_duplicate_ignored"
    )
    return {
        "hook": "idempotency",
        "pass": (
            first.status.value == "ingested"
            and second.status.value == "duplicate"
            and ingested_count == 1
            and duplicate_count == 1
        ),
        "ingested_count": ingested_count,
        "duplicate_count": duplicate_count,
    }


def _hook_no_silent_loss() -> dict:
    eng = InMemoryLineageEngine(events=[])
    consumer = _consumer(eng)
    good = consumer.ingest(_cue("v-loss-good"), tai_moment=_PM)
    bad = consumer.ingest(_cue("v-loss-bad", cue_type="not_a_class"), tai_moment=_PM)

    # System fault -> TransientIngestError (the dead-letter branch).
    transient_raised = False
    try:
        _consumer(_FailingEmitter()).ingest(_cue("v-loss-transient"), tai_moment=_PM)
    except TransientIngestError:
        transient_raised = True

    # A dead-lettered cue's operator action closes the audit gap.
    dlq_eng = InMemoryLineageEngine(events=[])
    record_dlq_recovered(
        dlq_eng, cue_id="v-loss-transient", agent_id=_AGENT, stream_id=_STREAM,
        operator="im-v", tai_moment=_PM,
    )
    record_dlq_abandoned(
        dlq_eng, cue_id="v-loss-other", agent_id=_AGENT, stream_id=_STREAM,
        operator="im-v", reason="falsification_probe", tai_moment=_PM,
    )
    dlq_types = {e["event_type"] for e in dlq_eng.events}

    return {
        "hook": "no_silent_loss",
        "pass": (
            good.status.value == "ingested"
            and bad.status.value == "rejected"
            and transient_raised
            and "control_cue_dlq_recovered" in dlq_types
            and "control_cue_dlq_abandoned" in dlq_types
        ),
        "good": good.status.value,
        "bad": bad.status.value,
        "transient_raised": transient_raised,
        "dlq_types": sorted(dlq_types),
    }


def _hook_scope_containment() -> dict:
    eng = InMemoryLineageEngine(events=[])
    consumer = CueIngestionConsumer(
        lineage=eng, agent_id="agent-A", stream_id="stream-A",
        seen_cues=InMemorySeenCueStore(),
    )
    in_scope = consumer.ingest(
        _cue("v-scope-mine", agent_id="agent-A", stream_id="stream-A"), tai_moment=_PM
    )
    events_before_foreign = len(eng.events)
    foreign = consumer.ingest(
        _cue("v-scope-foreign", agent_id="agent-B", stream_id="stream-B"), tai_moment=_PM
    )
    # A foreign-scope cue routes away: no event in this worker's scope.
    no_foreign_effect = len(eng.events) == events_before_foreign
    return {
        "hook": "scope_containment",
        "pass": (
            in_scope.status.value == "ingested"
            and foreign.status.value == "routed_away"
            and no_foreign_effect
        ),
        "in_scope": in_scope.status.value,
        "foreign": foreign.status.value,
        "no_foreign_effect": no_foreign_effect,
    }


def run() -> dict:
    hooks = [
        _hook_replay_equivalence(),
        _hook_validation_equivalence(),
        _hook_idempotency(),
        _hook_no_silent_loss(),
        _hook_scope_containment(),
    ]
    pass_count = sum(1 for h in hooks if h["pass"])

    # Informational replay summary over one representative capture.
    rep_eng = InMemoryLineageEngine(events=[])
    _consumer(rep_eng).ingest(_cue("v-replay-summary"), tai_moment=_PM)

    summary = {
        "suite": "V",
        "pass_count": pass_count,
        "hook_count": len(hooks),
        "pass": pass_count == len(hooks),
        "hooks": hooks,
        "replay": summarize(rep_eng.events),
    }
    print(summary)
    return summary


if __name__ == "__main__":
    run()
