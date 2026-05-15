"""Closed quarantine reason additions for v7.

Spec: specs/EPISTEMIC_TRIANGLE.md §12

These reasons are deterministic strings emitted by ingestion and
validators when v7 envelope rules are violated. The closed enum
prevents audit drift; new reasons require a spec amendment.

This module defines only the v7 ADDITIONS. The full quarantine enum
is the union of v6 reasons (in TAI_TIMEKEEPING and earlier specs)
and these.
"""

from __future__ import annotations


V7_QUARANTINE_REASONS: frozenset[str] = frozenset({
    # record_kind / assertion_kind envelope rules (§3.6)
    "missing_record_kind",
    "invalid_record_kind",
    "missing_assertion_kind_for_record_kind",
    "reality_observation_outside_observation_event",
    "invalid_assertion_kind",
    "unmapped_event_type",
    # Subject classification on decision events (§3.3, §3.6)
    "missing_subject_assertion_kind",
    "subject_kind_mismatch",
    # Legacy field removal (§8)
    "legacy_event_time_present",
    # evidence_link_declared (§4)
    "invalid_link_id",
    "evidence_link_claim_kind_mismatch",
    "evidence_link_evidence_kind_mismatch",
    "evidence_link_dangling_after_grace_period",
})
