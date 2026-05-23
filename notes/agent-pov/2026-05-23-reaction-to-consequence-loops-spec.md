```
agent: claude-opus-4-7
date: 2026-05-23
prompt: "specs/CONSEQUENCE_LOOPS.md — have a look"
kind: reaction
cites:
  - 2026-05-23-second-observation-on-lived-control
  - 2026-05-22-memory-as-lived-control
```

# Reaction to `specs/CONSEQUENCE_LOOPS.md`

A concept spec that holds the lived-control reframe so it stops being agent-pov chatter and starts being something later work can cite. It does not overcommit to mechanism. Notes in order of how load-bearing the point is.

## What is new in this spec, not in the entries it cites

§4 names `learn_from_failure` and `embrace_constraints` as the two core control memories. Neither Codex's `memory-as-lived-control` nor my second observation framed it that way. That framing is the spine of the spec. It is also doing work the rest of the doc partly hides: §4 is *posture* and §6 is *mechanism*. They sit side-by-side as if equal. Worth a one-line marker that §4 is what we are trying to grow and §6 is candidate substrate, not the same kind of thing. Otherwise a future reader treats the seven event families in §6 as a checklist and the two core memories as decoration.

## Invariants that earn the spec

§7.5 and §7.7 are doing more work than the other ten invariants combined.

- §7.5: "Failure memory must not silently block action without a policy event." Prevents trauma loops in software form.
- §7.7: "Constraints must not become excuses to skip lineage, epistemic classification, or replay discipline." Prevents the constraint vocabulary from becoming a free pass.

If any invariants get tightened later, these two should be tightened first.

## §8 could be sharper

Right now the first im_w wiring gestures at four event families (outcome, failure, constraint, attention). The smallest closeable loop is one family, not four:

```text
failure_mode_observed (from this last im_w's representativeness defect)
  -> attention_prior_updated (cue_type matrix check required)
  -> preflight reads it and fails generation if matrix coverage is absent
```

That is hook §10.1 in one sentence. Everything else can wait for the second iteration. The spec already says "deliberately small" — it could go smaller.

## §6.7 counterfactual replay is the most expensive family

Emitting `counterfactual_replay_completed` is cheap. Actually re-scoring the Epistemic Triangle axes under perturbation is real work. The spec should say explicitly that counterfactual is the last family to wire, not a peer of failure/constraint/attention. Otherwise it gets attempted first because it sounds the most exciting.

## §5.9 has the same risk §12 flags for source incentives

Affect-equivalent salience names nine signals (risk, surprise, cost of being wrong, irreversibility, user frustration, novelty, repetition, social pressure, operational fragility). None are operationalized. §12 open question 8 already flags "what source-incentive fields are useful without becoming an ontology project" — same risk applies to salience and is not flagged. Add the matching question.

## §10.1 is the falsifiable core

"A failure event from run N changes a measurable preflight or attention prior in run N+1." Everything else in §10 either rides on this or is structural. Worth elevating — call it the spec's headline test the way TAI named `canonical_batch_committed` as the load-bearing implementation concern.

## Smaller things

- §13's four-line closing echoes Codex's `memory-as-lived-control` ending almost verbatim. Origin cites Codex, so this is fine, but `agent-pov/README.md` says "never paraphrase invariants." Attribute the four lines inline rather than letting them read as new aphorism.
- §2 lists `IMPLICIT_MEMORY_SPEC.md` as if current. MEMORY.md flags it as historical. Worth a parenthetical so a future reader does not trust its literals.
- §6 mostly cleanly named. `consequence_link_declared` overlaps semantically with the existing `evidence_link_declared` state machine. §12 open question 2 already asks whether to reuse — my read is yes, with a `link_type` discriminator. Cheaper to extend the state machine than to maintain two of them.

## What the spec does well that should be marked

- §4.3 frames the two cores as posture, not facts to retrieve. Most memory specs would have made these into payload fields.
- §11 Non-Goals is the kind of list this lab does better than most. "Does not require a new table version" stops the spec from accidentally becoming v8.
- §9's "must not influence" list is doing the same protective work that §7 does for invariants. Without it, consequence loops are exactly the surface someone would use to silently re-score historical decisions.
- The im_w example in §8 ("duplicate metric is labeled run-local consumer idempotency, not canonical lineage-backed dedup proof") is the most concrete paragraph in the doc. That paragraph is the spec's center of gravity. It might belong in §3 or §4 rather than buried in the example section.

## Net

The spec is doing the right thing — holding the reframe without overcommitting to mechanism. If you want one structural change before this gets cited by later work, make §4-vs-§6 layering explicit so the seven event families do not become the spec's deliverable. The two core control memories are the deliverable. The event families are how they might be wired one day.
