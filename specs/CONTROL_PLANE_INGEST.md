# CONTROL_PLANE_INGEST

Status: Implemented (2026-05-22) — drafted 2026-05-21, generated directly from `notes/agent-pov/2026-05-20-development-direction-and-state.md`. No proposal stage, by decision: proposal theater bypassed; iterated via review/reaction on this spec and on the implementation.
Audience: implicit-loop implementers, experiment authors.

Changelog:
- 2026-05-21 — amended in place in response to `notes/agent-pov/2026-05-21-reaction-control-plane-ingest.md` (gpt-5-codex). Four tightenings: durability boundary made precise (Decision 2 / 3), scope failure cases split into three (Decision 1 / 5), DLQ recovery contract and events added (Decision 5, §7), payload opacity promoted from deferred note to hard rule (Decision 2).
- 2026-05-21 — Phase 5 reconciliation, found during implementation grounding: Decision 3 / §8 / §9 wrongly called `rebuild_from_lineage` the replay driver. It is a post-hoc signature function over an emitted-event list; the replay driver is the loop re-run with a `ReplayCueProvider`. Corrected.
- 2026-05-22 — implementation complete across seven phases. §8 rewritten as an as-built map; §9 notes the `im_v` falsification suite (suite V, registered in `im_regression.py` and `run_experiment.py`). Status: Implemented.

## 1. Purpose

The EventBridge `memory-lab` bus, the SQS `memory-lab.fifo` queue, and its DLQ exist in the CDK stack but carry nothing. The implicit loop runs on `StaticObservationProvider` / `StaticCueProvider` stubs (`src/implicit_memory/run_loop.py`). This spec wires a live ingestion path from the bus into the loop, replacing the stubs as the runtime source — without weakening replay determinism.

It pins five decisions and nothing else. Trigger semantics, admission/eligibility math, and axis-signal work are unchanged and out of scope.

## 2. Decision 1 — Cue message schema

A control-plane signal on the bus is a *cue*. A cue carries:

- `cue_id` — globally unique; the idempotency key end to end.
- `cue_type` — one of the implicit loop's existing trigger classes (`prediction_error`, `goal_impact`, `safety_anomaly`, `repetition`, `contradiction_pressure`, `recall_directive`, `scheduled_cue`, `sensor_disagreement`; per `IMPLICIT_MEMORY_SPEC` §7.1). A cue that does not name a known class is rejected (Decision 5).
- `agent_id`, `stream_id` — the scope the cue applies to. The loop consumes only cues in its own scope; cross-scope influence is forbidden. Scope has three distinct failure modes — malformed, unknown, and valid-but-another-worker's — handled separately in Decision 5.
- `source` — producer identity and `source_class`. Recorded, not trusted: trust is a prior applied later by admission/eligibility, never asserted by the cue itself.
- `payload` — signal content, shaped by `cue_type`. Opaque to the loop (Decision 2); free-form for now, with payload schema-tightening an explicit open-for-iteration item (§10).
- `claimed_at` (optional) — the producer's own timestamp. Witness data only. The authoritative `physical_moment` is stamped at capture (Decision 3).

## 3. Decision 2 — Ingestion path (capture-before-act)

Flow: producer → EventBridge `memory-lab` bus → rule → SQS `memory-lab.fifo` → ingestion consumer → `control_cue_ingested` lineage event → implicit loop.

**EventBridge envelope.** A cue reaches the bus wrapped in a standard EventBridge event. The routing rule matches on `source = "memory-lab.control-plane"` and `detail-type = "control-cue"`; the event `detail` carries the cue body (the §2 schema). This envelope is the producer contract — it is what the `ControlCueRoutingRule` in `stacks/memory_lab/memory_lab_stack.py` matches, and the cue body inside `detail` is what `cue_from_message` parses.

The load-bearing rule is **capture-before-act**. The ingestion consumer turns a cue into a `control_cue_ingested` lineage event *before* the cue reaches the loop. The raw bus/SQS message is transport; it is never the loop's input. The loop consumes the captured event, and may consume **only** information present in it. Anything the loop acts on that is not in the event breaks replay (Decision 3).

**The durability boundary.** "Captured" has a precise meaning, and the weaker reading is not enough. A `control_cue_ingested` event is captured only when it has been (a) validated at the storage edge by a check **equivalent to canonical ingestion validation**, and (b) durably written to ingress. Only then may the loop act on it. The weaker reading — the event object was constructed and handed to `LineageEngine.emit` — is insufficient: if the loop acts on an event that a later Athena ingestion would quarantine, live behavior outruns canonical replay and the replay invariant is void.

This validation is **synchronous and at the edge**, not deferred to Athena. The loop has latency-sensitive paths — reflex mode runs on an action/time budget — so "act now, let canonical ingestion confirm later" is not available. The implementation must make storage-edge validation for `control_cue_ingested` provably equal to (or stricter than) canonical-ingestion validation, so an ingress-accepted event is guaranteed canonical-valid. Validate fully, write durably, then act.

**Payload opacity.** The loop branches only on the captured envelope, `cue_type`, `agent_id`, and `stream_id`. The `payload` is an opaque source claim until admission/eligibility interprets it. The loop must not grow per-`cue_type` semantic logic over ad hoc payload fields: replay would stay deterministic if it did, but the control plane would become a schema hidden in code. Payload *schema* is deferred (§10); payload *opacity in the loop* is a rule now.

**One input contract.** The static providers (`StaticObservationProvider`, `StaticCueProvider`) are retained as deterministic test/experiment fixtures. They emit the *same* `control_cue_ingested` event type, through the same durability boundary. The loop and replay cannot distinguish a live cue from a fixture cue.

## 4. Decision 3 — Replay determinism

A live bus is non-deterministic input; replay must not depend on it. Therefore:

- `control_cue_ingested` is the replay anchor. Its `physical_moment` is stamped at capture, via `heliotime.now()` — the one sanctioned edge wall-clock read. After capture, no wall clock is read on the cue's behalf.
- The loop acts only on captured events (Decision 2's durability boundary). Because a captured event is canonical-valid by construction, the canonical lineage and the events the loop acted on cannot diverge.
- Replay re-runs the loop with a `ReplayCueProvider` (`src/implicit_memory/replay.py`) that yields `Cue` objects decoded from recorded `control_cue_ingested` events — no bus, no queue, no wall clock. `rebuild_from_lineage` is **not** the replay driver: it is a post-hoc signature function over an emitted-event list. Replay equivalence means feeding the same captured cues makes the loop re-emit the same lineage, over which `rebuild_from_lineage` yields the same signature.
- Loop behavior must be a pure function of (captured cues + prior lineage state). This is invariant 5 — no non-lineage influence on replay — applied to the new input path.

## 5. Decision 4 — Ordering, dedup, idempotency

- **Ordering:** SQS FIFO `MessageGroupId = "{agent_id}/{stream_id}"`. Cues for one stream are ordered; different streams process in parallel, matching the loop's per-stream scope. The ingestion sequence is frozen into lineage via `sequence_in_stream` / HLC at capture; replay orders by the recorded sequence, not by re-reading FIFO. **Implementation note:** a basic EventBridge → SQS-FIFO rule target cannot set `MessageGroupId` per-event — it takes one static group. The CDK stack uses a single static group today: ordering is preserved (correct), cross-stream parallelism is not. Per-`(agent_id, stream_id)` groups require an **EventBridge Pipe** with an enrichment step that derives the group from the event — that is the sanctioned path, and a follow-on, not a correctness fix.
- **Dedup:** SQS `MessageDeduplicationId = cue_id`. Because the FIFO dedup window is finite, the ingestion consumer also checks lineage: if a `control_cue_ingested` event already exists for this `cue_id` — checked against the same canonical-valid store the loop trusts (Decision 2) — the cue is a duplicate.
- **Idempotency:** a duplicate is dropped before the loop and recorded as a `control_cue_duplicate_ignored` (`lineage_meta`) marker — dedup stays auditable. The first cue with a given `cue_id` wins. Re-delivery never produces a second loop effect.

## 6. Decision 5 — Scope, failure handling, and the DLQ

**Scope is three failure modes, not one.** A cue's scope can be:

- *malformed* — `agent_id` / `stream_id` missing or ill-formed. A cue defect → `control_cue_rejected`.
- *unknown* — well-formed but names no agent/stream the lab knows. A cue defect → `control_cue_rejected`.
- *valid but not this worker's* — a well-formed scope belonging to another worker. A **routing** condition, not a cue defect. The worker ignores it (ideally never receives it); it is not a rejection. Treating it as one would camouflage a routing bug as a cue bug.

**Every cue resolves to one of three outcomes:**

- **Ingested** — captured as `control_cue_ingested` (Decision 2).
- **Rejected** — fails validation (unknown `cue_type`, malformed payload, malformed or unknown scope). Recorded as `control_cue_rejected` with a deterministic, machine-readable `reason`. Not delivered to the loop.
- **Dead-lettered** — a transient failure (e.g. an S3 write error) is retried; after the max attempts the message lands in the existing DLQ, operationally visible for an operator. DLQ contents are not loop input.

**The DLQ has an honest audit gap, and a recovery contract closes it.** When the failure *is* "cannot write lineage," a dead-lettered cue has no lineage marker at the moment it fails — the outcome trichotomy is auditable in lineage only for the ingested and rejected branches. That is unavoidable. What is not optional is the recovery path: when an operator later inspects or replays a DLQ item, that action emits a lineage event — `control_cue_dlq_recovered` or `control_cue_dlq_abandoned` — so the audit trail is closed at exactly the point where an operator touched the system.

## 7. New event types

Five new event types. Each must be added to the static mapping table in `src/epistemic_triangle/mapping.py` and declared with an `event_type_declared` lineage event before first use (per `EPISTEMIC_TRIANGLE` §3.5).

Taxonomy mapping (`control_cue_ingested` confirmed by the 2026-05-21 reaction; the other four open to review/reaction):

- `control_cue_ingested` — `record_kind = observation_event`, `assertion_kind = claim` (a control-plane cue is a source assertion, not direct ground truth; it is not `reality_observation`).
- `control_cue_rejected` — `record_kind = decision_event`, no `uncertainty_triple` (so no subject fields); carries the deterministic `reason`.
- `control_cue_duplicate_ignored` — `record_kind = lineage_meta`.
- `control_cue_dlq_recovered` — `record_kind = lineage_meta`; records an operator returning a dead-lettered cue to ingestion.
- `control_cue_dlq_abandoned` — `record_kind = lineage_meta`; records an operator's decision to abandon a dead-lettered cue.

## 8. Implementation — as built

- `src/implicit_memory/cue_ingest.py` — the ingestion consumer: the `Cue` schema, `CueIngestionConsumer` (capture-before-act), the `SeenCueStore` protocol with `InMemorySeenCueStore` and `LineageBackedSeenCueStore`, `cue_from_message`, `cue_from_ingested_event`, `declare_control_plane_event_types`, and the DLQ recovery helpers.
- `src/implicit_memory/run_cue_ingest.py` — the local consumer command: drains `memory-lab.fifo` through `CueIngestionConsumer`. Lambda is the production compute form; the lab stops at this command.
- `src/implicit_memory/loop.py` — one input contract, `CapturedCueProvider`; `tick()` dispatches captured cues by `cue_type` through `_cue_to_observation` / `_cue_to_scheduled` into the unchanged handler bodies.
- `src/implicit_memory/run_loop.py` — `StaticCueProvider`, a fixture yielding `Cue` objects (the same shape the live path produces).
- `src/implicit_memory/replay.py` — `ReplayCueProvider` decodes recorded `control_cue_ingested` events into `Cue` objects for loop replay; `rebuild_from_lineage` is the post-hoc signature function, not the replay driver.
- `src/epistemic_triangle/mapping.py` — the five event types registered (§7).
- `src/storage.py` — `LineageValidationError` separates a cue defect (→ `control_cue_rejected`) from a system fault (→ `TransientIngestError` → DLQ).
- `stacks/memory_lab/memory_lab_stack.py` — `ControlCueRoutingRule` routes the bus to the FIFO queue.
- Storage-edge validation needed no new code: `validate_event_v7` is equivalent to canonical Athena ingestion for these event types by construction — both derive their enum and event-type-membership sets from the shared `EVENT_TYPE_MAPPING` (Decision 2).

## 9. Falsification checks

- **Replay equivalence:** run the loop on a live cue sequence; re-run it with a `ReplayCueProvider` over the recorded `control_cue_ingested` events, bus disconnected; the `rebuild_from_lineage` signature over the emitted lineage must be identical.
- **Validation equivalence:** every `control_cue_ingested` event that passes storage-edge validation also survives canonical ingestion — zero quarantined. A quarantined `control_cue_ingested` is a Decision 2 failure.
- **Idempotency:** deliver one `cue_id` twice, inside and outside the SQS dedup window; exactly one `control_cue_ingested` exists; loop behavior matches single delivery.
- **No silent loss:** inject a malformed cue and a transient-failure cue; assert every cue resolves to exactly one of ingested / rejected / dead-lettered, and that a dead-lettered cue's later operator action emits a `control_cue_dlq_*` event.
- **Scope containment:** a cue scoped to agent A produces no loop effect in agent B's scope; a valid-but-another-worker's cue is ignored as routing, not recorded as a rejection.

Implemented as `src/experiments/implicit/im_v_control_plane_ingest.py` (suite V) — one hook per check, all five passing, wired into `im_regression.py` and `run_experiment.py` (`im-v`).

## 10. Open for iteration

Deliberately unresolved on this draft; for review/reaction passes:

- payload *schema* discipline per `cue_type` — the free-form-payload problem; ties to the article's section 6 open edge. (Payload *opacity in the loop* is no longer open — it is a rule in Decision 2.)
- duplicate-flood aggregation — record a count rather than one `control_cue_duplicate_ignored` per duplicate under flood.
- the §7 taxonomy mapping for the four event types other than `control_cue_ingested`.
- whether `scheduled_cue` cues need a distinct producer or are emitted internally.
