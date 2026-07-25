# Airway and WGS: a paired real-data example

This example shows what ABI means by contract-guided bioinformatics execution. Airway RNA-seq
and bacterial WGS use the same agent-facing lifecycle, but they do not share a generic biological
pipeline. Each plugin preserves its own study design, tools, resources, expected outputs,
scientific endpoints, and limitations.

```text
Research goal -> ABI plugin contract
                    |-- Airway -> STAR -> featureCounts -> DESeq2
                    |              `-> ranking + direction + sentinel evidence
                    `-- WGS ----> fastp -> SPAdes -> Prokka -> MLST -> AMRFinderPlus
                                   `-> ST93 + mecA evidence
Both lanes -> standard tables + provenance + limitations
```

The YAML configuration and `pipeline_dag.yaml` make the requested workflow inspectable. The ABI
core then validates inputs, resources, environments, permissions, step contracts, outputs, and
provenance. This distinction matters: a valid DAG is a plan, whereas a validated result directory
is execution evidence, and a comparison with preregistered endpoints is biological evidence.

## Shared operating lifecycle

For both analyses the researcher or agent follows the same control sequence:

```text
abi query -> abi plan -> abi check -> abi dry-run -> review
          -> abi run --confirm-execution -> abi inspect
          -> abi validate-result -> abi report
```

The concrete configuration and sample sheet remain analysis-specific. The execution plan is the
handoff between planning and runtime; published standard tables are the handoff between runtime
and scientific comparison.

## Airway RNA-seq

The Airway example uses eight paired-end libraries from four donors in GSE52778, comparing
dexamethasone with untreated cells. The ABI analysis fixes the DESeq2 design to
`~ donor + condition`, preventing donor-to-donor variation from being mistaken for treatment
response. STAR, featureCounts, and DESeq2 differ from the original hg19/TopHat/Cuffdiff analysis,
so the validation target is agreement in effect direction and ranking, not equality of p-values
or the significant-gene count.

| Endpoint | Result | Interpretation |
| --- | ---: | --- |
| Formal execution | 26/26 steps | Result directory passed validation |
| Genes compared with GEO | 13,725 | Genes mapped between ABI and the frozen GEO table |
| Dex log2FC rank agreement | Spearman ρ = 0.927 | Strong agreement in treatment-effect ranking |
| Effect-direction agreement | 90.8% | Matched genes with the same effect sign |
| Preregistered sentinel genes | 7/7 concordant | Targeted directional check passed |
| Significant-set overlap | 302 genes; Jaccard 0.0627 | Reported as method-sensitive, not as the sole validity endpoint |

![Airway biological validation](../_static/paper_examples/airway_biological_validation.png)

The chart intentionally plots only comparable agreement proportions. Spearman correlation and
significant-set Jaccard remain in the exact-value table rather than being mixed onto the same bar
axis.

## ST93 MRSA WGS

The WGS example uses six paired-end *Staphylococcus aureus* isolates from PRJNA286158. The plugin
performs read QC, assembly, annotation, MLST, and AMR detection. The preregistered endpoints are
recovery of the published ST93 identity and full-length `mecA` evidence.

| Endpoint | Result | Interpretation |
| --- | ---: | --- |
| Formal execution | 30/30 steps | Result directory and required standard tables passed validation |
| MLST | 6/6 ST93 | Study-specific sequence-type concordance |
| `mecA` | 6/6 | Each call had 100% amino-acid coverage and identity |
| AMR table | 145 rows | Tool evidence rows, not 145 distinct resistance genes |
| Core-SNP pairwise range (paper track) | 7-60 (median 47) | Original SPANDx v2.6 on the full 82-sample paper context restores the published 7-60 (mean 44); paper_exact_candidate |
| Core-SNP pairwise range (ABI-adjacent track) | 10-73 (median 55) | BWA mem + bcftools haploid joint calling; not the paper method, reported side by side |

![WGS biological validation](../_static/paper_examples/wgs_biological_validation.png)

The core-SNP endpoint is recovered at the pairwise-distance level by an external track running
the paper's own SPANDx v2.6 toolchain against JKD6159 CP002114, with the paper context cohorts
(PRJEB3144, PRJNA232112) included. The ABI `wgs_bacteria` plugin itself still ships no core-SNP
module, so the recovery is credited to the strict comparison harness, not to the plugin.

## Machine-readable evidence

- [Canonical claim table](../../metrics.tsv)
- [Airway endpoints](../paper_examples/airway_metrics.tsv)
- [WGS endpoints](../paper_examples/wgs_metrics.tsv)
- [Methods](../paper_examples/methods.tsv)
- [Limitations](../paper_examples/limitations.tsv)
- [Airway FigureSpec](../paper_examples/airway_validation.figure.yaml)
- [WGS FigureSpec](../paper_examples/wgs_validation.figure.yaml)
- [SCAPP descriptive FigureSpec](../paper_examples/scapp_descriptive.figure.yaml)
- [Airway significant-set data](../paper_examples/airway_significant_set_overlap.tsv)
- [WGS isolate evidence matrix](../paper_examples/wgs_isolate_evidence.tsv)
- [WGS SNP pairwise distances (both tracks)](../paper_examples/wgs_snp_pairwise_distances.tsv)
- [WGS SNP track comparison summary](../paper_examples/wgs_snp_track_comparison.tsv)
- [SCAPP per-plasmid biological evidence](../paper_examples/scapp_biological_evidence.tsv)
- [Biological figure provenance](../_static/paper_examples/biological_figures.provenance.json)
- [Reproducible figure builder](../../scripts/create_real_data_case_study_figures.py)

## Flagship case study: SCAPP plasmidome

SCAPP uses SRR11038083 to exercise ABI's most evidence-rich plugin. The completed run contains 167
primary calls, 157 consensus plasmids, and 54 candidates with terminal-repeat evidence; the
supplementary mobility analysis calls 20 candidates mobilizable. These values demonstrate a
complete, inspectable plasmid analysis and support evidence stratification. They are not an
independent accuracy estimate.

![SCAPP per-plasmid biological evidence](../_static/paper_examples/scapp_biological_evidence.png)

The scatter uses length, CoverM abundance, terminal-overlap status, mobility class, and AMR
support for all 157 consensus candidates. It does not use the invalid historical
reference-matched grouping and is not an accuracy curve.

Headline precision, recall, and F1 remain withheld. The earlier single-stage PLSDB screen omitted
the paper's contig-level gate and is excluded from `metrics.tsv`. The flagship accuracy panel may
be released only after the independent K127 assembly, both coverage gates, duplicate-prediction
rule, machine-evidence manifest, and figure provenance pass. Because the paper-specific
13,469-record PLSDB deduplication list is unavailable, even the final result must be described as a
**paper-method reconstruction**, not paper-exact reproduction.

The machine-readable status is recorded in [SCAPP status](../paper_examples/scapp_status.tsv).

## Limitations of this example

The two-workflow example establishes cross-plugin feasibility and recovery of study-specific
endpoints; it is not a population-level accuracy benchmark. Airway uses a different reference and
statistical toolchain from the original paper. The WGS core-SNP endpoint is recovered only through
an external paper-toolchain track (pairwise 7-60), while the ABI plugin itself still has no
core-SNP module and the ABI-adjacent bcftools track (10-73) must not be read as a paper
reproduction. SCAPP's independent headline metrics remain gated.
These boundaries are first-class outputs rather than qualifications added after the analysis.
