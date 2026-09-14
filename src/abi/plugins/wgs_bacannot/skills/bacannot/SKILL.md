# Bacannot

## Purpose

Run the ABI-managed, immutable Bacannot v3.4.4 workflow for Illumina paired-end bacterial isolates.

## Inputs

- ABI TSV samplesheet with `sample_id`, `platform`, `read1`, and `read2`.
- A locally provisioned Bacannot database directory with a recorded snapshot identity.

## Execution Boundary

ABI converts the samplesheet and launches `fmalmeida/bacannot` at commit
`a78ddb0bffe75139adf1f443260d6d5b1987fe27`. ABI owns the Nextflow trace, report,
timeline, DAG, log, task command evidence, and normalized tables. Do not add arbitrary
Nextflow arguments or replace the pinned revision.

## Outputs

Use `standard/` for normalized tables and `provenance/` for the execution snapshot,
task attempts, result-source mapping, and evidence manifest.

## Failure Handling

Inspect `validation.json`, then correlate its contract status with
`provenance/task_attempts.tsv` and the archived `.command.err` file. A disabled optional
module is `not_selected`; missing or failed required processes are errors.
