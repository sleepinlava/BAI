# RNA-seq Expression Workflow (`rnaseq_expression`)

The current built-in RNA-seq workflow is a five-node, Illumina paired-end
pipeline:

```text
fastp
  -> STAR
  -> featureCounts
  -> build_count_matrix.py
  -> DESeq2
```

`plugins/rnaseq_expression/pipeline_dag.yaml` is the topology source of truth.
`tool_registry.yaml` defines the five executable tools, while
`standard_tables.yaml`, `figure_specs.yaml`, and `limitations.yaml` define the
published result contract. HISAT2 remains a read-only parser compatibility alias;
it is not a runnable alternative in the current DAG. Salmon, Kallisto, edgeR,
clusterProfiler, and gseapy are not registered by this plugin.

## Initialize a workspace

Use `abi init` instead of copying an example path:

```bash
abi init --type rnaseq_expression --outdir work/rnaseq
```

This writes:

```text
work/rnaseq/
├── config/rnaseq_expression.yaml
└── samples.tsv
```

Edit `samples.tsv` with unique sample IDs and real paired FASTQ paths. The
required columns are `sample_id`, `read1`, and `read2`. Keep `condition` for
differential expression; paired or blocked designs may also add columns such as
`donor`.

Edit the generated configuration and replace both resource placeholders:

```yaml
input:
  sample_sheet: samples.tsv

resources:
  genome_index: /data/references/hg38/star_index
  annotation_gtf: /data/references/hg38/gencode.annotation.gtf

differential_expression:
  comparison: treatment_vs_control
  design: "~ condition"
  alpha: 0.05
```

Paths in an override configuration are resolved relative to that configuration
file. For a paired study, use a design such as `~ donor + condition` and ensure
the sample sheet contains `donor`.

## Plan, check, and run

```bash
abi plan \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml \
  --sample-sheet work/rnaseq/samples.tsv \
  --outdir results/rnaseq-plan

abi check \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml \
  --sample-sheet work/rnaseq/samples.tsv

abi check-resources \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml

abi dry-run \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml \
  --sample-sheet work/rnaseq/samples.tsv \
  --outdir results/rnaseq-dry-run

abi run \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml \
  --sample-sheet work/rnaseq/samples.tsv \
  --outdir results/rnaseq \
  --confirm-execution
```

`abi run` supports `--engine local|nextflow|snakemake|hpc`. Real execution
requires the `rnaseq` Conda environment (fastp, STAR, featureCounts, R/DESeq2),
a STAR index, and a compatible GTF.

## Results

The plugin publishes these standard tables:

| Table | Content |
| --- | --- |
| `qc_summary` | fastp metrics |
| `alignment_summary` | STAR alignment metrics |
| `gene_expression` | per-sample featureCounts values |
| `count_matrix` | long-form cross-sample raw count matrix |
| `normalized_expression` | DESeq2 normalized counts |
| `differential_expression` | base mean, fold change, test statistic, p-value, and adjusted p-value |

Current figure specifications include required QC, mapping-rate, and volcano
plots plus optional PCA, heatmap, and MA plots. Optional matrix-oriented plots
may be skipped when their source table cannot be represented by the current
renderer. Inspect the generated report rather than assuming every optional
figure exists.

```bash
abi inspect --result-dir results/rnaseq
abi validate-result --type rnaseq_expression --result-dir results/rnaseq
abi report --type rnaseq_expression --result-dir results/rnaseq
```

## Limitations

The authoritative list is
`plugins/rnaseq_expression/limitations.yaml` and is included in generated
reports. Important boundaries include reference/annotation sensitivity,
DESeq2 design assumptions, low-count uncertainty, batch effects, and the fact
that RNA abundance does not directly measure protein abundance.
