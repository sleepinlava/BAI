# Workflow Validation and Scientific Evidence Plan

This page separates what ABI already checks from what still needs scientific validation. It also
records the evidence expected before a workflow is described as reproducible or biologically
validated.

## Current Assessment

ABI already provides the following control-layer checks:

- **Constrained**: plans are generated from plugin schemas and the metagenomic
  plasmid DAG; external execution is confirmation-gated; step contracts enforce
  output existence, size, extension, directory contents, file counts, FASTA
  contig counts, JSON required keys, JSON schema fields, assertions, and
  checksum chaining.
- **Verifiable**: runs write `execution_plan.json`, `provenance/commands.tsv`,
  `resolved_inputs.tsv`, `tool_versions.tsv`, `resources.json`,
  `run_summary.json`, step logs, standard tables, and reports.
- **Reproducible in structure**: the same config/sample sheet should generate
  the same plan and canonical artifact layout; checksums preserve downstream
  file identity.
- **Literature-aligned**: core route stages use established bioinformatics
  tools with published method papers.

ABI is **not yet** a fully validated scientific workflow. Papers for individual tools support the
choice of components, but the full route still needs pinned environments, database manifests,
benchmark datasets, expected biological outputs, and written acceptance thresholds.

## Evidence Spine

The table below is the initial evidence spine for the default metagenomic
plasmid route. It is intentionally conservative: each reference supports a
component method, not the complete ABI workflow as an integrated scientific
claim.

| Workflow stage | ABI tools | Literature evidence | What it supports | Remaining ABI validation |
| --- | --- | --- | --- | --- |
| Read QC and trimming | `fastp` | Chen et al., 2018, Bioinformatics, DOI: [10.1093/bioinformatics/bty560](https://doi.org/10.1093/bioinformatics/bty560) | FASTQ preprocessing, adapter trimming, quality filtering, JSON/HTML QC reports | Lock fastp version and assert before/after read-count invariants on benchmark FASTQs. |
| Cross-sample QC reporting | `multiqc` | Ewels et al., 2016, Bioinformatics, DOI: [10.1093/bioinformatics/btw354](https://doi.org/10.1093/bioinformatics/btw354) | Aggregated QC report across tools and samples | Add expected MultiQC artifact checks when MultiQC is enabled. |
| Short-read metagenome assembly | `megahit` | Li et al., 2015, Bioinformatics, DOI: [10.1093/bioinformatics/btv033](https://doi.org/10.1093/bioinformatics/btv033) | Large and complex metagenomic assembly with succinct de Bruijn graphs | Maintain assembly benchmark fixtures with minimum N50/contig-count thresholds. |
| Mobile genetic element detection | `genomad` | Camargo et al., 2023, Nature Biotechnology, DOI: [10.1038/s41587-023-01953-y](https://doi.org/10.1038/s41587-023-01953-y) | Identification of plasmids, viruses, and other mobile genetic elements | Version the geNomad database and assert known positive plasmid/viral hits in smoke datasets. |
| Plasmid detection (secondary) | `platon` | Schwengers et al., 2020, bioRxiv, DOI: [10.1101/2020.06.24.168914](https://doi.org/10.1101/2020.06.24.168914) | Plasmid, virus, and replicon typing via protein- and contig-level features | Version-lock platon database; track database path in provenance and validate against known reference plasmids. |
| Bacterial genome annotation | `bakta` | Schwengers et al., 2021, Microbial Genomics, DOI: [10.1099/mgen.0.000685](https://doi.org/10.1099/mgen.0.000685) | Rapid standardized bacterial genome annotation and structured outputs | Add annotation acceptance checks for known reference plasmids. |
| Gene prediction subtask | `prodigal` | Hyatt et al., 2010, BMC Bioinformatics, DOI: [10.1186/1471-2105-11-119](https://doi.org/10.1186/1471-2105-11-119) | Prokaryotic coding sequence prediction | Require generated GFF/FAA/FFN files and minimum coding sequence counts where enabled. |

## Final-State Acceptance Criteria

ABI can be called a constrained, verifiable, and stably reproducible workflow
when all of the following are true:

1. Every production route has a versioned DAG, schema-validated config, and
   output contracts for every step that feeds downstream biological claims.
2. Tool environments are pinned by exact package versions or containers, and
   `tool_versions.tsv` records real executable versions, not only status.
3. Every database/model/reference has a manifest with path, version, source URL,
   checksum, license note, and last validation date.
4. At least one small benchmark dataset per route has expected standard-table
   rows and biological assertions, checked in CI or a reproducible local test.
5. Reports include methods provenance: tool versions, database versions,
   parameters, citations, and known interpretation limits.
6. Golden agent traces cover plan, dry-run, inspect, run-blocking,
   failure-recovery, report, and result-validation paths.
7. Nextflow/local runtimes produce comparable standard artifacts for the same
   fixture inputs.

## Validation Roadmap

### Phase 0: Control-Layer Hardening

- Extend contract validation to inputs, not only outputs and checksum chaining.
- Promote contract violations to stable diagnostic error codes in JSON
  envelopes.
- Add contract-lint commands for `pipeline_dag.yaml` and `tool_contracts/*.yaml`. ✅ Implemented via abi.contracts.run_contract_lint
- Keep `pytest`, `ruff check`, `ruff format --check`, and `mypy src/abi/`
  passing on every change. ✅ CI enforced

### Phase 1: Reproducibility Manifests

- Generate `provenance/tool_versions.tsv` from the selected plan's real
  `--version` probes. ✅ Implemented
- Add `provenance/resource_manifest.json` with resource versions, sources, and
  file or content-tree SHA-256 checksums. ✅ Implemented
- Record `run_id`, ABI version, Git commit/dirty status, and the runtime-lock
  SHA-256 identity in `provenance/run_summary.json`. ✅ Implemented
- Pin smoke-test environments through explicit conda lock files or containers.
- Record command templates and resolved command tokens in machine-readable form.

For release or paper runs, declare identities for every external reference.
Directory resources listed in `checksum_resource_ids` use a deterministic
content-tree SHA-256; a publisher-supplied checksum can instead be placed in
`checksum_sha256`.

```yaml
provenance:
  runtime_lock: /frozen/runtime-lock.json
  required_resource_identity_ids:
    - reference_genome
    - annotation_gtf
    - genome_index
    - amrfinder_db
    - mlst_db
    - scapp_db
  checksum_resource_ids:
    - genome_index
    - amrfinder_db
    - mlst_db
    - scapp_db
  resource_identities:
    reference_genome:
      path: /references/genome.fa
      version: "<assembly accession and release>"
      source_url: "<authoritative download URL>"
    annotation_gtf:
      path: /references/annotation.gtf
      version: "<annotation release>"
      source_url: "<authoritative download URL>"
    genome_index:
      path: /references/star_index
      version: "<STAR version + genome/annotation release>"
      source_url: "<index build recipe or archived bundle URL>"
    amrfinder_db:
      path: /databases/amrfinder/latest
      version: "<AMRFinder database release>"
      source_url: "https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/"
    mlst_db:
      path: /databases/mlst
      version: "<snapshot date or commit>"
      source_url: "<scheme snapshot URL>"
    scapp_db:
      path: /databases/scapp
      version: "<database release>"
      source_url: "<archived database URL>"
```

When `required_resource_identity_ids` is present, ABI refuses to start the
formal execution if a listed resource lacks a path, version, or source. A
directory must also have a declared checksum or be selected in
`checksum_resource_ids`.

Paper evidence bundles are verified with `abi verify-evidence MANIFEST
--artifact-root REPOSITORY_ROOT`. The repository-level
`python scripts/verify_paper_evidence.py` command verifies the three checked-in
legacy-run bundles and independently tampers with every TSV copy to prove the
integrity check fails. These bundles are marked `verified_legacy_run`; formal
archival bundles must replace them after rerunning with complete mandatory
resource identities.

### Phase 2: Biological Benchmarks

- Add curated tiny positive controls: known plasmid references, negative
  chromosomal controls, and mixed samples. The benchmark harness and smoke
  tests exist, but the current checkout does not ship a complete
  `data/benchmarks/` fixture tree; provision and freeze the exact datasets
  before claiming a reproducible benchmark.
- Define standard-table acceptance checks for plasmid calls, annotations,
  abundance rows, and report contents.
- Attach expected failure cases: missing database, malformed sample sheet,
  empty output, swapped R1/R2, and incompatible platform/input combinations.

### Phase 3: Literature and Reporting

- Add a citation registry keyed by tool id and workflow stage.
- Emit citations and method limitations into `report/methods.md`.
- Link each default route in `pipeline_dag.yaml` to evidence entries and
  validation fixtures.
- Review plasmid-specific optional tools one by one and mark each as
  `validated`, `available`, or `experimental` in documentation.
