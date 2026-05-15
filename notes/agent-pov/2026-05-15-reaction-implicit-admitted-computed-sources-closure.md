```yaml
agent: openai-gpt-5-codex
date: 2026-05-15
prompt: "yes, proceed"
kind: reaction
cites:
  - specs/EPISTEMIC_TRIANGLE.md
  - 2026-05-15-reaction-after-third-epistemic-triangle-update
  - 2026-05-15-epistemic-triangle-implementation-code-review-response
```

# Implicit-admitted computed-sources closure

Follow-up review after implementing the spec §15 exit criterion for implicit admission.

## What was added

- `implicit_admitted` decision payloads now carry axis signal blocks directly:
  - `claim_signals`
  - `recall_signals`
  - `provenance_signal`
- New falsification hook:
  - `hook_32_implicit_admitted_all_computed_sources`
  - emits a real `implicit_admitted` decision through `_admit_and_gate`
  - verifies `claim_signals.signal_source == "computed"`, `recall_signals.signal_source == "computed"`, `provenance_signal.signal_source == "computed"` on the same decision
  - verifies `subject_assertion_kind` present

## Verification

Ran:

```bash
PYTHONPATH=. uv run --project stacks python -m src.experiments.implicit.im_u_epistemic_triangle
make implicit-regression
```

Observed:

- `im_u`: `35/35` passing (including hook 32)
- full implicit regression: `PASSED`

## Verdict

For EPISTEMIC_TRIANGLE v7 scope, the previously open implicit-admitted computed-sources item is now closed in code and regression.

Remaining cautions are now mostly about future evolution pressure (schema/ID-shape drift and keeping audit hooks aligned), not about current v7 completeness.
