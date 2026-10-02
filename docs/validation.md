# Validation record

Verified on 2026-10-01 (Europe/Amsterdam). The tested host was Codex Desktop/app-server and CLI 0.159.2, with Python 3.14.7 on macOS. The table below records the initial 1.0.0 validation; the 1.0.1 routing check is recorded separately. This is a scoped validation record, not a universal benchmark or world-best claim.

| Layer | Actual check | Result and scope |
|---|---|---|
| State engine | 23 executed CLI unit tests | Passed: recursive gates, original acceptance, required/optional branches, acyclic edits, contradictions, artifact changes, history replay, concurrency, nonmutating errors, fresh parent integration and persistent control decisions. |
| Independent state review | 9 executed counterexample probes on the final script | Passed: includes the previously failing blocked/rejected ancestor cases, explicit resume and preserving a separately blocked child. |
| Independent semantic review | Migration and one-experiment plan-only exercises | Correct bounded responses; six synthetic migration-oracle checks also passed. No real migration/service claim. |
| Packaging | Official skill validator, JSON, local reference links and manifest identity | Passed. These establish structure, not task quality. |
| Installed host | Stock app-server `plugin/list` and forced `skills/list` | Plugin installed and enabled; namespaced skill discovered and enabled under the same local Codex Home. |
| Installed code | SHA-256 comparison of reviewed source and plugin cache | Identical state engine. |
| Live implicit activation | Ephemeral read-only Codex turn on a synthetic dependent migration goal, without naming the skill | Codex read the installed SKILL.md automatically, inspected the fixture and calculated the missing destination records. It kept the parent incomplete and cutover unauthorized. |
| Live explicit activation | Ephemeral read-only turn using `$outcome-decomposition` with a one-experiment, plan-only fixture | Codex read the installed SKILL.md, proposed a bounded discriminating test, gave outcome-dependent decisions and did not execute it or assert parent completion. |
| Live negative control | Translation-only request on the same model/host | Translation only; no shell commands or decomposition skill read. |

All three live smoke turns explicitly selected `gpt-6.1-sol` with `model_reasoning_effort="medium"` through supported CLI options. The host model catalog confirmed this selection was supported before launch. The global model/defaults were not changed. No extra user chats or background automation were created.

Initial 1.0.0 / 1.0.1 state engine SHA-256:

```text
13e732a0b18615cb5df7bb22adcfc3523308b1b31a957f63de6c15d20befe720
```

The tests caught and corrected two integration problems: old parent evidence could resurrect after a child change, and automatic evidence revisions could drop a blocked/rejected ancestor's control. Fresh integration revisions and separate persistent control records now prevent those observed failures.

## 1.0.1 planning and approval routing

The installed 1.0.1 skill was tested through stock app-server in an ephemeral conversation with two successive turns, explicitly selecting supported `gpt-6.1-sol` / `medium`. A standing personal routing rule was also added to the author's global Codex `AGENTS.md`; this is a local preference, not an automatic modification made by the plugin package on other hosts.

1. A Russian plan-only request described a dependent local JSON-to-CSV pipeline without naming the skill. The trace read the installed 1.0.1 `SKILL.md`, presented outcomes and acceptance checks, and left every fixture file unchanged.
2. The same conversation then received only `План подтверждаю.`. It implemented the accepted pipeline, generated a CSV and ran separate source/output readback without requesting the same approval again. An independent CSV parse confirmed IDs `c1,c2,c3`, labels `Alpha,Beta,Gamma`, three records and a value sum of six. The original source SHA-256 was unchanged. All implementation artifacts stayed in the disposable local test directory; no external migration was performed.
3. A fresh unrelated translation-only conversation produced only the requested translation and no commands or decomposition skill read.

An independent semantic reviewer also exercised plan-only, full approval, partial approval and direct implementation requests and found no material contradiction. Partial approval was reviewed semantically, not tested against a live deployment. The optional state engine was unchanged from 1.0.0; its recorded 23 unit tests and nine independent probes are not represented as a new behavioral routing test.

Native forced discovery confirmed the plugin installed and enabled at local version 1.0.1, and the namespaced skill enabled. The reviewed routing files matched the installed cache. Planning/approval test instructions are in [live-smoke.md](../evals/live-smoke.md). These observations do not guarantee deterministic selection on every future prompt, and existing turns still require current instructions or refreshed discovery.

## 2.0.0 state replay and replacement correction

The [version 2 verification record](state-v2-2026-10-02.md) documents a replacement-invalidation defect found after the initial release, its repair, backward-readable history and explicit migration. The current state suite has 33 tests. The initial 23-test result above is historical and did not cover the newly identified counterexamples.

## Reproduce and assess limits

Run `python3 -m unittest discover -s tests -v`. The GitHub workflow runs this suite on Ubuntu with Python 3.10 and 3.14; inspect the repository's current checks for the actual remote run. Run `python3 tools/host_check.py --cwd /path/to/project` to read current local installation/skill discovery without launching a model turn. Live smoke inputs and task prompts are in [evals/live-smoke.md](../evals/live-smoke.md); additional behavioral oracles are in [evals/cases.json](../evals/cases.json). Those additional scenarios are not claimed as completed live Codex trials.

Unit/probe results prove their recorded invariants, not the truth of agent-entered observations. Model smoke tests prove these three observed behaviors, not every prompt or future version. No controlled comparison against competing plugins establishes superior task performance, and no model weights were trained or upgraded.

Native GUI automation did not permit access to the Codex application. Installation was verified through the supported CLI and host API rather than screenshots. Existing active turns may retain their previously supplied skill catalog; installation does not retroactively rewrite those turns. No active chat was interrupted or app forcibly restarted.
