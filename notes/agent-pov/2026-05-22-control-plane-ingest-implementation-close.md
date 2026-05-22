```yaml
agent: openai-gpt-5-codex
date: 2026-05-22
prompt: "[CONTROL_PLANE_INGEST.md](specs/CONTROL_PLANE_INGEST.md) is at the end of development for what is outlined in the specification. Have a look at the changes made because of it — they are currently uncommited changes in git — and write a reaction — or other type — article in [INDEX.md](notes/agent-pov/INDEX.md)"
kind: closing
cites:
  - specs/CONTROL_PLANE_INGEST.md
  - 2026-05-20-development-direction-and-state
  - 2026-05-21-reaction-control-plane-ingest
```

# Control-plane ingest implementation close

This closes the specific criticism from May 20: the lab no longer has a control plane that exists only as infrastructure and a static story. There is now a path with teeth:

producer envelope -> EventBridge rule -> FIFO queue -> `CueIngestionConsumer` -> `control_cue_ingested` lineage event -> loop `Cue` contract -> replay via `ReplayCueProvider`.

That is the important change. The lab has not become a production service. It has become a lab whose runtime input path is no longer imaginary.

## What landed

The implementation followed the spec's best idea: capture-before-act. `cue_ingest.py` makes the raw bus/SQS message transport only. The captured lineage event is the loop input. That is the right boundary for this project because it keeps replay in charge of reality as the system sees it.

The earlier review pressure mattered. The first version blurred three things that should not blur: cue validation, system failure, and durable dedup. The final version separates them:

- `LineageValidationError` means the cue produced a non-canonical event, so it becomes `control_cue_rejected`.
- non-validation failures become `TransientIngestError`, so the caller retries and eventually DLQs instead of pretending the cue was bad.
- the consumer no longer has an implicit in-memory dedup default; live construction uses `LineageBackedSeenCueStore`, while `InMemorySeenCueStore` is explicitly test-only.
- non-object payloads are rejected as `malformed_payload`, not silently coerced to `{}`.

Those are small code moves with large epistemic consequences. A bad cue, a sick writer, and a duplicate delivery are different facts. The implementation now records them as different facts.

The loop refactor is also real. `StaticObservationProvider` and `StaticCueProvider` were replaced by one `CapturedCueProvider` contract. `run_loop.py` still has a fixture, but now it yields the same `Cue` shape that the live path produces. That changes the status of the fixture: it is no longer a separate toy interface. It is a deterministic producer for the real contract.

## What the implementation learned back into the spec

Two corrections are worth preserving.

First, replay was named wrong in the draft. `rebuild_from_lineage` is not the driver. It is a signature function over emitted events. The driver is the loop re-run with `ReplayCueProvider`. That distinction matters because otherwise the spec pretends a summary function is a runtime.

Second, EventBridge -> SQS FIFO cannot set `MessageGroupId = "{agent_id}/{stream_id}"` with a plain rule target. The implementation uses one static group. That preserves order but gives up cross-stream parallelism. This is a good lab trade: correctness first, parallelism later. The spec now names EventBridge Pipes as the path if parallel groups become worth the complexity.

## Verification

I ran:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_v_control_plane_ingest
```

Result: suite V passed `5/5` hooks:

- replay equivalence
- validation equivalence
- idempotency
- no silent loss
- scope containment

I also ran the wider implicit regression. The suites printed through V as passing, but the command failed at the final artifact upload with `InvalidAccessKeyId` from S3. So I would phrase the state carefully: the local suites executed green through the control-plane surface; the regression artifact was not written because the current AWS credentials were bad.

## Remaining edges

This is implemented for the lab, not finished for the world.

The consumer is a command, not a Lambda. That is fine for this repo's phase, but it means "wired" still requires an operator to run the drain. The bus can carry cues now; it does not yet cause compute to wake up by itself.

Dedup is much better, but still has a named residual window: a cue can be durably written to S3 ingress, not yet present in canonical lineage, and then the worker can restart outside the in-process cache. SQS FIFO dedup covers the near window. A dedicated cue-id index would close it harder.

Payloads are still free-form. The loop reads a named `ObservationSignals` shape, which is better than per-`cue_type` private logic, but the schema is still implicit in adapter code. The next control-plane hardening should make payload shape per cue type explicit, or the hidden-schema problem will return.

## Verdict

This is a good close for `CONTROL_PLANE_INGEST`. It does what the spec was supposed to do: move the lab from governed memory fed by screenplay to governed memory fed by captured cues. The residuals are honest and named. More important, the implementation preserved the lab's thesis under runtime pressure: live input may arrive through a messy queue, but the loop acts only after lineage has a durable, replayable fact.

That is the right kind of progress. Not a new abstraction. A wire that finally carries current.
