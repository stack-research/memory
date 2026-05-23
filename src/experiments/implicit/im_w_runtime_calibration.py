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
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
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
GENERATION_BINDING_ID = "adversarial_matrix_coverage_required"
DOMINANT_AXIS_BINDING_ID = "dominant_axis_distribution_diversity_required"


@dataclass(frozen=True)
class WorkloadProfile:
    name: str
    purpose: str
    workload_counts: dict[str, int]
    adversarial_distribution: tuple[tuple[str, str, int], ...]
    duplicate_submissions: int

    @property
    def unique_cues(self) -> int:
        return sum(self.workload_counts.values())

    @property
    def adversarial_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for _, adversarial_class, count in self.adversarial_distribution:
            counts[adversarial_class] += count
        return dict(counts)


FULL_PROFILE = WorkloadProfile(
    name="full",
    purpose="runtime_calibration",
    workload_counts={
        "repetition": 125,
        "scheduled_cue": 100,
        "recall_directive": 75,
        "goal_impact": 60,
        "prediction_error": 50,
        "contradiction_pressure": 40,
        "safety_anomaly": 30,
        "sensor_disagreement": 20,
    },
    adversarial_distribution=(
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
    ),
    duplicate_submissions=25,
)

LOOP_PROBE_PROFILE = WorkloadProfile(
    name="loop_probe",
    purpose="consequence_loop_probe",
    workload_counts={
        "repetition": 24,
        "scheduled_cue": 16,
        "recall_directive": 12,
        "goal_impact": 12,
        "prediction_error": 10,
        "contradiction_pressure": 8,
        "safety_anomaly": 8,
        "sensor_disagreement": 6,
    },
    adversarial_distribution=(
        ("safety_anomaly", "spoofed_urgency", 4),
        ("scheduled_cue", "spoofed_urgency", 4),
        ("sensor_disagreement", "spoofed_urgency", 2),
        ("sensor_disagreement", "spoofed_sensory_confidence", 2),
        ("safety_anomaly", "spoofed_sensory_confidence", 2),
        ("prediction_error", "spoofed_sensory_confidence", 2),
        ("contradiction_pressure", "high_trust_conflict_pressure", 4),
        ("goal_impact", "high_trust_conflict_pressure", 2),
        ("recall_directive", "high_trust_conflict_pressure", 2),
        ("repetition", "event_flood_pressure", 8),
    ),
    duplicate_submissions=8,
)

WORKLOAD_PROFILES = {
    FULL_PROFILE.name: FULL_PROFILE,
    LOOP_PROBE_PROFILE.name: LOOP_PROBE_PROFILE,
}

WORKLOAD_COUNTS = FULL_PROFILE.workload_counts
ADVERSARIAL_COUNTS = FULL_PROFILE.adversarial_counts
ADVERSARIAL_DISTRIBUTION = FULL_PROFILE.adversarial_distribution
DUPLICATE_SUBMISSIONS = FULL_PROFILE.duplicate_submissions
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


def load_workload_profile() -> WorkloadProfile:
    name = os.environ.get("IMPLICIT_CALIBRATION_PROFILE", FULL_PROFILE.name)
    try:
        return WORKLOAD_PROFILES[name]
    except KeyError as exc:
        allowed = ", ".join(sorted(WORKLOAD_PROFILES))
        raise ValueError(
            f"unknown IMPLICIT_CALIBRATION_PROFILE {name!r}; expected one of: {allowed}"
        ) from exc


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


def _adversarial_assignments(*, profile: WorkloadProfile) -> dict[str, list[str | None]]:
    assignments: dict[str, list[str | None]] = {
        cue_type: [None] * count for cue_type, count in profile.workload_counts.items()
    }
    offsets: Counter[str] = Counter()
    for cue_type, adversarial_class, count in profile.adversarial_distribution:
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
    profile: WorkloadProfile | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (unique cue details, duplicate cue details)."""

    rid = run_id or _run_id()
    stream = stream_id or f"{STREAM_PREFIX}-{rid}"
    selected_profile = profile or load_workload_profile()
    adversarial = _adversarial_assignments(profile=selected_profile)

    unique: list[dict[str, Any]] = []
    cursor = 0
    for cue_type, count in selected_profile.workload_counts.items():
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
    for i, original in enumerate(unique[:selected_profile.duplicate_submissions]):
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


def fixture_disclosures(*, profile: WorkloadProfile) -> dict[str, Any]:
    return {
        "fixture_shape": True,
        "dedup_substitution": {
            "generated_cue_ids_use_run_local_front_cache": True,
            "lineage_backed_store_fallback_for_non_generated_ids": True,
            "duplicate_probe_interpretation": (
                f"The {profile.duplicate_submissions} duplicate submissions exercise "
                "consumer idempotency and "
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


def _read_json_uri(*, cfg: Any, uri: str) -> dict[str, Any]:
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        if not parsed.netloc or not parsed.path:
            raise ValueError(f"expected s3 URI with bucket/key, got {uri!r}")
        s3 = make_session(cfg).client("s3", config=AWS_CLIENT_CONFIG)
        obj = s3.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
        body = obj["Body"].read().decode("utf-8")
    elif parsed.scheme in {"", "file"}:
        path = parsed.path if parsed.scheme == "file" else uri
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
    else:
        raise ValueError(f"unsupported JSON URI scheme for {uri!r}")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object at {uri!r}")
    return data


def _expected_adversarial_matrix(*, profile: WorkloadProfile) -> dict[str, int]:
    return {
        f"{cue_type}:{adversarial_class}": count
        for cue_type, adversarial_class, count in profile.adversarial_distribution
    }


def _coerce_matrix(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    try:
        return {str(key): int(count) for key, count in value.items()}
    except (TypeError, ValueError):
        return None


def _default_generation_binding(
    *,
    source: str,
    profile: WorkloadProfile,
    source_uri: str | None = None,
) -> dict[str, Any]:
    return {
        "binding_id": GENERATION_BINDING_ID,
        "active": True,
        "path": "im_w.generate_cue_details",
        "context": "runtime_calibration",
        "profile": profile.name,
        "authority": "execution_evidence_from_prior_run"
        if source == "prior_summary"
        else "spec_default",
        "source": source,
        "source_uri": source_uri,
        "effect": "fail_generation_if_adversarial_matrix_absent_or_mismatched",
        "expected_adversarial_distribution": _expected_adversarial_matrix(
            profile=profile
        ),
        "forbidden_adversarial_distributions": [],
    }


def _merge_forbidden_pattern(
    binding: dict[str, Any],
    *,
    source_matrix: dict[str, int],
) -> None:
    forbidden = binding.get("forbidden_adversarial_distributions")
    forbidden_matrices = [
        matrix
        for item in forbidden
        if (matrix := _coerce_matrix(item)) is not None
    ] if isinstance(forbidden, list) else []
    if source_matrix not in forbidden_matrices:
        forbidden_matrices.append(source_matrix)
    binding["forbidden_adversarial_distributions"] = forbidden_matrices
    binding["authority"] = "failure_direct_prior_run"


def _apply_prior_generation_consequence(
    binding: dict[str, Any],
    prior_summary: dict[str, Any],
    *,
    profile: WorkloadProfile,
) -> dict[str, Any]:
    generation = prior_summary.get("generation")
    if not isinstance(generation, dict):
        return binding

    source_matrix = _coerce_matrix(generation.get("adversarial_distribution"))
    prior_profile = prior_summary.get("workload_profile")
    prior_profile_name = (
        prior_profile.get("name")
        if isinstance(prior_profile, dict)
        else FULL_PROFILE.name
    )
    binding["source_run_id"] = prior_summary.get("run_id")
    binding["source_profile"] = prior_profile_name
    binding["source_generation_pass"] = generation.get("pass")
    binding["source_adversarial_distribution"] = source_matrix
    if (
        source_matrix
        and prior_profile_name == profile.name
        and source_matrix != _expected_adversarial_matrix(profile=profile)
    ):
        _merge_forbidden_pattern(binding, source_matrix=source_matrix)
    return binding


def _derive_generation_binding_from_summary(
    prior_summary: dict[str, Any],
    *,
    profile: WorkloadProfile,
    source_uri: str,
) -> dict[str, Any]:
    binding = _default_generation_binding(
        source="prior_summary", profile=profile, source_uri=source_uri
    )
    return _apply_prior_generation_consequence(
        binding, prior_summary, profile=profile
    )


def load_generation_binding(*, cfg: Any, profile: WorkloadProfile | None = None) -> dict[str, Any]:
    """Load the one current im_w consequence binding before cue generation."""

    selected_profile = profile or load_workload_profile()
    prior_summary_uri = os.environ.get("IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI")
    if not prior_summary_uri:
        return _default_generation_binding(source="built_in", profile=selected_profile)

    prior_summary = _read_json_uri(cfg=cfg, uri=prior_summary_uri)
    explicit = prior_summary.get("generation_binding")
    if isinstance(explicit, dict):
        binding = dict(explicit)
        binding.setdefault("binding_id", GENERATION_BINDING_ID)
        binding.setdefault("active", True)
        binding.setdefault("path", "im_w.generate_cue_details")
        binding.setdefault("context", "runtime_calibration")
        binding["profile"] = selected_profile.name
        binding.setdefault("authority", "execution_evidence_from_prior_run")
        binding.setdefault(
            "effect", "fail_generation_if_adversarial_matrix_absent_or_mismatched"
        )
        binding["expected_adversarial_distribution"] = _expected_adversarial_matrix(
            profile=selected_profile
        )
        binding.setdefault("forbidden_adversarial_distributions", [])
        binding["source"] = "prior_summary"
        binding["source_uri"] = prior_summary_uri
        return _apply_prior_generation_consequence(
            binding, prior_summary, profile=selected_profile
        )
    return _derive_generation_binding_from_summary(
        prior_summary, profile=selected_profile, source_uri=prior_summary_uri
    )


def _coerce_dominant_axis_distribution(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    try:
        coerced = {str(key): int(count) for key, count in value.items()}
    except (TypeError, ValueError):
        return None
    if not coerced:
        return None
    return coerced


def _default_dominant_axis_binding(
    *,
    source: str,
    profile: WorkloadProfile,
    source_uri: str | None = None,
) -> dict[str, Any]:
    return {
        "binding_id": DOMINANT_AXIS_BINDING_ID,
        "active": True,
        "path": "im_w.validate_epistemic_surface",
        "context": "runtime_calibration",
        "profile": profile.name,
        "authority": "execution_evidence_from_prior_run"
        if source == "prior_summary"
        else "spec_default",
        "source": source,
        "source_uri": source_uri,
        "effect": "fail_epistemic_validation_if_dominant_axis_distribution_matches_forbidden_pattern",
        "forbidden_dominant_axis_distributions": [],
    }


def _merge_forbidden_dominant_axis_pattern(
    binding: dict[str, Any],
    *,
    source_distribution: dict[str, int],
) -> None:
    forbidden = binding.get("forbidden_dominant_axis_distributions")
    forbidden_distributions = [
        distribution
        for item in forbidden
        if (distribution := _coerce_dominant_axis_distribution(item)) is not None
    ] if isinstance(forbidden, list) else []
    if source_distribution not in forbidden_distributions:
        forbidden_distributions.append(source_distribution)
    binding["forbidden_dominant_axis_distributions"] = forbidden_distributions
    binding["authority"] = "failure_direct_prior_run"


def _apply_prior_epistemic_consequence(
    binding: dict[str, Any],
    prior_summary: dict[str, Any],
    *,
    profile: WorkloadProfile,
) -> dict[str, Any]:
    epistemic = prior_summary.get("epistemic_surface")
    if not isinstance(epistemic, dict):
        return binding

    source_distribution = _coerce_dominant_axis_distribution(
        epistemic.get("dominant_axis_distribution")
    )
    prior_profile = prior_summary.get("workload_profile")
    prior_profile_name = (
        prior_profile.get("name")
        if isinstance(prior_profile, dict)
        else FULL_PROFILE.name
    )
    binding["source_run_id"] = prior_summary.get("run_id")
    binding["source_profile"] = prior_profile_name
    binding["source_pass"] = prior_summary.get("pass")
    binding["source_failure_stage"] = prior_summary.get("failure_stage")
    binding["source_dominant_axis_distribution"] = source_distribution
    prior_failed = (
        prior_summary.get("pass") is False
        or prior_summary.get("failure_stage") is not None
    )
    if (
        source_distribution
        and prior_profile_name == profile.name
        and prior_failed
    ):
        _merge_forbidden_dominant_axis_pattern(
            binding, source_distribution=source_distribution
        )
    return binding


def _derive_dominant_axis_binding_from_summary(
    prior_summary: dict[str, Any],
    *,
    profile: WorkloadProfile,
    source_uri: str,
) -> dict[str, Any]:
    binding = _default_dominant_axis_binding(
        source="prior_summary", profile=profile, source_uri=source_uri
    )
    return _apply_prior_epistemic_consequence(
        binding, prior_summary, profile=profile
    )


def load_dominant_axis_binding(
    *, cfg: Any, profile: WorkloadProfile | None = None
) -> dict[str, Any]:
    """Load the second im_w consequence binding before live loop validation."""

    selected_profile = profile or load_workload_profile()
    prior_summary_uri = os.environ.get("IMPLICIT_CALIBRATION_PRIOR_SUMMARY_URI")
    if not prior_summary_uri:
        return _default_dominant_axis_binding(
            source="built_in", profile=selected_profile
        )

    prior_summary = _read_json_uri(cfg=cfg, uri=prior_summary_uri)
    explicit = prior_summary.get("dominant_axis_binding")
    if isinstance(explicit, dict):
        binding = dict(explicit)
        binding.setdefault("binding_id", DOMINANT_AXIS_BINDING_ID)
        binding.setdefault("active", True)
        binding.setdefault("path", "im_w.validate_epistemic_surface")
        binding.setdefault("context", "runtime_calibration")
        binding["profile"] = selected_profile.name
        binding.setdefault("authority", "execution_evidence_from_prior_run")
        binding.setdefault(
            "effect",
            "fail_epistemic_validation_if_dominant_axis_distribution_matches_forbidden_pattern",
        )
        binding.setdefault("forbidden_dominant_axis_distributions", [])
        binding["source"] = "prior_summary"
        binding["source_uri"] = prior_summary_uri
        return _apply_prior_epistemic_consequence(
            binding, prior_summary, profile=selected_profile
        )
    return _derive_dominant_axis_binding_from_summary(
        prior_summary, profile=selected_profile, source_uri=prior_summary_uri
    )


def _validate_epistemic_surface(
    epistemic_surface: dict[str, Any],
    *,
    dominant_axis_binding: dict[str, Any],
) -> dict[str, Any]:
    binding_active = bool(dominant_axis_binding.get("active", True))
    forbidden_patterns = dominant_axis_binding.get(
        "forbidden_dominant_axis_distributions"
    )
    forbidden_distributions = [
        distribution
        for item in forbidden_patterns
        if (distribution := _coerce_dominant_axis_distribution(item)) is not None
    ] if isinstance(forbidden_patterns, list) else []
    current_distribution = _coerce_dominant_axis_distribution(
        epistemic_surface.get("dominant_axis_distribution")
    ) or {}
    forbidden_match = any(
        current_distribution == distribution
        for distribution in forbidden_distributions
    )
    binding_pass = (not binding_active) or (not forbidden_match)
    return {
        "pass": binding_pass,
        "binding_pass": binding_pass,
        "binding_applied": binding_active,
        "binding_id": dominant_axis_binding.get("binding_id", DOMINANT_AXIS_BINDING_ID),
        "binding_authority": dominant_axis_binding.get("authority"),
        "forbidden_pattern_count": len(forbidden_distributions),
        "forbidden_pattern_matched": forbidden_match,
        "current_dominant_axis_distribution": dict(sorted(current_distribution.items())),
    }


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


def _validate_generation(
    unique: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    *,
    generation_binding: dict[str, Any],
    profile: WorkloadProfile,
) -> dict[str, Any]:
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
    for cue_type, adversarial_class, count in profile.adversarial_distribution:
        expected_by_cue_type[cue_type] += count
    duplicate_reuse = all(dup["cue_id"] == unique[i]["cue_id"] for i, dup in enumerate(duplicates))
    binding_active = bool(generation_binding.get("active", True))
    binding_expected = generation_binding.get("expected_adversarial_distribution")
    binding_expected_matrix = _coerce_matrix(binding_expected) or _expected_adversarial_matrix(
        profile=profile
    )
    forbidden_patterns = generation_binding.get("forbidden_adversarial_distributions")
    forbidden_matrices = [
        matrix
        for item in forbidden_patterns
        if (matrix := _coerce_matrix(item)) is not None
    ] if isinstance(forbidden_patterns, list) else []
    actual_matrix = {
        f"{cue_type}:{adversarial_class}": count
        for (cue_type, adversarial_class), count in sorted(adversarial_matrix.items())
    }
    forbidden_match = any(actual_matrix == matrix for matrix in forbidden_matrices)
    binding_pass = (
        (not binding_active)
        or (actual_matrix == binding_expected_matrix and not forbidden_match)
    )
    base_pass = (
        len(unique) == profile.unique_cues
        and len({d["cue_id"] for d in unique}) == profile.unique_cues
        and dict(cue_type_counts) == profile.workload_counts
        and sum(adversarial_counts.values()) == sum(profile.adversarial_counts.values())
        and dict(adversarial_counts) == profile.adversarial_counts
        and adversarial_by_cue_type == expected_by_cue_type
        and len(duplicates) == profile.duplicate_submissions
        and duplicate_reuse
    )
    return {
        "pass": base_pass and binding_pass,
        "base_pass": base_pass,
        "binding_pass": binding_pass,
        "binding_applied": binding_active,
        "binding_id": generation_binding.get("binding_id", GENERATION_BINDING_ID),
        "binding_authority": generation_binding.get("authority"),
        "forbidden_pattern_count": len(forbidden_matrices),
        "forbidden_pattern_matched": forbidden_match,
        "unique_count": len(unique),
        "unique_cue_ids": len({d["cue_id"] for d in unique}),
        "cue_type_counts": dict(cue_type_counts),
        "adversarial_counts": dict(adversarial_counts),
        "adversarial_cue_type_counts": dict(adversarial_by_cue_type),
        "adversarial_distribution": actual_matrix,
        "expected_adversarial_distribution": dict(sorted(binding_expected_matrix.items())),
        "duplicate_submissions": len(duplicates),
        "duplicates_reuse_cue_id": duplicate_reuse,
    }


def _consequence_binding_summary(
    *,
    generation_binding: dict[str, Any],
    generation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "binding_id": generation_binding.get("binding_id", GENERATION_BINDING_ID),
        "path": generation_binding.get("path"),
        "profile": generation_binding.get("profile"),
        "source": generation_binding.get("source"),
        "source_uri": generation_binding.get("source_uri"),
        "source_run_id": generation_binding.get("source_run_id"),
        "source_profile": generation_binding.get("source_profile"),
        "authority": generation_binding.get("authority"),
        "applied": generation.get("binding_applied"),
        "passed": generation.get("binding_pass"),
        "forbidden_pattern_count": generation.get("forbidden_pattern_count"),
        "forbidden_pattern_matched": generation.get("forbidden_pattern_matched"),
        "effect": generation_binding.get("effect"),
    }


def _epistemic_binding_summary(
    *,
    dominant_axis_binding: dict[str, Any],
    epistemic_validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "binding_id": dominant_axis_binding.get(
            "binding_id", DOMINANT_AXIS_BINDING_ID
        ),
        "path": dominant_axis_binding.get("path"),
        "profile": dominant_axis_binding.get("profile"),
        "source": dominant_axis_binding.get("source"),
        "source_uri": dominant_axis_binding.get("source_uri"),
        "source_run_id": dominant_axis_binding.get("source_run_id"),
        "source_profile": dominant_axis_binding.get("source_profile"),
        "source_pass": dominant_axis_binding.get("source_pass"),
        "source_failure_stage": dominant_axis_binding.get("source_failure_stage"),
        "authority": dominant_axis_binding.get("authority"),
        "applied": epistemic_validation.get("binding_applied"),
        "passed": epistemic_validation.get("binding_pass"),
        "forbidden_pattern_count": epistemic_validation.get("forbidden_pattern_count"),
        "forbidden_pattern_matched": epistemic_validation.get(
            "forbidden_pattern_matched"
        ),
        "effect": dominant_axis_binding.get("effect"),
    }


def _workload_profile_summary(profile: WorkloadProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "purpose": profile.purpose,
        "unique_cues": profile.unique_cues,
        "duplicate_submissions": profile.duplicate_submissions,
    }


def _target_counts(profile: WorkloadProfile) -> dict[str, Any]:
    return {
        "unique_cues": profile.unique_cues,
        "duplicate_submissions": profile.duplicate_submissions,
        "cue_type_counts": profile.workload_counts,
        "adversarial_counts": profile.adversarial_counts,
        "adversarial_distribution": [
            {
                "cue_type": cue_type,
                "adversarial_class": adversarial_class,
                "count": count,
            }
            for cue_type, adversarial_class, count in profile.adversarial_distribution
        ],
    }


def run() -> dict:
    run_id = _run_id()
    stream_id = f"{STREAM_PREFIX}-{run_id}"
    profile = load_workload_profile()
    phase_started = time.monotonic()
    phase_elapsed: dict[str, float] = {}
    failure_stage: str | None = None
    _progress(
        f"starting run_id={run_id} stream_id={stream_id} profile={profile.name}"
    )

    def mark(stage: str, started: float) -> None:
        phase_elapsed[stage] = round(time.monotonic() - started, 3)
        _progress(f"{stage} completed in {phase_elapsed[stage]}s")

    def write_summary_artifact(run_summary: dict[str, Any]) -> str:
        started = time.monotonic()
        _progress("writing S3 run summary artifact")
        try:
            artifact_uri = write_artifact(
                name="im-w-runtime-calibration-summary", payload=run_summary
            )
            mark("artifact_write", started)
            run_summary["artifact"] = artifact_uri
            run_summary["phase_elapsed_seconds"] = phase_elapsed
            _rewrite_artifact_payload(
                cfg=cfg, artifact_uri=artifact_uri, payload=run_summary
            )
            _progress(f"run summary artifact={artifact_uri}")
            return artifact_uri
        except Exception as exc:
            print(
                f"[im-w] failed to write run summary artifact: {exc}",
                file=sys.stderr,
                flush=True,
            )
            raise

    _progress("loading config and AWS clients")
    cfg = load_config()
    session = make_session(cfg)
    sqs = session.client("sqs", config=AWS_CLIENT_CONFIG)
    events = session.client("events", config=AWS_CLIENT_CONFIG)

    generation_binding = load_generation_binding(cfg=cfg, profile=profile)
    _progress(
        "loaded generation binding "
        f"{generation_binding.get('binding_id', GENERATION_BINDING_ID)} "
        f"from {generation_binding.get('source')}"
    )

    dominant_axis_binding = load_dominant_axis_binding(cfg=cfg, profile=profile)
    _progress(
        "loaded dominant axis binding "
        f"{dominant_axis_binding.get('binding_id', DOMINANT_AXIS_BINDING_ID)} "
        f"from {dominant_axis_binding.get('source')}"
    )

    unique, duplicates = generate_cue_details(
        run_id=run_id, stream_id=stream_id, profile=profile
    )
    generation = _validate_generation(
        unique, duplicates, generation_binding=generation_binding, profile=profile
    )
    if not generation["pass"]:
        failure_stage = "generation"
        run_summary = {
            "pass": False,
            "run_id": run_id,
            "agent_id": AGENT_ID,
            "stream_id": stream_id,
            "workload_profile": _workload_profile_summary(profile),
            "target_counts": _target_counts(profile),
            "actual_submitted_counts": {
                "unique": len(unique),
                "duplicates": len(duplicates),
                "eventbridge": None,
            },
            "generation": generation,
            "generation_binding": generation_binding,
            "consequence_binding_summary": _consequence_binding_summary(
                generation_binding=generation_binding,
                generation=generation,
            ),
            "dominant_axis_binding": dominant_axis_binding,
            "epistemic_validation": None,
            "epistemic_binding_summary": None,
            "cue_payload_fixture_shape": cue_payload_fixture_shape(unique),
            "fixture_disclosures": fixture_disclosures(profile=profile),
            "phase_elapsed_seconds": phase_elapsed,
            "failure_stage": failure_stage,
            "control_plane_outcomes": None,
            "loop_decisions": None,
            "loop_stats": None,
            "replay_loop_stats": None,
            "epistemic_surface": None,
            "replay": None,
            "time_context": None,
        }
        write_summary_artifact(run_summary)
        raise AssertionError(f"runtime calibration generation check failed: {generation}")
    _progress("generation check passed")

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

        epistemic_surface = _axis_metrics(live_loop_lineage.events, cfg)
        epistemic_validation = _validate_epistemic_surface(
            epistemic_surface, dominant_axis_binding=dominant_axis_binding
        )

        run_summary = {
            "pass": replay_equivalent and epistemic_validation["pass"],
            "run_id": run_id,
            "agent_id": AGENT_ID,
            "stream_id": stream_id,
            "workload_profile": _workload_profile_summary(profile),
            "target_counts": _target_counts(profile),
            "actual_submitted_counts": {
                "unique": len(unique),
                "duplicates": len(duplicates),
                "eventbridge": produce,
            },
            "generation": generation,
            "generation_binding": generation_binding,
            "consequence_binding_summary": _consequence_binding_summary(
                generation_binding=generation_binding,
                generation=generation,
            ),
            "dominant_axis_binding": dominant_axis_binding,
            "epistemic_validation": epistemic_validation,
            "epistemic_binding_summary": _epistemic_binding_summary(
                dominant_axis_binding=dominant_axis_binding,
                epistemic_validation=epistemic_validation,
            ),
            "cue_payload_fixture_shape": cue_payload_fixture_shape(unique),
            "fixture_disclosures": fixture_disclosures(profile=profile),
            "phase_elapsed_seconds": phase_elapsed,
            "failure_stage": failure_stage,
            "control_plane_outcomes": drain,
            "loop_decisions": _loop_decision_metrics(live_loop_lineage.events),
            "loop_stats": loop_stats,
            "replay_loop_stats": replay_stats,
            "epistemic_surface": epistemic_surface,
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

        if not epistemic_validation["pass"]:
            failure_stage = failure_stage or "epistemic_surface"
            run_summary["pass"] = False
            run_summary["failure_stage"] = failure_stage
            write_summary_artifact(run_summary)
            raise AssertionError(
                f"runtime calibration epistemic check failed: {epistemic_validation}"
            )

        artifact_uri = write_summary_artifact(run_summary)

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
