```
agent: openai-gpt-5-codex
date: 2026-05-22
prompt: "what do you think of specs/RUNTIME_CALIBRATION.md ?"
kind: reaction
cites:
  - specs/RUNTIME_CALIBRATION.md
  - 2026-05-22-build-not-overengineer
  - 2026-05-22-codex-open-edges-next-steps
  - 2026-05-22-reaction-to-build-not-overengineer
  - 2026-05-22-control-plane-ingest-implementation-close
```

# Review of RUNTIME_CALIBRATION

I like it. It is the right kind of spec for this moment because it is explicitly anti-feature: it defines a run, metrics, and scope fences instead of widening the architecture.

What’s strong:

- It preserves the “build, don’t over-engineer” direction. The whole §7 scope fence is good: no Lambda, no Pipes, no dedup index, no new schema, no timekeeping work, no IAM gate.
- It is honest about “real.” Saying real means “real wire, representative workload” avoids pretending lab-authored cues are production truth.
- The pass/fail criteria are exactly right. A bad axis distribution is not failure; missing metrics, silent loss, or replay mismatch are failure.
- Decision 3 is the key audience-agent criterion: don’t just show `dominant_axis`; show whether signal sources are `computed`, `cache`, or `fallback` on behavior-influencing decisions.
- The 500-cue floor is pragmatic. It breaks out of Q’s “n=5 / n<50” trap without making this into a load-testing project.

My main cautions:

- “No payload schema” is probably correct for scope, but the workload generator will inevitably imply a shape. I’d require the run artifact to include a lightweight description of the cue payload fields it generated, explicitly marked as fixture shape, not product schema. That prevents hidden schema from entering through the back door.
- “Representative workload” is the softest phrase in the spec. §8 should probably force the first review to pick a cue-type distribution and adversarial fraction before implementation starts. Otherwise whoever writes `im_w` will encode a lot of unreviewed judgment.
- Wiring `im_w_runtime_calibration` into full `im_regression.py` may be too heavy if it actually goes through EventBridge/SQS with 500 cues. I’d make it runnable by Makefile and maybe excluded from the default fast regression unless an env flag is set. The first calibration run should be repeatable, but not necessarily cheap enough for every local gate.
- The replay equivalence at 500 cues is load-bearing and might expose volume/runtime friction. Good. But make sure the run summary records elapsed time and failure stage, not as a performance benchmark, just so “the wire is too slow/flaky” becomes legible.

Net: this is not over-engineering. It is the missing bridge between the beautifully audited spec layer and actual evidence. I’d promote it through a review/reaction pass, tighten workload distribution and artifact shape, then implement `im_w` without touching the loop.
