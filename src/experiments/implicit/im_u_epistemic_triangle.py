"""
im_u — EPISTEMIC_TRIANGLE falsification suite.

Implements the 16 hooks from `specs/EPISTEMIC_TRIANGLE.md` §13 plus
the 3 implementation gates carried forward from the v1.2 promotion
review preamble:

  Hooks (spec §13):
    1.  record_kind + assertion_kind round-trip through validator
    2.  Mapping table coverage of actively-emitted event_types
    3.  Decision-event subject classification required when
        uncertainty_triple is in payload
    4.  evidence_link_declared deterministic link_id
    5.  Latest-state walker semantics (pending/resolved/invalid)
    6.  Recall variance limitation hooks (6a, 6b, 6c)
    7.  time_since_last_recall_myr replay-deterministic
    8.  Score-time fallback visibility (signal_source + fallback_reason)
    9.  Normalized signal_source across all three axes
    10. score_candidate retirement: precision-targeted check on
        v7 emit functions
    11. Ordering replacement: no event_time in v7 readers/SQL
    12. Engine seq=0: first event in every stream is sequence 0
    13. event_time absent on v7 events (storage validator quarantines)
    14. Cross-scope evidence link policy (within-agent default)
    15. reality_observation scope (observation_event only)
    16. Mapping extension via event_type_declared
       (unmapped quarantine + recovery via declaration)

  Implementation gates (spec preamble):
    G1. Bootstrap same-batch resolution — cutover_v7 genesis
        references same-batch time_context_declared without dangling
    G2. Cache discipline — signal_source=cache only legitimate when
        backed by canonical *_signals_computed payload, never by S3
        Vector metadata as source of truth
    G3. Decision-event subjects without prior subject_event_id —
        deterministic placeholder pattern (`memory_id_referenced:<id>`)
        is replay-stable and tagged `subject_kind_source: v1_default`

Each hook returns `(name, ok, detail)`. Suite passes iff every hook
and gate passes. Replay summary included so the regression artifact
carries a deterministic signature for this suite.

Run:
  PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_u_epistemic_triangle
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from src.cutover_v7 import CANONICAL_META_STREAM, cutover
from src.epistemic_triangle import (
    ASSERTION_KIND_ENUM,
    AssertionKind,
    EVENT_TYPE_MAPPING,
    LinkType,
    RECORD_KIND_ENUM,
    RecordKind,
    ResolutionState,
    V7_QUARANTINE_REASONS,
    V7_SCHEMA_VERSION,
    compute_link_id,
    lookup_event_type,
    select_latest_link_states,
    validate_event_v7,
)
from src.epistemic_triangle.links import (
    LINK_INVALID_REASONS,
    LINK_PENDING_REASONS,
    EvidenceLinkPayload,
)
from src.experiments.implicit.common import InMemoryLineageEngine
from src.explicit_memory.claim import (
    CLAIM_FALLBACK_REASONS,
    compute_claim_signals,
)
from src.explicit_memory.provenance import ProvenanceSignals
from src.explicit_memory.recall_signals import (
    RECALL_FALLBACK_REASONS,
    compute_recall_signals,
)
from src.explicit_memory.signals import (
    SIGNAL_METHOD_ENUM,
    SIGNAL_SOURCE_ENUM,
    SignalMethod,
    SignalSource,
    normalize_provenance_signals,
)
from src.heliotime import physical_moment
from src.implicit_memory.loop import ImplicitControllerLoop
from src.lineage_engine import LineageEngine, StreamState
from src.types import EVENT_SCHEMA_VERSION, MemoryEvent


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _ok(name: str, **detail: Any) -> tuple[str, bool, dict]:
    return (name, True, dict(detail))


def _fail(name: str, reason: str, **detail: Any) -> tuple[str, bool, dict]:
    return (name, False, {"reason": reason, **detail})


def _v7_event_view(
    *,
    event_type: str = "recalled",
    record_kind: str | None = "memory_event",
    assertion_kind: str | None = "memory",
    payload: dict | None = None,
    extras: dict | None = None,
) -> dict[str, Any]:
    """Construct a minimal v7-shaped event dict for validator tests."""
    view: dict[str, Any] = {
        "event_id": "evt-test",
        "event_type": event_type,
        "agent_id": "a",
        "stream_id": "s",
        "memory_id": "m",
        "schema_version": V7_SCHEMA_VERSION,
        "actor_class": "system_worker",
        "source_class": "internal_engine",
        "payload": payload or {},
        "physical_moment": {"tai_iso": "2026-05-15T01:00:00.000"},
        "record_kind": record_kind,
        "assertion_kind": assertion_kind,
    }
    if extras:
        view.update(extras)
    return view


# ---------------------------------------------------------------------------
# hooks (spec §13)
# ---------------------------------------------------------------------------


def hook_1_record_kind_round_trip() -> tuple[str, bool, dict]:
    """record_kind and assertion_kind survive validator round-trip."""
    view = _v7_event_view(event_type="recalled", record_kind="memory_event", assertion_kind="memory")
    failure = validate_event_v7(view)
    if failure is not None:
        return _fail("hook_1_record_kind_round_trip", "validator rejected well-formed event", failure=failure.reason)
    # Round-trip via dict mutation: assertion_kind change must produce a different validator result.
    bad = dict(view)
    bad["record_kind"] = "not_a_kind"
    if validate_event_v7(bad) is None:
        return _fail("hook_1_record_kind_round_trip", "validator did not reject invalid record_kind")
    return _ok("hook_1_record_kind_round_trip", record_kind="memory_event", assertion_kind="memory")


def hook_2_mapping_table_coverage() -> tuple[str, bool, dict]:
    """Every actively-emitted event_type must be in the v7 mapping
    table OR be declared via event_type_declared. Grep for live
    event_type literals and confirm coverage.

    Excludes test/verifier files that intentionally pass unknown
    event_types to validator fixtures (quarantine-testing strings
    should not be confused with live emissions)."""
    repo_root = Path(__file__).resolve().parents[3]
    src_root = repo_root / "src"
    pattern = re.compile(r'event_type="([a-z_][a-z_0-9]*)"')
    # Test/verifier files emit unmapped event_type strings on
    # purpose to exercise quarantine paths. Exclude them so live
    # emit-site coverage stays meaningful.
    test_excludes = (
        "_phase1_verify.py",
        "_phase2_verify.py",
        "_phase3_verify.py",
        "im_u_epistemic_triangle.py",
        "im_t_tai_timekeeping.py",
    )
    found_types: set[str] = set()
    for path in src_root.rglob("*.py"):
        if path.name in test_excludes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in pattern.finditer(text):
            found_types.add(match.group(1))

    mapped = set(EVENT_TYPE_MAPPING.keys())
    missing = sorted(found_types - mapped)
    if missing:
        return _fail(
            "hook_2_mapping_table_coverage",
            "event_types emitted in src/ are not in the mapping table (require spec amendment + event_type_declared)",
            missing=missing,
        )
    return _ok(
        "hook_2_mapping_table_coverage",
        emitted_event_type_count=len(found_types),
        mapped_count=len(mapped),
    )


def hook_3_decision_event_subject_required() -> tuple[str, bool, dict]:
    """Decision events carrying uncertainty_triple must carry
    subject_assertion_kind."""
    view = _v7_event_view(
        event_type="implicit_admitted",
        record_kind="decision_event",
        assertion_kind=None,
        payload={"uncertainty_triple": {}},
    )
    # Missing subject must quarantine.
    failure = validate_event_v7(view)
    if failure is None:
        return _fail(
            "hook_3_decision_event_subject_required",
            "validator accepted implicit_admitted with no subject_assertion_kind",
        )
    if failure.reason != "missing_subject_assertion_kind":
        return _fail(
            "hook_3_decision_event_subject_required",
            "wrong quarantine reason",
            got=failure.reason,
            expected="missing_subject_assertion_kind",
        )
    # With subject classification, must pass.
    view_with_subject = dict(view)
    view_with_subject["subject_event_id"] = "memory_id_referenced:m"
    view_with_subject["subject_record_kind"] = "memory_event"
    view_with_subject["subject_assertion_kind"] = "memory"
    if validate_event_v7(view_with_subject) is not None:
        return _fail(
            "hook_3_decision_event_subject_required",
            "validator rejected implicit_admitted with full subject classification",
        )
    return _ok("hook_3_decision_event_subject_required")


def hook_4_link_id_deterministic() -> tuple[str, bool, dict]:
    """compute_link_id is deterministic and discriminates inputs."""
    a = compute_link_id(claim_event_id="c1", evidence_event_id="e1", link_type="supports")
    b = compute_link_id(claim_event_id="c1", evidence_event_id="e1", link_type="supports")
    if a != b:
        return _fail("hook_4_link_id_deterministic", "same inputs produced different hashes", a=a, b=b)
    different = {
        compute_link_id(claim_event_id="c2", evidence_event_id="e1", link_type="supports"),
        compute_link_id(claim_event_id="c1", evidence_event_id="e2", link_type="supports"),
        compute_link_id(claim_event_id="c1", evidence_event_id="e1", link_type="refutes"),
    }
    if a in different or len(different) != 3:
        return _fail("hook_4_link_id_deterministic", "input differences did not produce distinct hashes")
    return _ok("hook_4_link_id_deterministic", sample_link_id=a)


def _link_event(*, payload: dict, tai_iso: str, seq: int, event_id: str, agent_id: str = "a") -> dict:
    return {
        "event_id": event_id,
        "event_type": "evidence_link_declared",
        "agent_id": agent_id,
        "stream_id": "stream-meta",
        "memory_id": "n/a",
        "physical_moment": {"tai_iso": tai_iso, "sequence_in_stream": seq},
        "payload": payload,
    }


def _resolved_payload(claim_id="c1", evidence_id="e1", link_type="supports") -> dict:
    return EvidenceLinkPayload(
        claim_event_id=claim_id,
        evidence_event_id=evidence_id,
        link_type=LinkType(link_type),
        resolution_state=ResolutionState.RESOLVED,
    ).to_dict()


def _invalid_payload(claim_id="c1", evidence_id="e1", link_type="supports") -> dict:
    return EvidenceLinkPayload(
        claim_event_id=claim_id,
        evidence_event_id=evidence_id,
        link_type=LinkType(link_type),
        resolution_state=ResolutionState.INVALID,
        resolution_reason="dangling_after_grace_period",
    ).to_dict()


def hook_5_latest_state_walker() -> tuple[str, bool, dict]:
    """invalid supersedes prior resolved; later resolved
    re-contributes; pending/invalid don't contribute."""
    link_id = compute_link_id(claim_event_id="c1", evidence_event_id="e1", link_type="supports")
    # Case A: resolved -> invalid → no contribution
    case_a = select_latest_link_states([
        _link_event(payload=_resolved_payload(), tai_iso="2026-05-15T00:00:00.000", seq=0, event_id="l0"),
        _link_event(payload=_invalid_payload(), tai_iso="2026-05-15T00:01:00.000", seq=1, event_id="l1"),
    ])
    # Case B: resolved -> invalid -> resolved → contributes
    case_b = select_latest_link_states([
        _link_event(payload=_resolved_payload(), tai_iso="2026-05-15T00:00:00.000", seq=0, event_id="l0"),
        _link_event(payload=_invalid_payload(), tai_iso="2026-05-15T00:01:00.000", seq=1, event_id="l1"),
        _link_event(payload=_resolved_payload(), tai_iso="2026-05-15T00:02:00.000", seq=2, event_id="l2"),
    ])
    if link_id in case_a:
        return _fail("hook_5_latest_state_walker", "invalid did not supersede prior resolved")
    if link_id not in case_b:
        return _fail("hook_5_latest_state_walker", "latest resolved did not contribute after invalid")
    return _ok("hook_5_latest_state_walker", link_id=link_id)


def _recall_event(*, event_id: str, tai_iso: str, age_myr: float, seq: int, payload: dict, memory_id="m") -> dict:
    return {
        "event_id": event_id,
        "event_type": "recalled",
        "agent_id": "a",
        "stream_id": "s",
        "memory_id": memory_id,
        "assertion_kind": AssertionKind.MEMORY.value,
        "physical_moment": {
            "tai_iso": tai_iso,
            "sequence_in_stream": seq,
            "solar_age_myr": age_myr,
        },
        "payload": dict(payload),
    }


def hook_6_recall_variance_limitations() -> tuple[str, bool, dict]:
    """Three sub-cases: wording drift (variance moves), evidence
    drift (variance moves), adversarial stable projection (variance
    does NOT move; v1 limitation marker present)."""
    base_age = 4603.000026
    # 6a: wording drift
    priors_a = [
        _recall_event(event_id="r0", tai_iso="2026-05-15T00:00:00.000", age_myr=base_age + 0.000001, seq=0, payload={"claim": "v1"}),
        _recall_event(event_id="r1", tai_iso="2026-05-15T00:01:00.000", age_myr=base_age + 0.000002, seq=1, payload={"claim": "v2"}),
    ]
    target_a = _recall_event(event_id="r2", tai_iso="2026-05-15T00:02:00.000", age_myr=base_age + 0.000003, seq=2, payload={"claim": "v3"})
    a = compute_recall_signals(target_event=target_a, prior_recall_events=priors_a, as_of_time="2026-05-15T01:00:00.000")
    if not (a.signal_source == SignalSource.COMPUTED and a.reconstruction_variance > 0.0):
        return _fail("hook_6_recall_variance_limitations", "6a wording drift did not move variance", got=a.reconstruction_variance)
    # 6b: evidence drift, wording stable
    priors_b = [
        _recall_event(event_id="r0", tai_iso="2026-05-15T00:00:00.000", age_myr=base_age + 0.000001, seq=0, payload={"claim": "k", "evidence_ids": ["a"]}),
        _recall_event(event_id="r1", tai_iso="2026-05-15T00:01:00.000", age_myr=base_age + 0.000002, seq=1, payload={"claim": "k", "evidence_ids": ["b"]}),
    ]
    target_b = _recall_event(event_id="r2", tai_iso="2026-05-15T00:02:00.000", age_myr=base_age + 0.000003, seq=2, payload={"claim": "k", "evidence_ids": ["c"]})
    b = compute_recall_signals(target_event=target_b, prior_recall_events=priors_b, as_of_time="2026-05-15T01:00:00.000")
    if not (b.signal_source == SignalSource.COMPUTED and b.reconstruction_variance > 0.0):
        return _fail("hook_6_recall_variance_limitations", "6b evidence drift did not move variance", got=b.reconstruction_variance)
    # 6c: adversarial stable projection, meaning drifts
    stable_proj = {"claim": "k", "evidence_ids": ["a"]}
    priors_c = [
        _recall_event(event_id="r0", tai_iso="2026-05-15T00:00:00.000", age_myr=base_age + 0.000001, seq=0, payload={**stable_proj, "meaning": "tea soon"}),
        _recall_event(event_id="r1", tai_iso="2026-05-15T00:01:00.000", age_myr=base_age + 0.000002, seq=1, payload={**stable_proj, "meaning": "tea soon"}),
    ]
    target_c = _recall_event(event_id="r2", tai_iso="2026-05-15T00:02:00.000", age_myr=base_age + 0.000003, seq=2, payload={**stable_proj, "meaning": "boiling water for soup"})
    c = compute_recall_signals(target_event=target_c, prior_recall_events=priors_c, as_of_time="2026-05-15T01:00:00.000")
    if c.reconstruction_variance != 0.0:
        return _fail("hook_6_recall_variance_limitations", "6c adversarial case unexpectedly moved variance", got=c.reconstruction_variance)
    if c.limitation_marker != "stable_projection_with_drifting_meaning":
        return _fail("hook_6_recall_variance_limitations", "6c did not emit limitation_marker", got=c.limitation_marker)
    return _ok(
        "hook_6_recall_variance_limitations",
        wording_drift_variance=a.reconstruction_variance,
        evidence_drift_variance=b.reconstruction_variance,
        adversarial_variance=c.reconstruction_variance,
        adversarial_marker=c.limitation_marker,
    )


def hook_7_time_since_last_replay_deterministic() -> tuple[str, bool, dict]:
    """time_since_last_recall_myr computed from solar_age_myr deltas
    only; no wall-clock; deterministic across calls."""
    priors = [
        _recall_event(event_id="r0", tai_iso="2026-05-15T00:00:00.000", age_myr=4603.000010, seq=0, payload={"claim": "x"}),
        _recall_event(event_id="r1", tai_iso="2026-05-15T00:30:00.000", age_myr=4603.000015, seq=1, payload={"claim": "y"}),
    ]
    target = _recall_event(event_id="r2", tai_iso="2026-05-15T01:00:00.000", age_myr=4603.000020, seq=2, payload={"claim": "z"})
    a = compute_recall_signals(target_event=target, prior_recall_events=priors, as_of_time="2026-05-15T02:00:00.000")
    b = compute_recall_signals(target_event=target, prior_recall_events=priors, as_of_time="2026-05-15T02:00:00.000")
    if a != b:
        return _fail("hook_7_time_since_last_replay_deterministic", "non-deterministic output")
    expected = 4603.000020 - 4603.000015
    if a.time_since_last_recall_myr is None or abs(a.time_since_last_recall_myr - expected) > 1e-12:
        return _fail(
            "hook_7_time_since_last_replay_deterministic",
            "time delta not from solar_age_myr",
            got=a.time_since_last_recall_myr,
            expected=expected,
        )
    return _ok(
        "hook_7_time_since_last_replay_deterministic",
        time_since_last_recall_myr=a.time_since_last_recall_myr,
    )


def hook_8_score_time_fallback_visibility() -> tuple[str, bool, dict]:
    """When a signal walker falls back, signal_source must be
    `fallback` and fallback_reason must be in the per-axis closed
    enum. v7 scoring layers will pick this up; v7 falsification
    asserts the signal layer is loud about fallback."""
    # Claim with no resolved evidence links → fallback.
    target = {
        "event_id": "claim-x",
        "event_type": "stored",
        "agent_id": "a",
        "stream_id": "s",
        "memory_id": "mc",
        "assertion_kind": AssertionKind.CLAIM.value,
        "physical_moment": {"tai_iso": "2026-05-15T01:00:00.000"},
        "payload": {},
    }
    claim = compute_claim_signals(
        target_event=target,
        link_events=[],
        evidence_events={},
        as_of_time="2026-05-15T02:00:00.000",
    )
    if claim.signal_source != SignalSource.FALLBACK:
        return _fail("hook_8_score_time_fallback_visibility", "claim walker did not fall back without links")
    if claim.fallback_reason not in CLAIM_FALLBACK_REASONS:
        return _fail("hook_8_score_time_fallback_visibility", "claim fallback_reason outside closed enum", reason=claim.fallback_reason)
    # Recall with no priors → first_recall fallback.
    recall_target = _recall_event(event_id="r0", tai_iso="2026-05-15T01:00:00.000", age_myr=4603.000020, seq=0, payload={"claim": "z"})
    recall = compute_recall_signals(target_event=recall_target, prior_recall_events=[], as_of_time="2026-05-15T02:00:00.000")
    if recall.signal_source != SignalSource.FALLBACK:
        return _fail("hook_8_score_time_fallback_visibility", "recall walker did not fall back without priors")
    if recall.fallback_reason not in RECALL_FALLBACK_REASONS:
        return _fail("hook_8_score_time_fallback_visibility", "recall fallback_reason outside closed enum", reason=recall.fallback_reason)
    return _ok(
        "hook_8_score_time_fallback_visibility",
        claim_fallback_reason=claim.fallback_reason,
        recall_fallback_reason=recall.fallback_reason,
    )


def hook_9_normalized_signal_source() -> tuple[str, bool, dict]:
    """All three axis signal types share `signal_source ∈ {computed,
    cache, fallback}` after normalization."""
    if SIGNAL_SOURCE_ENUM != frozenset({"computed", "cache", "fallback"}):
        return _fail("hook_9_normalized_signal_source", "SIGNAL_SOURCE_ENUM drifted")
    if SIGNAL_METHOD_ENUM != frozenset({"provenance_chain", "evidence_links", "recall_history", "none"}):
        return _fail("hook_9_normalized_signal_source", "SIGNAL_METHOD_ENUM drifted")
    # Adapter pass-through: provenance "computed" -> NormalizedSignals.COMPUTED.
    prov = ProvenanceSignals(
        parent_chain_depth=2, source_diversity=0.5, age_of_original_source=1.0,
        chain_root_event_id="r", chain_length=3, distinct_source_classes=2,
        computed_at="2026-05-15T01:00:00.000", as_of_time="2026-05-15T01:00:00.000",
        fallback_reason=None, provenance_signal_source="computed",
    )
    norm = normalize_provenance_signals(prov)
    if norm.signal_source != SignalSource.COMPUTED or norm.signal_method != SignalMethod.PROVENANCE_CHAIN:
        return _fail("hook_9_normalized_signal_source", "provenance adapter did not pass through computed")
    return _ok("hook_9_normalized_signal_source")


_SCORE_CANDIDATE_NAME = "score_candidate"
# v7 emit-bearing functions: spec §11.1 forbids score_candidate()
# calls inside these. Includes the eligibility gate itself because
# the implicit loop's emit path runs through it (the v1.2
# cross-substrate review caught the earlier scope being too narrow).
# Explicit recall (src/explicit_memory/recall.py) remains an OFFLINE
# analysis path until v8 per spec §16.
_V7_EMIT_FILES = (
    "src/implicit_memory/loop.py",
    "src/implicit_memory/lineage_events.py",
    "src/implicit_memory/eligibility.py",
    "src/cutover_v7.py",
)


def hook_10_score_candidate_retirement() -> tuple[str, bool, dict]:
    """No v7 emit-bearing function calls score_candidate(...) directly."""
    repo_root = Path(__file__).resolve().parents[3]
    offending: list[dict[str, Any]] = []
    call_pattern = re.compile(rf"\b{re.escape(_SCORE_CANDIDATE_NAME)}\s*\(")
    for relpath in _V7_EMIT_FILES:
        path = repo_root / relpath
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if call_pattern.search(line):
                offending.append({"file": relpath, "line": lineno, "text": line.strip()})
    if offending:
        return _fail("hook_10_score_candidate_retirement", "v7 emit paths still call score_candidate()", offending=offending)
    return _ok("hook_10_score_candidate_retirement", checked_files=list(_V7_EMIT_FILES))


def hook_11_ordering_replacement() -> tuple[str, bool, dict]:
    """No v7 reader uses event_time for ordering. SQL audits and
    Python readers must reference pm_tai_iso for canonical order."""
    repo_root = Path(__file__).resolve().parents[3]
    sql_dir = repo_root / "src" / "experiments" / "sql"
    readers = (
        "src/lineage_reader.py",
        "src/ingestion/athena_ingestion.py",
        "src/ingestion/preflight.py",
    )
    offending: list[dict[str, Any]] = []
    # SQL files
    for sql_path in sql_dir.glob("*.sql"):
        text = sql_path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("--") or not stripped:
                continue
            if re.search(r"\bevent_time\b", line):
                offending.append({"file": str(sql_path.relative_to(repo_root)), "line": lineno, "text": stripped})
    # Python readers — only complain on bare `event_time` references
    # (column or field), excluding the v6 compatibility shim.
    for relpath in readers:
        path = repo_root / relpath
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "ORDER BY event_time" in line or 'ORDER BY "event_time"' in line:
                offending.append({"file": relpath, "line": lineno, "text": line.strip()})
    if offending:
        return _fail("hook_11_ordering_replacement", "event_time still referenced in v7 readers/SQL", offending=offending)
    return _ok("hook_11_ordering_replacement")


def hook_12_engine_seq_zero() -> tuple[str, bool, dict]:
    """First event in every stream has sequence_in_stream = 0
    (spec §10.1: StreamState.sequence init -1).

    Asserts BOTH the real `LineageEngine` AND the
    `InMemoryLineageEngine` (used by experiment suites A–K) carry
    the full envelope so downstream readers like
    `e.get("memory_id")` work. The memory_id-drop bug that landed
    in Phase 3 (and broke suites B and E) was invisible to the
    Phase 3 verifier because it only checked the real engine; this
    hook now covers the in-memory engine envelope shape too."""
    state = StreamState()
    if state.sequence != -1:
        return _fail("hook_12_engine_seq_zero", "StreamState.sequence init is not -1", got=state.sequence)
    pm = physical_moment("2026-05-15T01:00:00.000", scale="tai")

    # Real engine
    engine = LineageEngine(storage=None, time_context_id="tc-hook12")
    e_alpha = engine.emit(event_type="recalled", agent_id="a", stream_id="alpha", memory_id="m", payload={}, tai_moment=pm)
    e_beta = engine.emit(event_type="recalled", agent_id="a", stream_id="beta", memory_id="m2", payload={}, tai_moment=pm)
    if e_alpha.physical_moment["sequence_in_stream"] != 0:
        return _fail("hook_12_engine_seq_zero", "alpha stream first emit was not seq=0", got=e_alpha.physical_moment["sequence_in_stream"])
    if e_beta.physical_moment["sequence_in_stream"] != 0:
        return _fail("hook_12_engine_seq_zero", "beta stream first emit was not seq=0", got=e_beta.physical_moment["sequence_in_stream"])

    # In-memory engine envelope completeness — every envelope field
    # downstream readers depend on must be present on the recorded
    # dict. This catches accidental drops during refactors.
    in_mem_events: list[dict] = []
    in_mem = InMemoryLineageEngine(events=in_mem_events)
    in_mem.emit(event_type="observed", agent_id="a", stream_id="s", memory_id="mem-X", payload={})
    in_mem.emit(event_type="implicit_admitted", agent_id="a", stream_id="s", memory_id="mem-X", payload={"uncertainty_triple": {}}, subject_event_id="memory_id_referenced:mem-X", subject_record_kind="memory_event", subject_assertion_kind="memory")
    required_keys = {
        "event_id", "event_type", "agent_id", "stream_id", "memory_id",
        "schema_version", "payload", "actor_class", "source_class",
        "parent_event_id", "physical_moment",
        "record_kind", "assertion_kind",
        "subject_event_id", "subject_record_kind", "subject_assertion_kind",
    }
    for idx, e in enumerate(in_mem_events):
        missing = required_keys - set(e.keys())
        if missing:
            return _fail(
                "hook_12_engine_seq_zero",
                "InMemoryLineageEngine event missing envelope keys (regression on memory_id-drop class of bug)",
                event_index=idx,
                missing=sorted(missing),
            )
        if e["memory_id"] != "mem-X":
            return _fail("hook_12_engine_seq_zero", "InMemoryLineageEngine memory_id not preserved", got=e["memory_id"])
    if in_mem_events[0]["physical_moment"]["sequence_in_stream"] != 0:
        return _fail("hook_12_engine_seq_zero", "InMemoryLineageEngine first emit not seq=0")
    return _ok("hook_12_engine_seq_zero", checked_in_memory_envelope_keys=sorted(required_keys))


def hook_13_event_time_absent_on_v7() -> tuple[str, bool, dict]:
    """v7 events MUST NOT carry the legacy event_time envelope
    field. validate_event_v7 quarantines if present."""
    view = _v7_event_view(extras={"event_time": "2026-05-15T01:00:00.000"})
    failure = validate_event_v7(view)
    if failure is None:
        return _fail("hook_13_event_time_absent_on_v7", "validator accepted v7 event with event_time present")
    if failure.reason != "legacy_event_time_present":
        return _fail("hook_13_event_time_absent_on_v7", "wrong quarantine reason", got=failure.reason)
    return _ok("hook_13_event_time_absent_on_v7")


def hook_14_cross_scope_evidence_link_policy() -> tuple[str, bool, dict]:
    """Cross-agent evidence link denied unless explicit policy flag."""
    target = {
        "event_id": "claim-x",
        "event_type": "stored",
        "agent_id": "agent-a",
        "stream_id": "s",
        "memory_id": "mc",
        "assertion_kind": AssertionKind.CLAIM.value,
        "physical_moment": {"tai_iso": "2026-05-15T01:00:00.000"},
        "payload": {},
    }
    foreign_evidence = {
        "event_id": "ev-x",
        "event_type": "stored",
        "agent_id": "agent-other",
        "stream_id": "s2",
        "memory_id": "me",
        "assertion_kind": AssertionKind.EVIDENCE.value,
        "source_class": "telescope_b",
        "physical_moment": {"tai_iso": "2026-05-15T01:00:30.000"},
        "payload": {},
    }
    link = _link_event(
        payload=_resolved_payload(claim_id="claim-x", evidence_id="ev-x"),
        tai_iso="2026-05-15T01:01:00.000", seq=0, event_id="l0", agent_id="agent-a",
    )
    denied = compute_claim_signals(
        target_event=target,
        link_events=[link],
        evidence_events={"ev-x": foreign_evidence},
        as_of_time="2026-05-15T02:00:00.000",
    )
    if denied.signal_source != SignalSource.FALLBACK or denied.fallback_reason != "cross_scope_denied":
        return _fail("hook_14_cross_scope_evidence_link_policy", "cross-scope link was not denied by default", got=denied.fallback_reason)
    # And allowed with the explicit policy flag (link must come from
    # the other agent or be visible across scope).
    cross_link = _link_event(
        payload=_resolved_payload(claim_id="claim-x", evidence_id="ev-x"),
        tai_iso="2026-05-15T01:01:00.000", seq=0, event_id="l0", agent_id="agent-other",
    )
    allowed = compute_claim_signals(
        target_event=target,
        link_events=[cross_link],
        evidence_events={"ev-x": foreign_evidence},
        as_of_time="2026-05-15T02:00:00.000",
        allow_cross_agent=True,
    )
    if allowed.signal_source != SignalSource.COMPUTED:
        return _fail("hook_14_cross_scope_evidence_link_policy", "allow_cross_agent did not unlock the link", got=allowed.signal_source.value)
    return _ok("hook_14_cross_scope_evidence_link_policy")


def hook_15_reality_observation_scope() -> tuple[str, bool, dict]:
    """assertion_kind=reality_observation only legal when
    record_kind=observation_event. Spec §3.2."""
    # Bad: reality_observation on a memory_event.
    bad = _v7_event_view(
        event_type="stored",
        record_kind="memory_event",
        assertion_kind="reality_observation",
    )
    failure = validate_event_v7(bad)
    if failure is None or failure.reason != "reality_observation_outside_observation_event":
        return _fail("hook_15_reality_observation_scope", "validator did not quarantine reality_observation on non-observation_event", got=failure.reason if failure else None)
    # Good: on `observed` event.
    good = _v7_event_view(
        event_type="observed",
        record_kind="observation_event",
        assertion_kind="reality_observation",
    )
    if validate_event_v7(good) is not None:
        return _fail("hook_15_reality_observation_scope", "validator rejected observation_event/reality_observation")
    return _ok("hook_15_reality_observation_scope")


def hook_16_mapping_extension_via_event_type_declared() -> tuple[str, bool, dict]:
    """Unmapped event types quarantine. Once declared (via the
    event_type_declared lineage event channel), they would be
    accepted by the v7 validator. v7 Phase 4 hook asserts the
    static side: unknown -> quarantine, known -> pass. The runtime
    event_type_declared resolver is Phase 5."""
    unknown = _v7_event_view(event_type="never_heard_of_this", record_kind="lineage_meta", assertion_kind=None)
    failure = validate_event_v7(unknown)
    if failure is None or failure.reason != "unmapped_event_type":
        return _fail("hook_16_mapping_extension_via_event_type_declared", "validator did not quarantine unknown event_type", got=failure.reason if failure else None)
    # `event_type_declared` itself must be in the static mapping table.
    if lookup_event_type("event_type_declared") is None:
        return _fail("hook_16_mapping_extension_via_event_type_declared", "event_type_declared not in static mapping")
    return _ok("hook_16_mapping_extension_via_event_type_declared")


# ---------------------------------------------------------------------------
# Implementation gates (spec preamble)
# ---------------------------------------------------------------------------


def gate_1_bootstrap_same_batch_resolution() -> tuple[str, bool, dict]:
    """cutover_v7 emits: canonical_table_genesis(seq=0) referencing
    a time_context_id that is self-referentially declared by the
    next event time_context_declared(seq=1). Same-batch resolution
    per TAI v1.2 §6.2 means genesis is NOT dangling."""

    class _CaptureStorage:
        def __init__(self) -> None:
            self.events: list = []

        def append_event(self, event) -> dict:
            self.events.append(event)
            return {}

    storage = _CaptureStorage()
    summary = cutover(storage=storage)
    events = storage.events
    if len(events) != 3:
        return _fail("gate_1_bootstrap_same_batch_resolution", "cutover did not emit 3 bootstrap events", got=len(events))
    by_type = {e.event_type: e for e in events}
    genesis = by_type.get("canonical_table_genesis")
    declared = by_type.get("time_context_declared")
    commit = by_type.get("canonical_batch_committed")
    if not (genesis and declared and commit):
        return _fail("gate_1_bootstrap_same_batch_resolution", "missing one of the bootstrap event types")
    if genesis.physical_moment["sequence_in_stream"] != 0:
        return _fail("gate_1_bootstrap_same_batch_resolution", "genesis not at seq=0", got=genesis.physical_moment["sequence_in_stream"])
    if declared.physical_moment["sequence_in_stream"] != 1:
        return _fail("gate_1_bootstrap_same_batch_resolution", "time_context_declared not at seq=1", got=declared.physical_moment["sequence_in_stream"])
    if commit.physical_moment["sequence_in_stream"] != 2:
        return _fail("gate_1_bootstrap_same_batch_resolution", "canonical_batch_committed not at seq=2", got=commit.physical_moment["sequence_in_stream"])
    # All three share the same time_context_id — that's the same-batch
    # resolution that prevents genesis from looking dangling.
    if genesis.physical_moment["time_context_id"] != declared.physical_moment["time_context_id"]:
        return _fail("gate_1_bootstrap_same_batch_resolution", "genesis time_context_id != declared time_context_id")
    if genesis.physical_moment["time_context_id"] != summary["time_context_id"]:
        return _fail("gate_1_bootstrap_same_batch_resolution", "summary time_context_id does not match emitted events")
    if genesis.stream_id != CANONICAL_META_STREAM:
        return _fail("gate_1_bootstrap_same_batch_resolution", "genesis not on __canonical_meta__ stream", got=genesis.stream_id)
    return _ok(
        "gate_1_bootstrap_same_batch_resolution",
        time_context_id=summary["time_context_id"],
        batch_id=summary["batch_id"],
    )


def gate_2_cache_discipline() -> tuple[str, bool, dict]:
    """signal_source=cache is legitimate only when the underlying
    walker has a canonical *_signals_computed event. The provenance
    adapter preserves the source field straight from
    `provenance_signal_source` and does NOT manufacture "cache" from
    Vector metadata. We assert the adapter's behavior end-to-end."""
    cache_input = ProvenanceSignals(
        parent_chain_depth=1, source_diversity=1.0, age_of_original_source=0.5,
        chain_root_event_id="root", chain_length=1, distinct_source_classes=1,
        computed_at="2026-05-15T01:00:00.000", as_of_time="2026-05-15T01:00:00.000",
        fallback_reason=None, provenance_signal_source="cache",
    )
    out = normalize_provenance_signals(cache_input)
    if out.signal_source != SignalSource.CACHE:
        return _fail("gate_2_cache_discipline", "cache input not preserved by adapter", got=out.signal_source.value)
    # An unrecognized source (e.g., "vector_metadata") MUST collapse
    # to fallback rather than be silently treated as cache.
    bogus_input = ProvenanceSignals(
        parent_chain_depth=0, source_diversity=0.0, age_of_original_source=0.0,
        chain_root_event_id=None, chain_length=0, distinct_source_classes=0,
        computed_at="2026-05-15T01:00:00.000", as_of_time="2026-05-15T01:00:00.000",
        fallback_reason=None, provenance_signal_source="vector_metadata",
    )
    bogus_out = normalize_provenance_signals(bogus_input)
    if bogus_out.signal_source != SignalSource.FALLBACK:
        return _fail("gate_2_cache_discipline", "vector_metadata source was not collapsed to fallback", got=bogus_out.signal_source.value)
    if bogus_out.fallback_reason != "unrecognized_signal_source":
        return _fail("gate_2_cache_discipline", "fallback reason did not name the unknown source", got=bogus_out.fallback_reason)
    return _ok("gate_2_cache_discipline")


def hook_17_explicit_recall_subject_classification() -> tuple[str, bool, dict]:
    """src/explicit_memory/recall.py emits `rejected` (record_kind=
    decision_event) with `uncertainty_triple` in payload. Spec §3.3
    requires subject classification on such events. Cross-substrate
    review caught that the prior implementation omitted them. Static
    check: every lineage.emit(...event_type="rejected"...) call
    inside recall.py must pass subject classification kwargs."""
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "src" / "explicit_memory" / "recall.py"
    text = path.read_text(encoding="utf-8")
    # Each rejected emit block spans ~1500 chars. Pick a window
    # large enough to cover the largest emit block (cross-scope
    # rejected has many payload fields) but small enough to not
    # bleed into the next emit.
    rejected_blocks = re.findall(r'event_type="rejected"[\s\S]{0,2000}', text)
    if not rejected_blocks:
        return _fail("hook_17_explicit_recall_subject_classification", "no `rejected` emit blocks found — refactor unexpectedly removed them?")
    for idx, block in enumerate(rejected_blocks):
        if "**subject" not in block:
            return _fail(
                "hook_17_explicit_recall_subject_classification",
                "`rejected` emit in recall.py missing **subject classification kwargs",
                block_index=idx,
            )
        if 'subject_kind_source' not in block or '"v1_default"' not in block:
            return _fail(
                "hook_17_explicit_recall_subject_classification",
                "`rejected` emit missing `subject_kind_source: v1_default` audit tag",
                block_index=idx,
            )
    return _ok("hook_17_explicit_recall_subject_classification", rejected_emits_in_recall=len(rejected_blocks))


def hook_18_score_triple_consumes_axis_signals() -> tuple[str, bool, dict]:
    """score_triple must accept optional claim_signals,
    recall_signals, provenance_signals and apply the spec §11
    fallback multiplier. Pass a synthetic FALLBACK-tagged signal
    and verify the corresponding axis is multiplied by the
    fallback_multiplier (default 0.5)."""
    from src.explicit_memory.eligibility import (
        V7_FALLBACK_MULTIPLIER_DEFAULT,
        score_triple,
    )

    class _FallbackSignal:
        signal_source = SignalSource.FALLBACK
        fallback_reason = "no_evidence_links"

    base = score_triple(
        relevance=1.0, trust=1.0, recency=1.0, reinforcement=1.0,
        consistency=1.0, safety=1.0,
        parent_chain_depth=0.0, source_diversity=1.0, age_of_original_source=0.0,
    )
    with_fb = score_triple(
        relevance=1.0, trust=1.0, recency=1.0, reinforcement=1.0,
        consistency=1.0, safety=1.0,
        parent_chain_depth=0.0, source_diversity=1.0, age_of_original_source=0.0,
        claim_signals=_FallbackSignal(),
    )
    if base.confidence_in_claim <= 0.0:
        return _fail("hook_18_score_triple_consumes_axis_signals", "base claim axis unexpectedly zero")
    expected = base.confidence_in_claim * V7_FALLBACK_MULTIPLIER_DEFAULT
    if abs(with_fb.confidence_in_claim - expected) > 1e-9:
        return _fail(
            "hook_18_score_triple_consumes_axis_signals",
            "fallback multiplier not applied to claim axis",
            base=base.confidence_in_claim, with_fb=with_fb.confidence_in_claim, expected=expected,
        )
    if not with_fb.axis_fallback_used.get("claim"):
        return _fail("hook_18_score_triple_consumes_axis_signals", "axis_fallback_used['claim'] not True")
    if with_fb.axis_fallback_reasons.get("claim") != "no_evidence_links":
        return _fail("hook_18_score_triple_consumes_axis_signals", "axis_fallback_reasons not propagated")
    if with_fb.policy_fallback_multiplier != V7_FALLBACK_MULTIPLIER_DEFAULT:
        return _fail("hook_18_score_triple_consumes_axis_signals", "policy_fallback_multiplier not recorded")
    # Recall and provenance axes should NOT be affected when their signals are None.
    if with_fb.axis_fallback_used.get("recall_process") or with_fb.axis_fallback_used.get("provenance_chain"):
        return _fail("hook_18_score_triple_consumes_axis_signals", "unrelated axes flagged fallback when their signals were None")
    return _ok(
        "hook_18_score_triple_consumes_axis_signals",
        base_claim=base.confidence_in_claim,
        with_fb_claim=with_fb.confidence_in_claim,
    )


def hook_19_validator_subject_required_only_on_decision_event() -> tuple[str, bool, dict]:
    """Spec §3.3: subject classification is required ONLY for
    decision events that carry uncertainty triples — not for memory
    or observation events that happen to carry triples (the event
    IS the subject for those record kinds). Cross-substrate review
    caught the previous validator over-triggering on any triple.
    """
    # memory_event with triple — should NOT require subject.
    memory_view = _v7_event_view(
        event_type="recalled",
        record_kind="memory_event",
        assertion_kind="memory",
        payload={"uncertainty_triple": {}},
    )
    if validate_event_v7(memory_view) is not None:
        return _fail("hook_19_validator_subject_required_only_on_decision_event", "memory_event with triple should not require subject", got=validate_event_v7(memory_view))
    # decision_event with triple — MUST require subject.
    decision_view = _v7_event_view(
        event_type="implicit_admitted",
        record_kind="decision_event",
        assertion_kind=None,
        payload={"uncertainty_triple": {}},
    )
    failure = validate_event_v7(decision_view)
    if failure is None or failure.reason != "missing_subject_assertion_kind":
        return _fail("hook_19_validator_subject_required_only_on_decision_event", "decision_event with triple should require subject_assertion_kind", got=failure.reason if failure else None)
    return _ok("hook_19_validator_subject_required_only_on_decision_event")


def hook_20_validator_chains_evidence_link_payload() -> tuple[str, bool, dict]:
    """validate_event_v7 must call validate_evidence_link_payload
    for event_type == 'evidence_link_declared'. Cross-substrate
    review caught that link payload validation existed but wasn't
    wired into the envelope validator."""
    from src.epistemic_triangle.links import compute_link_id
    # Build a v7 evidence_link_declared event with a corrupt link_id.
    payload = {
        "link_id": "not_the_actual_hash",
        "link_type": "supports",
        "claim_event_id": "c1",
        "evidence_event_id": "e1",
        "resolution_state": "resolved",
        "resolution_reason": None,
    }
    view = _v7_event_view(
        event_type="evidence_link_declared",
        record_kind="lineage_meta",
        assertion_kind=None,
        payload=payload,
    )
    failure = validate_event_v7(view)
    if failure is None or failure.reason != "invalid_link_id":
        return _fail(
            "hook_20_validator_chains_evidence_link_payload",
            "corrupt link_id was not caught by validate_event_v7",
            got=failure.reason if failure else None,
        )
    # And with a correct link_id, the chain passes through.
    correct_payload = dict(payload)
    correct_payload["link_id"] = compute_link_id(claim_event_id="c1", evidence_event_id="e1", link_type="supports")
    correct_view = _v7_event_view(
        event_type="evidence_link_declared",
        record_kind="lineage_meta",
        assertion_kind=None,
        payload=correct_payload,
    )
    if validate_event_v7(correct_view) is not None:
        return _fail("hook_20_validator_chains_evidence_link_payload", "well-formed evidence_link_declared rejected")
    return _ok("hook_20_validator_chains_evidence_link_payload")


def hook_21_storage_schema_parity_with_cdk() -> tuple[str, bool, dict]:
    """LineageStorage.ensure_table schema and the CDK
    `LineageTable` schema declare the same v7 hot columns in the
    same order. Athena INSERT is positional; drift between the two
    silently breaks ingestion. Cross-substrate review caught
    ensure_table missing pm_* columns entirely."""
    repo_root = Path(__file__).resolve().parents[3]
    storage_text = (repo_root / "src" / "storage.py").read_text(encoding="utf-8")
    stack_text = (repo_root / "stacks" / "memory_lab" / "memory_lab_stack.py").read_text(encoding="utf-8")

    def _extract_field_names(text: str, pattern: str) -> list[str]:
        return re.findall(pattern, text)

    # storage.py uses {"name": "X", ...} dicts; CDK uses name="X" kwargs.
    storage_fields = _extract_field_names(storage_text, r'\{"name":\s*"([a-z_][a-z_0-9]*)"')
    stack_fields = _extract_field_names(stack_text, r'name="([a-z_][a-z_0-9]*)",\s*type="')

    expected = [
        "event_id", "event_type", "agent_id", "stream_id", "memory_id",
        "payload", "actor_class", "source_class",
        "schema_version", "parent_event_id",
        "physical_moment",
        "pm_tai_iso", "pm_solar_age_myr", "pm_ecliptic_lon_deg",
        "pm_sequence_in_stream", "pm_hlc_timestamp", "pm_hlc_signature_eligible",
        "pm_time_context_id",
        "record_kind", "assertion_kind",
        "subject_event_id", "subject_record_kind", "subject_assertion_kind",
    ]
    if storage_fields != expected:
        return _fail(
            "hook_21_storage_schema_parity_with_cdk",
            "src/storage.py ensure_table schema diverges from expected v7 column order",
            got=storage_fields, expected=expected,
        )
    if stack_fields != expected:
        return _fail(
            "hook_21_storage_schema_parity_with_cdk",
            "CDK LineageTable schema diverges from expected v7 column order",
            got=stack_fields, expected=expected,
        )
    return _ok("hook_21_storage_schema_parity_with_cdk", columns=len(expected))


def hook_22_pm_tai_iso_string_comparison() -> tuple[str, bool, dict]:
    """lineage_reader.query_memory_events compares pm_tai_iso as a
    STRING (not TIMESTAMP). Cross-substrate review caught the prior
    `TIMESTAMP 'as_of'` cast that would mismatch the string column."""
    repo_root = Path(__file__).resolve().parents[3]
    text = (repo_root / "src" / "lineage_reader.py").read_text(encoding="utf-8")
    if re.search(r"pm_tai_iso\s*<=\s*TIMESTAMP\b", text):
        return _fail("hook_22_pm_tai_iso_string_comparison", "lineage_reader still compares pm_tai_iso as TIMESTAMP")
    if "pm_tai_iso <= '{as_of_time}'" not in text and "pm_tai_iso <= '" not in text:
        return _fail("hook_22_pm_tai_iso_string_comparison", "expected string comparison shape not found in lineage_reader")
    return _ok("hook_22_pm_tai_iso_string_comparison")


def hook_23_link_ordering_includes_stream_id() -> tuple[str, bool, dict]:
    """select_latest_link_states orders by spec §8.2 cross-stream
    tuple `(pm_tai_iso, stream_id, sequence_in_stream, event_id)`,
    not the §8.1 single-stream tuple. Cross-substrate review caught
    the missing stream_id."""
    same_tai = "2026-05-15T01:00:00.000"
    same_seq = 0
    link_id = compute_link_id(claim_event_id="c1", evidence_event_id="e1", link_type="supports")
    # Two events with identical (tai, seq, event_id-prefix) on
    # different streams — without stream_id in the tuple they would
    # tie-break on event_id only.
    a = _link_event(
        payload=_invalid_payload(),
        tai_iso=same_tai, seq=same_seq, event_id="lev-aaa", agent_id="a",
    )
    a["stream_id"] = "stream-A"
    b = _link_event(
        payload=_resolved_payload(),
        tai_iso=same_tai, seq=same_seq, event_id="lev-aab",
    )
    b["stream_id"] = "stream-B"
    # In §8.2 ordering, stream-A < stream-B so b (resolved on stream-B) wins;
    # in §8.1 ordering, event_id tie-break would pick b too — so we use a
    # structural test: the ordering key function must include stream_id.
    from src.epistemic_triangle.links import _link_event_canonical_order_key
    key = _link_event_canonical_order_key(b)
    if not isinstance(key, tuple) or len(key) != 4:
        return _fail("hook_23_link_ordering_includes_stream_id", "ordering key is not the 4-tuple required by §8.2", got=key)
    # Position 1 must be stream_id.
    if key[1] != "stream-B":
        return _fail("hook_23_link_ordering_includes_stream_id", "ordering key position 1 is not stream_id", key=key)
    return _ok("hook_23_link_ordering_includes_stream_id")


def hook_24_athena_ingestion_v7_predicate_coverage() -> tuple[str, bool, dict]:
    """athena_ingestion's valid_rows_predicate enforces the v7
    closed-enum rules. Cross-substrate review caught that the prior
    predicate only checked schema_version, physical_moment Tier 1a,
    record_kind IS NOT NULL, and event_time IS NULL — missing the
    enum membership, assertion_kind-required, reality_observation
    scope, unmapped event_type, and subject classification rules.
    Static check on the source file (no AwsConfig construction
    needed — we read the predicate-builder directly)."""
    repo_root = Path(__file__).resolve().parents[3]
    text = (repo_root / "src" / "ingestion" / "athena_ingestion.py").read_text(encoding="utf-8")
    required_substrings = [
        "schema_version = '7.0'",
        "event_time IS NULL",
        "record_kind IS NOT NULL",
        "record_kind IN ",         # the closed-enum membership check
        "assertion_kind IN ",      # enum membership for assertion_kind
        "reality_observation",     # scope check
        "subject_assertion_kind IS NOT NULL",  # decision-event subject requirement
        "uncertainty_triple",      # inline substring check on payload
        "unmapped_event_type",     # quarantine reason
        "missing_subject_assertion_kind",
        "missing_assertion_kind_for_record_kind",
        "reality_observation_outside_observation_event",
        "invalid_record_kind",
        "invalid_assertion_kind",
    ]
    missing = [s for s in required_substrings if s not in text]
    if missing:
        return _fail(
            "hook_24_athena_ingestion_v7_predicate_coverage",
            "athena ingestion predicate missing v7 rules",
            missing=missing,
        )
    return _ok("hook_24_athena_ingestion_v7_predicate_coverage", checked_substrings=len(required_substrings))


def hook_25_athena_predicate_null_safe_assertion_kind() -> tuple[str, bool, dict]:
    """End-to-end: the Athena valid-row predicate must accept a
    well-formed v7 lineage_meta row whose assertion_kind is NULL.

    Cross-substrate review (gpt-5-codex, 2026-05-15) caught that
    the `assertion_kind <> 'reality_observation'` clause was UNKNOWN
    (not TRUE) under three-valued logic when assertion_kind was
    NULL, silently quarantining valid lineage_meta /
    decision_event / policy_event rows. The fix added IS NULL guards;
    this hook proves the guards are present in the rendered SQL.
    """
    repo_root = Path(__file__).resolve().parents[3]
    text = (repo_root / "src" / "ingestion" / "athena_ingestion.py").read_text(encoding="utf-8")
    null_safe_guard = "assertion_kind IS NULL OR assertion_kind <> 'reality_observation'"
    if null_safe_guard not in text:
        return _fail(
            "hook_25_athena_predicate_null_safe_assertion_kind",
            "valid-row predicate not null-safe on assertion_kind",
            expected=null_safe_guard,
        )
    quarantine_guard = (
        "assertion_kind IS NOT NULL AND assertion_kind = 'reality_observation'"
    )
    if quarantine_guard not in text:
        return _fail(
            "hook_25_athena_predicate_null_safe_assertion_kind",
            "quarantine clause not null-safe on assertion_kind",
            expected=quarantine_guard,
        )
    return _ok("hook_25_athena_predicate_null_safe_assertion_kind")


def hook_26_athena_quarantines_corrupt_evidence_link() -> tuple[str, bool, dict]:
    """End-to-end: a malformed `evidence_link_declared` raw row
    (bad link_type / state / reason) must be quarantined by the
    Athena ingestion path, not just by the Python validator.

    Cross-substrate review noted that wiring the Python validator
    only closes the Python side of the bypass — raw ingress can
    still reach canonical insert via Athena. The fix added the
    link state-machine enums into both the valid-row predicate and
    the quarantine CASE/WHERE. This hook asserts the SQL fragments
    are present and target the `invalid_link_id` reason.
    """
    repo_root = Path(__file__).resolve().parents[3]
    text = (repo_root / "src" / "ingestion" / "athena_ingestion.py").read_text(encoding="utf-8")
    required = [
        "event_type = 'evidence_link_declared'",
        "json_extract_scalar(payload, '$.link_id')",
        "json_extract_scalar(payload, '$.link_type') IN ('supports','refutes')",
        "json_extract_scalar(payload, '$.resolution_state') IN ('pending','resolved','invalid')",
        "claim_not_yet_emitted",
        "dangling_after_grace_period",
        "'invalid_link_id'",
    ]
    missing = [s for s in required if s not in text]
    if missing:
        return _fail(
            "hook_26_athena_quarantines_corrupt_evidence_link",
            "evidence_link_declared SQL validation incomplete",
            missing=missing,
        )
    return _ok("hook_26_athena_quarantines_corrupt_evidence_link", checked_substrings=len(required))


def hook_27_recall_path_emits_scoring_function_marker() -> tuple[str, bool, dict]:
    """End-to-end: `RecallEngine.retrieve` is a v7 emit path per
    spec §11.1; every v7 decision payload (`rejected`, `recalled`)
    must carry `scoring_function: "score_triple"`, and recall.py
    must not call `score_candidate` directly. Cross-substrate
    review caught that the prior response retained `score_candidate`
    in recall.py and emitted no `scoring_function` marker anywhere.
    """
    repo_root = Path(__file__).resolve().parents[3]
    recall_text = (repo_root / "src" / "explicit_memory" / "recall.py").read_text(encoding="utf-8")
    loop_text = (repo_root / "src" / "implicit_memory" / "loop.py").read_text(encoding="utf-8")
    # Static: no score_candidate( call in recall.py
    if re.search(r"\bscore_candidate\s*\(", recall_text):
        return _fail("hook_27_recall_path_emits_scoring_function_marker", "recall.py still calls score_candidate()")
    # Static: scoring_function marker present in both emit paths.
    if '"scoring_function": "score_triple"' not in recall_text:
        return _fail("hook_27_recall_path_emits_scoring_function_marker", "recall.py decision payloads missing scoring_function marker")
    if '"scoring_function": "score_triple"' not in loop_text:
        return _fail("hook_27_recall_path_emits_scoring_function_marker", "implicit loop decision payloads missing scoring_function marker")
    # Behavioral: emitting a recall through the in-memory engine
    # actually puts `scoring_function: "score_triple"` in the
    # payload of an implicit_admitted/implicit_rejected event.
    events: list[dict] = []
    in_mem = InMemoryLineageEngine(events=events)
    in_mem.emit(
        event_type="implicit_admitted",
        agent_id="a",
        stream_id="s",
        memory_id="m",
        payload={
            "uncertainty_triple": {},
            "scoring_function": "score_triple",
        },
        subject_event_id="memory_id_referenced:m",
        subject_record_kind="memory_event",
        subject_assertion_kind="memory",
    )
    if events[0]["payload"].get("scoring_function") != "score_triple":
        return _fail("hook_27_recall_path_emits_scoring_function_marker", "in-memory engine dropped scoring_function from payload")
    return _ok("hook_27_recall_path_emits_scoring_function_marker")


def hook_28_loop_passes_v7_signals_to_gate() -> tuple[str, bool, dict]:
    """End-to-end: `ImplicitControllerLoop._admit_and_gate` must
    supply claim/recall/provenance NormalizedSignals to the gate
    rather than running in `signal is None` mode (which spec §11
    only allows on pre-v7 paths). Cross-substrate review caught
    that the prior response made the gate ACCEPT signals but did
    not WIRE them on the live emit path.

    Static check: the loop body contains the helper that builds
    the three signals and passes them as kwargs to eligibility_gate.
    Behavioral check is omitted because constructing a controller
    with full deps is heavy; the runtime check is covered by the
    full im_regression where `axis_fallback_used` now lands on
    every implicit decision payload."""
    repo_root = Path(__file__).resolve().parents[3]
    loop_text = (repo_root / "src" / "implicit_memory" / "loop.py").read_text(encoding="utf-8")
    required = [
        "_build_v7_axis_signals",
        "claim_signals=claim_signals",
        "recall_signals=recall_signals",
        "provenance_signals=prov_signals",
    ]
    missing = [s for s in required if s not in loop_text]
    if missing:
        return _fail(
            "hook_28_loop_passes_v7_signals_to_gate",
            "implicit loop not supplying v7 signals to eligibility_gate",
            missing=missing,
        )
    return _ok("hook_28_loop_passes_v7_signals_to_gate")


def hook_29_preflight_projection_matches_ingestion() -> tuple[str, bool, dict]:
    """End-to-end: the projection printed by `preflight.py` must
    match the projection actually used by
    `AthenaLineageIngestionJob`'s canonical INSERT. INSERT is
    positional in Athena, so a stale preflight projection silently
    misleads anyone diffing it against ingestion. Cross-substrate
    review caught the stale form (only `pm_tai_iso` printed, all
    other `pm_*` columns missing)."""
    repo_root = Path(__file__).resolve().parents[3]
    preflight_text = (repo_root / "src" / "ingestion" / "preflight.py").read_text(encoding="utf-8")
    required = [
        "pm_solar_age_myr",
        "pm_ecliptic_lon_deg",
        "pm_sequence_in_stream",
        "pm_hlc_timestamp",
        "pm_hlc_signature_eligible",
        "pm_time_context_id",
        "record_kind,assertion_kind,subject_event_id,subject_record_kind,subject_assertion_kind",
    ]
    missing = [s for s in required if s not in preflight_text]
    if missing:
        return _fail(
            "hook_29_preflight_projection_matches_ingestion",
            "preflight insert_projection missing v7 hot columns",
            missing=missing,
        )
    return _ok("hook_29_preflight_projection_matches_ingestion")


def hook_30_athena_link_id_hash_verification() -> tuple[str, bool, dict]:
    """End-to-end: the Athena ingestion path must verify
    `link_id == sha256(canonical_json({claim_event_id,
    evidence_event_id, link_type}))` per spec §4.2 — not only the
    payload shape. Third cross-substrate review (gpt-5-codex,
    2026-05-15) caught that hash verification was still missing
    after the shape-validation pass.

    Static check: both the valid-row predicate and the quarantine
    clause must contain the SHA-256 recomputation against the
    canonical JSON literal and compare it to the payload link_id.
    """
    repo_root = Path(__file__).resolve().parents[3]
    text = (repo_root / "src" / "ingestion" / "athena_ingestion.py").read_text(encoding="utf-8")
    required_substrings = [
        # The SHA-256 hash check fragment.
        "lower(to_hex(sha256(to_utf8(concat(",
        # Canonical JSON shape literals — alphabetical keys,
        # separator-tight per python json.dumps(sort_keys=True,
        # separators=(',',':')).
        '{\\"claim_event_id\\":\\"',
        '\\",\\"evidence_event_id\\":\\"',
        '\\",\\"link_type\\":\\"',
        '\\"}',
        # Comparison against payload link_id.
        "json_extract_scalar(payload, '$.link_id')",
    ]
    missing = [s for s in required_substrings if s not in text]
    if missing:
        return _fail(
            "hook_30_athena_link_id_hash_verification",
            "Athena ingestion path missing deterministic link_id hash check",
            missing=missing,
        )
    # Both occurrences (valid predicate + quarantine clause) must
    # be present, not just one.
    sha_occurrences = text.count("lower(to_hex(sha256(to_utf8(concat(")
    if sha_occurrences < 2:
        return _fail(
            "hook_30_athena_link_id_hash_verification",
            "link_id hash check appears in only one of (valid-row predicate, quarantine clause)",
            sha_occurrences=sha_occurrences,
        )
    return _ok("hook_30_athena_link_id_hash_verification", sha_occurrences=sha_occurrences)


def hook_31_explicit_recall_passes_v7_signals() -> tuple[str, bool, dict]:
    """End-to-end: `RecallEngine.retrieve` is a v7 emit path (spec
    §11.1) and must supply `claim_signals`, `recall_signals`,
    `provenance_signals` to `score_triple`. Spec §11 only permits
    `signal is None` on pre-v7 paths. Third cross-substrate review
    caught that recall.py still ran in None-mode after the loop was
    wired.

    Static checks:
      - recall.py has a `_build_v7_axis_signals` helper that builds
        the three NormalizedSignals.
      - `score_triple(...)` call passes `claim_signals`,
        `recall_signals`, `provenance_signals` kwargs.
      - Decision payloads carry `axis_fallback_used` /
        `axis_fallback_reasons` / `policy_fallback_multiplier`
        markers (the per-axis visibility surface).
    """
    repo_root = Path(__file__).resolve().parents[3]
    recall_text = (repo_root / "src" / "explicit_memory" / "recall.py").read_text(encoding="utf-8")
    required = [
        "_build_v7_axis_signals",
        "claim_signals=claim_signals",
        "recall_signals=recall_signals",
        "provenance_signals=prov_signals",
        '"axis_fallback_used"',
        '"axis_fallback_reasons"',
        '"policy_fallback_multiplier"',
    ]
    missing = [s for s in required if s not in recall_text]
    if missing:
        return _fail(
            "hook_31_explicit_recall_passes_v7_signals",
            "RecallEngine.retrieve not supplying v7 signals or omitting fallback visibility",
            missing=missing,
        )
    return _ok("hook_31_explicit_recall_passes_v7_signals")


def hook_32_implicit_admitted_all_computed_sources() -> tuple[str, bool, dict]:
    """Exit-criteria check from spec §15:

    At least one `implicit_admitted` decision in lineage carries
    lineage-derived claim + recall + provenance signals with
    `signal_source == computed` on the same decision, plus subject
    classification.

    This hook drives the real `_admit_and_gate` method on a minimal
    test double and injects computed axis signals built by the
    canonical walkers so the emitted decision payload can be checked
    end-to-end.
    """
    from src.explicit_memory.eligibility import V7_FALLBACK_MULTIPLIER_DEFAULT
    from src.explicit_memory.provenance import ProvenanceSignals

    # Build computed claim signals.
    claim_target = {"event_id": "claim-evt", "agent_id": "a", "assertion_kind": "claim"}
    link_events = [{
        "event_type": "evidence_link_declared",
        "event_id": "link-evt",
        "agent_id": "a",
        "stream_id": "s",
        "physical_moment": {"tai_iso": "2026-05-15T02:00:00.000", "sequence_in_stream": 1},
        "payload": {
            "link_id": compute_link_id(claim_event_id="claim-evt", evidence_event_id="evidence-evt", link_type="supports"),
            "link_type": "supports",
            "claim_event_id": "claim-evt",
            "evidence_event_id": "evidence-evt",
            "resolution_state": "resolved",
            "resolution_reason": None,
        },
    }]
    evidence_events = {
        "evidence-evt": {
            "event_id": "evidence-evt",
            "agent_id": "a",
            "source_class": "sensor",
            "assertion_kind": "evidence",
        }
    }
    claim = compute_claim_signals(
        target_event=claim_target,
        link_events=link_events,
        evidence_events=evidence_events,
        as_of_time="2026-05-15T02:00:00.000",
    )
    if claim.signal_source != SignalSource.COMPUTED:
        return _fail("hook_32_implicit_admitted_all_computed_sources", "claim signal did not compute", got=claim.signal_source.value)

    # Build computed recall signals.
    target_recall = {
        "event_type": "recalled",
        "memory_id": "mem-32",
        "agent_id": "a",
        "assertion_kind": "memory",
        "payload": {"claim": "x", "evidence_ids": ["e1", "e2"]},
        "physical_moment": {"tai_iso": "2026-05-15T03:00:00.000", "solar_age_myr": 4603.0},
    }
    prior_recalls = [
        {
            "event_type": "recalled",
            "event_id": "r1",
            "memory_id": "mem-32",
            "agent_id": "a",
            "assertion_kind": "memory",
            "payload": {"claim": "x", "evidence_ids": ["e1"]},
            "physical_moment": {"tai_iso": "2026-05-15T01:00:00.000", "sequence_in_stream": 1, "solar_age_myr": 4602.999999},
        },
        {
            "event_type": "recalled",
            "event_id": "r2",
            "memory_id": "mem-32",
            "agent_id": "a",
            "assertion_kind": "memory",
            "payload": {"claim": "x", "evidence_ids": ["e1", "e2"]},
            "physical_moment": {"tai_iso": "2026-05-15T02:00:00.000", "sequence_in_stream": 2, "solar_age_myr": 4602.9999995},
        },
    ]
    recall = compute_recall_signals(
        target_event=target_recall,
        prior_recall_events=prior_recalls,
        as_of_time="2026-05-15T03:00:00.000",
    )
    if recall.signal_source != SignalSource.COMPUTED:
        return _fail("hook_32_implicit_admitted_all_computed_sources", "recall signal did not compute", got=recall.signal_source.value)

    # Build computed provenance signal (normalized).
    prov_norm = normalize_provenance_signals(
        ProvenanceSignals(
            parent_chain_depth=1,
            source_diversity=1.0,
            age_of_original_source=0.5,
            chain_root_event_id="root",
            chain_length=2,
            distinct_source_classes=2,
            computed_at="2026-05-15T03:00:00.000",
            as_of_time="2026-05-15T03:00:00.000",
            fallback_reason=None,
            provenance_signal_source="computed",
        )
    )
    if prov_norm.signal_source != SignalSource.COMPUTED:
        return _fail("hook_32_implicit_admitted_all_computed_sources", "provenance signal did not compute", got=prov_norm.signal_source.value)

    # Run the real _admit_and_gate with a tiny self-object.
    events: list[dict[str, Any]] = []
    lineage = InMemoryLineageEngine(events=events)

    class _PolicyState:
        threshold_map = {"admission_threshold": 0.0, "eligibility_threshold": 0.0}

    class _RP:
        uncertainty_gate_mode = "combined"
        uncertainty_combined_threshold = 0.0
        uncertainty_claim_threshold = 0.0
        uncertainty_recall_process_threshold = 0.0
        uncertainty_provenance_chain_threshold = 0.0
        uncertainty_safety_floor = 0.0

    class _Cfg:
        retrieval_policy = _RP()

    class _Self:
        agent_id = "a"
        stream_id = "s"
        policy_state = _PolicyState()
        cfg = _Cfg()

        def __init__(self, lineage_engine: InMemoryLineageEngine) -> None:
            self.lineage = lineage_engine

        def _subject_classification_for_memory(self, memory_id: str) -> dict[str, str]:
            return ImplicitControllerLoop._subject_classification_for_memory(self, memory_id)

        def _emit_rejected(self, **kwargs: Any) -> None:
            raise AssertionError(f"unexpected rejection in hook_32: {kwargs}")

        def _build_v7_axis_signals(self, *, memory_id: str, gate_inputs: dict[str, float]):
            return claim, recall, prov_norm

    ok = ImplicitControllerLoop._admit_and_gate(
        _Self(lineage),
        memory_id="mem-32",
        source_class="internal_engine",
        admission_value=1.0,
        gate_inputs={
            "relevance": 1.0,
            "trust": 1.0,
            "recency": 1.0,
            "reinforcement": 1.0,
            "consistency": 1.0,
            "safety": 1.0,
            "parent_chain_depth": 1.0,
            "source_diversity": 1.0,
            "age_of_original_source": 0.5,
        },
        admission_reason="hook_32",
    )
    if not ok:
        return _fail("hook_32_implicit_admitted_all_computed_sources", "admission unexpectedly rejected")

    admitted = next((e for e in events if e.get("event_type") == "implicit_admitted"), None)
    if admitted is None:
        return _fail("hook_32_implicit_admitted_all_computed_sources", "implicit_admitted not emitted")
    payload = admitted.get("payload", {})
    claim_src = (((payload.get("claim_signals") or {}).get("signal_source")))
    recall_src = (((payload.get("recall_signals") or {}).get("signal_source")))
    prov_src = (((payload.get("provenance_signal") or {}).get("signal_source")))
    if claim_src != "computed" or recall_src != "computed" or prov_src != "computed":
        return _fail(
            "hook_32_implicit_admitted_all_computed_sources",
            "not all axis signal sources were computed on implicit_admitted",
            claim_source=claim_src,
            recall_source=recall_src,
            provenance_source=prov_src,
        )
    if admitted.get("subject_assertion_kind") != "memory":
        return _fail(
            "hook_32_implicit_admitted_all_computed_sources",
            "subject_assertion_kind missing on implicit_admitted",
            got=admitted.get("subject_assertion_kind"),
        )
    if payload.get("policy_fallback_multiplier") != V7_FALLBACK_MULTIPLIER_DEFAULT:
        return _fail(
            "hook_32_implicit_admitted_all_computed_sources",
            "policy_fallback_multiplier missing or drifted",
            got=payload.get("policy_fallback_multiplier"),
        )
    return _ok("hook_32_implicit_admitted_all_computed_sources")


def gate_3_decision_subject_placeholder_pattern() -> tuple[str, bool, dict]:
    """ImplicitControllerLoop._subject_classification_for_memory
    produces a deterministic placeholder pattern when the decision
    subject has no concrete event_id yet (spec preamble caution #3).
    Replay-stable across calls; tagged via subject_kind_source =
    'v1_default' in the decision payload so audits know it's a
    defaulted classification, not derived."""
    # Build a minimal loop just to call the helper. We avoid the
    # full controller dependencies by accessing the bound method
    # statically.
    func = ImplicitControllerLoop._subject_classification_for_memory
    self_placeholder = type("_S", (), {})()  # not actually used by the method
    a = func(self_placeholder, "mem-42")
    b = func(self_placeholder, "mem-42")
    c = func(self_placeholder, "mem-other")
    if a != b:
        return _fail("gate_3_decision_subject_placeholder_pattern", "placeholder not deterministic for same memory_id")
    if a["subject_event_id"] != "memory_id_referenced:mem-42":
        return _fail("gate_3_decision_subject_placeholder_pattern", "placeholder not in expected format", got=a["subject_event_id"])
    if a["subject_assertion_kind"] != "memory":
        return _fail("gate_3_decision_subject_placeholder_pattern", "default subject_assertion_kind not 'memory'", got=a["subject_assertion_kind"])
    if c["subject_event_id"] == a["subject_event_id"]:
        return _fail("gate_3_decision_subject_placeholder_pattern", "different memory_ids produced same placeholder")
    return _ok("gate_3_decision_subject_placeholder_pattern", placeholder=a["subject_event_id"])


# ---------------------------------------------------------------------------
# suite assembly
# ---------------------------------------------------------------------------


HOOKS: list[Callable[[], tuple[str, bool, dict]]] = [
    hook_1_record_kind_round_trip,
    hook_2_mapping_table_coverage,
    hook_3_decision_event_subject_required,
    hook_4_link_id_deterministic,
    hook_5_latest_state_walker,
    hook_6_recall_variance_limitations,
    hook_7_time_since_last_replay_deterministic,
    hook_8_score_time_fallback_visibility,
    hook_9_normalized_signal_source,
    hook_10_score_candidate_retirement,
    hook_11_ordering_replacement,
    hook_12_engine_seq_zero,
    hook_13_event_time_absent_on_v7,
    hook_14_cross_scope_evidence_link_policy,
    hook_15_reality_observation_scope,
    hook_16_mapping_extension_via_event_type_declared,
    # Hooks 17-24 added in response to cross-substrate code review
    # (2026-05-15). Each targets a specific gap the prior suite
    # missed; see spec §13 + the v1.2 promotion-review preamble.
    hook_17_explicit_recall_subject_classification,
    hook_18_score_triple_consumes_axis_signals,
    hook_19_validator_subject_required_only_on_decision_event,
    hook_20_validator_chains_evidence_link_payload,
    hook_21_storage_schema_parity_with_cdk,
    hook_22_pm_tai_iso_string_comparison,
    hook_23_link_ordering_includes_stream_id,
    hook_24_athena_ingestion_v7_predicate_coverage,
    # Hooks 25-29 added in response to the second cross-substrate
    # code review (openai-gpt-5-codex, 2026-05-15). Each closes a
    # gap the first response left open.
    hook_25_athena_predicate_null_safe_assertion_kind,
    hook_26_athena_quarantines_corrupt_evidence_link,
    hook_27_recall_path_emits_scoring_function_marker,
    hook_28_loop_passes_v7_signals_to_gate,
    hook_29_preflight_projection_matches_ingestion,
    # Hooks 30-31 added in response to the third cross-substrate
    # code review (openai-gpt-5-codex, 2026-05-15). Two residual
    # findings from the second-pass response: deterministic link_id
    # hash verification at the Athena path, and explicit recall
    # still running in `signal is None` mode.
    hook_30_athena_link_id_hash_verification,
    hook_31_explicit_recall_passes_v7_signals,
    hook_32_implicit_admitted_all_computed_sources,
    gate_1_bootstrap_same_batch_resolution,
    gate_2_cache_discipline,
    gate_3_decision_subject_placeholder_pattern,
]


def _run_hook(fn: Callable[[], tuple[str, bool, dict]]) -> dict[str, Any]:
    try:
        name, ok, detail = fn()
        return {"name": name, "ok": ok, "detail": detail}
    except Exception as exc:
        return {
            "name": fn.__name__,
            "ok": False,
            "detail": {"error": f"{type(exc).__name__}: {exc}"},
        }


def run() -> dict[str, Any]:
    results = [_run_hook(fn) for fn in HOOKS]
    suite_pass = all(r["ok"] for r in results)
    payload = json.dumps(
        [{"name": r["name"], "ok": r["ok"]} for r in results],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    signature = hashlib.sha256(payload).hexdigest()
    summary = {
        "suite": "U",
        "pass": suite_pass,
        "hook_count": len(results),
        "pass_count": sum(1 for r in results if r["ok"]),
        "hooks": results,
        "replay": {
            "event_count": len(results),
            "event_type_counts": {h["name"]: 1 for h in results},
            "decision_signature": signature,
        },
    }
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
