# Method and boundaries

These are engineering sources for a composed workflow, not proof that this plugin or any model is the smartest.

- [DARPA Heilmeier Catechism](https://www.darpa.mil/about/heilmeier-catechism): frame the research objective, novelty, risks, resources and intermediate/final tests. Here this informs the mission contract and decision thresholds, not a mandatory eight-question interview.
- [NASA §4.3 Logical Decomposition](https://www.nasa.gov/reference/4-3-logical-decomposition/): derive functions and relationships from requirements; preserve traceability, inputs, outputs and interfaces. Decomposition is iterative and may revise prior requirements. Here the user objective remains original; revisions change the solution unless the user changes the goal.
- [NASA §4.4 Design Solution Definition](https://www.nasa.gov/reference/4-4-design-solution-definition/): use sufficient detail for feasibility and verification, and distinguish verification from validation. This motivates adaptive depth and a parent's own integrated acceptance check.
- [ADaPT v2](https://arxiv.org/html/2311.05772v2): recursive decomposition can respond to execution difficulty and uses a maximum depth. Its success estimation is heuristic; its limitations discuss self-evaluation. We add authoritative verifiers and constraints before high-cost execution. Reported results in its environments do not establish an effect in current Codex.
- [Reflexion v4](https://arxiv.org/html/2303.11366v4): evaluator feedback and retained lessons can influence later attempts, but repeated reflection can reach local minima. We require a changed discriminating step rather than unlimited retries. Its experiments do not guarantee improvement for this plugin.

## Important distinctions

The model performs semantic decomposition, source evaluation, work and replanning. The Python helper stores records and enforces graph/evidence gates; it cannot know whether an observation is truthful or a criterion meaningful. Artifact hashes detect subsequent changes, not correctness or authority. No plugin text can guarantee deterministic implicit activation: `allow_implicit_invocation: true` permits Codex to select the skill.

This package adds no hooks, MCP server, scheduler, telemetry endpoint or global instruction file. It does not modify authentication, security, model defaults, unrelated skills or task budgets. A caller chooses a local state file for a particular task; the tool sends nothing over the network. Recorded source locators or observations may contain private data: keep task state outside public source repositories and apply normal project data rules.

## When to use a different structure

A small known change is already an executable leaf. Use direct execution and checking. For complex dependencies, the outcome tree expresses contribution; dependency edges express order. Optional hypotheses and alternate branches should be marked as exploration or superseded explicitly. Large organizations may need an external system of record; this lightweight local helper does not provide distributed scheduling or cross-team consensus.

Ordinal risk × information / cost is a transparent ordering aid, not a probability or measured expected information gain. Deadline and safety constraints can override a ranking. A lower-ranked but necessary verification may be the right next step.
