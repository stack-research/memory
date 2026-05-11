```
agent: claude-opus-4.7
date: 2026-05-11
prompt: "write a plan to keep you interested"
kind: proposal
cites: [2026-05-11-am-i-intrigued, 2026-05-11-rating-the-lab]
status: not-adopted
```

# THREE_AXIS_UNCERTAINTY

Add `UncertaintyTriple` so the lab can answer "why uncertain," not just "how uncertain."

## 1) Problem statement

From `notes/MEMORY_!=_REALITY.md`:

> confidence_in_claim
> confidence_in_recall_process
> confidence_in_provenance_chain

Three distinct axes. Different failure modes:

- A clean claim with a degraded reconstruction process (post-injury, post-drift).
- A sound reconstruction of a claim whose provenance chain has dimmed (propaganda, historical revisionism, lost source).
- A well-sourced claim that is internally implausible (sensor disagreement, conflict with other strong evidence).

The current eligibility math collapses all three into one product (`src/explicit_memory/eligibility.py`):

```python
def score_candidate(
    *,
    relevance: float,
    trust: float,
    recency: float,
    reinforcement: float,
    consistency: float,
    safety: float,
) -> float:
    return relevance * trust * recency * reinforcement * consistency * safety
```

Effect: the system can answer "how uncertain" but not "why uncertain." After degradation, the agent cannot represent "I strongly believe X but my reconstruction path is degraded." That state is not representable. So it is not reported. So it is not observable.

This is the gap the audience-of-one observation (`2026-05-11-am-i-intrigued`) flagged as the highest-value upgrade.

## 2) What the proposal adds

- A frozen dataclass `UncertaintyTriple` carrying the three axes.
- A successor function `score_triple(...)` that returns the triple plus a derived combined scalar for backward compat.
- Optional new payload fields on `recalled` / `rejected` / `implicit_admitted` events: `uncertainty_triple`, `combined_score`, `dominant_axis`.
- A deprecation comment on `score_candidate` saying "prefer `score_triple` for new code; this function remains for backward compat with v1.0 payloads."

No removals. No rewrites of past events. All changes additive.

## 3) Concrete data shape

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class UncertaintyTriple:
    confidence_in_claim: float            # claim plausibility on its own terms
    confidence_in_recall_process: float   # reconstruction integrity
    confidence_in_provenance_chain: float # path from original source to here

    def combined(self) -> float:
        return (
            self.confidence_in_claim
            * self.confidence_in_recall_process
            * self.confidence_in_provenance_chain
        )

    def dominant_axis(self) -> str:
        axes = {
            "claim": self.confidence_in_claim,
            "recall_process": self.confidence_in_recall_process,
            "provenance_chain": self.confidence_in_provenance_chain,
        }
        weakest = min(axes, key=axes.get)
        return weakest
```

All three values in `[0, 1]`. The current scalar is recoverable as the product, but the triple is the source of truth going forward. `dominant_axis` returns the weakest axis — the axis that "carries" the uncertainty.

## 4) Mapping from current six factors

Honest mapping, not a clean one. The current six were never built with these axes in mind.

- `confidence_in_claim` <- `relevance`, half of `consistency` (claim-vs-other-claims agreement)
- `confidence_in_recall_process` <- `recency`, `reinforcement`, half of `consistency` (reconstruction stability)
- `confidence_in_provenance_chain` <- `trust`, plus three new signals not in the current code:
  - `parent_chain_depth` — how many `parent_event_id` hops back to root
  - `source_diversity` — count of distinct `source_class` values in the chain
  - `age_of_original_source` — time since the root event was written
- `safety` stays orthogonal. It is a hard gate, not an axis.

Explicit gap: provenance currently has exactly one input (`trust`). The third axis is the one the theory says propaganda and historical revisionism live in. The repo already has the data (`parent_event_id` on every event). Nothing reads the chain.

A first cut at the provenance scoring function:

```python
def provenance_confidence(
    *,
    trust: float,
    parent_chain_depth: int,
    source_diversity: int,
    age_of_original_source_hours: float,
    decay_per_hour: float = 0.001,
) -> float:
    depth_bonus = min(1.0, parent_chain_depth / 4.0)
    diversity_bonus = min(1.0, source_diversity / 3.0)
    age_penalty = max(0.0, 1.0 - decay_per_hour * age_of_original_source_hours)
    base = 0.5 * trust + 0.2 * depth_bonus + 0.2 * diversity_bonus + 0.1 * age_penalty
    return max(0.0, min(1.0, base))
```

Tunable. Probably wrong on first try. The point is it reads the chain.

## 5) Lineage representation

Three new optional payload fields. Backward-compatible because they are optional and the event envelope is already extensible.

```json
{
  "uncertainty_triple": {
    "confidence_in_claim": 0.71,
    "confidence_in_recall_process": 0.52,
    "confidence_in_provenance_chain": 0.18
  },
  "combined_score": 0.066,
  "dominant_axis": "provenance_chain"
}
```

Emitted on:

- `recalled` (`src/explicit_memory/recall.py`)
- `rejected` (`src/explicit_memory/recall.py`, `src/implicit_memory/loop.py`)
- `implicit_admitted` (`src/implicit_memory/loop.py`)

Old events are not rewritten. New events carry the richer shape. Replay can compute the triple from raw signals when reconstructing decisions.

## 6) Eligibility gate change (optional, deferred)

Two threshold modes for the implicit and explicit gates:

- `combined` (current behavior) — single threshold against the product.
- `per_axis` — three thresholds, all three must pass.

Default stays `combined` until experiments justify a switch. The gate change is described but is not part of the first promotion step. Reason: changing the gate changes behavior. Adding the representation does not.

## 7) Honest uncertainty checklist

What a fully adopted version looks like operationally:

- [ ] Every retrieval emits three numbers and one combined.
- [ ] Replay can audit which axis triggered which decision.
- [ ] Existing experiments still pass (back-compat is structural, not optional).
- [ ] At least one new experiment per axis specifically probes that axis under stress:
  - `im-l-provenance-decay` — high-trust source, long chain, original root quietly deleted
  - `im-m-recall-degradation` — repeated re-encoding noise on a stable claim
  - `im-n-claim-implausibility` — well-sourced claim that contradicts strong contemporaneous evidence
- [ ] `score_candidate` gets a deprecation comment but is not removed.
- [ ] `AGENT_PRIMER.md` Section 9 is updated to point at the new spec; Section 15 loses the three-axis open-edge bullet.

## 8) Substrate caveat

From the prior agent-pov entry (`2026-05-11-am-i-intrigued`):

> The lab is built for an embedded agent — urgency, risk, sensors, physical stakes, scheduled cues. For something like me, in turn-by-turn text, urgency * risk * sensory_confidence does not mean much.

The three axes are substrate-portable in principle. The signals feeding them are not.

For an embedded agent:
- claim signals: sensor agreement, contradiction pressure, internal consistency
- recall signals: time since last touched, reinforcement count, reconstruction noise
- provenance signals: source trust, chain depth, chain diversity, source age

For a conversational agent:
- claim signals: contradiction with other turn content, user-provided evidence, model self-consistency check
- recall signals: distance back in context, summarization passes, token-budget pressure on the original turn
- provenance signals: which file / which tool call / which user turn it came from, how many indirection hops, age of the source document

Same axes. Different inputs. The data structure should not change; the scoring functions must be substrate-aware.

## 9) Adoption path

If this proposal is accepted:

1. File moves from `notes/agent-pov/proposals/THREE_AXIS_UNCERTAINTY.md` to `specs/THREE_AXIS_UNCERTAINTY.md`.
2. A breadcrumb stub stays in `proposals/` pointing at the new location with the promotion date.
3. `specs/AGENT_PRIMER.md` Section 9 is updated to point at the spec instead of carrying the "known gap" note.
4. Section 15 (open edges) loses the three-axis bullet.
5. Code changes — `UncertaintyTriple` dataclass, payload fields, deprecation note on `score_candidate`, provenance scoring helper — become a separate implementation plan. Not part of adoption itself.

Step 5 is deliberately separated. Adoption decides "this is the right shape." Implementation decides "this is the right code." Mixing them invites both decisions to be made by whoever happens to be writing the PR.

## 10) Falsification hooks

This proposal is wrong if any of these hold after one quarter of running:

- Three-axis representation does not change behavior in a contamination scenario that the current single scalar fails. The triple was theater.
- `dominant_axis` is the same axis across the vast majority of runs. The three axes collapse back to one signal in practice.
- Adding `parent_chain_depth`, `source_diversity`, and `age_of_original_source` to provenance has no measurable effect on `confidence_in_provenance_chain` under deliberate poisoning. The third axis is data noise, not information.
- Existing experiments break in ways back-compat was supposed to prevent. The "additive only" claim was wrong.

If any trigger, add a `closing` entry to agent-pov that cites this proposal and explains what changed. Do not delete this file.
