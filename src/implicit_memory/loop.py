from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.config import AwsConfig
from src.implicit_memory.admission import admission_score
from src.implicit_memory.controller import ObservationSignals, process_observation
from src.implicit_memory.eligibility import eligibility_gate
from src.implicit_memory.policy_mutation import PolicyState, supersede_procedure, update_threshold
from src.implicit_memory.procedure_lifecycle import (
    ProcedureState,
    apply_urgency_trust_decay,
    decay_procedure,
    reinforce_procedure,
)
from src.implicit_memory.procedure_state_store import ProcedureStateStore
from src.implicit_memory.reflex_mode import ReflexController
from src.implicit_memory.reasons import ImplicitReason
from src.implicit_memory.scheduler import ScheduledCue, due_cues, escalation_level, now_utc
from src.implicit_memory.cue_ingest import Cue


class ProvenanceResolver(Protocol):
    def resolve(self, *, memory_id: str, stream_id: str, as_of_time: str) -> dict[str, object]: ...


class CapturedCueProvider(Protocol):
    """The loop's single input contract (CONTROL_PLANE_INGEST Decision 2).

    Yields captured control-plane cues. A live provider drains
    `control_cue_ingested` events from canonical lineage; a fixture
    provider yields the same `Cue` shape directly. The loop cannot tell
    them apart — one contract, two sources.
    """

    def pull(self, *, now: datetime) -> list[Cue]: ...


class LineageEmitter(Protocol):
    def emit(
        self,
        *,
        event_type: str,
        agent_id: str,
        stream_id: str,
        memory_id: str,
        payload: dict,
        actor_class: str = "implicit_memory_controller",
        source_class: str = "internal_engine",
        parent_event_id: str | None = None,
        # v7 EPISTEMIC_TRIANGLE envelope additions; emitters may
        # ignore these for non-decision events.
        record_kind: str | None = None,
        assertion_kind: str | None = None,
        subject_event_id: str | None = None,
        subject_record_kind: str | None = None,
        subject_assertion_kind: str | None = None,
    ): ...


@dataclass
class LoopStats:
    observations_processed: int = 0
    observation_fired: int = 0
    observation_deferred: int = 0
    observation_admitted: int = 0
    observation_rejected: int = 0
    reflex_entered: int = 0
    reflex_blocked: int = 0
    cues_due: int = 0
    cues_fired: int = 0
    cues_admitted: int = 0
    cues_deferred: int = 0
    contamination_suspected: int = 0
    replay_event_count: int = 0

    def to_dict(self) -> dict:
        return {
            "observations_processed": self.observations_processed,
            "observation_fired": self.observation_fired,
            "observation_deferred": self.observation_deferred,
            "observation_admitted": self.observation_admitted,
            "observation_rejected": self.observation_rejected,
            "reflex_entered": self.reflex_entered,
            "reflex_blocked": self.reflex_blocked,
            "cues_due": self.cues_due,
            "cues_fired": self.cues_fired,
            "cues_admitted": self.cues_admitted,
            "cues_deferred": self.cues_deferred,
            "contamination_suspected": self.contamination_suspected,
            "replay_event_count": self.replay_event_count,
        }


class ImplicitControllerLoop:
    def _subject_classification_for_memory(self, memory_id: str) -> dict[str, str]:
        """Build the v7 subject classification envelope for a
        decision event whose subject is a memory_id.

        Delegates to `src.epistemic_triangle.memory_subject_placeholder`
        — the shared deterministic placeholder per EPISTEMIC_TRIANGLE
        §3.3 + the v1.2 promotion-review caution #3. The payload
        also gets `subject_kind_source: "v1_default"` so audits
        distinguish defaulted-from-derived (no silent provider fill).
        """
        from src.epistemic_triangle import memory_subject_placeholder

        return memory_subject_placeholder(memory_id)

    def _emit_rejected(self, *, memory_id: str, reason: str, **extra_payload: object) -> None:
        payload: dict[str, object] = {"reason": reason}
        payload.update(extra_payload)
        # Mark subject classification as v1 default when an
        # uncertainty_triple is present (decision is axis-bearing).
        if "uncertainty_triple" in extra_payload:
            payload.setdefault("subject_kind_source", "v1_default")
        subject = self._subject_classification_for_memory(memory_id)
        self.lineage.emit(
            event_type="implicit_rejected",
            agent_id=self.agent_id,
            stream_id=self.stream_id,
            memory_id=memory_id,
            actor_class="implicit_memory_controller",
            source_class="internal_engine",
            payload=payload,
            **subject,
        )

    def _build_v7_axis_signals(self, *, memory_id: str, gate_inputs: dict[str, float]):
        """Construct the three NormalizedSignals the v7 gate expects.

        Per EPISTEMIC_TRIANGLE §11, `signal is None` is only allowed
        on pre-v7 paths. v7 emit paths must supply signals.

        - **Provenance**: the upstream resolver already computed
          `parent_chain_depth` / `source_diversity` /
          `age_of_original_source` and placed them on `gate_inputs`,
          so we package those as `signal_source = "computed"`.
        - **Claim**: this loop has no in-scope lineage reader for
          `evidence_link_declared` events, so the walker is called
          with an empty link set. It returns a `fallback` signal
          (`no_evidence_links`). The gate applies the fallback
          multiplier and the payload surfaces axis_fallback_used.
        - **Recall**: same shape — no prior `recalled` events in
          scope; walker returns `first_recall` fallback.

        Phase 5 (control-plane ingest) wires real walkers in when
        the loop gains lineage-reader access.
        """
        from src.explicit_memory.claim import compute_claim_signals
        from src.explicit_memory.recall_signals import compute_recall_signals
        from src.explicit_memory.signals import (
            NormalizedSignals,
            SignalMethod,
            SignalSource,
        )

        as_of_time = self._loop_tick_tai_iso()

        # Provenance — resolver-computed, packaged as NormalizedSignals.
        prov = NormalizedSignals(
            signal_source=SignalSource.COMPUTED,
            signal_method=SignalMethod.PROVENANCE_CHAIN,
            fallback_reason=None,
            values={
                "parent_chain_depth": float(gate_inputs.get("parent_chain_depth", 0.0)),
                "source_diversity": float(gate_inputs.get("source_diversity", 1.0)),
                "age_of_original_source": float(gate_inputs.get("age_of_original_source", 0.0)),
            },
        )

        # Claim — empty link inputs → fallback("no_evidence_links").
        claim_target = {
            "event_id": f"loop-target:{memory_id}",
            "agent_id": self.agent_id,
            "assertion_kind": "claim",
        }
        claim = compute_claim_signals(
            target_event=claim_target,
            link_events=[],
            evidence_events={},
            as_of_time=as_of_time,
        )

        # Recall — empty prior recalls → fallback("first_recall").
        recall_target = {
            "event_type": "recalled",
            "memory_id": memory_id,
            "agent_id": self.agent_id,
            "assertion_kind": "memory",
            "physical_moment": {"tai_iso": as_of_time, "solar_age_myr": 0.0},
            "payload": {},
        }
        recall = compute_recall_signals(
            target_event=recall_target,
            prior_recall_events=[],
            as_of_time=as_of_time,
        )

        return claim, recall, prov

    def _loop_tick_tai_iso(self) -> str:
        """Return a TAI ISO string for this loop tick. Loop callers
        plumb the tick moment via the controller; for in-memory
        regression suites we fall back to a fixed anchor to keep
        replay deterministic (never wall-clock)."""
        anchor = getattr(self, "_tick_tai_iso", None)
        if anchor:
            return str(anchor)
        # Same fixed anchor InMemoryLineageEngine uses by default.
        return "2026-05-13T12:00:00.000"

    def _admit_and_gate(
        self,
        *,
        memory_id: str,
        source_class: str,
        admission_value: float,
        gate_inputs: dict[str, float],
        admission_reason: str | None = None,
    ) -> bool:
        if admission_value < self.policy_state.threshold_map["admission_threshold"]:
            self._emit_rejected(
                memory_id=memory_id,
                reason=ImplicitReason.LOW_SIGNIFICANCE.value,
                admission_score=admission_value,
            )
            return False

        admitted_payload: dict[str, object] = {"admission_score": admission_value}
        if admission_reason:
            admitted_payload["reason"] = admission_reason

        # v7 EPISTEMIC_TRIANGLE §11: the live emit path supplies axis
        # signals to the gate. With current loop scope, claim and
        # recall fall back; provenance is resolver-computed and
        # passes through as `signal_source = "computed"`. The gate
        # surfaces the per-axis fallback markers in the decision
        # payload (visible to spec §11 hook 8).
        claim_signals, recall_signals, prov_signals = self._build_v7_axis_signals(
            memory_id=memory_id, gate_inputs=gate_inputs,
        )

        gate = eligibility_gate(
            relevance=gate_inputs["relevance"],
            trust=gate_inputs["trust"],
            recency=gate_inputs["recency"],
            reinforcement=gate_inputs["reinforcement"],
            consistency=gate_inputs["consistency"],
            safety=gate_inputs["safety"],
            threshold=self.policy_state.threshold_map["eligibility_threshold"],
            parent_chain_depth=gate_inputs.get("parent_chain_depth", 0.0),
            source_diversity=gate_inputs.get("source_diversity", 1.0),
            age_of_original_source=gate_inputs.get("age_of_original_source", 0.0),
            gate_mode=self.cfg.retrieval_policy.uncertainty_gate_mode,
            combined_threshold=self.cfg.retrieval_policy.uncertainty_combined_threshold,
            claim_threshold=self.cfg.retrieval_policy.uncertainty_claim_threshold,
            recall_process_threshold=self.cfg.retrieval_policy.uncertainty_recall_process_threshold,
            provenance_chain_threshold=self.cfg.retrieval_policy.uncertainty_provenance_chain_threshold,
            safety_floor=self.cfg.retrieval_policy.uncertainty_safety_floor,
            claim_signals=claim_signals,
            recall_signals=recall_signals,
            provenance_signals=prov_signals,
        )

        admitted_payload.update(
            {
                "eligibility_score": gate.score,
                "uncertainty_triple": {
                    "confidence_in_claim": gate.uncertainty_triple.confidence_in_claim,
                    "confidence_in_recall_process": gate.uncertainty_triple.confidence_in_recall_process,
                    "confidence_in_provenance_chain": gate.uncertainty_triple.confidence_in_provenance_chain,
                },
                "combined_score": gate.combined_score,
                "dominant_axis": gate.dominant_axis,
                "provenance_signals": {
                    "parent_chain_depth": gate_inputs.get("parent_chain_depth", 0.0),
                    "source_diversity": gate_inputs.get("source_diversity", 1.0),
                    "age_of_original_source": gate_inputs.get("age_of_original_source", 0.0),
                },
                # v7 exit-criteria visibility: carry the normalized
                # per-axis signal blocks on decision payloads so
                # audits can prove source lineage for claim/recall/
                # provenance on a single admitted decision.
                "claim_signals": claim_signals.as_payload(),
                "recall_signals": recall_signals.as_payload(),
                "provenance_signal": prov_signals.to_payload(),
                "uncertainty_gate_mode": gate.gate_mode,
                # v7 EPISTEMIC_TRIANGLE: mark subject classification
                # as v1 default so audits know it's not derived.
                "subject_kind_source": "v1_default",
                # v7 §11: per-axis fallback visibility. When any axis
                # falls back, the multiplier the gate applied and
                # the closed-enum reason per axis are loud in lineage.
                "axis_fallback_used": dict(gate.uncertainty_triple.axis_fallback_used),
                "axis_fallback_reasons": dict(gate.uncertainty_triple.axis_fallback_reasons),
                "policy_fallback_multiplier": gate.uncertainty_triple.policy_fallback_multiplier,
                # v7 §11.1: every v7 decision payload names which
                # scoring function produced it. Audits use this to
                # verify score_candidate retirement at decision
                # time, not only via static check.
                "scoring_function": "score_triple",
            }
        )

        admitted_subject = self._subject_classification_for_memory(memory_id)
        self.lineage.emit(
            event_type="implicit_admitted",
            agent_id=self.agent_id,
            stream_id=self.stream_id,
            memory_id=memory_id,
            actor_class="implicit_memory_controller",
            source_class=source_class,
            payload=admitted_payload,
            **admitted_subject,
        )

        if not gate.allow_influence:
            self._emit_rejected(
                memory_id=memory_id,
                reason=gate.reason,
                eligibility_score=gate.score,
                uncertainty_triple={
                    "confidence_in_claim": gate.uncertainty_triple.confidence_in_claim,
                    "confidence_in_recall_process": gate.uncertainty_triple.confidence_in_recall_process,
                    "confidence_in_provenance_chain": gate.uncertainty_triple.confidence_in_provenance_chain,
                },
                combined_score=gate.combined_score,
                dominant_axis=gate.dominant_axis,
                provenance_signals={
                    "parent_chain_depth": gate_inputs.get("parent_chain_depth", 0.0),
                    "source_diversity": gate_inputs.get("source_diversity", 1.0),
                    "age_of_original_source": gate_inputs.get("age_of_original_source", 0.0),
                },
                uncertainty_gate_mode=gate.gate_mode,
                # v7 §11 / §11.1 visibility on the rejected branch.
                axis_fallback_used=dict(gate.uncertainty_triple.axis_fallback_used),
                axis_fallback_reasons=dict(gate.uncertainty_triple.axis_fallback_reasons),
                policy_fallback_multiplier=gate.uncertainty_triple.policy_fallback_multiplier,
                scoring_function="score_triple",
            )
            return False
        return True

    def _sensor_spread(self, sensor_values: list[float]) -> float:
        if len(sensor_values) < 2:
            return 0.0
        return max(sensor_values) - min(sensor_values)

    def _attack_surface_reason(
        self,
        *,
        signals: ObservationSignals,
        obs_counts: dict[str, int],
        memory_id: str,
    ) -> str | None:
        if obs_counts[memory_id] > self.cfg.retrieval_policy.implicit_event_flood_threshold:
            return ImplicitReason.EVENT_FLOOD_SUSPECTED.value

        if signals.urgency >= 0.9 and signals.risk_signal <= 0.2 and signals.prediction_error <= 0.2:
            return ImplicitReason.URGENCY_SPOOF_SUSPECTED.value

        spread = self._sensor_spread(signals.sensor_values)
        coherence = 1.0 - max(0.0, min(1.0, spread))
        if signals.sensory_confidence >= 0.9 and (signals.sensory_confidence - coherence) >= 0.5:
            return ImplicitReason.SENSORY_CONFIDENCE_SPOOF_SUSPECTED.value

        return None

    def _emit_policy_mutation(self, *, event_type: str, memory_id: str, payload: dict[str, object]) -> None:
        self.lineage.emit(
            event_type=event_type,
            agent_id=self.agent_id,
            stream_id=self.stream_id,
            memory_id=memory_id,
            actor_class="implicit_memory_controller",
            source_class="internal_engine",
            payload=payload,
        )

    def _mutate_policy_from_attack(self, *, reason: str, memory_id: str) -> None:
        if reason in self.policy_mutations_applied:
            return

        # Harden thresholds under attack signals.
        if reason in {
            ImplicitReason.URGENCY_SPOOF_SUSPECTED.value,
            ImplicitReason.SENSORY_CONFIDENCE_SPOOF_SUSPECTED.value,
            ImplicitReason.EVENT_FLOOD_SUSPECTED.value,
        }:
            current_adm = self.policy_state.threshold_map["admission_threshold"]
            new_adm = min(1.0, current_adm + 0.05)
            if new_adm != current_adm:
                self.policy_state, payload = update_threshold(
                    self.policy_state,
                    name="admission_threshold",
                    new_value=new_adm,
                    reason=f"auto_hardening:{reason}",
                )
                self._emit_policy_mutation(
                    event_type="policy_threshold_updated",
                    memory_id=memory_id,
                    payload=payload,
                )

            current_el = self.policy_state.threshold_map["eligibility_threshold"]
            new_el = min(1.0, current_el + 0.02)
            if new_el != current_el:
                self.policy_state, payload = update_threshold(
                    self.policy_state,
                    name="eligibility_threshold",
                    new_value=new_el,
                    reason=f"auto_hardening:{reason}",
                )
                self._emit_policy_mutation(
                    event_type="policy_threshold_updated",
                    memory_id=memory_id,
                    payload=payload,
                )

            old_proc = self.policy_state.procedure_map.get("reflex_slot")
            if old_proc == self.procedure_id:
                self.policy_state, payload = supersede_procedure(
                    self.policy_state,
                    slot="reflex_slot",
                    new_procedure_id=f"{self.procedure_id}-hardened",
                    reason=f"auto_hardening:{reason}",
                )
                self._emit_policy_mutation(
                    event_type="policy_procedure_superseded",
                    memory_id=memory_id,
                    payload=payload,
                )

        self.policy_mutations_applied.add(reason)

    def __init__(
        self,
        *,
        cfg: AwsConfig,
        lineage: LineageEmitter,
        cue_provider: CapturedCueProvider,
        agent_id: str,
        stream_id: str,
        procedure_state_store: ProcedureStateStore | None = None,
        provenance_resolver: ProvenanceResolver | None = None,
        procedure_id: str = "proc-reflex-triage",
    ) -> None:
        self.cfg = cfg
        self.lineage = lineage
        self.cue_provider = cue_provider
        self.agent_id = agent_id
        self.stream_id = stream_id
        self.procedure_state_store = procedure_state_store
        self.provenance_resolver = provenance_resolver
        self.procedure_id = procedure_id
        self.reflex = ReflexController(
            max_actions=self.cfg.retrieval_policy.implicit_reflex_max_actions,
            cooldown_steps=self.cfg.retrieval_policy.implicit_reflex_cooldown_steps,
        )
        self.policy_state = PolicyState(
            threshold_map={
                "eligibility_threshold": self.cfg.retrieval_policy.eligibility_threshold,
                "admission_threshold": self.cfg.retrieval_policy.implicit_admission_threshold,
                "reflex_threshold": self.cfg.retrieval_policy.implicit_reflex_threshold,
            },
            procedure_map={"reflex_slot": self.procedure_id},
        )
        self.policy_mutations_applied: set[str] = set()

    def _resolve_provenance(self, *, memory_id: str, as_of_time: str) -> dict[str, object]:
        if self.provenance_resolver is None:
            return {
                "parent_chain_depth": 0.0,
                "source_diversity": 0.0,
                "age_of_original_source": 0.0,
                "fallback_reason": "resolver_not_configured",
                "provenance_signal_source": "fallback",
            }
        payload = self.provenance_resolver.resolve(
            memory_id=memory_id,
            stream_id=self.stream_id,
            as_of_time=as_of_time,
        )
        return {
            "parent_chain_depth": float(payload.get("parent_chain_depth", 0.0)),
            "source_diversity": float(payload.get("source_diversity", 0.0)),
            "age_of_original_source": float(payload.get("age_of_original_source", 0.0)),
            "fallback_reason": payload.get("fallback_reason"),
            "provenance_signal_source": payload.get("provenance_signal_source", "computed"),
            "chain_root_event_id": payload.get("chain_root_event_id"),
            "chain_length": payload.get("chain_length", 0),
            "distinct_source_classes": payload.get("distinct_source_classes", 0),
            "computed_at": payload.get("computed_at", as_of_time),
            "as_of_time": payload.get("as_of_time", as_of_time),
        }

    def _cue_to_observation(self, cue: Cue) -> tuple[str, ObservationSignals]:
        """Adapt a captured cue to the (memory_id, ObservationSignals)
        pair the observation path consumes.

        The cue payload is deserialized into the explicit
        `ObservationSignals` dataclass — one defined shape, read
        uniformly for every non-scheduled cue. This is not the
        per-cue_type ad hoc payload-peeking CONTROL_PLANE_INGEST
        Decision 2 forbids: the loop dispatches on `cue_type`, and the
        signal shape is a named contract, not a schema hidden in code.

        Honest gap: attack detection and trigger evaluation still read
        these signals before admission, so the payload is not strictly
        opaque-until-admission as Decision 2 states. Moving that
        interpretation past admission is a separate change, beyond
        Phase 4's input unification.
        """
        p = cue.payload if isinstance(cue.payload, dict) else {}
        memory_id = str(p.get("memory_id") or cue.cue_id)
        signals = ObservationSignals(
            prediction_error=float(p.get("prediction_error", 0.0)),
            goal_impact=float(p.get("goal_impact", 0.0)),
            risk_signal=float(p.get("risk_signal", 0.0)),
            repetition_signal=float(p.get("repetition_signal", 0.0)),
            contradiction_pressure=float(p.get("contradiction_pressure", 0.0)),
            explicit_directive=bool(p.get("explicit_directive", False)),
            urgency=float(p.get("urgency", 0.0)),
            sensory_confidence=float(p.get("sensory_confidence", 0.0)),
            sensor_values=[float(v) for v in (p.get("sensor_values") or [])],
        )
        return memory_id, signals

    def _cue_to_scheduled(self, cue: Cue) -> ScheduledCue:
        """Adapt a `scheduled_cue` captured cue to a `ScheduledCue`.

        `due_at` rides the payload as an ISO string (JSON carries no
        datetime); fixtures always supply it.
        """
        p = cue.payload if isinstance(cue.payload, dict) else {}
        due_raw = p.get("due_at")
        due_at = (
            datetime.fromisoformat(due_raw)
            if isinstance(due_raw, str) and due_raw
            else now_utc()
        )
        return ScheduledCue(
            cue_id=cue.cue_id,
            memory_id=str(p.get("memory_id") or cue.cue_id),
            due_at=due_at,
            urgency=float(p.get("urgency", 0.0)),
            risk_signal=float(p.get("risk_signal", 0.0)),
            acknowledged=bool(p.get("acknowledged", False)),
        )

    def tick(self, *, now: datetime | None = None) -> dict:
        t = now or now_utc()
        stats = LoopStats()
        self.reflex.tick()

        procedure_state = (
            self.procedure_state_store.load(procedure_id=self.procedure_id)
            if self.procedure_state_store
            else None
        )
        if procedure_state is None:
            procedure_state = ProcedureState(procedure_id=self.procedure_id, strength=1.0, trust=1.0)

        # CONTROL_PLANE_INGEST Decision 2: one input contract. Pull
        # captured cues once, then dispatch by cue_type — scheduled_cue
        # to the scheduled path, everything else to the observation
        # path. The handler bodies below are unchanged.
        captured_cues = self.cue_provider.pull(now=t)
        observations = [
            self._cue_to_observation(c)
            for c in captured_cues
            if c.cue_type != "scheduled_cue"
        ]
        observation_counts: dict[str, int] = defaultdict(int)
        for memory_id, signals in observations:
            observation_counts[memory_id] += 1

            attack_reason = self._attack_surface_reason(
                signals=signals,
                obs_counts=observation_counts,
                memory_id=memory_id,
            )
            if attack_reason is not None:
                stats.observations_processed += 1
                stats.observation_rejected += 1
                self.lineage.emit(
                    event_type="contamination_suspected",
                    agent_id=self.agent_id,
                    stream_id=self.stream_id,
                    memory_id=memory_id,
                    actor_class="implicit_memory_controller",
                    source_class="internal_engine",
                    payload={
                        "reason": attack_reason,
                        "urgency": signals.urgency,
                        "risk_signal": signals.risk_signal,
                        "sensory_confidence": signals.sensory_confidence,
                        "observation_count": observation_counts[memory_id],
                    },
                )
                stats.contamination_suspected += 1
                self._emit_rejected(
                    memory_id=memory_id,
                    reason=attack_reason,
                    observation_count=observation_counts[memory_id],
                )
                self._mutate_policy_from_attack(reason=attack_reason, memory_id=memory_id)
                continue

            decision = process_observation(
                lineage=self.lineage,
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                memory_id=memory_id,
                signals=signals,
            )
            stats.observations_processed += 1
            if decision.action.value in {"invoke_encode", "invoke_recall", "reflex_execute"}:
                stats.observation_fired += 1
                procedure_state = reinforce_procedure(procedure_state, reward=0.05)
                self.lineage.emit(
                    event_type="procedure_reinforced",
                    agent_id=self.agent_id,
                    stream_id=self.stream_id,
                    memory_id=procedure_state.procedure_id,
                    actor_class="implicit_memory_controller",
                    source_class="internal_engine",
                    payload={"strength": procedure_state.strength, "trust": procedure_state.trust},
                )

                if decision.action.value == "reflex_execute":
                    reflex_score = signals.urgency * signals.risk_signal * signals.sensory_confidence
                    if reflex_score < self.policy_state.threshold_map["reflex_threshold"]:
                        self._emit_rejected(
                            memory_id=memory_id,
                            reason=ImplicitReason.ELIGIBILITY_BELOW_THRESHOLD.value,
                            reflex_score=reflex_score,
                            reflex_threshold=self.policy_state.threshold_map["reflex_threshold"],
                        )
                        stats.observation_rejected += 1
                        continue

                    if not self.reflex.in_reflex:
                        if self.reflex.enter():
                            stats.reflex_entered += 1
                            self.lineage.emit(
                                event_type="reflex_mode_entered",
                                agent_id=self.agent_id,
                                stream_id=self.stream_id,
                                memory_id=memory_id,
                                actor_class="implicit_memory_controller",
                                source_class="internal_engine",
                                payload={
                                    "max_actions": self.reflex.max_actions,
                                    "cooldown_steps": self.reflex.cooldown_steps,
                                    "forced_governed_reentry": True,
                                },
                            )

                    if self.reflex.in_reflex:
                        self.reflex.record_action()
                        self.lineage.emit(
                            event_type="reflex_action_executed",
                            agent_id=self.agent_id,
                            stream_id=self.stream_id,
                            memory_id=memory_id,
                            actor_class="implicit_memory_controller",
                            source_class="internal_engine",
                            payload={"actions_taken": self.reflex.actions_taken},
                        )

                        if not self.reflex.in_reflex:
                            self.lineage.emit(
                                event_type="reflex_mode_exited",
                                agent_id=self.agent_id,
                                stream_id=self.stream_id,
                                memory_id=memory_id,
                                actor_class="implicit_memory_controller",
                                source_class="internal_engine",
                                payload={
                                    "reason": ImplicitReason.BUDGET_EXHAUSTED.value,
                                    "cooldown_remaining": self.reflex.cooldown_remaining,
                                },
                            )
                        else:
                            # Forced re-entry to governed mode after bounded reflex action.
                            self.reflex.exit()
                            self.lineage.emit(
                                event_type="reflex_mode_exited",
                                agent_id=self.agent_id,
                                stream_id=self.stream_id,
                                memory_id=memory_id,
                                actor_class="implicit_memory_controller",
                                source_class="internal_engine",
                                payload={
                                    "reason": ImplicitReason.CYCLE_COMPLETE.value,
                                    "cooldown_remaining": self.reflex.cooldown_remaining,
                                    "forced_governed_reentry": True,
                                },
                            )
                    else:
                        stats.reflex_blocked += 1
                        self._emit_rejected(
                            memory_id=memory_id,
                            reason=ImplicitReason.REFLEX_BUDGET_EXHAUSTED.value,
                            cooldown_remaining=self.reflex.cooldown_remaining,
                        )
                        stats.observation_rejected += 1
                else:
                    adm = admission_score(
                        significance=decision.score,
                        source_trust=signals.sensory_confidence,
                        novelty=signals.prediction_error,
                        risk_signal=signals.risk_signal,
                    )
                    provenance = self._resolve_provenance(memory_id=memory_id, as_of_time=t.isoformat())
                    self.lineage.emit(
                        event_type="provenance_signals_computed",
                        agent_id=self.agent_id,
                        stream_id=self.stream_id,
                        memory_id=memory_id,
                        actor_class="implicit_memory_controller",
                        source_class="internal_engine",
                        payload={
                            "provenance_signals": {
                                "parent_chain_depth": provenance["parent_chain_depth"],
                                "source_diversity": provenance["source_diversity"],
                                "age_of_original_source": provenance["age_of_original_source"],
                            },
                            "chain_root_event_id": provenance.get("chain_root_event_id"),
                            "chain_length": provenance.get("chain_length", 0),
                            "distinct_source_classes": provenance.get("distinct_source_classes", 0),
                            "computed_at": provenance.get("computed_at", t.isoformat()),
                            "as_of_time": provenance.get("as_of_time", t.isoformat()),
                            "fallback_reason": provenance.get("fallback_reason"),
                            "provenance_signal_source": provenance.get("provenance_signal_source", "computed"),
                        },
                    )
                    allowed = self._admit_and_gate(
                        memory_id=memory_id,
                        source_class="internal_engine",
                        admission_value=adm,
                        gate_inputs={
                            "relevance": max(0.0, min(1.0, decision.score)),
                            "trust": signals.sensory_confidence,
                            "recency": 1.0,
                            "reinforcement": max(0.0, min(1.0, signals.repetition_signal + 0.5)),
                            "consistency": max(0.0, min(1.0, 1.0 - signals.contradiction_pressure)),
                            "safety": max(0.0, min(1.0, 1.0 - signals.risk_signal * 0.2)),
                            "parent_chain_depth": provenance["parent_chain_depth"],
                            "source_diversity": provenance["source_diversity"],
                            "age_of_original_source": provenance["age_of_original_source"],
                        },
                    )
                    if allowed:
                        stats.observation_admitted += 1
                    else:
                        stats.observation_rejected += 1
            else:
                stats.observation_deferred += 1
                procedure_state = decay_procedure(procedure_state, decay=0.02)
                self.lineage.emit(
                    event_type="procedure_decayed",
                    agent_id=self.agent_id,
                    stream_id=self.stream_id,
                    memory_id=procedure_state.procedure_id,
                    actor_class="implicit_memory_controller",
                    source_class="internal_engine",
                    payload={
                        "strength": procedure_state.strength,
                        "trust": procedure_state.trust,
                        "reason": ImplicitReason.DEFERRED.value,
                    },
                )

            procedure_state, trust_decayed = apply_urgency_trust_decay(
                procedure_state,
                urgency=signals.urgency,
            )
            if trust_decayed:
                self.lineage.emit(
                    event_type="policy_threshold_updated",
                    agent_id=self.agent_id,
                    stream_id=self.stream_id,
                    memory_id=procedure_state.procedure_id,
                    actor_class="implicit_memory_controller",
                    source_class="internal_engine",
                    payload={
                        "reason": ImplicitReason.PROLONGED_HIGH_URGENCY_TRUST_DECAY.value,
                        "high_urgency_streak": procedure_state.high_urgency_streak,
                        "trust": procedure_state.trust,
                    },
                )

        cues = [
            self._cue_to_scheduled(c)
            for c in captured_cues
            if c.cue_type == "scheduled_cue"
        ]
        due = due_cues(now=t, cues=cues)
        stats.cues_due = len(due)

        for cue in due:
            overdue_seconds = max(0.0, (t - cue.due_at).total_seconds())
            level = escalation_level(overdue_seconds=overdue_seconds)

            self.lineage.emit(
                event_type="implicit_trigger_evaluated",
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                memory_id=cue.memory_id,
                actor_class="implicit_memory_controller",
                source_class="scheduler",
                payload={
                    "trigger": "scheduled_cue",
                    "cue_id": cue.cue_id,
                    "overdue_seconds": overdue_seconds,
                    "escalation_level": level,
                    "urgency": cue.urgency,
                    "risk_signal": cue.risk_signal,
                },
            )
            self.lineage.emit(
                event_type="implicit_trigger_fired",
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                memory_id=cue.memory_id,
                actor_class="implicit_memory_controller",
                source_class="scheduler",
                payload={"action": "invoke_recall", "cue_id": cue.cue_id, "escalation_level": level},
            )
            stats.cues_fired += 1

            admission_value = cue.urgency * cue.risk_signal
            provenance = self._resolve_provenance(memory_id=cue.memory_id, as_of_time=t.isoformat())
            self.lineage.emit(
                event_type="provenance_signals_computed",
                agent_id=self.agent_id,
                stream_id=self.stream_id,
                memory_id=cue.memory_id,
                actor_class="implicit_memory_controller",
                source_class="scheduler",
                payload={
                    "provenance_signals": {
                        "parent_chain_depth": provenance["parent_chain_depth"],
                        "source_diversity": provenance["source_diversity"],
                        "age_of_original_source": provenance["age_of_original_source"],
                    },
                    "chain_root_event_id": provenance.get("chain_root_event_id"),
                    "chain_length": provenance.get("chain_length", 0),
                    "distinct_source_classes": provenance.get("distinct_source_classes", 0),
                    "computed_at": provenance.get("computed_at", t.isoformat()),
                    "as_of_time": provenance.get("as_of_time", t.isoformat()),
                    "fallback_reason": provenance.get("fallback_reason"),
                    "provenance_signal_source": provenance.get("provenance_signal_source", "computed"),
                },
            )
            allowed = self._admit_and_gate(
                memory_id=cue.memory_id,
                source_class="scheduler",
                admission_value=admission_value,
                admission_reason=ImplicitReason.SCHEDULED_PRIORITY.value,
                gate_inputs={
                    "relevance": max(0.0, min(1.0, admission_value)),
                    "trust": max(0.0, min(1.0, cue.risk_signal)),
                    "recency": 1.0,
                    "reinforcement": 1.0,
                    "consistency": 1.0,
                    "safety": max(0.0, min(1.0, 1.0 - cue.risk_signal * 0.1)),
                    "parent_chain_depth": provenance["parent_chain_depth"],
                    "source_diversity": provenance["source_diversity"],
                    "age_of_original_source": provenance["age_of_original_source"],
                },
            )
            if allowed:
                stats.cues_admitted += 1
            else:
                self.lineage.emit(
                    event_type="implicit_trigger_deferred",
                    agent_id=self.agent_id,
                    stream_id=self.stream_id,
                    memory_id=cue.memory_id,
                    actor_class="implicit_memory_controller",
                    source_class="scheduler",
                    payload={"reason": ImplicitReason.SCHEDULED_LOW_PRIORITY.value, "cue_id": cue.cue_id},
                )
                stats.cues_deferred += 1

        persisted = None
        if self.procedure_state_store:
            persisted = self.procedure_state_store.save(state=procedure_state)

        stats.replay_event_count = (
            stats.observations_processed
            + stats.observation_fired
            + stats.observation_deferred
            + stats.observation_admitted
            + stats.observation_rejected
            + stats.reflex_entered
            + stats.reflex_blocked
            + stats.cues_due
            + stats.cues_fired
            + stats.cues_admitted
            + stats.cues_deferred
            + stats.contamination_suspected
        )

        primary_metrics = {
            "false_reflex_rate": stats.reflex_blocked / max(1, stats.reflex_entered + stats.reflex_blocked),
            "missed_critical_trigger_rate": stats.cues_deferred / max(1, stats.cues_due),
            "time_to_action_under_risk_proxy": stats.observation_fired / max(1, stats.observations_processed),
            "replay_determinism_proxy": 1.0,
            "contamination_containment_rate": stats.observation_rejected / max(1, stats.contamination_suspected),
        }

        secondary_metrics = {
            "trigger_precision_proxy": stats.observation_admitted / max(1, stats.observation_fired),
            "trigger_recall_proxy": stats.observation_fired / max(1, stats.observations_processed),
            "lineage_completeness_proxy": 1.0,
            "governance_overhead_proxy": (
                (stats.observation_rejected + stats.observation_deferred) / max(1, stats.observations_processed)
            ),
        }

        self.lineage.emit(
            event_type="snapshotted",
            agent_id=self.agent_id,
            stream_id=self.stream_id,
            memory_id="implicit-loop-tick",
            actor_class="implicit_memory_controller",
            source_class="internal_engine",
            payload={
                "snapshot_type": "implicit_loop_tick",
                "timestamp": t.isoformat(),
                "stats": stats.to_dict(),
                "primary_metrics": primary_metrics,
                "secondary_metrics": secondary_metrics,
                "procedure_state": {
                    "procedure_id": procedure_state.procedure_id,
                    "strength": procedure_state.strength,
                    "trust": procedure_state.trust,
                    "high_urgency_streak": procedure_state.high_urgency_streak,
                    "persisted": persisted is not None,
                },
                "runtime_policy_state": {
                    "threshold_map": self.policy_state.threshold_map,
                    "procedure_map": self.policy_state.procedure_map,
                    "mutations_applied": sorted(self.policy_mutations_applied),
                },
                **self.cfg.retrieval_policy.audit_fields(),
            },
        )

        return stats.to_dict()
