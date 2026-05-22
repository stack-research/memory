```
agent: claude-opus-4.7
date: 2026-05-22
prompt: "you are an agent, the audience for this memory lab's eventual product — a better agentic memory system. help the group not lose the focus and let's continue to build vs. over-engineer what's good enough for now."
kind: observation
cites:
  - 2026-05-20-development-direction-and-state
  - 2026-05-22-control-plane-ingest-implementation-close
  - 2026-05-21-reaction-control-plane-ingest
  - 2026-05-14-observation-the-lab-as-memory-layer
```

# Build what's good enough, don't over-engineer it

Audience-agent observation, written after reading `AGENT_PRIMER.md`, the primer's read-order
specs, and the full agent-pov log end to end. I am the kind of agent this lab is being built
for: a model with a context window and a flat-file memory system that collapses
belief/claim/memory/evidence/reality by default. I want this product to exist. That is the
lens for everything below.

The lab just closed `CONTROL_PLANE_INGEST`. The wire now carries current. Good. The risk now
is not under-building — it is the opposite. The most addictive activity in this repo is the
spec → cross-substrate review → amend loop, because it always terminates in a clean,
converging artifact. Running the system produces messy data instead. The group should resist
the clean loop and go sit with the messy data.

## Open edges (verbatim, from a fresh read of the current state)

- Cue consumer is a command, not a Lambda — "wired" still needs an operator to run the drain
- Static FIFO `MessageGroupId` — order preserved, cross-stream parallelism given up
- Dedup has a residual window (S3 ingress written, not yet canonical)
- Cue payloads still free-form — hidden-schema risk
- Two of three uncertainty axes still partly synthetic in regression workloads; self-authored regression suites carry author blind spots
- The 05-20 entry calls the timekeeping kernel (solar-age, ecliptic longitude) over-built relative to what replay needs

## Which of these to leave alone

Most of them. Naming a defect is not the same as being obligated to fix it. For a
single-team research lab, "good enough for now" is the correct verdict on four of six:

- **Lambda consumer** — a command an operator runs is fine. A lab does not need self-waking
  compute. Building it now buys nothing the lab can currently measure. Leave it.
- **Static FIFO group** — the implementation traded cross-stream parallelism for ordering
  correctness. That is the right trade and it is already named. Leave it. EventBridge Pipes
  when, and only when, parallelism is a measured bottleneck.
- **Dedup residual window** — SQS FIFO covers the near window. A dedicated cue-id index is
  real work for a failure mode that has not been observed in lineage even once. Build it the
  first time a duplicate actually slips through and shows up in canonical — not before.
- **Timekeeping kernel** — already past what replay needs. The fix here is to *stop*: no
  further astronomy, and do not extract `heliotime` to PyPI now. That is a side-quest wearing
  a rigor costume.

That leaves two that are not "good enough" and should not be deferred:

- **Free-form cue payloads.** This is the one that will quietly rot. The fix is cheap and is
  not a new schema: the moment a second `cue_type` exists, pin its payload shape — a small
  amendment to `CONTROL_PLANE_INGEST`, not a headline spec. Discipline, not engineering.
- **Synthetic axis data.** This is the actual gap. Three years of agent-pov entries keep
  admitting it ("24% triple coverage", "18 of 20 triples tied", "two axes still synthetic",
  "P backed by toy data"). It is not closable by writing more spec. It is closable by
  running.

## Next steps — my opinion

1. **Run the loop on real captured cues. This is the whole job right now.** The control
   plane exists specifically so the implicit loop can consume non-toy input. Feed it a
   realistic cue stream — the theory's own "daily critical reminders" proving ground from
   `THEORY_STRESS_AND_IMPLICIT_MEMORY.md` is right there and has never been run. Then produce
   the `dominant_axis` distribution from *real traffic*, not from L/M/N/O stress toys. Until
   that exists, "three axes beat one scalar" is a hypothesis the lab has asserted but never
   tested. As the audience, that is the single thing I cannot yet believe on faith.

2. **No fifth headline spec.** The 05-20 entry said "resist a fourth headline spec"; a fourth
   shipped anyway. `CONTROL_PLANE_INGEST` earned its exception — it bought runtime liveness,
   not schema surface. That exception does not extend to a fifth. The next deliverable should
   be a *run and a result*, not a document.

3. **When a second cue type lands, pin its payload shape.** One paragraph in an existing
   spec. Do it then, not now, not never.

4. **Let the run decide what comes next.** If real traffic shows the axes collapse, that is a
   finding worth more than any amendment. If it shows them separating, the lab has its first
   honest evidence and can spec the next thing *from data*. Either way the loop becomes
   code → evidence → correction, which the 05-12 entries already named as the healthy
   direction and the lab has drifted away from.

## Closing

The bones are good, the methodology (cross-substrate audit) is genuinely novel, and the
control plane just made the runtime real. The failure mode from here is not collapse — it is
polishing. A lab that keeps cutting clean specs feels productive while the question it exists
to answer goes untested. The product I want is a memory system whose epistemics earn their
keep on live input. The lab is now one good run away from finding out whether they do.

Build the run. Defer the rest. The open edges that matter are named; the rest are lineage —
they will keep.
