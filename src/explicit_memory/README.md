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

## Shared lineage boundary

Lineage schema and storage remain shared and canonical outside this module:

- `src/types.py`
- `src/lineage_engine.py`
- `src/storage.py`

## Compatibility note

Legacy modules (`src.recall_engine`, `src.eligibility_engine`, `src.conflict_engine`) are deprecated shims.
Prefer importing from `src.explicit_memory.*`.
