# AGENTS

This file sets working rules for agents operating in this repository.

## Purpose

Build an experimental memory lab that tests belief formation, not just retrieval ordering.

## Core Model

- Memory is a control system, not a storage bucket.
- Two planes:
  - Cognitive plane: mutable, adaptive, reconstructive.
  - Audit lineage plane: immutable, append-only, replayable.
- Invariant: cognitive state may mutate; lineage must not.

## Architecture Boundaries

- Hot path:
  - S3 Vectors for similarity retrieval.
  - S3 objects for raw events and materialized memory state.
- Cold / analytic path:
  - Compacted Parquet + Athena + Glue Data Catalog.

Storage boundary rule:
- S3 Vectors bucket/index is retrieval-plane only.
- Parquet analytics data lives in separate standard analytics storage (bucket or strictly isolated analytics prefix).
- Raw event objects remain source-of-truth storage.

Hard rule:
- Vectors may influence recall.
- Parquet/event lineage must explain recall.

## Required Invariants

1. Every vector maps to a source event object identity or source payload hash.
2. Every Parquet row is traceable to raw event identity.
3. Vector indexes can be deleted and rebuilt from durable event/parquet data.

## Retrieval and Belief Safety

- Do not auto-resolve contradictions.
- Quarantine suspicious or poisoned memories before promotion.
- Use eligibility gating before memory can influence output:
  - relevance * trust * recency * reinforcement * consistency * safety

## Operational Guidance

- Context-first rule:
  - Before asking the user for clarification, check relevant files in `notes/` for existing intent, decisions, and terminology.
  - Ask clarifying questions only after this pass if ambiguity still blocks progress.
- Keep namespace examples suggestive until namespace sprint; avoid locking key grammar early.
- Prefer simple, auditable flows over premature optimization.
- Design for replay, traceability, and rebuildability first.

