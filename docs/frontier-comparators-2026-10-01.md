# Frontier comparison: evidence and execution gap

Observed 2026-10-01. This is primary-source research and a feasibility check, **not an executed frontier evaluation**. ODRD 1.0.1 was installed at this checkpoint. The [2.0.0 state-tool correction](state-v2-2026-10-02.md) was published the following day; it does not change the historical comparison results or establish frontier parity. Two earlier candidates failed their adoption gate; the completed 24-attempt local screen cannot establish frontier parity.

| Target | Published outcome | Reproduction status |
| --- | --- | --- |
| Terminal-Bench 2.1, Harbor revision 6, 89 tasks | Codex + GPT-6 Astra/high: 87.4% ±1.8% | Public source job specifies Codex 0.151.0, five attempts per task, Docker, default task resources. Concrete historical comparison; task/image/evaluator digests and full trial records still need pinning. |
| Terminal-Bench 4.0.0, Harbor revision 4, 66 tasks | Codex + GPT-6 Astra/max: 58.2% ±2.8% | Current outcome target. Exact source-job settings and attempt count for this row were not established. Full coverage requires GPU and multiple containers. |
| DeepSWE v1.1, 113 tasks | Astra: 74.1% in OpenAI's launch table | Owner uses mini-swe-agent + Pier + Modal. Running Codex would compare agent systems rather than reproduce that scaffold. Exact row-level run settings remain unresolved. |

TB2.1's owner [leaderboard](https://hub.harborframework.com/datasets/terminal-bench/terminal-bench-2-1/latest?leaderboard=main&tab=leaderboard) directly links the high-effort row to its [public job](https://hub.harborframework.com/jobs/17d1a7f6-3339-4670-8b70-3b145979f57f). Five attempts mean 445 trials for one effort, not best-of-five selection. The source sweep's 2,225 trials cover five efforts. The [owner protocol](https://github.com/harbor-framework/terminal-bench-2-1/blob/main/leaderboard/SUBMIT.md) requires full task coverage and counts errored trials as zero rather than silently excluding them. Community submissions are currently closed; local evaluation remains distinct from leaderboard acceptance.

TB4's [version-specific owner board](https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4.0.0?tab=leaderboard&leaderboard=4-0-0) supplies the current percentage. Its [pinned dataset README](https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4.0.0) documents GPU and multiple-container requirements; the [release description](https://www.tbench.ai/news/terminal-bench-4-0) documents changed tasks and an eight-hour agent timeout. Percentages cannot be transferred between benchmark versions. DeepSWE's [owner documentation](https://deepswe.datacurve.ai/run), [task repository](https://github.com/datacurve-ai/deep-swe), and [OpenAI table](https://openai.com/index/gpt-6-astra/) identify its different agent and verifier contract.

## What prevents execution here

The local Mac preflight found none of `docker`, `podman`, `colima`, `limactl`, `lima`, `qemu-system-aarch64`, `orb`, or `container` on PATH, and no runtime in the five application paths checked. This is a bounded check, not an exhaustive inventory. Installed Codex is 0.159.2, differing from the TB2.1 source job.

Harbor's [Codex adapter at the inspected commit](https://github.com/harbor-framework/harbor/blob/bf991e490394ef9c3250a6db2bc5cbda903cb4c3/src/harbor/agents/installed/codex.py#L1470) defaults to API-key authentication. Its explicit `auth.json` option copies that credential file into the task environment; ACP mode rejects that option. No credential file was read or copied, no API spending started, and no global model, authentication or security setting changed. A compliant model-access route is not yet established.

## Next discriminating action

Confirm an existing authorized Linux/container/GPU environment and model-access route, then obtain the target row's exact configuration and frozen task/image/evaluator identifiers. Before model runs, validate the benchmark-owned verifier with oracle and empty controls and freeze the hypothesis, stop rule and cost cap. Compare stock Codex and a frozen ODRD bundle under matched conditions, with task-level uncertainty and full error accounting. Keep plugin uplift, reproduction of a historical row, and current frontier parity as separate claims. A pilot subset establishes feasibility only.

The automatic planning → human approval → implementation behavior is already verified. The larger frontier parity goal remains incomplete; access and measurement gaps are recorded rather than converted into a success claim.
