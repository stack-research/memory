"""Control-plane cue ingestion.

Spec: specs/CONTROL_PLANE_INGEST.md (Decisions 1, 2, 4, 5).

Capture-before-act: a live control-plane cue becomes a
`control_cue_ingested` lineage event — validated and durably written —
*before* the implicit loop may act on it. The raw EventBridge/SQS
message is transport; the loop's input is the captured event, and the
loop may read only what the event carries (Decision 2).

This module is the testable core. The SQS receive loop and the Lambda
handler are thin transport wrappers wired in CDK (spec §8 / Phase 6).
Connecting captured `control_cue_ingested` events to the implicit loop
is Phase 4 — `ingest()` ends at the INGESTED outcome.

Durability boundary (Decision 2): `LineageEngine.emit` ->
`LineageStorage.append_event` validates the event with
`validate_event_v7` and then writes it durably to S3 ingress. Phase 2
static analysis found storage-edge validation equivalent to canonical
Athena ingestion for these event types; the runtime end-to-end proof
is the Phase 7 "validation equivalence" falsification check.
`append_event` returning without raising means the event is *both*
canonical-valid and durably written — only then is the cue "captured"
and safe to release to the loop.

Failure classification (Decision 2): a `LineageValidationError` means
the cue produced a non-canonical event — a cue defect, recorded as
`control_cue_rejected`. Any other failure (missing config, a durable
write error, transport) is a system fault — it raises
`TransientIngestError`, the caller retries, and the SQS message
dead-letters. The two are never conflated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from src.epistemic_triangle import lookup_event_type
from src.heliotime import PhysicalMoment, now as heliotime_now
from src.lineage_reader import LineageReader
from src.storage import LineageValidationError


# Decision 1 — valid cue types are exactly the implicit loop's existing
# trigger classes (IMPLICIT_MEMORY_SPEC §7.1). A cue naming anything
# else is rejected.
VALID_CUE_TYPES: frozenset[str] = frozenset({
    "prediction_error",
    "goal_impact",
    "safety_anomaly",
    "repetition",
    "contradiction_pressure",
    "recall_directive",
    "scheduled_cue",
    "sensor_disagreement",
})

# The five event types this module emits (CONTROL_PLANE_INGEST §7).
# Registered in src/epistemic_triangle/mapping.py; record_kind /
# assertion_kind are auto-derived from that table by LineageEngine.emit.
CONTROL_PLANE_EVENT_TYPES: tuple[str, ...] = (
    "control_cue_ingested",
    "control_cue_rejected",
    "control_cue_duplicate_ignored",
    "control_cue_dlq_recovered",
    "control_cue_dlq_abandoned",
)

_ACTOR_CLASS = "control_plane_ingestor"


class CueRejectionReason(str, Enum):
    """Deterministic, machine-readable rejection reasons (Decision 5)."""

    MALFORMED_CUE_ID = "malformed_cue_id"
    UNKNOWN_CUE_TYPE = "unknown_cue_type"
    MALFORMED_SOURCE = "malformed_source"
    MALFORMED_SCOPE = "malformed_scope"
    MALFORMED_PAYLOAD = "malformed_payload"
    UNKNOWN_SCOPE = "unknown_scope"
    VALIDATION_FAILED = "validation_failed"


class IngestStatus(str, Enum):
    """Outcome of a single `ingest()` call.

    The spec's failure trichotomy is ingested / rejected / dead-lettered.
    Dead-lettering is not an `ingest()` return — it is the caller's
    response to a raised `TransientIngestError`. DUPLICATE and
    ROUTED_AWAY are not failures: a duplicate is idempotently dropped;
    a routed-away cue belongs to another worker's scope.
    """

    INGESTED = "ingested"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    ROUTED_AWAY = "routed_away"


@dataclass(frozen=True)
class Cue:
    """A control-plane signal — CONTROL_PLANE_INGEST Decision 1.

    `payload` is opaque to the loop (Decision 2): the loop branches only
    on `cue_type` and scope; the payload is read by admission/eligibility,
    never branched on in the loop itself. It is typed `Any` because a
    producer may send a non-object — that is a malformed cue, rejected,
    not silently coerced. `claimed_at` is the producer's own timestamp,
    witness data only; the authoritative `physical_moment` is stamped at
    capture.
    """

    cue_id: str
    cue_type: str
    agent_id: str
    stream_id: str
    source_id: str
    source_class: str
    payload: Any = field(default_factory=dict)
    claimed_at: str | None = None


@dataclass(frozen=True)
class IngestOutcome:
    status: IngestStatus
    cue_id: str
    event_id: str | None = None  # the control_cue_ingested event, when INGESTED
    reason: str | None = None    # a CueRejectionReason value, when REJECTED


class TransientIngestError(RuntimeError):
    """Capture failed for a non-cue reason — missing config, a durable
    write error, transport.

    The caller must retry; after the SQS retry budget the message
    dead-letters (Decision 5). Distinct from a malformed cue, which is
    recorded as `control_cue_rejected` and is *not* an exception.
    """


class SeenCueStore(Protocol):
    """Dedup backing (Decision 4).

    `InMemorySeenCueStore` is for tests only. Live use requires a
    lineage-backed implementation — one that asks canonical lineage
    whether a `control_cue_ingested` already exists for this `cue_id`.
    That implementation is a Phase 4 prerequisite (CONTROL_PLANE_INGEST
    §10): without it the Decision 4 idempotency guarantee does not hold
    across consumer restarts.
    """

    def has_seen(self, cue_id: str) -> bool: ...
    def mark_seen(self, cue_id: str) -> None: ...


class InMemorySeenCueStore:
    """Process-lifetime dedup. TEST USE ONLY.

    Pairs with SQS `MessageDeduplicationId` for the FIFO dedup window,
    but loses state across consumer restarts — a redelivery outside the
    FIFO window would then produce a second `control_cue_ingested`. The
    lineage-backed store closes that gap; this one must not back a live
    consumer.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def has_seen(self, cue_id: str) -> bool:
        return cue_id in self._seen

    def mark_seen(self, cue_id: str) -> None:
        self._seen.add(cue_id)


class LineageBackedSeenCueStore:
    """Dedup backed by canonical lineage (Decision 4 / spec §10).

    `has_seen` is layered:
      - an in-process cache covers cues captured during this process's
        lifetime, including the window before Athena has ingested the
        `control_cue_ingested` event into the canonical table;
      - a canonical-lineage query covers cues captured by a prior
        process or another worker — the cross-restart safety net.

    `control_cue_ingested` events carry `memory_id == cue_id`, so a
    per-(stream, memory_id) lineage query is an exact cue-id lookup.

    Residual window: a cue captured (written to S3 ingress) but not yet
    ingested into the canonical table, when the worker then restarts, is
    invisible to both layers. SQS FIFO `MessageDeduplicationId` covers
    that short window; a dedicated cue-id index is the §10 hardening
    follow-up. The canonical query is also multi-second latency — it is
    reached only for cues absent from the in-process cache (and, live,
    absent from the SQS FIFO dedup window): genuinely-new or long-delayed
    cues.
    """

    def __init__(self, *, reader: LineageReader, stream_id: str) -> None:
        self.reader = reader
        self.stream_id = stream_id
        self._recent: set[str] = set()

    def has_seen(self, cue_id: str) -> bool:
        if cue_id in self._recent:
            return True
        rows = self.reader.query_memory_events(
            stream_id=self.stream_id, memory_id=cue_id
        )
        return any(r.get("event_type") == "control_cue_ingested" for r in rows)

    def mark_seen(self, cue_id: str) -> None:
        self._recent.add(cue_id)


class CueIngestionConsumer:
    """Capture-before-act ingestion for one worker's scope.

    `ingest()` is the testable core. Construct one per
    `(agent_id, stream_id)` worker. `seen_cues` is required and has no
    default: the dedup-backing choice (in-memory for tests, lineage-backed
    for live) must be explicit at every construction site.
    """

    def __init__(
        self,
        *,
        lineage: Any,  # LineageEngine, or any .emit-compatible emitter
        agent_id: str,
        stream_id: str,
        seen_cues: SeenCueStore,
        known_scopes: frozenset[tuple[str, str]] | None = None,
    ) -> None:
        self.lineage = lineage
        self.agent_id = agent_id
        self.stream_id = stream_id
        self.seen_cues = seen_cues
        # When provided, a well-formed scope absent from this set is
        # `unknown` (a cue defect -> rejected). Absent the registry, a
        # well-formed not-mine scope is treated as routing (-> ROUTED_AWAY),
        # the conservative choice: never reject what might be another
        # worker's valid cue. CONTROL_PLANE_INGEST Decision 5.
        self.known_scopes = known_scopes

    def ingest(
        self, cue: Cue, *, tai_moment: PhysicalMoment | None = None
    ) -> IngestOutcome:
        """Capture one cue. Returns an IngestOutcome, or raises
        TransientIngestError if a system fault prevents capture (caller
        retries; the SQS message then dead-letters).
        """
        # The capture moment, stamped once here at the edge. heliotime.now()
        # is the one sanctioned edge wall-clock read (Decision 3). Tests
        # and replay pass `tai_moment` explicitly for determinism.
        moment = tai_moment if tai_moment is not None else heliotime_now()

        # 1. Cue shape (Decision 1 / 5).
        shape_failure = self._shape_failure(cue)
        if shape_failure is not None:
            reason, detail = shape_failure
            return self._reject(cue, reason=reason, moment=moment, detail=detail)

        # 2. Scope routing — three modes (Decision 5).
        scope = (cue.agent_id, cue.stream_id)
        if scope != (self.agent_id, self.stream_id):
            if self.known_scopes is not None and scope not in self.known_scopes:
                return self._reject(
                    cue,
                    reason=CueRejectionReason.UNKNOWN_SCOPE,
                    moment=moment,
                    detail=f"scope {scope} is not a known worker scope",
                )
            # Well-formed scope, another worker's: a routing condition,
            # not a cue defect. No event — recording it as a rejection
            # would camouflage a routing bug as a cue bug.
            return IngestOutcome(status=IngestStatus.ROUTED_AWAY, cue_id=cue.cue_id)

        # 3. Dedup (Decision 4). A dedup-check failure is a system
        #    fault, not a cue defect — retry, then DLQ.
        try:
            already_seen = self.seen_cues.has_seen(cue.cue_id)
        except Exception as exc:
            raise TransientIngestError(
                f"dedup check for cue {cue.cue_id} failed: {exc}"
            ) from exc
        if already_seen:
            self._emit_or_transient(
                "control_cue_duplicate_ignored",
                cue,
                moment,
                payload={"cue_id": cue.cue_id, "cue_type": cue.cue_type},
                source_class=cue.source_class,
            )
            return IngestOutcome(status=IngestStatus.DUPLICATE, cue_id=cue.cue_id)

        # 4. Capture-before-act (Decision 2). emit -> append_event
        #    validates (canonical-equivalent) then durably writes.
        try:
            event = self.lineage.emit(
                event_type="control_cue_ingested",
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                memory_id=cue.cue_id,
                payload={
                    "cue_id": cue.cue_id,
                    "cue_type": cue.cue_type,
                    "source_id": cue.source_id,
                    "claimed_at": cue.claimed_at,
                    # Opaque to the loop (Decision 2).
                    "cue_payload": cue.payload,
                },
                tai_moment=moment,
                actor_class=_ACTOR_CLASS,
                source_class=cue.source_class,
            )
        except LineageValidationError as exc:
            # The cue produced a non-canonical event — a cue defect.
            return self._reject(
                cue,
                reason=CueRejectionReason.VALIDATION_FAILED,
                moment=moment,
                detail=str(exc),
            )
        except Exception as exc:
            # Missing config, durable-write failure, transport — a
            # system fault. Never a cue rejection: retry, then DLQ.
            raise TransientIngestError(
                f"capture of cue {cue.cue_id} failed (system fault, not a cue defect): {exc}"
            ) from exc

        # append_event returned: validated AND durably written. Only
        # now is the cue captured and safe to release to the loop.
        self.seen_cues.mark_seen(cue.cue_id)
        return IngestOutcome(
            status=IngestStatus.INGESTED, cue_id=cue.cue_id, event_id=event.event_id
        )

    @staticmethod
    def _shape_failure(cue: Cue) -> tuple[CueRejectionReason, str] | None:
        """Return (reason, detail) for the first shape violation, or None.

        Detail is a deterministic, machine-readable string carried into
        the `control_cue_rejected` payload.
        """
        if not cue.cue_id or not str(cue.cue_id).strip():
            return (CueRejectionReason.MALFORMED_CUE_ID, "cue_id is empty")
        if cue.cue_type not in VALID_CUE_TYPES:
            return (
                CueRejectionReason.UNKNOWN_CUE_TYPE,
                f"cue_type '{cue.cue_type}' is not a known trigger class",
            )
        if not (cue.source_id and str(cue.source_id).strip()) or not (
            cue.source_class and str(cue.source_class).strip()
        ):
            return (
                CueRejectionReason.MALFORMED_SOURCE,
                "source_id and source_class are both required",
            )
        if not (cue.agent_id and str(cue.agent_id).strip()) or not (
            cue.stream_id and str(cue.stream_id).strip()
        ):
            return (
                CueRejectionReason.MALFORMED_SCOPE,
                "agent_id and stream_id are both required",
            )
        # Decision 5 lists malformed payload as a rejection trigger.
        # A non-object payload is not silently coerced (capture
        # fidelity): it is rejected, with the offending type recorded.
        if not isinstance(cue.payload, dict):
            return (
                CueRejectionReason.MALFORMED_PAYLOAD,
                f"payload must be a JSON object, got {type(cue.payload).__name__}",
            )
        if cue.claimed_at is not None and not isinstance(cue.claimed_at, str):
            return (
                CueRejectionReason.MALFORMED_PAYLOAD,
                f"claimed_at must be a string when present, got {type(cue.claimed_at).__name__}",
            )
        return None

    def _reject(
        self,
        cue: Cue,
        *,
        reason: CueRejectionReason,
        moment: PhysicalMoment,
        detail: str | None = None,
    ) -> IngestOutcome:
        payload: dict[str, Any] = {"reason": reason.value, "cue_id": cue.cue_id}
        if detail:
            payload["detail"] = detail
        # control_cue_rejected is recorded in THIS worker's scope. A
        # rejected cue's own (possibly malformed) scope must not steer
        # where the rejection lands. memory_id falls back to a sentinel
        # when the cue_id itself is malformed.
        memory_id = (
            str(cue.cue_id).strip()
            if (cue.cue_id and str(cue.cue_id).strip())
            else "control-cue:malformed"
        )
        # Failing to record a rejection is itself a write failure ->
        # transient (the SQS message is retried, then dead-lettered).
        self._emit_or_transient(
            "control_cue_rejected",
            cue,
            moment,
            payload=payload,
            source_class="internal_engine",
            memory_id=memory_id,
        )
        return IngestOutcome(
            status=IngestStatus.REJECTED, cue_id=cue.cue_id, reason=reason.value
        )

    def _emit_or_transient(
        self,
        event_type: str,
        cue: Cue,
        moment: PhysicalMoment,
        *,
        payload: dict[str, Any],
        source_class: str,
        memory_id: str | None = None,
    ) -> Any:
        """Emit a non-capture control-plane event. Any failure is a
        system fault -> TransientIngestError. The capture emit
        (`control_cue_ingested`) is NOT routed through here: it needs
        the LineageValidationError-vs-system-fault split."""
        try:
            return self.lineage.emit(
                event_type=event_type,
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                memory_id=memory_id if memory_id is not None else cue.cue_id,
                payload=payload,
                tai_moment=moment,
                actor_class=_ACTOR_CLASS,
                source_class=source_class,
            )
        except Exception as exc:
            raise TransientIngestError(
                f"emit of {event_type} for cue {cue.cue_id} failed: {exc}"
            ) from exc


def cue_from_message(body: dict[str, Any]) -> Cue:
    """Parse a control-plane bus/SQS message body into a `Cue`.

    Structural string fields are normalized to `str`. The `payload` and
    `claimed_at` are kept exactly as the producer sent them — a
    non-object payload or non-string `claimed_at` is preserved so shape
    validation can reject it deterministically (`MALFORMED_PAYLOAD`),
    rather than being silently coerced into a captured event that no
    longer reflects what was sent. A body that is not JSON-decodable at
    all is the transport layer's concern, upstream of this function.
    """
    return Cue(
        cue_id=str(body.get("cue_id", "") or ""),
        cue_type=str(body.get("cue_type", "") or ""),
        agent_id=str(body.get("agent_id", "") or ""),
        stream_id=str(body.get("stream_id", "") or ""),
        source_id=str(body.get("source_id", "") or ""),
        source_class=str(body.get("source_class", "") or ""),
        payload=body.get("payload", {}),       # raw — non-object is rejected, not coerced
        claimed_at=body.get("claimed_at"),     # raw — non-string is rejected, not coerced
    )


def cue_from_ingested_event(event: dict[str, Any]) -> Cue:
    """Decode a recorded `control_cue_ingested` lineage event back into
    the `Cue` it captured — the inverse of the consumer's capture.

    Enables deterministic replay (CONTROL_PLANE_INGEST Decision 3):
    decoded cues fed to the loop via `ReplayCueProvider` make it
    re-emit identical lineage. `event` is a full event dict (envelope +
    payload), as returned by `LineageStorage.append_event` or a
    canonical reader. `cue_id` prefers the payload field and falls back
    to the envelope `memory_id` (the consumer sets them equal).
    """
    payload = event.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    return Cue(
        cue_id=str(payload.get("cue_id") or event.get("memory_id") or ""),
        cue_type=str(payload.get("cue_type", "") or ""),
        agent_id=str(event.get("agent_id", "") or ""),
        stream_id=str(event.get("stream_id", "") or ""),
        source_id=str(payload.get("source_id", "") or ""),
        source_class=str(event.get("source_class", "") or ""),
        payload=payload.get("cue_payload", {}),
        claimed_at=payload.get("claimed_at"),
    )


def declare_control_plane_event_types(
    lineage: Any,
    *,
    agent_id: str,
    stream_id: str,
    tai_moment: PhysicalMoment | None = None,
) -> None:
    """Emit one `event_type_declared` per control-plane event type.

    The runtime half of the EPISTEMIC_TRIANGLE §3.5 two-channel mapping
    discipline (the static half is the `mapping.py` rows). Call once at
    consumer bootstrap, before the first `ingest()`. `__canonical_meta__`
    is the natural stream for these lineage_meta records.
    """
    moment = tai_moment if tai_moment is not None else heliotime_now()
    for event_type in CONTROL_PLANE_EVENT_TYPES:
        mapping = lookup_event_type(event_type)
        if mapping is None:
            raise ValueError(
                f"control-plane event_type '{event_type}' is not registered in "
                "src/epistemic_triangle/mapping.py (Phase 1 incomplete)"
            )
        lineage.emit(
            event_type="event_type_declared",
            agent_id=agent_id,
            stream_id=stream_id,
            memory_id=f"event-type:{event_type}",
            payload={
                "declared_event_type": event_type,
                "declared_record_kind": mapping.record_kind.value,
                "declared_assertion_kind": (
                    mapping.assertion_kind.value
                    if mapping.assertion_kind is not None
                    else None
                ),
                "declaration_reason": "control_plane_ingest_bootstrap",
            },
            tai_moment=moment,
            actor_class=_ACTOR_CLASS,
            source_class="internal_engine",
        )


def record_dlq_recovered(
    lineage: Any,
    *,
    cue_id: str,
    agent_id: str,
    stream_id: str,
    operator: str,
    detail: str | None = None,
    tai_moment: PhysicalMoment | None = None,
) -> None:
    """Record that an operator returned a dead-lettered cue to ingestion.

    Closes the DLQ audit gap (CONTROL_PLANE_INGEST Decision 5): a
    dead-lettered cue has no lineage marker at the moment it fails;
    this event closes the trail when an operator touches it.
    """
    moment = tai_moment if tai_moment is not None else heliotime_now()
    payload: dict[str, Any] = {"cue_id": cue_id, "operator": operator}
    if detail:
        payload["detail"] = detail
    lineage.emit(
        event_type="control_cue_dlq_recovered",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=cue_id,
        payload=payload,
        tai_moment=moment,
        actor_class=_ACTOR_CLASS,
        source_class="operator",
    )


def record_dlq_abandoned(
    lineage: Any,
    *,
    cue_id: str,
    agent_id: str,
    stream_id: str,
    operator: str,
    reason: str,
    tai_moment: PhysicalMoment | None = None,
) -> None:
    """Record that an operator abandoned a dead-lettered cue.

    The counterpart to `record_dlq_recovered`: the cue will not be
    re-ingested, and the audit trail says so explicitly.
    """
    moment = tai_moment if tai_moment is not None else heliotime_now()
    lineage.emit(
        event_type="control_cue_dlq_abandoned",
        agent_id=agent_id,
        stream_id=stream_id,
        memory_id=cue_id,
        payload={"cue_id": cue_id, "operator": operator, "reason": reason},
        tai_moment=moment,
        actor_class=_ACTOR_CLASS,
        source_class="operator",
    )
