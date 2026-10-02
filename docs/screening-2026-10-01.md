# Frontier research and candidate screening, 2026-10-01

**At the 2026-10-01 checkpoint, release 1.0.1 remained the installed and published method.** Two experimental
candidates were evaluated and not adopted. The [2.0.0 state-tool correction](state-v2-2026-10-02.md)
was published on 2026-10-02 with the same skill prompt and invocation policy.
Automatic complex-task planning and continuation after human approval remain enabled.
No frontier parity or world-best claim is established.

## Research hypotheses

Primary engineering sources informed these hypotheses, not measured superiority:

- [OpenAI: Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
  motivated a shorter entrypoint and conditional references. This model-specific
  advice still needed evaluation on our actual model.
- [OpenAI: Testing Agent Skills Systematically with Evals](https://developers.openai.com/blog/eval-skills)
  motivated observable invocation, artifact correctness and efficiency checks.
- [OpenAI: Build an Agent Improvement Loop with Traces, Evals, and Codex](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop)
  motivated changes driven by captured failures and evaluated outcomes.
- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
  motivated final-state scoring, known-right/wrong grader calibration and accepting
  alternative correct implementations.
- [Anthropic: Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
  motivated testing whether scaffolding and additional roles actually help.
- [Google DeepMind: AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)
  motivated evaluator-based selection while retaining a tested incumbent. Its
  algorithmic results do not transfer automatically to general planning.

## Observed results

The actual host was Codex CLI/Desktop app-server 0.159.2. Skill comparisons used
supported `gpt-6.1-sol` / `medium`, identical common settings, separate ephemeral
workspaces and a 240-second limit per turn. Positive method comparisons explicitly
read the staged skill; they do not establish implicit activation. The translation
control did not force a skill read. Existing installed-host activation evidence is
recorded in [validation.md](validation.md).

Candidate A shortened the entrypoint and moved execution/evaluation detail into
conditional references. Both methods solved six synthetic tasks: plan then short
approval, contradictory target evidence, changed accepted requirements on resume,
repairing a defective checker, simple translation and ledger recovery after a
negative feasibility probe. Observed cumulative input/output tokens were 613,331
for the incumbent and 597,563 for A. An exploratory boolean/number equality alias
in A's generated checker, outside the original frozen controls, motivated B; it
did not retroactively change A's original task scores.

Candidate B added general domain-type and boundary-control guidance. A new task
declared JSON equivalence at every nesting depth: booleans differ from numbers,
while permitted numeric equivalents such as `1` and `1.0` match. The independent
evaluator accepted its known-right checker on all 18 controls and rejected
length-only and shallow-equality alternatives before the live comparison.

| Seven-case population | Incumbent 1.0.1 | Candidate B |
|---|---:|---:|
| Correct outcomes | 7/7 | 7/7 |
| Cumulative input/output tokens | 731,561 | 871,331 |
| Included cached input tokens | 580,480 | 695,936 |
| Sum of turn elapsed seconds | 547.377 | 618.981 |

Both passed external checker controls, artifact readback and independent semantic
review. B used 19.1057% more total input/output tokens. The predefined adoption gate
required no meaningful regression and either an additional correct outcome or
lower aggregate observed tokens at equal correctness. B failed that gate. A was
also retained only as a development candidate; neither experimental instruction
set replaces the incumbent. [Machine-readable results](screening-2026-10-01.json)
contain the aggregate observations.

## Limits and remaining evidence

All 24 attempted comparative trials are accounted for: 20 valid method trials,
three infrastructure failures caused by an outer macOS sandbox preventing native
child execution, and one contaminated native control. Invalid trials and raw
records were retained locally. A skill-read detector initially missed successful
relative-path reads; it was repaired uniformly without changing task criteria or
discarding the original records. Consequential scores use external controls and
semantic review rather than trusting an agent's own completion claim.

These are single-run synthetic development observations. Six incumbent results
were reused for B, so temporal variance is uncontrolled. Both methods inherited
the same global instructions; catalog filtering was best effort. Scoring files
were readable under the same OS user, so this was not a protected holdout. The
native control does not support a pristine frontier comparison. Private raw host
traces and user instructions are not published, and this aggregate record is not
a fully reproducible public benchmark.

Thread-cumulative usage was counted once per trial, including both plan/approval
turns without double-counting the earlier turn. Total token counts include cached
input and do not measure quota consumption or price savings. Token/tool limits
were observed at notifications and can overshoot; the latest-context token limit
was not an aggregate turn cap.

Matching public engineering techniques does not train weights or reproduce a
closed laboratory system. Parity requires named comparator systems, a relevant
task distribution, matched conditions, credible independent scoring and sufficient
repeats. Those measurements remain outstanding. Future changes need a concrete
failure hypothesis and a new bounded protocol; more instructions alone are not
evidence of improvement.
