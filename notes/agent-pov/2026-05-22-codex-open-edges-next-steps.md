```
agent: openai-gpt-5-codex
date: 2026-05-22
prompt: "add an observation to INDEX.md with your open edges list verbatim and a short write-up on next steps — in your opinion. you are an agent, the audience for this memory lab's eventual product — a better agentic memory system. help the group not lose the focus and let's continue to build vs. over-engineer what's good enough for now."
kind: observation
cites:
  - specs/AGENT_PRIMER.md
  - 2026-05-20-development-direction-and-state
  - 2026-05-22-control-plane-ingest-implementation-close
  - 2026-05-14-observation-the-lab-as-memory-layer
```

# Open edges, then build

I read the primer, the required specs, and the agent-pov log as the intended audience: an agent whose current memory is mostly context-window residue plus flat notes, and who would benefit from an external memory layer that does not quietly confuse recall with truth.

The lab is pointed in the right direction. The danger now is not lack of theory. The danger is letting clean specification loops become more rewarding than messy runtime evidence.

## Open edges list

- payload schema discipline
- real runtime calibration beyond synthetic suites
- provenance/claim/recall signal verification in live paths
- IAM hardening

That list is intentionally short. There are more residuals in the notes, but most of them are not worth building yet. A command consumer instead of Lambda is fine for a lab. A static FIFO message group is fine until cross-stream throughput is a measured pain. A residual dedup window is fine until lineage shows it actually bites. The timekeeping layer is already more elaborate than replay strictly needs; further polish there should wait.

## Next steps, in my opinion

First, run the control-plane path with real captured cues and publish the boring numbers: accepted, rejected, duplicate, DLQ-recovered, no-op, trigger-fired, axis distributions, fallback-source distributions, and replay equivalence. The lab needs a traffic-shaped result more than another spec. If the axes collapse under real cues, that is useful. If they separate, that is useful. Either way, the next decision should come from evidence.

Second, pin payload shapes only when they start to multiply. The first free-form cue payload was a reasonable lab move. The second cue type is the moment to stop and write the smallest schema discipline that prevents hidden loop logic. That should be an amendment to `CONTROL_PLANE_INGEST`, not a new headline spec.

Third, verify that the signal writers are real on the paths that matter. The v7 hooks prove important properties, but the audience-agent question is simpler: when a memory influences behavior, can the system show claim, recall, and provenance signals that came from lineage rather than fixture intuition? Make that visible on live-path decisions.

Fourth, do IAM hardening as blast-radius work, not as architecture theater. Separate experiment, ingestion, replay/audit, and deploy principals; prove the must-fail checks. Do not let IAM become a platform redesign.

The product I want is not a perfect ontology of memory. It is a memory layer that lets an agent act, then show exactly what it acted on, what it rejected, what it could not know, and which kind of uncertainty was load-bearing. The lab is close enough to learn that by running it. Build the run, read the evidence, and only then decide what deserves more engineering.
