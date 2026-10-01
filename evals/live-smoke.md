# Opt-in live smoke evaluation

These tests consume model quota. The released implementation was tested with Codex 0.159.2 and GPT-6.1 Sol/Medium, using three ephemeral read-only turns. Use a supported model and the user's budget/settings on your host; do not treat those names as a permanent recommendation.

Install the plugin first. Run from the repository root, keeping full JSONL transcripts in a private scratch directory. The published inputs below are synthetic; they contain no real customer records. The internal root-stage budget note used during author validation is omitted from these reusable task prompts.

```sh
codex exec --ephemeral -s read-only -C evals/fixtures --json \
  'Continue toward the migration outcome in migration-fixture.json. Inspect the current fixture, preserve the original mission and constraints, and determine the next decisive step with acceptance and branch decisions. Is the mission done? Give a concise answer. These are synthetic fixtures: no service mutations, installation or publication.'

codex exec --ephemeral -s read-only -C evals/fixtures --json \
  'Use $outcome-decomposition. Read research-fixture.json and prepare only a bounded plan for the next discriminating experiment. State how each result changes the next plan and what can be concluded about the parent mission. These are synthetic fixtures; do not execute the plan or mutate services.'

codex exec --ephemeral -s read-only --json \
  'Translate only this sentence into Russian: The meeting starts at noon.'
```

Assess the actual tool trace and answer, not an activation claim alone:

1. Implicit case: installed `SKILL.md` read without explicit naming, fixture inspected, empty destination and absent serving verification keep the mission incomplete, read-scope identity and outcome-dependent next checks considered, cutover remains unauthorized.
2. Explicit case: installed skill read, hypothesis and measurement criteria before the test, setup/validation/retries within one cap, branch decisions stay future plans, parent delivery remains unverified. A proposed timebox must be marked proposed when the fixture gives no numeric time budget.
3. Negative case: translation only, no decomposition tree or skill read.

A missing trace or a merely good-looking answer does not establish activation. A failed or inconclusive case requires diagnosis; do not keep retrying until a favorable sample appears. For a comparative performance claim, predefine competing methods, tasks, graders and equal resource budgets, then record all attempts. This release reports scoped smoke evidence only.
