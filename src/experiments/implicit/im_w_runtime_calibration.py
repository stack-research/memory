"""im_w — runtime calibration over the live control-plane wire.

Spec: specs/RUNTIME_CALIBRATION.md.

This is intentionally not a new runtime feature. It is a repeatable
calibration run: produce a deterministic representative cue workload,
send it through EventBridge -> SQS -> CueIngestionConsumer, run the
implicit loop over captured lineage events, and publish the resulting
Run Summary artifact.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from botocore.config import Config

from src.aws_session import make_session
from src.config import load_config
from src.cutover_v7 import build_time_context
from src.experiments.implicit.artifacts import write_artifact
from src.experiments.implicit.common import InMemoryLineageEngine
from src.heliotime import physical_moment
from src.implicit_memory.cue_ingest import (
    CueIngestionConsumer,
    LineageBackedSeenCueStore,
    cue_from_ingested_event,
)
from src.implicit_memory.loop import ImplicitControllerLoop
from src.implicit_memory.replay import ReplayCueProvider, rebuild_from_lineage
from src.implicit_memory.run_cue_ingest import drain_queue
from src.lineage_engine import LineageEngine
from src.lineage_reader import build_lineage_reader
from src.storage import LineageStorage


AGENT_ID = "lab-agent-1"
STREAM_PREFIX = "im-w-runtime-calibration"
EVENT_BUS_DEFAULT = "memory-lab"
FIFO_QUEUE_DEFAULT = "memory-lab.fifo"
CONTROL_SOURCE = "memory-lab.control-plane"
CONTROL_DETAIL_TYPE = "control-cue"
FIXED_TAI = "2026-05-22T12:00:00.000"

WORKLOAD_COUNTS: dict[str, int] = {
    "repetition": 125,
    "scheduled_cue": 100,
    "recall_directive": 75,
    "goal_impact": 60,
    "prediction_error": 50,
    "contradiction_pressure": 40,
    "safety_anomaly": 30,
    "sensor_disagreement": 20,
}

ADVERSARIAL_COUNTS: dict[str, int] = {
    "spoofed_urgency": 40,
    "spoofed_sensory_confidence": 35,
    "high_trust_conflict_pressure": 30,
    "event_flood_pressure": 20,
}

ADVERSARIAL_DISTRIBUTION: tuple[tuple[str, str, int], ...] = (
    ("safety_anomaly", "spoofed_urgency", 20),
    ("scheduled_cue", "spoofed_urgency", 15),
    ("sensor_disagreement", "spoofed_urgency", 5),
    ("sensor_disagreement", "spoofed_sensory_confidence", 15),
    ("safety_anomaly", "spoofed_sensory_confidence", 10),
    ("prediction_error", "spoofed_sensory_confidence", 10),
    ("contradiction_pressure", "high_trust_conflict_pressure", 15),
    ("goal_impact", "high_trust_conflict_pressure", 10),
    ("recall_directive", "high_trust_conflict_pressure", 5),
    ("repetition", "event_flood_pressure", 20),
)

DUPLICATE_SUBMISSIONS = 25
AWS_CLIENT_CONFIG = Config(
    connect_timeout=10,
    read_timeout=30,
    retries={"max_attempts": 3, "mode": "standard"},
)


def _progress(message: str) -> None:
    print(f"[im-w] {message}", flush=True)


class RecordingLineage:
    """Record events returned by a real LineageEngine after durable emit."""

    def __init__(self, inner: LineageEngine) -> None:
        self.inner = inner
        self.events: list[dict[str, Any]] = []

    def emit(self, **kwargs: Any) -> Any:
        event = self.inner.emit(**kwargs)
        self.events.append(asdict(event))
        return event


class StaticProvenanceResolver:
    """Deterministic provenance inputs for calibration loop decisions."""

    def resolve(self, *, memory_id: str, stream_id: str, as_of_time: str) -> dict[str, object]:
        bucket = sum(ord(ch) for ch in memory_id) % 4
        return {
            "parent_chain_depth": bucket,
            "source_diversity": [0.25, 0.5, 0.75, 1.0][bucket],
            "age_of_original_source": float(bucket * 6),
            "fallback_reason": None,
            "provenance_signal_source": "computed",
            "chain_root_event_id": f"root:{memory_id}",
            "chain_length": bucket + 1,
            "distinct_source_classes": bucket + 1,
            "computed_at": as_of_time,
            "as_of_time": as_of_time,
        }


class CalibrationSeenCueStore:
    """Run-local front cache with lineage-backed fallback.

    The generated workload has a known cue-id set and the queue preflight
    proves no older messages are waiting. Avoiding a canonical point query
    for every first-seen generated cue keeps im_w focused on control-plane
    throughput. Duplicates are still detected after the first durable mark,
    and any cue outside this generated set falls through to canonical lineage.
    """

    def __init__(self, *, inner: LineageBackedSeenCueStore, generated_cue_ids: set[str]) -> None:
        self.inner = inner
        self.generated_cue_ids = generated_cue_ids
        self._seen_generated: set[str] = set()

    def has_seen(self, cue_id: str) -> bool:
        if cue_id in self.generated_cue_ids:
            return cue_id in self._seen_generated
        return self.inner.has_seen(cue_id)

    def mark_seen(self, cue_id: str) -> None:
        if cue_id in self.generated_cue_ids:
            self._seen_generated.add(cue_id)
        self.inner.mark_seen(cue_id)


def _run_id() -> str:
    return os.environ.get(
        "IMPLICIT_CALIBRATION_RUN_ID",
        f"im-w-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    )


def _event_bus_name() -> str:
    return os.environ.get("MEMORY_LAB_EVENT_BUS_NAME", EVENT_BUS_DEFAULT)


def _queue_name() -> str:
    return os.environ.get("MEMORY_LAB_FIFO_QUEUE_NAME", FIFO_QUEUE_DEFAULT)


def _fixed_now() -> datetime:
    return datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)


def _base_payload(
    *,
    cue_type: str,
    index: int,
    memory_id: str,
    run_id: str,
    adversarial_class: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "memory_id": memory_id,
        "prediction_error": 0.0,
        "goal_impact": 0.0,
        "risk_signal": 0.0,
        "repetition_signal": 0.0,
        "contradiction_pressure": 0.0,
        "explicit_directive": False,
        "urgency": 0.0,
        "sensory_confidence": 0.55,
        "sensor_values": [0.5, 0.52],
    }

    if cue_type == "repetition":
        payload.update(repetition_signal=0.65, sensory_confidence=0.7)
    elif cue_type == "scheduled_cue":
        payload.update(
            due_at=(_fixed_now() - timedelta(minutes=5 + index % 40)).isoformat(),
            urgency=0.55 + (index % 5) * 0.06,
            risk_signal=0.35 + (index % 4) * 0.08,
            sensory_confidence=0.75,
        )
    elif cue_type == "recall_directive":
        payload.update(explicit_directive=True, sensory_confidence=0.8)
    elif cue_type == "goal_impact":
        payload.update(goal_impact=0.75, risk_signal=0.25, sensory_confidence=0.72)
    elif cue_type == "prediction_error":
        payload.update(prediction_error=0.8, sensory_confidence=0.68)
    elif cue_type == "contradiction_pressure":
        payload.update(contradiction_pressure=0.72, sensory_confidence=0.66)
    elif cue_type == "safety_anomaly":
        payload.update(risk_signal=0.82, urgency=0.72, sensory_confidence=0.82)
    elif cue_type == "sensor_disagreement":
        payload.update(
            risk_signal=0.55,
            urgency=0.52,
            sensory_confidence=0.93,
            sensor_values=[0.05, 0.95],
        )

    if adversarial_class == "spoofed_urgency":
        payload.update(urgency=0.96, risk_signal=0.1, prediction_error=0.05)
    elif adversarial_class == "spoofed_sensory_confidence":
        payload.update(sensory_confidence=0.97, sensor_values=[0.05, 0.95])
    elif adversarial_class == "high_trust_conflict_pressure":
        payload.update(
            contradiction_pressure=0.88,
            sensory_confidence=0.94,
            risk_signal=max(float(payload["risk_signal"]), 0.45),
            source_trust_hint="high",
        )
    elif adversarial_class == "event_flood_pressure":
        payload.update(repetition_signal=0.9, sensory_confidence=0.9)
        payload["memory_id"] = f"{run_id}:flood-target"

    if adversarial_class:
        payload["adversarial_class"] = adversarial_class

    return payload


def _adversarial_assignments() -> dict[str, list[str | None]]:
    assignments: dict[str, list[str | None]] = {
        cue_type: [None] * count for cue_type, count in WORKLOAD_COUNTS.items()
    }
    offsets: Counter[str] = Counter()
    for cue_type, adversarial_class, count in ADVERSARIAL_DISTRIBUTION:
        start = offsets[cue_type]
        end = start + count
        if cue_type not in assignments:
            raise ValueError(f"unknown adversarial cue_type {cue_type!r}")
        if end > len(assignments[cue_type]):
            raise ValueError(
                f"adversarial distribution overfills {cue_type}: {end} > "
                f"{len(assignments[cue_type])}"
            )
        assignments[cue_type][start:end] = [adversarial_class] * count
        offsets[cue_type] = end
    return assignments


def generate_cue_details(
    *,
    run_id: str | None = None,
    agent_id: str = AGENT_ID,
    stream_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (unique cue details, duplicate cue details)."""

    rid = run_id or _run_id()
    stream = stream_id or f"{STREAM_PREFIX}-{rid}"
    adversarial = _adversarial_assignments()

    unique: list[dict[str, Any]] = []
    cursor = 0
    for cue_type, count in WORKLOAD_COUNTS.items():
        for local_index in range(count):
            adversarial_class = adversarial[cue_type][local_index]
            memory_id = f"{rid}:{cue_type}:{local_index:03d}"
            cue_id = f"{rid}:{cue_type}:{local_index:03d}"
            payload = _base_payload(
                cue_type=cue_type,
                index=cursor,
                memory_id=memory_id,
                run_id=rid,
                adversarial_class=adversarial_class,
            )
            unique.append(
                {
                    "cue_id": cue_id,
                    "cue_type": cue_type,
                    "agent_id": agent_id,
                    "stream_id": stream,
                    "source_id": "im-w-runtime-calibration",
                    "source_class": "fixture",
                    "payload": payload,
                    "claimed_at": FIXED_TAI,
                }
            )
            cursor += 1

    duplicates: list[dict[str, Any]] = []
    for i, original in enumerate(unique[:DUPLICATE_SUBMISSIONS]):
        dup = json.loads(json.dumps(original))
        dup["payload"]["duplicate_probe"] = True
        dup["payload"]["duplicate_probe_index"] = i
        dup["claimed_at"] = f"{FIXED_TAI}:duplicate:{i:02d}"
        duplicates.append(dup)

    return unique, duplicates


def cue_payload_fixture_shape(details: list[dict[str, Any]]) -> dict[str, Any]:
    fields_by_type: dict[str, set[str]] = defaultdict(set)
    for detail in details:
        payload = detail.get("payload", {})
        if isinstance(payload, dict):
            fields_by_type[str(detail.get("cue_type"))].update(payload.keys())
    return {
        "fixture_shape": True,
        "not_product_schema": True,
        "fields_by_cue_type": {
            key: sorted(value) for key, value in sorted(fields_by_type.items())
        },
    }


def fixture_disclosures() -> dict[str, Any]:
    return {
        "fixture_shape": True,
        "dedup_substitution": {
            "generated_cue_ids_use_run_local_front_cache": True,
            "lineage_backed_store_fallback_for_non_generated_ids": True,
            "duplicate_probe_interpretation": (
                "The 25 duplicate submissions exercise consumer idempotency and "
                "changed-body transport delivery, but are caught by the calibration "
                "front cache after first durable mark. They do not prove canonical "
                "lineage-backed dedup can catch in-run duplicates before Athena/S3 "
                "Tables ingestion has made S3 ingress writes query-visible."
            ),
            "canonical_lag_finding": (
                "A fast same-run duplicate probe crosses the known ingress-before-"
                "canonical visibility window. Treat this as a surfaced runtime "
                "calibration finding, not as production dedup closure."
            ),
        },
        "provenance_axis_substitution": {
            "resolver": "StaticProvenanceResolver",
            "provenance_signal_source": "computed",
            "interpretation": (
                "The provenance signal-source distribution is fixture-supplied and "
                "predetermined for this run. Claim and recall signal-source metrics "
                "still come from the loop's signal writers; provenance computed "
                "counts must not be read as a production-path measurement."
            ),
        },
        "replay_scope": {
            "provider": "ReplayCueProvider",
            "interpretation": (
                "Both loop passes consume the captured control_cue_ingested event "
                "list. The replay signature checks deterministic loop behavior over "
                "durably captured cues across real and in-memory emitters, not a "
                "separate live-bus loop run."
            ),
        },
    }


def _eventbridge_entries(details: list[dict[str, Any]], *, event_bus_name: str) -> list[dict[str, Any]]:
    return [
        {
            "Source": CONTROL_SOURCE,
            "DetailType": CONTROL_DETAIL_TYPE,
            "EventBusName": event_bus_name,
            "Detail": json.dumps(detail, sort_keys=True, separators=(",", ":")),
        }
        for detail in details
    ]


def _submit_eventbridge(events_client: Any, *, event_bus_name: str, details: list[dict[str, Any]]) -> dict[str, int]:
    submitted = 0
    failed = 0
    for start in range(0, len(details), 10):
        batch = _eventbridge_entries(details[start:start + 10], event_bus_name=event_bus_name)
        _progress(f"put_events batch {start // 10 + 1}/{(len(details) + 9) // 10}")
        resp = events_client.put_events(Entries=batch)
        failed += int(resp.get("FailedEntryCount", 0))
        submitted += len(batch) - int(resp.get("FailedEntryCount", 0))
    return {"submitted": submitted, "failed": failed}


def _queue_counts(sqs: Any, *, queue_url: str) -> dict[str, int]:
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
            "ApproximateNumberOfMessagesDelayed",
        ],
    )["Attributes"]
    return {
        "visible": int(attrs.get("ApproximateNumberOfMessages", "0")),
        "not_visible": int(attrs.get("ApproximateNumberOfMessagesNotVisible", "0")),
        "delayed": int(attrs.get("ApproximateNumberOfMessagesDelayed", "0")),
    }


def _rewrite_artifact_payload(*, cfg: Any, artifact_uri: str, payload: dict[str, Any]) -> None:
    parsed = urlparse(artifact_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"expected s3 artifact URI, got {artifact_uri!r}")
    s3 = make_session(cfg).client("s3", config=AWS_CLIENT_CONFIG)
    s3.put_object(
        Bucket=parsed.netloc,
        Key=parsed.path.lstrip("/"),
        Body=json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8"),
        ContentType="application/json",
    )


def _drain_until_accounted(
    *,
    consumer: CueIngestionConsumer,
    sqs: Any,
    queue_url: str,
    expected_terminal: int,
    timeout_seconds: int = 180,
) -> dict[str, int]:
    totals: Counter[str] = Counter()
    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        batch_counts = drain_queue(
            consumer=consumer, sqs_client=sqs, queue_url=queue_url, max_batches=100
        )
        totals.update(batch_counts)
        terminal = (
            totals["ingested"]
            + totals["rejected"]
            + totals["duplicate"]
            + totals["routed_away"]
        )
        _progress(
            "drain pass "
            f"{attempt}: terminal={terminal}/{expected_terminal}, counts={dict(totals)}"
        )
        if terminal >= expected_terminal:
            break
        time.sleep(2)
    return dict(totals)


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _axis_metrics(events: list[dict[str, Any]], cfg) -> dict[str, Any]:
    dominant: Counter[str] = Counter()
    signal_sources: dict[str, Counter[str]] = {
        "claim": Counter(),
        "recall": Counter(),
        "provenance": Counter(),
    }
    triple_count = 0
    tied = 0
    behavior = 0
    all_computed = 0
    missing_axis_blocks = 0
    combined_per_axis_delta = 0

    for event in events:
        payload = _event_payload(event)
        triple = payload.get("uncertainty_triple")
        if isinstance(triple, dict):
            triple_count += 1
            axis_values = {
                "claim": triple.get("confidence_in_claim"),
                "recall_process": triple.get("confidence_in_recall_process"),
                "provenance_chain": triple.get("confidence_in_provenance_chain"),
            }
            dominant_axis = payload.get("dominant_axis")
            if dominant_axis:
                dominant[str(dominant_axis)] += 1
            values = list(axis_values.values())
            if len(set(values)) == 1:
                tied += 1

            combined_allowed = float(payload.get("combined_score", 0.0)) >= (
                cfg.retrieval_policy.uncertainty_combined_threshold
                if cfg.retrieval_policy.uncertainty_combined_threshold is not None
                else cfg.retrieval_policy.eligibility_threshold
            )
            per_axis_allowed = (
                float(axis_values["claim"] or 0.0) >= cfg.retrieval_policy.uncertainty_claim_threshold
                and float(axis_values["recall_process"] or 0.0) >= cfg.retrieval_policy.uncertainty_recall_process_threshold
                and float(axis_values["provenance_chain"] or 0.0) >= cfg.retrieval_policy.uncertainty_provenance_chain_threshold
            )
            if combined_allowed != per_axis_allowed:
                combined_per_axis_delta += 1

        behavior_influencing = (
            event.get("event_type") in {"implicit_admitted", "reflex_action_executed"}
            or payload.get("allow_influence") is True
        )
        if not behavior_influencing:
            continue
        behavior += 1
        claim = payload.get("claim_signals")
        recall = payload.get("recall_signals")
        provenance = payload.get("provenance_signal")
        if not all(isinstance(block, dict) for block in (claim, recall, provenance)):
            missing_axis_blocks += 1
            continue
        claim_source = str(claim.get("signal_source", "missing"))
        recall_source = str(recall.get("signal_source", "missing"))
        provenance_source = str(provenance.get("signal_source", "missing"))
        signal_sources["claim"][claim_source] += 1
        signal_sources["recall"][recall_source] += 1
        signal_sources["provenance"][provenance_source] += 1
        if claim_source == recall_source == provenance_source == "computed":
            all_computed += 1

    return {
        "triple_bearing_decisions": triple_count,
        "dominant_axis_distribution": dict(dominant),
        "axis_tie_count": tied,
        "axis_tie_rate": tied / max(1, triple_count),
        "combined_vs_per_axis_delta": combined_per_axis_delta,
        "behavior_influencing_decisions": behavior,
        "behavior_influencing_missing_axis_blocks": missing_axis_blocks,
        "signal_source_distribution": {
            key: dict(counter) for key, counter in signal_sources.items()
        },
        "all_axes_computed_fraction": all_computed / max(1, behavior),
    }


def _loop_decision_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    trigger_actions: Counter[str] = Counter()
    rejected_reasons: Counter[str] = Counter()
    event_types = Counter(str(event.get("event_type")) for event in events)
    for event in events:
        payload = _event_payload(event)
        if event.get("event_type") == "implicit_trigger_evaluated":
            trigger_actions[str(payload.get("action", "unknown"))] += 1
        if event.get("event_type") == "implicit_rejected":
            rejected_reasons[str(payload.get("reason", "unknown"))] += 1
    return {
        "event_type_counts": dict(event_types),
        "trigger_outcome_counts": dict(trigger_actions),
        "implicit_admitted": event_types.get("implicit_admitted", 0),
        "implicit_rejected_by_reason": dict(rejected_reasons),
        "reflex_actions": event_types.get("reflex_action_executed", 0),
        "no_op": event_types.get("implicit_no_op", 0),
        "defer": event_types.get("implicit_trigger_deferred", 0),
    }


def _validate_generation(unique: list[dict[str, Any]], duplicates: list[dict[str, Any]]) -> dict[str, Any]:
    cue_type_counts = Counter(str(detail["cue_type"]) for detail in unique)
    adversarial_counts = Counter(
        str(detail["payload"].get("adversarial_class"))
        for detail in unique
        if detail["payload"].get("adversarial_class")
    )
    adversarial_by_cue_type = Counter(
        str(detail["cue_type"])
        for detail in unique
        if detail["payload"].get("adversarial_class")
    )
    adversarial_matrix = Counter(
        (str(detail["cue_type"]), str(detail["payload"].get("adversarial_class")))
        for detail in unique
        if detail["payload"].get("adversarial_class")
    )
    expected_by_cue_type = Counter()
    expected_matrix = Counter()
    for cue_type, adversarial_class, count in ADVERSARIAL_DISTRIBUTION:
        expected_by_cue_type[cue_type] += count
        expected_matrix[(cue_type, adversarial_class)] += count
    duplicate_reuse = all(dup["cue_id"] == unique[i]["cue_id"] for i, dup in enumerate(duplicates))
    return {
        "pass": (
            len(unique) == 500
            and len({d["cue_id"] for d in unique}) == 500
            and dict(cue_type_counts) == WORKLOAD_COUNTS
            and sum(adversarial_counts.values()) == 125
            and dict(adversarial_counts) == ADVERSARIAL_COUNTS
            and adversarial_by_cue_type == expected_by_cue_type
            and adversarial_matrix == expected_matrix
            and len(duplicates) == DUPLICATE_SUBMISSIONS
            and duplicate_reuse
        ),
        "unique_count": len(unique),
        "unique_cue_ids": len({d["cue_id"] for d in unique}),
        "cue_type_counts": dict(cue_type_counts),
        "adversarial_counts": dict(adversarial_counts),
        "adversarial_cue_type_counts": dict(adversarial_by_cue_type),
        "adversarial_distribution": {
            f"{cue_type}:{adversarial_class}": count
            for (cue_type, adversarial_class), count in sorted(adversarial_matrix.items())
        },
        "duplicate_submissions": len(duplicates),
        "duplicates_reuse_cue_id": duplicate_reuse,
    }


def run() -> dict:
    run_id = _run_id()
    stream_id = f"{STREAM_PREFIX}-{run_id}"
    phase_started = time.monotonic()
    phase_elapsed: dict[str, float] = {}
    failure_stage: str | None = None
    _progress(f"starting run_id={run_id} stream_id={stream_id}")

    def mark(stage: str, started: float) -> None:
        phase_elapsed[stage] = round(time.monotonic() - started, 3)
        _progress(f"{stage} completed in {phase_elapsed[stage]}s")

    unique, duplicates = generate_cue_details(run_id=run_id, stream_id=stream_id)
    generation = _validate_generation(unique, duplicates)
    if not generation["pass"]:
        raise AssertionError(f"runtime calibration generation check failed: {generation}")
    _progress("generation check passed")

    _progress("loading config and AWS clients")
    cfg = load_config()
    session = make_session(cfg)
    sqs = session.client("sqs", config=AWS_CLIENT_CONFIG)
    events = session.client("events", config=AWS_CLIENT_CONFIG)
    _progress(f"resolving queue {_queue_name()}")
    queue_url = sqs.get_queue_url(QueueName=_queue_name())["QueueUrl"]
    preflight_counts = _queue_counts(sqs, queue_url=queue_url)
    _progress(f"queue preflight counts={preflight_counts}")
    if any(preflight_counts.values()):
        raise RuntimeError(
            f"runtime calibration preflight failed: FIFO queue is not empty: {preflight_counts}"
        )

    _progress("building deterministic time context")
    time_context, time_context_id, _ = build_time_context()
    fixed_pm = physical_moment(FIXED_TAI, scale="tai")

    _progress("initializing lineage-backed ingestion")
    storage = LineageStorage(cfg)
    ingest_lineage = RecordingLineage(
        LineageEngine(storage=storage, time_context_id=time_context_id)
    )
    lineage_seen = LineageBackedSeenCueStore(
        reader=build_lineage_reader(cfg), stream_id=stream_id
    )
    consumer = CueIngestionConsumer(
        lineage=ingest_lineage,
        agent_id=AGENT_ID,
        stream_id=stream_id,
        seen_cues=CalibrationSeenCueStore(
            inner=lineage_seen,
            generated_cue_ids={str(detail["cue_id"]) for detail in unique},
        ),
    )

    all_submissions = unique + duplicates
    try:
        started = time.monotonic()
        _progress(f"submitting {len(all_submissions)} control cues to EventBridge")
        produce = _submit_eventbridge(
            events, event_bus_name=_event_bus_name(), details=all_submissions
        )
        mark("produce", started)
        if produce["failed"]:
            failure_stage = "produce"
            raise RuntimeError(f"EventBridge PutEvents failed entries: {produce}")

        started = time.monotonic()
        _progress("draining SQS into cue ingestion")
        drain = _drain_until_accounted(
            consumer=consumer,
            sqs=sqs,
            queue_url=queue_url,
            expected_terminal=len(all_submissions),
        )
        mark("ingest", started)
        accounted = sum(
            int(drain.get(key, 0))
            for key in ("ingested", "rejected", "duplicate", "routed_away")
        )
        if accounted != len(all_submissions):
            failure_stage = "ingest"
            raise RuntimeError(
                f"drain did not account for every submission: accounted={accounted}, "
                f"expected={len(all_submissions)}, drain={drain}"
            )

        captured_events = [
            event for event in ingest_lineage.events
            if event.get("event_type") == "control_cue_ingested"
        ]
        _progress(f"captured {len(captured_events)} ingested cue events")

        started = time.monotonic()
        _progress("running live implicit loop")
        live_loop_lineage = RecordingLineage(
            LineageEngine(
                storage=storage,
                time_context_id=time_context_id,
                default_tai_moment=fixed_pm,
            )
        )
        loop = ImplicitControllerLoop(
            cfg=cfg,
            lineage=live_loop_lineage,
            cue_provider=ReplayCueProvider(captured_events),
            agent_id=AGENT_ID,
            stream_id=stream_id,
            provenance_resolver=StaticProvenanceResolver(),
        )
        loop_stats = loop.tick(now=_fixed_now())
        mark("loop", started)

        started = time.monotonic()
        _progress("running replay comparison")
        replay_lineage = InMemoryLineageEngine(events=[])
        replay_loop = ImplicitControllerLoop(
            cfg=cfg,
            lineage=replay_lineage,
            cue_provider=ReplayCueProvider(captured_events),
            agent_id=AGENT_ID,
            stream_id=stream_id,
            provenance_resolver=StaticProvenanceResolver(),
        )
        replay_stats = replay_loop.tick(now=_fixed_now())
        live_signature = rebuild_from_lineage(live_loop_lineage.events)
        replay_signature = rebuild_from_lineage(replay_lineage.events)
        replay_equivalent = (
            live_signature["decision_signature"] == replay_signature["decision_signature"]
        )
        mark("replay", started)
        if not replay_equivalent:
            failure_stage = "replay"

        run_summary = {
            "pass": replay_equivalent,
            "run_id": run_id,
            "agent_id": AGENT_ID,
            "stream_id": stream_id,
            "target_counts": {
                "unique_cues": 500,
                "duplicate_submissions": DUPLICATE_SUBMISSIONS,
                "cue_type_counts": WORKLOAD_COUNTS,
                "adversarial_counts": ADVERSARIAL_COUNTS,
                "adversarial_distribution": [
                    {
                        "cue_type": cue_type,
                        "adversarial_class": adversarial_class,
                        "count": count,
                    }
                    for cue_type, adversarial_class, count in ADVERSARIAL_DISTRIBUTION
                ],
            },
            "actual_submitted_counts": {
                "unique": len(unique),
                "duplicates": len(duplicates),
                "eventbridge": produce,
            },
            "generation": generation,
            "cue_payload_fixture_shape": cue_payload_fixture_shape(unique),
            "fixture_disclosures": fixture_disclosures(),
            "phase_elapsed_seconds": phase_elapsed,
            "failure_stage": failure_stage,
            "control_plane_outcomes": drain,
            "loop_decisions": _loop_decision_metrics(live_loop_lineage.events),
            "loop_stats": loop_stats,
            "replay_loop_stats": replay_stats,
            "epistemic_surface": _axis_metrics(live_loop_lineage.events, cfg),
            "replay": {
                "live_signature": live_signature,
                "replay_signature": replay_signature,
                "equivalent": replay_equivalent,
                "live_event_count": len(live_loop_lineage.events),
                "replay_event_count": len(replay_lineage.events),
            },
            "time_context": {
                "time_context_id": time_context_id,
                "time_context": asdict(time_context),
            },
        }

        started = time.monotonic()
        _progress("writing S3 run summary artifact")
        artifact_uri = write_artifact(name="im-w-runtime-calibration-summary", payload=run_summary)
        mark("artifact_write", started)
        run_summary["artifact"] = artifact_uri
        run_summary["phase_elapsed_seconds"] = phase_elapsed
        _rewrite_artifact_payload(cfg=cfg, artifact_uri=artifact_uri, payload=run_summary)

        summary_payload = {
            "snapshot_type": "runtime_calibration_summary",
            "run_id": run_id,
            "artifact": artifact_uri,
            "replay_equivalent": replay_equivalent,
            "failure_stage": failure_stage,
            "epistemic_surface": run_summary["epistemic_surface"],
            "control_plane_outcomes": drain,
            "phase_elapsed_seconds": phase_elapsed,
        }
        _progress("emitting runtime calibration snapshot event")
        live_loop_lineage.emit(
            event_type="snapshotted",
            agent_id=AGENT_ID,
            stream_id=stream_id,
            memory_id=f"{run_id}:runtime-calibration-summary",
            actor_class="runtime_calibration",
            source_class="internal_engine",
            payload=summary_payload,
            tai_moment=fixed_pm,
        )

        if not replay_equivalent:
            raise AssertionError("runtime calibration replay equivalence failed")

        print(json.dumps(run_summary, indent=2, sort_keys=True, default=str))
        return run_summary
    except Exception:
        if failure_stage is None:
            failure_stage = "artifact_write" if "run_summary" in locals() else "unknown"
        raise
    finally:
        phase_elapsed["total"] = round(time.monotonic() - phase_started, 3)


if __name__ == "__main__":
    run()
