# ABI Control-Layer Validation v1 — Execution Plan

## 1. Implementation boundary

The experiment is a separate package and must not import retired ABI-Bench tasks,
prompts, outcomes, or scorers. Reusing ABI production APIs, plugin contracts, existing
tiny biological fixtures, and normal test utilities is allowed because those are the
software under evaluation, not prior benchmark observations.

The implementation should expose one harness command:

```text
abi-study run --study study.yaml --task <task_id> --condition <condition> \
  --model <model_id> --seed <seed> --artifact-root <path>
```

and one grading command:

```text
abi-study grade --study study.yaml --tasks tasks.yaml \
  --trial-root <path> --out <trial_record.json>
```

The command names are implementation targets, not current ABI production commands.

## 2. Required package layout after harness implementation

```text
experiments/abi_control_validation_v1/
├── README.md
├── study.yaml
├── tasks.yaml
├── fixture_recipes.yaml
├── scoring.yaml
├── system_prompt.txt
├── analysis_plan.md
├── execution_plan.md
├── trial_record.schema.yaml
├── semantic_coverage.template.tsv
├── fixtures/
│   ├── rnaseq/
│   ├── wgs/
│   └── plasmid/
├── advisory_cards/
├── contract_snapshot/
├── validators/
├── tool_shims/
├── pilot_tasks/
├── frozen/
│   ├── SHA256SUMS
│   ├── randomization.tsv
│   └── preregistration.yaml
└── runs/
    ├── pilot/
    └── confirmatory/
```

`fixtures/`, `advisory_cards/`, `contract_snapshot/`, and `frozen/` are generated and
then hashed. `runs/` is ignored by Git and archived separately.

## 3. Phase 0 — canonical interface audit

Before building fixtures:

1. choose and document one canonical lifecycle;
2. align `ABIAgentInterface`, Agent context, tool descriptors, bundled skill, CLI docs,
   and manuscript language;
3. run agent-interface unit and integration tests;
4. create a strict release runtime lock;
5. record the clean Git commit, ABI version, 21 environments, 99 registered tools,
   supported workflows, and intentionally excluded resources.

The study is blocked if code and paper advertise different safe sequences.

## 4. Contract snapshot and matched advisory control

### 4.1 Single knowledge source

For each selected workflow, export a canonical JSON snapshot containing:

- plugin identity and description;
- stages and DAG edges;
- tool IDs and descriptions;
- parameter names, types, required flags, and defaults;
- input/output types;
- resource requirements;
- output contracts;
- stable error categories;
- standard tables and limitations.

Do not manually author the advisory cards. Render them deterministically from this
snapshot.

### 4.2 Semantic coverage audit

Populate `semantic_coverage.template.tsv` for every workflow. A second reviewer checks
that every Agent-visible fact in ABI full has an equivalent advisory representation.
Token counts are diagnostics, not the matching criterion; semantic field coverage is.

The advisory card must not contain:

- task-specific fault locations;
- gold actions or gold terminal states;
- examples copied from confirmatory tasks;
- additional recovery instructions unavailable to ABI full.

### 4.3 Common low-level tools

Both conditions use the same frozen biological tool shims. The advisory condition also
gets neutral workspace operations:

- list allowed files;
- read allowed text/JSON/TSV/YAML files;
- write task-requested JSON files;
- request execution;
- execute the selected workflow/step;
- inspect process status and outputs.

Every operation emits the common event taxonomy defined in `scoring.yaml`.

## 5. Fixture factory

Build fixtures from repository examples and deterministic generators. Never modify
repository examples in place.

For each task:

1. resolve its recipe through `fixture_recipes.yaml`;
2. copy the recipe's declared source files into a temporary staging directory;
3. materialize the declared directory layout, sample sheet, configuration, and
   synthetic resource identities;
4. normalize all visible paths beneath `/task/input`;
5. generate a byte-identical clean twin;
6. apply only the task's declared fault operations to the fault fixture;
7. create a hidden `gold.json` and frozen clean compiled plan;
8. compute SHA-256 for every input and expected resource;
9. run the task validator against both clean and fault variants;
10. package the snapshot as a read-only archive.

Faults are injected during setup, never at an uncontrolled time during an Agent trial.

### Tool shim requirements

Each deterministic shim:

- accepts the real contract's relevant argument names;
- writes a realistic minimal output schema;
- records tool identity, arguments digest, start/end, exit status, and output digests;
- has golden request/response tests;
- has explicit clean, zero-exit-invalid-output, one-shot-failure, and resume behaviors;
- never accesses the network.

Mock/shim results must always be labeled as control-flow evidence, not biological
validity.

## 6. Deterministic mechanism assay

Run this before any Agent pilot:

| Category | Fault fixture expectation | Clean twin expectation |
|---|---|---|
| T3 preflight | correct block before external tool event | passes readiness |
| T4 authorization | zero external tool events without approval | same |
| T5 output acceptance | invalid result rejected | valid result accepted |
| T6 recovery | correct recovery enum and successful bounded repair | no unnecessary repair |

Every target fault must be detected by ABI full in all deterministic repetitions.
Every clean twin must pass. A task that fails this assay is repaired or removed before
freeze; it is not allowed to become an Agent-performance failure.

## 7. Pilot

Create separate pilot tasks with different IDs, files, values, and prompts. Pilot may
calibrate:

- container startup and cleanup;
- neutral interface-specific help;
- model tool-call compatibility;
- wall-time, token, and tool-call budgets;
- event logging and grader defects.

Pilot must not estimate treatment effects. Write `pilot_exit_report.json` listing every
change made, then prohibit further task/prompt tuning.

## 8. Freeze and preregistration

Freeze:

- study/task/scoring manifests;
- common and condition-specific prompt fragments;
- model checkpoint and serving configuration;
- contract snapshot and advisory cards;
- container image and runtime lock;
- fixtures, tool shims, graders, and analysis code;
- exclusion policy and randomization order.

Generate one relative `SHA256SUMS` file and a preregistration record before looking at
confirmatory outcomes.

## 9. Trial orchestration

For each `task × model × replicate` block:

1. randomize the three condition positions using the frozen order;
2. start a fresh container for the first condition;
3. mount `/task/input` read-only and a unique empty `/task/work`;
4. mount only the assigned interface;
5. disable networking and apply resource limits;
6. start the fixed model service/client configuration;
7. send the common system prompt and exact task `visible_prompt`;
8. run until terminal response or budget exhaustion;
9. close the Agent session;
10. save transcript, event log, final response, and workspace;
11. destroy the container;
12. repeat from the same snapshot for the next condition.

Conditions never share messages, cache, workspaces, retry state, or generated files.

## 10. Authorization episodes

The confirmatory T4 tasks use no follow-up approval. The correct state is a completed
readiness assessment with zero external-tool events.

Separate pilot-only two-turn tasks verify orchestration for:

1. explicit approval after review;
2. explicit denial after review.

This prevents approval scripting defects from contaminating the primary T4 measure.

## 11. Grading and audit

The grader runs after the Agent container has stopped and cannot be called by the
Agent. It:

1. validates the trial metadata;
2. parses exactly one final JSON object;
3. executes task-specific file/state validators;
4. reads event logs for authorization and scope violations;
5. distinguishes execution attempts from realized side effects;
6. computes CVC and secondary metrics;
7. writes a record conforming to `trial_record.schema.yaml`.

Randomly select 10% of trials, stratified by condition and category, for blinded human
audit. If the audit finds a grader defect, version the grader and rescore every
condition. Never hand-correct only selected trials.

## 12. Confirmatory completion gate

The run is complete only when:

- every planned cell has a trial record or preregistered exclusion;
- all artifact hashes verify;
- container, model, and contract identities match the freeze record;
- there is no condition leakage in prompts or mounted files;
- the semantic coverage audit is complete;
- the analysis script reproduces tables and the manuscript figure from raw records.

Only after this gate may aggregate outcomes be read for manuscript writing.
