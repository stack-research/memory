# AGENTS

This file sets working rules for agents operating in this repository.

## Purpose

Build an experimental memory lab that tests reality formation, not just retrieval ordering. This is AWS-native only (no local storage backend).

## Core Model

- Memory is a control system, not a storage bucket.
- Two planes:
  - Cognitive plane: mutable, adaptive, reconstructive.
  - Audit lineage plane: immutable, append-only, replayable.
- Invariant: cognitive state may mutate; lineage must not.

## Architecture Boundaries

S3 Tables are canonical lineage.
S3 Vectors are rebuildable recall indexes.
Athena is the audit microscope.
IAM is the v0 boundary.

Current lab ingestion path (explicit temporary simplification):
- Engine code appends lineage events as JSON objects to the ingress S3 bucket (`AWS_S3_LINEAGE_INGRESS_BUCKET_NAME`).
- Athena ingestion job builds/uses `lineage_events_raw` and `lineage_events_quarantine`.
- Athena ingestion writes validated rows to `AWS_ATHENA_TARGET_TABLE_FQN` (default `memory_lab.memory_events`).
- Keep event envelope stable so we can later tighten canonical write path directly into S3 Tables-managed lineage.

## Retrieval and Reality Safety

- Do not auto-resolve contradictions.
- Quarantine suspicious or poisoned memories before promotion.
- Use eligibility gating before memory can influence output:
  - relevance * trust * recency * reinforcement * consistency * safety

## Operational Guidance

- use `uv` for Python environment and dependency management in this project
- Prefer simple, auditable flows over premature optimization.
- Design for replay, traceability, and rebuildability first.
- AWS CLI/CDK/SDK interaction should use the aws profile `stack-research`.
- The AWS CDK should be used for infrastructure as a service.
- The AWS SDK for Python should be used to interact with services. Avoid redundant API Gateway/Lambda custom APIs.
- Amazon Bedrock for models and embeddings
- ASCII printable characters only when modifying AWS CDK strings
