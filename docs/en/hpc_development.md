# Runtime and HPC Development Guide

ABI supports four execution engines. They all consume the same compiled plan; the difference is
where and how each step runs.

| Engine | Implementation | Typical use |
| --- | --- | --- |
| `local` | `src/abi/runtimes/local.py` | One host, direct subprocess execution |
| `nextflow` | `src/abi/runtimes/nextflow.py` | Nextflow DSL2 on a workstation, cluster, or cloud |
| `snakemake` | `src/abi/runtimes/snakemake.py` | Snakemake with marker-file completion and optional Conda |
| `hpc` | `src/abi/runtimes/hpc.py` | ABI-native Slurm/PBS submission and polling |

`abi plan` writes `execution_plan.json` and `compiled_plan.json` without choosing a backend.
The engine is selected later with `abi run --engine`.

## Preflight

Run a side-effect-free check for the intended engine before submission:

```bash
abi check \
  --type rnaseq_expression \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --engine hpc
```

This checks plugin inputs and resources and, unless `--no-check-runtime` is used,
the required runtime executables. A successful preflight does not prove that
cluster nodes can see the same paths; verify shared storage, modules/Conda
environments, and scheduler account policy separately.

## Nextflow

Export a standalone DSL2 file:

```bash
abi export-nextflow \
  --type rnaseq_expression \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --output workflow.nf

nextflow run workflow.nf -resume
```

Or let ABI export and launch it:

```bash
abi run \
  --type rnaseq_expression \
  --engine nextflow \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --workflow workflow.nf \
  --work-dir work/nextflow \
  --nextflow-profile slurm \
  --resume \
  --confirm-execution
```

Relevant options include `--nextflow-bin`, `--nextflow-profile`, `--executor`,
`--nxf-home`, and `--work-dir`.

## Snakemake

Export a standalone Snakefile:

```bash
abi export-snakemake \
  --type rnaseq_expression \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --output Snakefile

snakemake --snakefile Snakefile --cores 8 --use-conda
```

Or execute through ABI:

```bash
abi run \
  --type rnaseq_expression \
  --engine snakemake \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --workflow Snakefile \
  --confirm-execution
```

ABI invokes Snakemake with `--rerun-incomplete` and writes provenance on
success and failure. Marker files represent completed rules; do not treat the
presence of a work directory alone as successful completion. The generic CLI
accepts `--resume`, but the current Snakemake backend does not add a separate
Snakemake resume flag.

## Native Slurm/PBS

```bash
abi run \
  --type rnaseq_expression \
  --engine hpc \
  --scheduler slurm \
  --partition production \
  --account project_abi \
  --qos normal \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --resource-profile hpc_standard \
  --hpc-timeout 86400 \
  --poll-interval 30 \
  --resume \
  --confirm-execution
```

The native runtime creates payload and scheduler scripts for worker-scoped
steps, submits dependency-linked jobs, polls the scheduler, records job IDs and
atomic step results, and cancels timed-out work. Slurm has the primary
production validation surface. PBS is supported for compatible directives and
dependency submission but should be accepted against the target cluster before
production use.

Resource choices can come from step contracts, a profile
(`dev_small`, `hpc_standard`, `hpc_large`), or command-line overrides:

```bash
--cpu 16 --memory 64GB --walltime 08:00:00 --accelerator gpu:v100:1
```

Container overrides are also available:

```bash
--container-image ghcr.io/example/abi-rnaseq:1.5.7.1 \
--container-runtime apptainer
```

Supported runtime names are `docker`, `podman`, `singularity`, and `apptainer`.
The container image still needs access to input, output, and resource paths.

## Conda and resources

`environments.yaml` is the tool-to-environment source of truth. The current
plugin assignments are:

| Plugin | Declared environments |
| --- | --- |
| `rnaseq_expression` | `rnaseq` |
| `wgs_bacteria` | `wgs` |
| `amplicon_16s` | `amplicon` |
| `metatranscriptomics` | `abi-qc`, `abi-stats` |
| `easymetagenome` | `easymeta-p0`, `easymeta-humann` |
| `viral_viwrap` | `autoplasm-base` (ViWrap itself is managed externally) |
| `metagenomic_plasmid` | 11 `autoplasm-*`/`stats` environments |

Set `ABI_MAMBA_ROOT` or pass `--mamba-root` to select a shared environment
root. Use `abi check-resources` for read-only diagnosis and
`abi setup-resources --dry-run` before any confirmed setup.

The managed cloud release layout and strict certification process are defined
in [Release-ready runtime locks](runtime_locks.md). Do not interchange the
top-level `ABI_RUNTIME_RESOURCE_ROOT` used by runtime locks with the legacy
plasmid database meaning of `ABI_RESOURCE_ROOT`.

## Acceptance checklist

Before calling a cluster deployment production-ready:

1. Run strict contract lint for the affected plugin.
2. Validate input and resource visibility from a compute node, not only the
   login node.
3. Export and inspect the selected workflow representation.
4. Run a small `--smoke` job with the same scheduler/profile/container path.
5. Test failure, timeout, cancellation, and `--resume`.
6. Verify standard tables, provenance, checksums, report limitations, and
   scheduler IDs.
7. Capture a strict runtime lock for the release scope.

See the [production manual acceptance checklist](production_manual_acceptance_checklist.md)
for the full set of local and HPC gates.
