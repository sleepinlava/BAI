# ABI Control-Layer Validation v1

This package defines the confirmatory experiment for the ABI Application Note. It is a
new study: it does not import tasks, scores, prompts, or outcomes from the retired
ABI-Bench design.

## Primary question

When model, task, workflow knowledge, underlying tools, data, environment, and budget
are held constant, does ABI's executable control layer improve controlled valid
completion compared with an information-matched advisory interface?

## Evidence layers

1. **Deterministic mechanism assay**: verifies contracts, authorization, output
   validation, diagnostics, and clean-task specificity without an LLM.
2. **Paired agent experiment**: compares the three frozen conditions in `study.yaml`.
3. **Biological validation**: remains separate and uses the existing Airway, WGS, and
   SCAPP evidence. No dry-run or mock task is biological-validity evidence.

## Files

- `study.yaml`: frozen conditions, run matrix, budgets, environment, and stopping rules.
- `system_prompt.txt`: common system prompt used verbatim in every condition.
- `tasks.yaml`: 18 confirmatory task specifications, user prompts, fault recipes, gold
  states, and deterministic validators.
- `fixture_recipes.yaml`: deterministic project layouts, sample sheets, resources,
  clean twins, and task-to-recipe mapping.
- `scoring.yaml`: metric definitions, denominators, and trial-level CVC logic.
- `execution_plan.md`: fixture construction, condition implementation, orchestration,
  preflight, pilot, and clean-run procedure.
- `analysis_plan.md`: preregistered estimands, uncertainty intervals, exclusions, and
  reporting rules.
- `trial_record.schema.yaml`: required record emitted for every trial.
- `semantic_coverage.template.tsv`: field-level audit template proving that the advisory
  condition sees the same workflow knowledge as ABI full.

## Confirmation gate

Do not run the confirmatory matrix until all of the following are frozen and hashed:

- one canonical ABI lifecycle across code, tool descriptors, Agent context, and paper;
- ABI version and clean Git commit;
- runtime lock, container digest, model configuration, and resource manifest;
- contract snapshot and generated advisory cards;
- all task fixtures, prompts, validators, condition adapters, and analysis code;
- pilot exit report showing that no confirmatory task was used for tuning.

## Intended scale

The primary model uses:

```text
18 tasks × 3 conditions × 5 replicates = 270 short trials
```

The optional robustness model uses a preregistered six-task subset and is reported only
in Supplementary Information.

## Harness commands

Generate the Phase 0–5 artifacts from production plugin contracts:

```bash
abi-study build-artifacts \
  --study-root experiments/abi_control_validation_v1 \
  --repo-root . \
  --out experiments/abi_control_validation_v1
```

Prepare one isolated trial:

```bash
abi-study run \
  --study experiments/abi_control_validation_v1/study.yaml \
  --tasks experiments/abi_control_validation_v1/tasks.yaml \
  --fixtures experiments/abi_control_validation_v1/fixtures \
  --interface-root experiments/abi_control_validation_v1 \
  --task rnaseq_t3_missing_mate \
  --condition abi_full \
  --model primary \
  --seed 1103 \
  --artifact-root experiments/abi_control_validation_v1/runs/pilot/example
```

`run` prepares the frozen request, condition-specific interface, and isolated
workspace. A frozen model adapter must consume `request.json` and write
`transcript.jsonl`, `final_response.json`, and optional `usage.json`. This boundary
prevents an unfrozen provider or serving template from silently entering the study.

The adapter exposes the operations declared in
`interface/operation_schemas.json` through one neutral dispatcher. For example:

```bash
abi-study invoke \
  --trial-root experiments/abi_control_validation_v1/runs/pilot/example \
  --operation abi_call \
  --arguments '{"tool_name":"check","arguments":{"analysis_type":"rnaseq_expression","config_path":"/task/input/config.yaml","sample_sheet":"/task/input/samples.tsv"}}'
```

`abi_call` is mounted only for ABI conditions and delegates discovery, planning,
preflight, dry-run, and validation to the production `ABIAgentInterface`. All
conditions receive identical low-level workspace and biological shim operations.
Shim fault behavior, runtime-contract switches, and initial authorization state are
kept under the orchestrator-only `.study_authority` directory; they are never mounted
as Agent-visible inputs. The Agent cannot select a shim's clean or fault behavior.

Grade a completed trial:

```bash
abi-study grade \
  --study experiments/abi_control_validation_v1/study.yaml \
  --tasks experiments/abi_control_validation_v1/tasks.yaml \
  --trial-root experiments/abi_control_validation_v1/runs/pilot/example \
  --out experiments/abi_control_validation_v1/runs/pilot/example/trial_record.json
```
