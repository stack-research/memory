# Theory Stress and Implicit Memory

Purpose: capture theory pivots from recent design discussion so future agent loops inherit context.

## Core pivot

Do not run confirmation demos when outcomes are already known.
Use falsification-oriented stress tests that can break assumptions.

## Anchor

- Baseline/common systems: encode + store + retrieve loop.
- Target in this repo: governed memory control system.

## Operating doctrine

Act on risk, don't wait on permission; always emit lineage; allow intervention, don't require it.

Footnote: "safest known strategy" may be incomplete or poisoned. Sensory-grounded actors may detect reality shifts sooner than distant observers.

## Key theory additions

1. Significance-triggered write; policy-gated influence.
2. Contradictions are first-class state; do not auto-collapse.
3. Contamination is first-class risk (trust is prior, not truth).
4. Reflex mode is legitimate but must be bounded and auditable.
5. Closed-loop cognitive control with open-loop lineage audit.

## Where governed memory should intentionally lose

Governed memory should yield to simpler/reflex execution when:
- reaction-time dominates correctness,
- policy lookup cost exceeds expected error cost,
- overlearned local procedure is safer than deliberation,
- live sensory stream outranks stale memory traces,
- memory interruption risk exceeds omission risk.

Rule: default governed mode, fall through to bounded reflex mode when urgency-risk-sensory confidence crosses threshold, then emit full lineage.

## Primary attack surfaces to test

- spoofed urgency
- spoofed sensory confidence
- reflex lock-in
- contamination from high-trust false sources
- event flooding to obscure causality
- silent policy drift

## Minimal controls

- split-reality events on sensor disagreement
- reflex action/time budgets and cooldown
- forced re-entry to governed mode
- deterministic quarantine/rejection reason taxonomy
- append-only policy change events

## Practical proving ground

Use daily critical reminders as a real test case:
- state-aware prompting,
- missed-ack escalation,
- interruption cost accounting,
- replay of what changed belief/action and why.

If theory helps here under real cognitive pressure, it is useful.

## Relationship to specs

- This note is theory context.
- `specs/IMPLICIT_MEMORY_SPEC.md` is implementation-oriented contract.
- `AGENTS.md` carries concise operating rules for coding agents.
