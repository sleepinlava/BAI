# Managed Bacannot integration

`wgs_bacannot` integrates Bacannot as a managed external Nextflow workflow. It is separate from
the lighter ABI-native `wgs_bacteria` plugin and currently supports Illumina paired-end bacterial
isolates only.

The supported upstream identity is immutable:

- Bacannot `v3.4.4`
- commit `a78ddb0bffe75139adf1f443260d6d5b1987fe27`
- contract set `bacannot-3.4.4-v1`
- Nextflow `>=25.10.0,<26.0.0`, Java 17, Docker or Singularity

Planning exposes one parent step and the expected process classes. Execution records every observed
Nextflow task attempt, including retries and `CACHED` tasks. ABI forces trace, report, timeline, DAG,
and log output; archives `.command.sh`, stdout, stderr, and exit-code evidence per attempt; and verifies
the evidence manifest before accepting the result.

Normalized results are written under `standard/` and mirrored to ABI's conventional `tables/`
directory. `provenance/result_sources.tsv` links normalized rows to source files, checksums, tasks,
processes, and parser version. Assembly, annotation, MLST, and AMR contracts fail closed when a process
or required artifact is missing. `validate-result` re-verifies required artifacts directly against the
published result tree, so deleting or corrupting a key artifact fails validation with sample, contract,
task, and file attribution.

Failures are diagnosed, not just reported. Every run writes `provenance/diagnostics.json`, which
classifies failed attempts into stable error codes (`EXTERNAL_TASK_FAILED`, `RESOURCE_EXHAUSTED`,
`DATABASE_MISSING`, `TOOL_OR_CONTAINER_UNAVAILABLE`) with the process, sample, attempt, exit code,
archived log paths, and actionable hints. Unmapped Nextflow processes are always recorded in
`task_attempts.tsv`; `audit.unmapped_policy` (default `warn`) decides whether unmapped tasks also
block result validation (`fail`).

Resume runs preserve the original run's evidence: the previous snapshot, task-attempt table, evidence
manifest, validation, and diagnostics are archived under `provenance/previous_runs/<run-id>/`, and the
new snapshot records `resumes_run_id` plus the archive location. Each run summary reports a
CACHED-versus-executed reconciliation, so resume outcomes stay auditable.

The plugin deliberately reports `production_ready: false`. D2/D3 biological validation, resume
certification, representative HPC runs, container/database manifests, and a strict release runtime
lock remain release gates. Until those are complete, use this integration for engineering validation,
not certified production interpretation.

The safe lifecycle is:

```text
query -> plan -> check -> dry-run -> reviewed run -> inspect -> validate-result -> report
```

Real execution requires explicit ABI confirmation and a fully provisioned Bacannot database bundle.
