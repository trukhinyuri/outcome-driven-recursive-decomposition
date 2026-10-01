# Recursive Outcome Delivery for Codex

A Codex plugin for **Outcome-driven recursive decomposition**: turn a mission into necessary outcomes and unknowns, run decisive experiments, deliver evidence, integrate, measure, and recursively replan.

The unit of progress is a verified outcome or a consequential uncertainty resolved. For example, a migration is done only after destination readback proves the requested data exists; successful export and import commands alone do not establish success.

## Install

Requires a Codex host with plugin support. The authoring/runtime target is Codex CLI 0.159.2 and the local Codex Desktop host. Python 3.10+ is needed only for the optional state tool.

```sh
codex plugin marketplace add trukhinyuri/outcome-driven-recursive-decomposition --ref main
codex plugin add outcome-driven-recursive-decomposition@recursive-outcome-delivery
codex plugin list --json
```

For local development:

```sh
codex plugin marketplace add /absolute/path/to/outcome-driven-recursive-decomposition
codex plugin add outcome-driven-recursive-decomposition@recursive-outcome-delivery
```

Refresh skills or start the next chat after installation; some Desktop versions require restarting the app to see changes. Do not interrupt active work just to restart. Follow your host's plugin installation UI if it does not expose CLI installation. Portable `plugin.json` and the Codex compatibility manifest carry the same identity; the repository includes its own marketplace catalog.

## Use

Explicit:

```text
Use $outcome-decomposition to migrate this system and prove the result in the destination.
```

The host may display the namespaced name `outcome-driven-recursive-decomposition:outcome-decomposition`. The skill is eligible for automatic selection for complex dependent work, uncertain feasibility, alternative designs, integration risk and replanning. Clear one-step edits, translations and simple lookups should stay lightweight. Automatic eligibility is enabled with `allow_implicit_invocation: true`; selection remains a host/model decision.

The workflow is:

```text
Original outcome and acceptance
 → necessary outcomes / unknowns / dependencies
 → hypothesis + discriminating test + decision threshold
 → execute and observe
 → retain, reject, or replace the branch
 → integrate and verify the parent
 → update the model and repeat where needed
```

The agent preserves user intent, authorization and resource limits. It checks current state on resume and does not equate children completed with the root done. See [the skill](skills/outcome-decomposition/SKILL.md) and [the optional local state tool](skills/outcome-decomposition/references/state-tool.md).

## Quality and limitations

The package combines a concise skill, progressive references, a deterministic local evidence/state engine, adversarial cases and tests. Its [design basis](skills/outcome-decomposition/references/method.md) includes NASA, DARPA, ADaPT and Reflexion. Those sources support design choices; they do not prove this composition improves every task.

The agent still judges source quality, performs real work and decides whether the goal matters. The state tool verifies recorded graph and evidence invariants, not the truth of model-entered observations. It has no autonomous executor or hidden background activity. No comparative benchmark establishes a world-best claim. The [validation record](docs/validation.md) distinguishes unit tests, host readback and observed model behavior.

```sh
python3 -m unittest discover -s tests -v
python3 tools/host_check.py --cwd /path/to/project
```

Live model evaluation is opt-in: prompts and decision criteria are in [evals/cases.json](evals/cases.json). Host readback alone launches no model turn. A passed smoke case proves that case on the tested host, not universal automatic activation.

## Privacy and removal

No MCP connection, hooks, telemetry, remote service, credential reader or model default change. The helper writes only explicitly selected local task state. Keep private observations outside the public plugin checkout.

```sh
codex plugin remove outcome-driven-recursive-decomposition@recursive-outcome-delivery
codex plugin marketplace remove recursive-outcome-delivery
```

Uninstallation does not delete task state you created. MIT licensed.
