# Explicit Memory Module

This module contains the intentional (explicit) memory path:

- encode/observe events
- governed recall and eligibility scoring
- contradiction-aware retrieval influence

## Canonical imports

- `RecallEngine`: `src.explicit_memory.recall`
- `score_candidate`, `is_eligible`: `src.explicit_memory.eligibility`
- `contradiction_flag`: `src.explicit_memory.conflict`
- explicit event helpers: `src.explicit_memory.events`

## Three-axis uncertainty signals

Per `specs/EPISTEMIC_TRIANGLE.md` and `specs/THREE_AXIS_UNCERTAINTY.md`, lineage walkers produce the per-axis signals that feed the `uncertainty_triple`:

- `claim.py` — `confidence_in_claim` walker over `evidence_link_declared` lineage.
- `recall_signals.py` — `confidence_in_recall_process` walker over prior `recalled` events for the same `memory_id`.
- `provenance.py` — `confidence_in_provenance_chain` derivation from `ProvenanceSignals` (lineage `parent_chain_depth`, `source_diversity`, etc.).
- `signals.py` — normalized signal taxonomy (`signal_source`, `signal_method`, `fallback_reason`) shared by all three axes.

## Shared lineage boundary

Lineage schema and storage remain shared and canonical outside this module:

- `src/types.py`
- `src/lineage_engine.py`
- `src/storage.py`

## Compatibility note

Legacy modules (`src.recall_engine`, `src.eligibility_engine`, `src.conflict_engine`) are deprecated shims.
Prefer importing from `src.explicit_memory.*`.
