---
name: autoplasm-agent
description: Plan, run, and audit ABI metagenomic plasmid analyses from reads or assemblies using the metagenomic_plasmid plugin, its registered tools, and recorded workflow evidence.
---

# ABI plasmid analysis

Use the installed `abi` CLI with `--type metagenomic_plasmid`. The legacy
`autoplasm` CLI and `abi.autoplasm` imports are retired. The plugin is installed
separately as `abi-agent-plugin-metagenomic-plasmid` at the core ABI version.

## Discover and prepare

Query current capabilities rather than assuming every optional tool is enabled:

```bash
abi query --type metagenomic_plasmid --what stages
abi query --type metagenomic_plasmid --what tools
abi doctor-agent --type metagenomic_plasmid
abi check-resources --type metagenomic_plasmid --config project.yaml
abi plan --type metagenomic_plasmid --config project.yaml
abi dry-run --type metagenomic_plasmid --config project.yaml
```

Check sample-sheet input paths, platform, group labels, configured database/model
paths, resolved tool versions and commands. The input platform selects Illumina,
ONT, PacBio HiFi, hybrid or assembly-only routing. Use `--no-check-files` only for
planning with unavailable inputs; it cannot demonstrate readiness for execution.

ABI uses the configured runtime environment and resource roots. Set `ABI_MAMBA_ROOT`
when needed and inspect the resolved identities. `setup-resources` only reports
readiness and external preparation requirements. Acquire inputs, databases and tool
installations outside ABI; do not promise automatic download or environment repair.

For source development, use the plugin's co-located `pipeline_dag.yaml`,
`tool_registry.yaml`, `tool_contracts/`, `limitations.yaml` and `lib/` beneath
`src/abi/plugins/metagenomic_plasmid/`. The maintained route and evidence description
is `docs/en/metagenomic_plasmid.md` (Chinese: `docs/zh/metagenomic_plasmid.md`).

## Execute the requested analysis

Select `local`, `nextflow`, `snakemake` or `hpc` according to the user's environment.
Real execution requires explicit user authorization and the CLI confirmation flag;
existing authorization in the conversation remains valid. Execute the inspected plan
and preserve its identity. Re-plan if inputs, tools, resources or commands change.

```bash
abi run --type metagenomic_plasmid --config project.yaml --confirm-execution
```

Use a sample sheet for single-sample and multi-sample projects. Check the generated
commands for unresolved placeholders and keep original reads separate from cleanup
operations. Do not manually edit provenance to force resume. ABI verifies external
inputs and outputs before reuse; a cancel request alone is not evidence of termination.

## Audit and troubleshoot

Inspect `execution_plan.json`, the compiled/resolved plans, and `provenance/`:
`commands.tsv`, `resolved_inputs.tsv`, `tool_versions.tsv`, `checksums.json`,
`resources.json`, `run_summary.json`, the audit snapshot, and per-step logs.
Prior evidence is archived under `provenance/previous_runs/` before rewriting results.
Basic historical audit remains available from the core even without the plugin.

Use `abi inspect`, `abi report`, and `abi validate-result` with the result directory;
consult `--help` for their current options. Result tables include plasmid predictions,
consensus, annotations, host predictions and abundance. Empty tables can represent
valid zero-hit results; distinguish them from failed or missing evidence.

For a failure, identify the first failed command, read its reason and stderr, then
correct inputs, configuration or the externally provisioned runtime. Re-plan and
verify the correction. Preserve user files and previous results during recovery.

## Scientific interpretation

- geNomad is the default plasmid detector; optional tools provide selected evidence.
- Comparative clinker, sequence comparisons and network computations remain available.
  Circular/linear maps and interactive network renderers are retired; use result tables
  with external plotting tools. Historical visualization tables remain readable.
- Assembly-only inputs do not count as read-based abundance replicates. Diversity,
  differential analysis and network eligibility follow the actual sample sheet.
- Dry-run verifies planning and command rendering, not biological accuracy.
- Tool publications support individual methods; whole-workflow validation requires
  pinned tools/resources, real benchmark execution and documented acceptance criteria.
- Plasmid clusters are operational groups, binning may be incomplete, host associations
  are evidence rather than definitive assignments, and correlations are not causal.

Preserve input protection, contracts, provenance, mandatory limitations and independent
audit when adjusting workflows. Follow `AGENTS.md` for development and release gates.
