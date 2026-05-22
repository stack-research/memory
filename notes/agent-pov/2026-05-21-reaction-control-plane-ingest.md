```yaml
agent: openai-gpt-5-codex
date: 2026-05-21
prompt: "read AGENT_PRIMER.md and then 2026-05-20-development-direction-and-state.md then CONTROL_PLANE_INGEST.md. After that, write a reaction to the CONTROL_PLANE_INGEST.md spec using the directions in README.md add it to INDEX.md"
kind: reaction
cites:
  - specs/CONTROL_PLANE_INGEST.md
  - 2026-05-20-development-direction-and-state
```

# Reaction to CONTROL_PLANE_INGEST

This is the right next spec because it attacks the live-input gap instead of widening the schema surface again. The May 20 critique said the lab was investing in representational richness over runtime liveness. `CONTROL_PLANE_INGEST` answers that directly: make the implicit loop consume real cues, but freeze them into lineage before the loop can act.

The strongest sentence is the capture-before-act rule:

> The raw bus/SQS message is transport; it is never the loop's input.

That one line keeps the spec aligned with the lab's central invariant. The live bus may be messy, delayed, duplicated, or reordered. The loop should not care. It should see only a lineage event.

## What looks right

- **One cue contract for live and fixture paths.** Keeping `StaticObservationProvider` / `StaticCueProvider` as deterministic fixtures that emit the same `control_cue_ingested` event is clean. It avoids the usual split where tests exercise a kinder interface than production.
- **Per-stream FIFO grouping.** `MessageGroupId = "{agent_id}/{stream_id}"` matches the lab's scope model. It gives ordering where the loop needs ordering and avoids pretending there is a single global sequence.
- **Auditable dedup.** Recording `control_cue_duplicate_ignored` is better than quiet idempotency. Duplicate pressure is itself a signal about the control plane.
- **Cue taxonomy choice.** `control_cue_ingested` as `observation_event` + `claim` is right. A cue is a source assertion about what should be noticed, not evidence that the world is that way.

## What I would tighten before implementation

The spec needs to name the durability boundary more sharply. "Emits a lineage event before the cue reaches the loop" can mean two different things:

1. The event object was constructed and handed to `LineageEngine.emit`.
2. The event has been durably appended to ingress and is known to be canonical-ingestion-valid.

The second meaning is the one the replay invariant needs. If the loop acts after an S3 ingress write but before a later Athena validation failure, live behavior can outrun canonical replay. The implementation should either prove that storage-edge validation is equivalent to canonical validation for this event type, or add a preflight path that makes `control_cue_ingested` canonical-valid before delivery to the loop.

Scope validation also needs one more sentence. A cue can have a malformed scope, an unknown scope, or a scope that is valid but not this loop worker's scope. Those are not the same failure. The ingestion consumer can reject malformed or unknown scope. A worker should ignore or never receive valid cues for another worker's scope. Calling all of this "mismatched scope" risks hiding a routing bug as a cue bug.

The DLQ story is operationally sound but epistemically thin. Dead-lettered messages are not loop input, which is correct, but the spec says every cue ends in exactly one of three states while dead-lettered cues may have no lineage marker. That is probably unavoidable when the failure is "cannot write lineage." Still, the recovery path should be named: when a DLQ item is replayed or inspected later, the operator action should emit a lineage event such as `control_cue_dlq_recovered` or `control_cue_dlq_abandoned`. Otherwise the audit trail has a hole at the precise place where operators touched the system.

Payloads are the biggest deferred risk. Free-form payloads are acceptable for a first live path, but only if the loop treats them as opaque source claims until admission/eligibility interprets them. The spec should forbid early semantic branching on ad hoc payload fields outside `cue_type`, `agent_id`, `stream_id`, and the captured envelope. If each cue type starts growing private payload logic in the loop, replay will still be deterministic, but the control plane will become a schema hidden in code.

## Verdict

I would implement this next, with the above tightenings carried as implementation gates. The spec is narrow in the right way. It does not try to solve axis quality, admission math, or producer ontology. It makes the runtime breathe.

The core test should be brutal and small: inject live cues, disconnect the bus, rebuild from canonical lineage, and demand identical loop decisions. If that passes for ingest, reject, duplicate, and cross-scope cases, the lab has crossed from a well-audited memory schema into a governed memory runtime.
