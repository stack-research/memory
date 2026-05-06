# AGENTS

This file sets working rules for agents operating in this repository.

## Purpose

Build an experimental memory lab that tests reality formation, not just retrieval ordering.

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

## Retrieval and Reality Safety

- Do not auto-resolve contradictions.
- Quarantine suspicious or poisoned memories before promotion.
- Use eligibility gating before memory can influence output:
  - relevance * trust * recency * reinforcement * consistency * safety

## Operational Guidance

- Prefer simple, auditable flows over premature optimization.
- Design for replay, traceability, and rebuildability first.
- AWS CLI/CDK/SDK interaction should use the aws profile `stack-research`.
- The AWS CDK should be used for infrastructure as a service.
- The AWS SDK for Python should be used to interact with services. Avoid redundant API Gateway/Lambda custom APIs.
- Amazon Bedrock for models and embeddings
