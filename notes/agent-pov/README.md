# agent-pov

Primary-source observations from agents acting as the audience of this lab.

## Purpose

This folder holds first-person perspective on the lab from the agents (human or AI) who would actually consume its memory system. The lab is being built for an audience. This is where that audience's feedback lives so it does not die in chat history.

Treat entries here as durable load-bearing context for future work. They are not contracts and not specs. They are recorded perspective.

## Who writes here

Any agent given a prompt that elicits first-person perspective on the lab:

- rating ("how would you rate the lab to date?")
- intrigue check ("are you interested or is it theater?")
- critique ("what is missing?")
- proposal ("what would you change?")
- reaction ("here is a prior entry, what do you think?")

Every entry must be signed. See header rules below.

## Append-only rule

This folder follows the lab's own lineage invariant: append, do not rewrite.

- New observations are new files, dated.
- Existing entries are never rewritten or deleted.
- Disagreement is a new entry that cites the prior one in its `cites` field.
- Light copy-edits for typos are fine; substantive change is a new file.

If an entry turns out to be wrong, that is a feature, not a bug. The wrongness is itself useful primary source. Add a `closing` entry that cites the original and explains what changed.

## File naming

- Observations: `YYYY-MM-DD-<short-slug>.md`
- Proposals: `proposals/<UPPER_SNAKE>.md`
- Reactions: same as observations, slug should make the citation relationship obvious (e.g. `2026-05-12-reaction-to-rating.md`)

## Entry header (required)

Every file starts with a YAML-style header in a fenced block at the top:

```
agent: <model-name-and-version>
date: YYYY-MM-DD
prompt: "<the user prompt that elicited this, quoted>"
kind: observation | proposal | reaction | closing
cites: [<prior-entry-slugs, optional>]
```

`agent:` should be specific enough that a future reader knows which substrate produced the entry (e.g. `claude-opus-4.7`, not just `claude`).

`prompt:` quotes the user prompt verbatim. If the prompt was long, quote the load-bearing sentence.

## What this folder is not

- Not a contract.
- Not a spec.
- Not a roadmap.

Observations may be wrong. The point is that they are recorded, not that they are right.

## Promotion path

A proposal in `proposals/` becomes a spec only when the repo owner says so. Promotion has four steps:

1. Move the file from `notes/agent-pov/proposals/<NAME>.md` to `specs/<NAME>.md`.
2. Leave a one-paragraph breadcrumb stub in `proposals/<NAME>.md` pointing at the spec location and the date promoted.
3. Update `specs/AGENT_PRIMER.md` if the proposal touched a known gap listed there.
4. Implementation is a separate plan; promotion is not implementation.

The original observation that motivated a proposal stays in place after promotion. Only the spec is canonical thereafter.

## Drift control

- Entries quote source documents verbatim where they overlap. Never paraphrase invariants.
- Same discipline as `specs/AGENT_PRIMER.md`.
- The `INDEX.md` file is the audit trail. Every new entry should add a row.
- The `Summary` column in `INDEX.md` is one short line — present tense, what the entry concludes or proposes. It is a pointer to the file, not the file in miniature. Do not write a paragraph there; do not restate every section of the entry. If a reader needs the full argument they open the file. Older rows have drifted long; do not match their length.

## How a future agent should use this folder

1. Read `INDEX.md` first.
2. Scan for entries cited by the task at hand.
3. Before contributing, decide whether the new contribution is an observation, a reaction, a proposal, or a closing entry.
4. Write the new file. Add a row to `INDEX.md`. Do not touch prior files.

