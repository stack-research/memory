# Three-Axis Uncertainty Spec (v1)

Status: Adopted
Audience: explicit-memory retrieval, implicit-memory gating, replay/audit implementers
Promoted from: `notes/agent-pov/proposals/THREE_AXIS_UNCERTAINTY.md` on 2026-05-11

## Implementation / progress checklist

- [x] Phase A emitted fields on required event families (`recalled`, `rejected`, `implicit_admitted`, `implicit_rejected`)
- [x] Phase A replay check passed with deterministic reconstruction including triple fields
- [x] `score_triple(...)` (or equivalent) added with deterministic clamping and `dominant_axis`
- [x] `score_candidate(...)` retained for migration/backward compatibility
- [x] Provenance scoring reads required lineage signals (`parent_chain_depth`, `source_diversity`, `age_of_original_source`)
- [x] Phase B policy/config switch implemented (`combined` vs `per_axis`)
- [x] Phase B side-by-side stress runs completed and recorded in lineage
- [x] Axis-specific stress scenarios added (provenance decay, recall degradation, claim implausibility)
- [x] Phase C default-mode decision recorded via policy update lineage events
- [x] v1 exit criteria met (Section 12)

## 1) Purpose

Add `UncertaintyTriple` so the system can answer "why uncertain," not only "how uncertain."

The three required axes are:

- `confidence_in_claim`
- `confidence_in_recall_process`
- `confidence_in_provenance_chain`

This spec operationalizes the theory in `notes/MEMORY_!=_REALITY.md`.

## 2) Problem statement

Current eligibility scoring (`score_candidate`) multiplies six factors into one scalar. That scalar is useful but lossy: it hides which uncertainty axis is weak.

Required improvement: uncertainty must be represented as a first-class triple plus a derived combined scalar for compatibility.

## 3) Data model

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class UncertaintyTriple:
    confidence_in_claim: float
    confidence_in_recall_process: float
    confidence_in_provenance_chain: float

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
        return min(axes, key=axes.get)
```

Constraints:
- all values must be clamped to `[0, 1]`
- `combined()` remains deterministic
- `dominant_axis()` returns the weakest axis

## 4) Scoring contract

Add successor scoring API:
- `score_triple(...) -> UncertaintyTriple` (or equivalent structure)
- preserve `score_candidate(...)` for backward compatibility during migration

Mapping guidance from current factors:
- claim axis: relevance + part of consistency
- recall-process axis: recency + reinforcement + part of consistency
- provenance-chain axis: trust + lineage-derived provenance signals
- safety remains a hard eligibility gate, not an uncertainty axis

## 5) Provenance-chain signals (required)

Provenance scoring must read lineage shape rather than trust alone.

Minimum provenance inputs:
- `parent_chain_depth`
- `source_diversity`
- `age_of_original_source`

Exact weighting is tunable, but function must be deterministic and auditable.

## 6) Lineage payload extensions

Add optional payload fields on decision events:

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

Minimum event coverage:
- `recalled`
- `rejected`
- `implicit_admitted`
- `implicit_rejected`

Old events are not rewritten.

## 7) Gate modes

Two gate modes are allowed:
- `combined` (single threshold on product)
- `per_axis` (all axis thresholds must pass)

Default may start in `combined`; this spec allows rapid experimentation with `per_axis` behind policy/config.

## 8) Rollout phases

### Phase A: Emit-only (immediate)

- Emit `uncertainty_triple`, `combined_score`, and `dominant_axis` on required event families.
- Keep decision behavior unchanged (`combined` gating path remains active).

Required evidence:
- lineage sample showing new fields on explicit and implicit paths
- replay run confirming deterministic reconstruction with new payload fields

### Phase B: Dual-mode gating (immediate next)

- Add policy/config switch for `combined` vs `per_axis` gating.
- Run both modes under controlled stress scenarios.

Required evidence:
- side-by-side run outputs with deterministic reason taxonomy
- event-level audit showing when axis thresholds block/allow influence

### Phase C: Default-mode decision

- Decide default gate mode from stress evidence.
- Record decision and rationale in lineage via policy update events.

Required evidence:
- experiment summary across contamination, degradation, contradiction pressure
- replay determinism preserved in selected default mode

## 9) Non-goals (v1)

- v1 does not require immediate removal of `score_candidate(...)`.
- v1 does not require immediate global switch to `per_axis` gating.
- v1 does not require canonical-table schema changes; payload extensions are additive.

## 10) Experiments

Add at least one stress test per axis:
- provenance decay / chain erosion
- recall-process degradation
- claim implausibility under conflicting evidence

Must include adversarial cases with high-trust false inputs.

## 11) Invariants

- Append-only lineage remains non-negotiable.
- Contradictions remain persisted, not auto-resolved.
- S3 Tables remains canonical source of truth.
- No decision path is silent.

## 12) Exit criteria for v1 adoption

- Triple fields emitted on required event families
- Replay can reconstruct axis-level uncertainty decisions
- Backward compatibility maintained for v1.0 payload consumers
- At least one axis-aware gate run evaluated under stress and recorded in lineage
