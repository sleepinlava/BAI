# ABI Specification v0.1

## Lifecycle API

`ABIAgentInterface` is the stable boundary for all transports:

- `list_types`
- `query`
- `plan`
- `check`
- `dry_run`
- `inspect`
- `report`
- `run`
- `export_nextflow`
- `export_snakemake`
- `export_agent_context`
- `check_resources`
- `doctor_agent`
- `install_skills`
- `abi_validate_result`
- `autoplasm_validate_result` (compatibility alias)
- `dispatch`

Every public method returns a JSON string with a uniform envelope.

## JSON Envelopes

Success:

```json
{
  "status": "success",
  "command": "plan",
  "result": {}
}
```

Confirmation gate:

```json
{
  "status": "confirmation_required",
  "command": "run",
  "result": {
    "message": "Re-run with confirm_execution=true after user approval."
  }
}
```

Error (compact, default):

```json
{
  "status": "error",
  "command": "dry_run",
  "error_code": "missing_input",
  "error": "Input file does not exist.",
  "diagnostic_hints": []
}
```

By default `error_type` is omitted from error envelopes to save tokens.
Pass `verbose_errors=True` when constructing `ABIAgentInterface` to include the
Python exception class for debugging.

## Permissions

- `read_only`: `list_types`, `query`, `check`, `inspect`,
  `abi_validate_result`, `autoplasm_validate_result`, `check_resources`,
  `export_agent_context`, `doctor_agent`
- `planning_write`: `plan`, `dry_run`, `report`, `export_nextflow`,
  `export_snakemake`, `install_skills`
- `execution`: `run`

Execution requires `confirm_execution=true`. Descriptors do not export
`abi_run` by default.
The value must be the Boolean `true`; this gate checks the request value and
does not authenticate a human identity.

## Standard Artifacts

Planning and dry-run outputs should converge on this structure:

```text
outdir/
  execution_plan.json
  compiled_plan.json
  provenance/
    commands.tsv
    resolved_inputs.tsv
    tool_versions.tsv
    resources.json
    run_summary.json
    progress.jsonl
  tables/
    *.tsv
  report/
    report.md
    report.html
```

`provenance/commands.tsv` records the lifecycle fields defined by the
provenance schema. Nextflow-backed runs also populate
`remote_scheduler_job_id` when the Nextflow trace exposes a scheduler/native
ID, for example from Slurm or a cloud batch executor.

`compiled_plan.json` carries a `plan_id` — the SHA-256 content digest of the
compiled plan. Actual execution binds to this identity: `run` recompiles the
prepared plan and verifies it against the confirmed `compiled_plan.json`
before starting; when configuration, plugin declarations, or the tool catalog
changed after confirmation, the run refuses with `invalid_config` (plan
drift) instead of executing an unapproved plan. A direct run without a prior
`plan` persists the verified plan first, so later runs verify against the
same identity. `run_summary.json` records `plan_id`, linking the run record
to the confirmed plan.

Run history is never overwritten: before a retry or resume rewrites the
provenance view, the prior run's evidence is archived under
`provenance/previous_runs/<prior_run_id>/`. A resume records
`resumes_run_id` (the prior run's `run_id`) in its `run_summary.json`; a
fresh re-run records the archive path in `previous_run_archive` without
claiming a resume link.

All four backends (local, Nextflow, Snakemake, HPC) share these evidence
semantics: their run summaries carry the same run identity, `plan_id`, and
history-linkage fields.

On resume, reused steps are additionally bound to the prior run's recorded
checksums: a step whose declared outputs or inputs no longer match the
prior run's `checksums.json` is not reused — it re-executes, and the
command record states why (`resume reuse rejected: …`). Old results remain
readable, but a run without a valid resume identity cannot establish safe
reuse and must execute again; file existence alone is insufficient.
The resume identity records content digests for external raw inputs while
excluding paths that are declared as outputs of an upstream DAG step; an
`output_dir` alone does not claim ownership of files below it, so user
provided files and symlinks remain protected. Changes to those external
inputs therefore still reject reuse.

Cancellation distinguishes the request from confirmed termination. A cancel
request is recorded with unconfirmed evidence; only exit evidence of actual
termination (death by signal, or never started) marks a job `cancelled`.
Work that completes despite a recorded cancel request is reported by its
real outcome (`succeeded`/`failed`) with the unconfirmed request preserved
in the job's `termination` field; killing the dispatch worker is never
claimed as termination of downstream engine or scheduler processes.

Basic reports include an "Execution Facts" section — step status counts,
failed calls with reasons, reused (validated-resume) steps, and history
linkage — so a report never restates only the plan tables. `inspect` exposes
the same linkage fields (`run_id`, `plan_id`, `resumes_run_id`,
`previous_run_archive`) plus the reused-step list and whether an audit
snapshot is present.

## Error Codes

ABI uses 19 stable error codes from `abi.diagnostics`, enumerating every
recognized failure mode:

| Code | Triggers when |
| --- | --- |
| `unknown_analysis_type` | plugin ID not recognized |
| `invalid_config` | YAML/JSON config failed schema validation |
| `invalid_sample_sheet` | sample sheet missing or malformed |
| `missing_input` | a required input file does not exist |
| `missing_resource` | a resource is NOT_CONFIGURED or missing |
| `missing_database` | a bioinformatics database is unavailable |
| `tool_not_found` | an external tool executable is not on PATH |
| `permission_required` | execution requires explicit user confirmation |
| `runtime_not_supported` | the requested engine is not local/nextflow/snakemake/hpc |
| `nonzero_exit` | an external command returned non-zero |
| `parse_failed` | tool output could not be parsed into tables |
| `empty_result` | the pipeline produced no output |
| `artifact_missing` | a required result artifact is absent |
| `internal_error` | unexpected/unclassified error at the ABI boundary |
| `contract_violation` | a step contract assertion or output check failed |
| `duplicate_sample_id` | sample sheet contains duplicate sample IDs |
| `incomplete_pairs` | paired-end reads have mismatched R1/R2 files |
| `invalid_platform` | platform identifier is not supported by the plugin |
| `missing_sample_id` | a sample ID is missing from the expected set |

The frozen set is defined in `abi.diagnostics.ERROR_CODES` and each error
response carries a stable `error_code` + actionable `diagnostic_hints`. Each
hint also carries a structured `recovery` block (`action`, `api_call`,
`params`) from a data-driven table covering all 19 codes: `action` is one of
`retry`, `resume`, `fix_input`, `install_resource`, `request_authorization`,
or `do_not_retry`, and `do_not_retry` classes (malformed sample sheets,
contract violations, internal errors) must never be auto-retried.

## Plugin Contracts

Each plugin must provide:

- `abi-plugin.yaml`
- `tool_registry.yaml`
- `standard_tables.yaml`
- `tool_contracts/*.yaml`
- `limitations.yaml` (mandatory, non-empty; enforced by contract lint)

`abi.testing.assert_plugin_contract()` validates runtime Python interfaces and
machine-readable plugin assets. Validation also enforces output-contract
coverage: every external-tool node in `pipeline_dag.yaml` must declare a
`contract:` block, or an explicit `contract: {exempt: true, reason: ...}` for
output-less aggregation nodes.

## Plugin Discovery and Loading

`list_types`, agent summaries, and `doctor` use
`list_plugin_metadata()` to read plugin declarations without instantiating
every implementation. `get_plugin()` loads only the selected plugin; the
legacy SDK `list_plugins()` remains an explicit full-load compatibility API.
ABI does not yet provide independently installable plugin packages, and
`query`/catalog callers that still assume global resource roots remain a
future migration.

## Plan Summary

`plan` envelopes include a `summary` field so agents understand workflow
structure without reading the full `execution_plan.json` (which can be large
for workflows such as the 90-node metagenomic plasmid DAG).

```json
{
  "status": "success",
  "command": "plan",
  "result": {
      "plan_path": "/tmp/plan/execution_plan.json",
      "compiled_plan_path": "/tmp/plan/compiled_plan.json",
      "steps": 90,
    "summary": {
      "pipeline": "metagenomic_plasmid",
      "stages": ["qc", "assembly", "plasmid_detection", "annotation", "abundance"],
      "key_tools": ["fastp", "megahit", "genomad", "bakta", "coverm"],
      "platforms": ["illumina", "nanopore"]
    }
  }
}
```

## Query Interface

`abi query` provides lightweight metadata access (~50ms) by reading
`pipeline_dag.yaml` and tool registry directly — no config loading or plan
building required.

```bash
abi query --type <plugin> --what stages|tools|platforms
abi query --type <plugin> --step <id> --what inputs|outputs|resources
```

This is NOT a replacement for `abi plan` — it is a fast path for agents
that only need metadata (available tools, pipeline structure, step I/O).

## Step Contracts and Reproducibility

Runtime step contracts are embedded in `PlanStep.params["_contract"]` by the
shared DAG planner. All eight built-in plugins copy this block from their
`pipeline_dag.yaml`.

Supported output checks include:

- existence of declared files or directories
- `min_size`
- `extensions`
- directory `contains`
- `min_files`
- FASTA `min_contigs`
- JSON `required_keys`
- dotted JSON `schema`
- runtime `assertions`
- checksum recording for downstream verification

Executors may resolve actual files after a tool succeeds when a planner path is
abstract but the tool writes fixed filenames. Resolved outputs, not abstract
planner placeholders, are used for output contracts and assertions.

Scientific reproducibility requires more than the ABI envelope. Production
workflows should also pin tool versions, record database/model manifests and
checksums, and validate known benchmark datasets. The repository-level target is
tracked in [Workflow Validation and Scientific Evidence Plan](workflow_validation.md).
