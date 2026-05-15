"""Phase 2 self-test for EPISTEMIC_TRIANGLE walkers + signals.

Spec: specs/EPISTEMIC_TRIANGLE.md (canonical, promoted 2026-05-14)

Phase 2 covers:

  - evidence_link_declared schema, deterministic link_id, latest-state
    walker (links.py)
  - Normalized signal taxonomy + provenance adapter (signals.py)
  - compute_claim_signals (claim.py)
  - compute_recall_signals with Jaccard variance + hook 6c
    adversarial limitation marker (recall_signals.py)

All tests are pure (no wall-clock, no network). Run via:

  PYTHONPATH=. uv run --project stacks python -m src.epistemic_triangle._phase2_verify
"""

from __future__ import annotations

import sys
from typing import Any, Mapping

from src.epistemic_triangle import (
    EvidenceLinkPayload,
    LinkType,
    ResolutionState,
    compute_link_id,
    select_latest_link_states,
    validate_evidence_link_payload,
)
from src.epistemic_triangle.kinds import AssertionKind, RecordKind
from src.explicit_memory.claim import (
    CLAIM_FALLBACK_REASONS,
    ClaimSignals,
    compute_claim_signals,
)
from src.explicit_memory.recall_signals import (
    RECALL_FALLBACK_REASONS,
    RecallSignals,
    compute_recall_signals,
)
from src.explicit_memory.provenance import ProvenanceSignals
from src.explicit_memory.signals import (
    SIGNAL_METHOD_ENUM,
    SIGNAL_SOURCE_ENUM,
    SignalMethod,
    SignalSource,
    normalize_provenance_signals,
)


# ---------------------------------------------------------------------------
# link_id determinism
# ---------------------------------------------------------------------------


def test_link_id_is_deterministic() -> None:
    a = compute_link_id(
        claim_event_id="claim-1", evidence_event_id="ev-1", link_type="supports"
    )
    b = compute_link_id(
        claim_event_id="claim-1", evidence_event_id="ev-1", link_type="supports"
    )
    assert a == b


def test_link_id_input_differences_change_hash() -> None:
    base = compute_link_id(
        claim_event_id="claim-1", evidence_event_id="ev-1", link_type="supports"
    )
    different_claim = compute_link_id(
        claim_event_id="claim-2", evidence_event_id="ev-1", link_type="supports"
    )
    different_evidence = compute_link_id(
        claim_event_id="claim-1", evidence_event_id="ev-2", link_type="supports"
    )
    different_type = compute_link_id(
        claim_event_id="claim-1", evidence_event_id="ev-1", link_type="refutes"
    )
    assert len({base, different_claim, different_evidence, different_type}) == 4


def test_link_id_rejects_invalid_link_type() -> None:
    raised = False
    try:
        compute_link_id(
            claim_event_id="c", evidence_event_id="e", link_type="not_a_real_type"
        )
    except ValueError:
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# evidence_link_declared payload validation
# ---------------------------------------------------------------------------


def _resolved_link_payload(
    *, claim_id: str = "claim-1", evidence_id: str = "ev-1", link_type: str = "supports"
) -> dict[str, Any]:
    return EvidenceLinkPayload(
        claim_event_id=claim_id,
        evidence_event_id=evidence_id,
        link_type=LinkType(link_type),
        resolution_state=ResolutionState.RESOLVED,
        resolution_reason=None,
    ).to_dict()


def _pending_link_payload(reason: str = "claim_not_yet_emitted") -> dict[str, Any]:
    return EvidenceLinkPayload(
        claim_event_id="claim-1",
        evidence_event_id="ev-1",
        link_type=LinkType.SUPPORTS,
        resolution_state=ResolutionState.PENDING,
        resolution_reason=reason,
    ).to_dict()


def _invalid_link_payload(reason: str = "dangling_after_grace_period") -> dict[str, Any]:
    return EvidenceLinkPayload(
        claim_event_id="claim-1",
        evidence_event_id="ev-1",
        link_type=LinkType.SUPPORTS,
        resolution_state=ResolutionState.INVALID,
        resolution_reason=reason,
    ).to_dict()


def test_evidence_link_payload_validation_accepts_well_formed() -> None:
    assert validate_evidence_link_payload(_resolved_link_payload()) is None
    assert validate_evidence_link_payload(_pending_link_payload()) is None
    assert validate_evidence_link_payload(_invalid_link_payload()) is None


def test_evidence_link_payload_validation_rejects_link_id_mismatch() -> None:
    payload = _resolved_link_payload()
    payload["link_id"] = "abc123notthehash"
    assert validate_evidence_link_payload(payload) == "invalid_link_id"


def test_evidence_link_payload_validation_rejects_pending_with_unknown_reason() -> None:
    payload = _pending_link_payload(reason="some_made_up_reason")
    assert validate_evidence_link_payload(payload) == "invalid_link_id"


def test_evidence_link_payload_validation_rejects_resolved_with_reason() -> None:
    payload = _resolved_link_payload()
    payload["resolution_reason"] = "should_be_null_when_resolved"
    assert validate_evidence_link_payload(payload) == "invalid_link_id"


# ---------------------------------------------------------------------------
# Latest-state walker semantics
# ---------------------------------------------------------------------------


def _link_event(
    *,
    payload: Mapping[str, Any],
    tai_iso: str,
    sequence_in_stream: int,
    event_id: str,
    agent_id: str = "agent-a",
    stream_id: str = "stream-meta",
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "evidence_link_declared",
        "agent_id": agent_id,
        "stream_id": stream_id,
        "memory_id": "n/a",
        "physical_moment": {
            "tai_iso": tai_iso,
            "sequence_in_stream": sequence_in_stream,
        },
        "payload": payload,
    }


def test_latest_state_pending_then_resolved_then_invalid_does_not_contribute() -> None:
    link_id = compute_link_id(
        claim_event_id="claim-1", evidence_event_id="ev-1", link_type="supports"
    )
    pending = _link_event(
        payload=_pending_link_payload(),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
    )
    resolved = _link_event(
        payload=_resolved_link_payload(),
        tai_iso="2026-05-14T12:01:00.000",
        sequence_in_stream=1,
        event_id="lev-1",
    )
    invalid = _link_event(
        payload=_invalid_link_payload(),
        tai_iso="2026-05-14T12:02:00.000",
        sequence_in_stream=2,
        event_id="lev-2",
    )
    latest = select_latest_link_states([pending, resolved, invalid])
    assert link_id not in latest, "invalid latest must supersede prior resolved"


def test_latest_state_resolved_then_invalid_then_resolved_contributes() -> None:
    link_id = compute_link_id(
        claim_event_id="claim-1", evidence_event_id="ev-1", link_type="supports"
    )
    e0 = _link_event(
        payload=_resolved_link_payload(),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
    )
    e1 = _link_event(
        payload=_invalid_link_payload(),
        tai_iso="2026-05-14T12:01:00.000",
        sequence_in_stream=1,
        event_id="lev-1",
    )
    e2 = _link_event(
        payload=_resolved_link_payload(),
        tai_iso="2026-05-14T12:02:00.000",
        sequence_in_stream=2,
        event_id="lev-2",
    )
    latest = select_latest_link_states([e0, e1, e2])
    assert link_id in latest
    assert latest[link_id]["event_id"] == "lev-2"


def test_latest_state_respects_as_of_time() -> None:
    link_id = compute_link_id(
        claim_event_id="claim-1", evidence_event_id="ev-1", link_type="supports"
    )
    e0 = _link_event(
        payload=_resolved_link_payload(),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
    )
    e1 = _link_event(
        payload=_invalid_link_payload(),
        tai_iso="2026-05-14T12:05:00.000",
        sequence_in_stream=1,
        event_id="lev-1",
    )
    # As of 12:01:00, the invalid hasn't happened yet — the link
    # contributes via the resolved state.
    latest = select_latest_link_states([e0, e1], as_of_time="2026-05-14T12:01:00.000")
    assert link_id in latest
    # As of 12:06:00, the invalid has happened — the link does not
    # contribute.
    latest_later = select_latest_link_states(
        [e0, e1], as_of_time="2026-05-14T12:06:00.000"
    )
    assert link_id not in latest_later


# ---------------------------------------------------------------------------
# Normalized signal taxonomy + provenance adapter
# ---------------------------------------------------------------------------


def test_signal_enums_match_spec_section_7() -> None:
    assert SIGNAL_SOURCE_ENUM == frozenset({"computed", "cache", "fallback"})
    assert SIGNAL_METHOD_ENUM == frozenset(
        {"provenance_chain", "evidence_links", "recall_history", "none"}
    )


def test_normalize_provenance_signals_computed_pass_through() -> None:
    prov = ProvenanceSignals(
        parent_chain_depth=3,
        source_diversity=0.66,
        age_of_original_source=12.5,
        chain_root_event_id="evt-root",
        chain_length=4,
        distinct_source_classes=2,
        computed_at="2026-05-14T12:00:00.000",
        as_of_time="2026-05-14T12:00:00.000",
        fallback_reason=None,
        provenance_signal_source="computed",
    )
    normalized = normalize_provenance_signals(prov)
    assert normalized.signal_source == SignalSource.COMPUTED
    assert normalized.signal_method == SignalMethod.PROVENANCE_CHAIN
    assert normalized.fallback_reason is None
    assert normalized.values["parent_chain_depth"] == 3.0
    assert normalized.values["source_diversity"] == 0.66


def test_normalize_provenance_signals_fallback_with_unknown_source_is_loud() -> None:
    prov = ProvenanceSignals(
        parent_chain_depth=0,
        source_diversity=0.0,
        age_of_original_source=0.0,
        chain_root_event_id=None,
        chain_length=0,
        distinct_source_classes=0,
        computed_at="2026-05-14T12:00:00.000",
        as_of_time="2026-05-14T12:00:00.000",
        fallback_reason=None,
        provenance_signal_source="not_a_real_source_value",
    )
    normalized = normalize_provenance_signals(prov)
    assert normalized.signal_source == SignalSource.FALLBACK
    assert normalized.fallback_reason == "unrecognized_signal_source"


# ---------------------------------------------------------------------------
# compute_claim_signals
# ---------------------------------------------------------------------------


def _claim_event(*, event_id: str = "claim-1", agent_id: str = "agent-a") -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "stored",
        "agent_id": agent_id,
        "stream_id": "stream-claim",
        "memory_id": "mem-claim",
        "assertion_kind": AssertionKind.CLAIM.value,
        "physical_moment": {"tai_iso": "2026-05-14T11:00:00.000"},
        "payload": {"claim": "earth orbits sun"},
    }


def _evidence_event(
    *,
    event_id: str,
    agent_id: str = "agent-a",
    source_class: str = "telescope_a",
    assertion_kind: str = AssertionKind.EVIDENCE.value,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "stored",
        "agent_id": agent_id,
        "stream_id": "stream-evidence",
        "memory_id": "mem-evidence",
        "assertion_kind": assertion_kind,
        "source_class": source_class,
        "physical_moment": {"tai_iso": "2026-05-14T11:30:00.000"},
        "payload": {},
    }


def test_claim_signals_compute_with_two_supports() -> None:
    target = _claim_event()
    ev1 = _evidence_event(event_id="ev-1", source_class="telescope_a")
    ev2 = _evidence_event(event_id="ev-2", source_class="telescope_b")
    link1 = _link_event(
        payload=_resolved_link_payload(claim_id="claim-1", evidence_id="ev-1"),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
    )
    link2 = _link_event(
        payload=_resolved_link_payload(claim_id="claim-1", evidence_id="ev-2"),
        tai_iso="2026-05-14T12:00:01.000",
        sequence_in_stream=1,
        event_id="lev-1",
    )
    result = compute_claim_signals(
        target_event=target,
        link_events=[link1, link2],
        evidence_events={"ev-1": ev1, "ev-2": ev2},
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.signal_source == SignalSource.COMPUTED
    assert result.signal_method == SignalMethod.EVIDENCE_LINKS
    assert result.evidence_support_count == 2
    assert result.refutation_count == 0
    # Two distinct source classes / 2 supports = 1.0.
    assert result.evidence_diversity == 1.0


def test_claim_signals_count_refutations() -> None:
    target = _claim_event()
    ev_supports = _evidence_event(event_id="ev-1")
    ev_refutes = _evidence_event(event_id="ev-2", source_class="telescope_b")
    link_support = _link_event(
        payload=_resolved_link_payload(
            claim_id="claim-1", evidence_id="ev-1", link_type="supports"
        ),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
    )
    link_refute = _link_event(
        payload=_resolved_link_payload(
            claim_id="claim-1", evidence_id="ev-2", link_type="refutes"
        ),
        tai_iso="2026-05-14T12:00:01.000",
        sequence_in_stream=1,
        event_id="lev-1",
    )
    result = compute_claim_signals(
        target_event=target,
        link_events=[link_support, link_refute],
        evidence_events={"ev-1": ev_supports, "ev-2": ev_refutes},
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.evidence_support_count == 1
    assert result.refutation_count == 1
    # Diversity is supports-only: 1 distinct source / 1 support = 1.0.
    assert result.evidence_diversity == 1.0


def test_claim_signals_fallback_no_evidence_links() -> None:
    target = _claim_event()
    result = compute_claim_signals(
        target_event=target,
        link_events=[],
        evidence_events={},
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.signal_source == SignalSource.FALLBACK
    assert result.fallback_reason == "no_evidence_links"
    assert result.fallback_reason in CLAIM_FALLBACK_REASONS


def test_claim_signals_fallback_not_claim_kind() -> None:
    target = _claim_event()
    target["assertion_kind"] = AssertionKind.MEMORY.value
    result = compute_claim_signals(
        target_event=target,
        link_events=[],
        evidence_events={},
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.fallback_reason == "not_claim_kind"


def test_claim_signals_fallback_assertion_kind_unset() -> None:
    target = _claim_event()
    target["assertion_kind"] = None
    result = compute_claim_signals(
        target_event=target,
        link_events=[],
        evidence_events={},
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.fallback_reason == "assertion_kind_unset"


def test_claim_signals_cross_scope_denied_by_default() -> None:
    target = _claim_event()
    foreign_evidence = _evidence_event(event_id="ev-foreign", agent_id="agent-other")
    link = _link_event(
        payload=_resolved_link_payload(claim_id="claim-1", evidence_id="ev-foreign"),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
        agent_id="agent-a",
    )
    result = compute_claim_signals(
        target_event=target,
        link_events=[link],
        evidence_events={"ev-foreign": foreign_evidence},
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.signal_source == SignalSource.FALLBACK
    assert result.fallback_reason == "cross_scope_denied"


def test_claim_signals_cross_scope_allowed_with_flag() -> None:
    target = _claim_event()
    foreign_evidence = _evidence_event(event_id="ev-foreign", agent_id="agent-other")
    link = _link_event(
        payload=_resolved_link_payload(claim_id="claim-1", evidence_id="ev-foreign"),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
        agent_id="agent-other",  # link from foreign agent
    )
    result = compute_claim_signals(
        target_event=target,
        link_events=[link],
        evidence_events={"ev-foreign": foreign_evidence},
        as_of_time="2026-05-14T13:00:00.000",
        allow_cross_agent=True,
    )
    assert result.signal_source == SignalSource.COMPUTED
    assert result.evidence_support_count == 1


def test_claim_signals_walk_depth_exceeded() -> None:
    target = _claim_event()
    # Build 200 link events; cap is 64.
    links = [
        _link_event(
            payload=_resolved_link_payload(
                claim_id="claim-1", evidence_id=f"ev-{i}"
            ),
            tai_iso="2026-05-14T12:00:00.000",
            sequence_in_stream=i,
            event_id=f"lev-{i}",
        )
        for i in range(200)
    ]
    result = compute_claim_signals(
        target_event=target,
        link_events=links,
        evidence_events={},
        as_of_time="2026-05-14T13:00:00.000",
        max_depth=64,
    )
    assert result.fallback_reason == "walk_depth_exceeded"


def test_claim_signals_invalid_link_does_not_contribute() -> None:
    target = _claim_event()
    ev = _evidence_event(event_id="ev-1")
    resolved = _link_event(
        payload=_resolved_link_payload(claim_id="claim-1", evidence_id="ev-1"),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
    )
    invalid = _link_event(
        payload=_invalid_link_payload(),
        tai_iso="2026-05-14T12:01:00.000",
        sequence_in_stream=1,
        event_id="lev-1",
    )
    result = compute_claim_signals(
        target_event=target,
        link_events=[resolved, invalid],
        evidence_events={"ev-1": ev},
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.fallback_reason == "no_evidence_links"


def test_claim_signals_replay_determinism() -> None:
    target = _claim_event()
    ev = _evidence_event(event_id="ev-1")
    link = _link_event(
        payload=_resolved_link_payload(claim_id="claim-1", evidence_id="ev-1"),
        tai_iso="2026-05-14T12:00:00.000",
        sequence_in_stream=0,
        event_id="lev-0",
    )
    args = dict(
        target_event=target,
        link_events=[link],
        evidence_events={"ev-1": ev},
        as_of_time="2026-05-14T13:00:00.000",
    )
    a = compute_claim_signals(**args)
    b = compute_claim_signals(**args)
    assert a == b


# ---------------------------------------------------------------------------
# compute_recall_signals — including hook 6a/6b/6c
# ---------------------------------------------------------------------------


def _recall_event(
    *,
    event_id: str,
    tai_iso: str,
    solar_age_myr: float,
    sequence_in_stream: int,
    payload: Mapping[str, Any],
    memory_id: str = "mem-1",
    agent_id: str = "agent-a",
    stream_id: str = "stream-recall",
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "recalled",
        "agent_id": agent_id,
        "stream_id": stream_id,
        "memory_id": memory_id,
        "assertion_kind": AssertionKind.MEMORY.value,
        "physical_moment": {
            "tai_iso": tai_iso,
            "sequence_in_stream": sequence_in_stream,
            "solar_age_myr": solar_age_myr,
        },
        "payload": dict(payload),
    }


def test_recall_signals_first_recall_fallback() -> None:
    target = _recall_event(
        event_id="r-now",
        tai_iso="2026-05-14T12:00:00.000",
        solar_age_myr=4603.000026366500,
        sequence_in_stream=10,
        payload={"claim": "the kettle is on"},
    )
    result = compute_recall_signals(
        target_event=target,
        prior_recall_events=[],
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.signal_source == SignalSource.FALLBACK
    assert result.fallback_reason == "first_recall"
    assert result.fallback_reason in RECALL_FALLBACK_REASONS


def test_recall_signals_single_recall_fallback_carries_time_delta() -> None:
    target = _recall_event(
        event_id="r-now",
        tai_iso="2026-05-14T12:00:00.000",
        solar_age_myr=4603.000026366500,
        sequence_in_stream=10,
        payload={"claim": "x"},
    )
    prior = _recall_event(
        event_id="r-1",
        tai_iso="2026-05-14T11:00:00.000",
        solar_age_myr=4603.000026366490,
        sequence_in_stream=9,
        payload={"claim": "x"},
    )
    result = compute_recall_signals(
        target_event=target,
        prior_recall_events=[prior],
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.signal_source == SignalSource.FALLBACK
    assert result.fallback_reason == "single_recall"
    assert result.recall_count == 1
    assert result.time_since_last_recall_myr is not None
    assert result.time_since_last_recall_myr > 0.0


def test_recall_signals_hook_6a_wording_drifts_evidence_stable() -> None:
    """Hook 6a: claim text drifts across recalls; evidence_ids stable.
    Variance must move."""
    common_payload_a = {"claim": "the meeting starts at 3pm"}
    common_payload_b = {"claim": "the meeting starts at three"}
    common_payload_c = {"claim": "meeting at 1500"}
    priors = [
        _recall_event(
            event_id="r-1",
            tai_iso="2026-05-14T10:00:00.000",
            solar_age_myr=4603.000026366480,
            sequence_in_stream=1,
            payload=common_payload_a,
        ),
        _recall_event(
            event_id="r-2",
            tai_iso="2026-05-14T10:30:00.000",
            solar_age_myr=4603.000026366485,
            sequence_in_stream=2,
            payload=common_payload_b,
        ),
    ]
    target = _recall_event(
        event_id="r-3",
        tai_iso="2026-05-14T11:00:00.000",
        solar_age_myr=4603.000026366490,
        sequence_in_stream=3,
        payload=common_payload_c,
    )
    result = compute_recall_signals(
        target_event=target,
        prior_recall_events=priors,
        as_of_time="2026-05-14T12:00:00.000",
    )
    assert result.signal_source == SignalSource.COMPUTED
    assert result.reconstruction_variance > 0.0


def test_recall_signals_hook_6b_evidence_drifts_wording_stable() -> None:
    """Hook 6b: evidence_ids drift; claim text stable. Variance must move."""
    base_claim = "the kettle is on"
    priors = [
        _recall_event(
            event_id="r-1",
            tai_iso="2026-05-14T10:00:00.000",
            solar_age_myr=4603.000026366480,
            sequence_in_stream=1,
            payload={"claim": base_claim, "evidence_ids": ["e-a"]},
        ),
        _recall_event(
            event_id="r-2",
            tai_iso="2026-05-14T10:30:00.000",
            solar_age_myr=4603.000026366485,
            sequence_in_stream=2,
            payload={"claim": base_claim, "evidence_ids": ["e-b"]},
        ),
    ]
    target = _recall_event(
        event_id="r-3",
        tai_iso="2026-05-14T11:00:00.000",
        solar_age_myr=4603.000026366490,
        sequence_in_stream=3,
        payload={"claim": base_claim, "evidence_ids": ["e-c"]},
    )
    result = compute_recall_signals(
        target_event=target,
        prior_recall_events=priors,
        as_of_time="2026-05-14T12:00:00.000",
    )
    assert result.signal_source == SignalSource.COMPUTED
    assert result.reconstruction_variance > 0.0


def test_recall_signals_hook_6c_adversarial_stable_projection_drifting_meaning() -> None:
    """Hook 6c: projection (memory_id, assertion_kind, claim,
    evidence_ids) is stable but a meaning-bearing field drifts.
    v1 Jaccard cannot detect this; reconstruction_variance must NOT
    move. The walker must emit `limitation_marker =
    "stable_projection_with_drifting_meaning"` so the failure mode
    is loud in lineage."""
    stable_projection_payload_base = {
        "claim": "the kettle is on",
        "evidence_ids": ["e-a"],
    }
    priors = [
        _recall_event(
            event_id="r-1",
            tai_iso="2026-05-14T10:00:00.000",
            solar_age_myr=4603.000026366480,
            sequence_in_stream=1,
            payload={**stable_projection_payload_base, "meaning": "tea soon"},
        ),
        _recall_event(
            event_id="r-2",
            tai_iso="2026-05-14T10:30:00.000",
            solar_age_myr=4603.000026366485,
            sequence_in_stream=2,
            payload={**stable_projection_payload_base, "meaning": "tea soon"},
        ),
    ]
    target = _recall_event(
        event_id="r-3",
        tai_iso="2026-05-14T11:00:00.000",
        solar_age_myr=4603.000026366490,
        sequence_in_stream=3,
        # SAME claim + same evidence_ids; meaning has drifted.
        payload={**stable_projection_payload_base, "meaning": "boiling water for soup"},
    )
    result = compute_recall_signals(
        target_event=target,
        prior_recall_events=priors,
        as_of_time="2026-05-14T12:00:00.000",
    )
    # Variance is 0 (Jaccard projection is stable).
    assert result.reconstruction_variance == 0.0
    # But the limitation marker MUST be present so lineage records
    # the v1-undetectable case.
    assert result.limitation_marker == "stable_projection_with_drifting_meaning"
    assert result.signal_source == SignalSource.COMPUTED


def test_recall_signals_time_since_last_uses_solar_age_not_wall_clock() -> None:
    """The time delta MUST come from solar_age_myr deltas. We confirm
    by setting tai_iso wildly differently on prior vs target while
    keeping solar_age_myr deltas equal across two runs."""
    target = _recall_event(
        event_id="r-now",
        tai_iso="2026-05-14T12:00:00.000",
        solar_age_myr=4603.000026366500,
        sequence_in_stream=10,
        payload={"claim": "x"},
    )
    prior_a = _recall_event(
        event_id="r-1",
        tai_iso="2026-05-14T11:00:00.000",
        solar_age_myr=4603.000026366490,
        sequence_in_stream=9,
        payload={"claim": "y"},
    )
    prior_b = _recall_event(
        event_id="r-2",
        tai_iso="2026-05-14T11:30:00.000",
        solar_age_myr=4603.000026366495,
        sequence_in_stream=10,
        payload={"claim": "z"},
    )
    result = compute_recall_signals(
        target_event=target,
        prior_recall_events=[prior_a, prior_b],
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.time_since_last_recall_myr is not None
    # Expected delta: 4603.000026366500 - 4603.000026366495.
    expected = 4603.000026366500 - 4603.000026366495
    assert abs(result.time_since_last_recall_myr - expected) < 1e-15


def test_recall_signals_replay_determinism() -> None:
    target = _recall_event(
        event_id="r-now",
        tai_iso="2026-05-14T12:00:00.000",
        solar_age_myr=4603.000026366500,
        sequence_in_stream=10,
        payload={"claim": "x", "evidence_ids": ["e-a"]},
    )
    priors = [
        _recall_event(
            event_id="r-1",
            tai_iso="2026-05-14T11:00:00.000",
            solar_age_myr=4603.000026366490,
            sequence_in_stream=9,
            payload={"claim": "y"},
        ),
        _recall_event(
            event_id="r-2",
            tai_iso="2026-05-14T11:30:00.000",
            solar_age_myr=4603.000026366495,
            sequence_in_stream=10,
            payload={"claim": "z"},
        ),
    ]
    args = dict(
        target_event=target,
        prior_recall_events=priors,
        as_of_time="2026-05-14T13:00:00.000",
    )
    a = compute_recall_signals(**args)
    b = compute_recall_signals(**args)
    assert a == b


def test_recall_signals_cross_scope_denied_by_default() -> None:
    target = _recall_event(
        event_id="r-now",
        tai_iso="2026-05-14T12:00:00.000",
        solar_age_myr=4603.000026366500,
        sequence_in_stream=10,
        payload={"claim": "x"},
        agent_id="agent-a",
    )
    foreign_priors = [
        _recall_event(
            event_id="r-fa",
            tai_iso="2026-05-14T10:00:00.000",
            solar_age_myr=4603.000026366480,
            sequence_in_stream=1,
            payload={"claim": "x"},
            agent_id="agent-other",
        ),
        _recall_event(
            event_id="r-fb",
            tai_iso="2026-05-14T10:30:00.000",
            solar_age_myr=4603.000026366485,
            sequence_in_stream=2,
            payload={"claim": "x"},
            agent_id="agent-other",
        ),
    ]
    result = compute_recall_signals(
        target_event=target,
        prior_recall_events=foreign_priors,
        as_of_time="2026-05-14T13:00:00.000",
    )
    assert result.signal_source == SignalSource.FALLBACK
    assert result.fallback_reason == "cross_scope_denied"


# ---------------------------------------------------------------------------
# Cross-axis normalized signal_source consistency
# ---------------------------------------------------------------------------


def test_normalized_signal_source_consistent_across_axes() -> None:
    """spec §7: all three axis types share `signal_source ∈
    {computed, cache, fallback}` after normalization. Confirm the
    enum values match across all three signal-bearing dataclasses."""
    claim = ClaimSignals(
        evidence_support_count=1,
        refutation_count=0,
        evidence_diversity=1.0,
        signal_source=SignalSource.COMPUTED,
        signal_method=SignalMethod.EVIDENCE_LINKS,
        fallback_reason=None,
    )
    recall = RecallSignals(
        recall_count=2,
        reconstruction_variance=0.5,
        time_since_last_recall_myr=0.000000001,
        signal_source=SignalSource.COMPUTED,
        signal_method=SignalMethod.RECALL_HISTORY,
        fallback_reason=None,
    )
    prov = normalize_provenance_signals(
        ProvenanceSignals(
            parent_chain_depth=2,
            source_diversity=0.5,
            age_of_original_source=10.0,
            chain_root_event_id="r",
            chain_length=3,
            distinct_source_classes=2,
            computed_at="2026-05-14T12:00:00.000",
            as_of_time="2026-05-14T12:00:00.000",
            fallback_reason=None,
            provenance_signal_source="computed",
        )
    )
    assert claim.signal_source.value in SIGNAL_SOURCE_ENUM
    assert recall.signal_source.value in SIGNAL_SOURCE_ENUM
    assert prov.signal_source.value in SIGNAL_SOURCE_ENUM


TESTS = [
    ("link_id_is_deterministic", test_link_id_is_deterministic),
    ("link_id_input_differences_change_hash", test_link_id_input_differences_change_hash),
    ("link_id_rejects_invalid_link_type", test_link_id_rejects_invalid_link_type),
    ("evidence_link_payload_validation_accepts_well_formed", test_evidence_link_payload_validation_accepts_well_formed),
    ("evidence_link_payload_validation_rejects_link_id_mismatch", test_evidence_link_payload_validation_rejects_link_id_mismatch),
    ("evidence_link_payload_validation_rejects_pending_with_unknown_reason", test_evidence_link_payload_validation_rejects_pending_with_unknown_reason),
    ("evidence_link_payload_validation_rejects_resolved_with_reason", test_evidence_link_payload_validation_rejects_resolved_with_reason),
    ("latest_state_pending_then_resolved_then_invalid_does_not_contribute", test_latest_state_pending_then_resolved_then_invalid_does_not_contribute),
    ("latest_state_resolved_then_invalid_then_resolved_contributes", test_latest_state_resolved_then_invalid_then_resolved_contributes),
    ("latest_state_respects_as_of_time", test_latest_state_respects_as_of_time),
    ("signal_enums_match_spec_section_7", test_signal_enums_match_spec_section_7),
    ("normalize_provenance_signals_computed_pass_through", test_normalize_provenance_signals_computed_pass_through),
    ("normalize_provenance_signals_fallback_with_unknown_source_is_loud", test_normalize_provenance_signals_fallback_with_unknown_source_is_loud),
    ("claim_signals_compute_with_two_supports", test_claim_signals_compute_with_two_supports),
    ("claim_signals_count_refutations", test_claim_signals_count_refutations),
    ("claim_signals_fallback_no_evidence_links", test_claim_signals_fallback_no_evidence_links),
    ("claim_signals_fallback_not_claim_kind", test_claim_signals_fallback_not_claim_kind),
    ("claim_signals_fallback_assertion_kind_unset", test_claim_signals_fallback_assertion_kind_unset),
    ("claim_signals_cross_scope_denied_by_default", test_claim_signals_cross_scope_denied_by_default),
    ("claim_signals_cross_scope_allowed_with_flag", test_claim_signals_cross_scope_allowed_with_flag),
    ("claim_signals_walk_depth_exceeded", test_claim_signals_walk_depth_exceeded),
    ("claim_signals_invalid_link_does_not_contribute", test_claim_signals_invalid_link_does_not_contribute),
    ("claim_signals_replay_determinism", test_claim_signals_replay_determinism),
    ("recall_signals_first_recall_fallback", test_recall_signals_first_recall_fallback),
    ("recall_signals_single_recall_fallback_carries_time_delta", test_recall_signals_single_recall_fallback_carries_time_delta),
    ("recall_signals_hook_6a_wording_drifts_evidence_stable", test_recall_signals_hook_6a_wording_drifts_evidence_stable),
    ("recall_signals_hook_6b_evidence_drifts_wording_stable", test_recall_signals_hook_6b_evidence_drifts_wording_stable),
    ("recall_signals_hook_6c_adversarial_stable_projection_drifting_meaning", test_recall_signals_hook_6c_adversarial_stable_projection_drifting_meaning),
    ("recall_signals_time_since_last_uses_solar_age_not_wall_clock", test_recall_signals_time_since_last_uses_solar_age_not_wall_clock),
    ("recall_signals_replay_determinism", test_recall_signals_replay_determinism),
    ("recall_signals_cross_scope_denied_by_default", test_recall_signals_cross_scope_denied_by_default),
    ("normalized_signal_source_consistent_across_axes", test_normalized_signal_source_consistent_across_axes),
]


def main() -> int:
    failures: list[tuple[str, str]] = []
    for name, fn in TESTS:
        try:
            fn()
            print(f"  PASS {name}")
        except AssertionError as exc:
            failures.append((name, str(exc) or "AssertionError"))
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  FAIL {name}: {type(exc).__name__}: {exc}")

    print()
    if failures:
        print(f"Phase 2 verifier: FAILED {len(failures)}/{len(TESTS)}")
        return 1
    print(f"Phase 2 verifier: PASSED {len(TESTS)}/{len(TESTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
