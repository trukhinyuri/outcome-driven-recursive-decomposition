# Optional local state tool

Use this helper when a task needs durable recursive outcomes, dependency gates, evidence and traceable revisions. For a simple leaf, existing task notes are enough. Python 3.10+; standard library only. This tool does not execute tasks, browse a source or certify the truth of an entered observation.

Locate `scripts/odrd.py` relative to this skill's `SKILL.md`; do not assume a fixed installed path. Inspect a script's origin and effects before the first execution in an unfamiliar installation. Set a task-specific shell variable to that path, then choose a task state file outside the public plugin repository. Its parent directory must already exist. Use canonical physical paths: symlink path components are refused, including aliases such as macOS `/var` to `/private/var`.

```sh
ODRD_TOOL=/absolute/path/to/skills/outcome-decomposition/scripts/odrd.py
python3 "$ODRD_TOOL" init /absolute/project/.odrd/mission.json \
  --goal 'Customers are migrated and served correctly' \
  --criterion 'Destination readback matches the source data' \
  --criterion 'Serving reads pass the agreed acceptance test' \
  --constraint 'No cutover without authorization'
```

The root ID is `root`. Criteria and constraints can be repeated. Keep original user requirements in the root acceptance; the tool preserves them across root revisions. Initialization never overwrites an existing state file.

## Decompose into executable outcomes

```sh
python3 "$ODRD_TOOL" add /absolute/project/.odrd/mission.json \
  --id mapping --parent root --kind experiment \
  --outcome 'The transformation preserves customer identities' \
  --criterion 'Transformation test passes on the agreed fixture' \
  --uncertainty 'Does the mapping lose or duplicate identities?' \
  --risk 5 --information 4 --cost 1
python3 "$ODRD_TOOL" add /absolute/project/.odrd/mission.json \
  --id readback --parent root --kind outcome --depends mapping \
  --outcome 'The destination contains the expected customers' \
  --criterion 'Destination readback matches the source data' \
  --uncertainty 'Are the imported rows present in the intended deployment?' \
  --risk 5 --information 5 --cost 2
```

Kinds: `outcome`, `hypothesis`, `experiment`, `deliverable`. Each node contributes to its parent; `--depends` declares prerequisite gates. Required children are the default. Use `--optional` for exploration whose rejection should not block the mission. Do not mark a necessary condition optional to make a completion check pass. Use one comparable cost unit for the current task. Risk and information are ordinal integers 1–5, not probabilities.

`next STATE` ranks eligible nodes by risk × information / cost and explains blocked gates. It is an ordinal heuristic, not true value of information or an executor. The agent considers deadlines, critical paths and authorization before acting. `status STATE` shows gaps; `--summary` selects concise text instead of JSON.

## Observe and decide

```sh
python3 "$ODRD_TOOL" evidence /absolute/project/.odrd/mission.json \
  --node mapping --criterion 'Transformation test passes on the agreed fixture' \
  --source file:/absolute/project/test-results/mapping.txt \
  --artifact /absolute/project/test-results/mapping.txt \
  --observation 'The executed fixture test passed with no lost or duplicated IDs' \
  --verdict supports
python3 "$ODRD_TOOL" decide /absolute/project/.odrd/mission.json \
  --node mapping --action complete --reason 'Fixture acceptance passed; evidence inspected'
```

Use the exact criterion text. A source must be an HTTP(S), `doi:`, `urn:`, `file:` locator or an existing absolute file. Remote/URN locators preserve provenance only; inspect their contents separately. `--artifact` captures file size and SHA-256. Later edits make its evidence stale. Fingerprints do not prove correctness, authority or that a test was actually executed.

Verdicts: `supports`, `contradicts`, `inconclusive`. Actions: `complete` for outcomes/experiments/deliverables, `retain` for verified hypotheses, `reject`, and `block`. Hypothesis rejection requires current contrary evidence. Successful decisions require supportive evidence for every criterion and verified prerequisites/required children. Root completion requires its own evidence for all original acceptance criteria. Closing children alone cannot close the root.

A later supporting observation does not silently clear an earlier contradiction. First investigate it. To record a justified explanation, use the returned evidence IDs:

```sh
python3 "$ODRD_TOOL" resolve /absolute/project/.odrd/mission.json \
  --node readback --evidence e7 --basis e9 \
  --reason 'The earlier observation queried a different deployment; the identity-checked readback is authoritative'
```

The basis must be later current supporting evidence for the same node/criterion. The tool checks this relationship; the agent must check that the explanation is supported.

## Replan and resume

`revise STATE --node ID --outcome TEXT --criterion TEXT --reason TEXT` records a new version and invalidates affected proof, including ancestors' integration evidence. Unrelated sibling proof stays fresh. Re-enter preserved criteria deliberately; original root criteria cannot be removed. Omitted constraints and dependencies are preserved. Use `--constraint` when changing the current constraint set; original root constraints remain necessary. Repeated `--depends ID` replaces the dependency list, and `--clear-depends` clears it; the resulting graph must remain acyclic.

`replan STATE --node OLD --replacement NEW --reason TEXT` supersedes a branch with an active sibling and retains the old history. A required branch needs a required replacement. Dependency gates follow the replacement. Rejected/superseded descendants are not suggested for new work. A blocked/rejected node needs an explicit revision or replacement before returning to work. New observations and automatic ancestor invalidation preserve those control decisions; they never grant permission to resume a blocked branch.

When continuing, read `status`, inspect current external inputs and artifacts, then use `next`. If an upstream assumption changed, revise first and re-observe the affected criteria. Completion decisions do not turn old measurements into current truth.

```sh
python3 "$ODRD_TOOL" status /absolute/project/.odrd/mission.json
python3 "$ODRD_TOOL" next /absolute/project/.odrd/mission.json --summary
python3 "$ODRD_TOOL" validate /absolute/project/.odrd/mission.json
```

The event log is hash chained and atomically replaced under a cooperative local lock. It detects ordinary corruption; an author who rewrites all hashes can forge records, so it is not a security boundary or distributed consensus. `validate` checks replay, graph integrity and captured artifacts, not mission success. Exit 0 means valid records; exit 1 means artifact verification failed; exit 2 means an invalid request/state or I/O error. Read-only `status` may exit 0 while reporting an incomplete mission or artifact gaps.

If interrupted while holding a lock, inspect the lock's recorded PID and the live process before removing a demonstrably stale lock. Do not delete a lock merely because an observation timed out. Private task state is yours; plugin removal leaves it in place.

## Upgrade version 1 journals

New journals use schema 2. Their initial event includes the schema version in its hash. The completion and invalidation rules both follow the current replacement of each dependency, including chains of replacements.

Older schema 1 journals remain readable through `status`, `next` and `validate`. Until an explicit upgrade, they report `upgrade_required: true` and `mission_verified: false`; ordinary writes are refused. An intact historical journal may still pass `validate`: that command checks record integrity, not completion. This prevents a completion recorded under the earlier invalidation rules from being mistaken for current proof.

Keep a copy if you need to reopen the journal with version 1 of the tool. Then upgrade the chosen journal explicitly:

```sh
cp /absolute/project/.odrd/mission.json /absolute/project/.odrd/mission.v1.json
python3 "$ODRD_TOOL" upgrade /absolute/project/.odrd/mission.json \
  --reason 'Use replacement-aware verification rules and recheck the active outcomes'
python3 "$ODRD_TOOL" status /absolute/project/.odrd/mission.json
```

The upgrade appends one hash-chained event. Earlier events and hashes, the original objective and requirements, and explicit `block`/`reject` decisions are preserved. Proof revisions of all active nodes are invalidated conservatively. Repeat the relevant real-world checks and record fresh evidence from prerequisites and children through the parent integration check; the upgrade itself is not evidence of completion.

For an upgraded journal, `initial_schema` remains 1 and `current_schema` becomes 2. The original header continues to identify how its historical prefix must be replayed. Do not change that header or rehash old events to simulate an upgrade. A new schema 2 journal needs no upgrade, and a repeated upgrade is rejected without modifying the file. The old tool cannot read the appended upgrade event; use the preserved pre-upgrade copy if rollback is necessary.
