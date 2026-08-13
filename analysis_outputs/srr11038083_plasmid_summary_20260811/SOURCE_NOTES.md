# SRR11038083 report source and QA notes

## Report contract

- Audience: technical / research.
- Delivery mode: Data Analytics MCP report artifact.
- Scope: one SRR11038083 sample; descriptive, not inferential or causal.
- Snapshot time: 2026-08-11 23:00:12 +08:00.
- Primary artifact input: `artifact.json`.
- Reproducible transformation: `build_summary_artifact.py`.
- Queryable reviewed snapshot: `derived/analysis.sqlite`.
- Raw reviewed evidence: `source/main`, `source/followup`, and `source/amrfinder`.

## Required technical-report structure mapping

| Required role | Reader-facing section |
|---|---|
| Title | SRR11038083 宏基因组质粒分析图表汇总 |
| Technical summary | 技术摘要 |
| Key findings with visual evidence | Candidate distribution, abundance, typing, annotation, AMR and arsenic-resistance sections |
| Scope, data and metric definitions | 分析范围、数据与指标定义 |
| Methodology | 方法与稳健性检查 |
| Limitations and robustness | 局限性、不确定性与反证 |
| Recommended next steps | 推荐的下一步 |
| Further questions | 仍待回答的问题 |

## Chart map

| Section | Analytical question | Family / type | Dataset and fields | Supported claim |
|---|---|---|---|---|
| Candidate structure | How are final candidate lengths distributed? | Comparison / bar | `length_distribution`: bin, candidate_count | 59/156 candidates are shorter than 1 kb; only 3 are at least 10 kb. |
| Candidate structure | How do length and abundance relate? | Relationship / scatter | `candidate_detail`: length_kb, log10_tpm, finding_group | Abundance spans orders of magnitude; functional importance is not identical to abundance rank. |
| Abundance | Which candidates dominate by TPM? | Ranking / bar | `top_abundance`: contig_id, tpm | A small number of candidates dominate read-based abundance estimates. |
| Typing | Which replicon types are represented? | Comparison / bar | `typing_distribution`: replicon_type, hit_count | Only 8 unique candidates are typed; Col(MG828) has the most hits. |
| Annotation | What types of Bakta features were recorded? | Composition comparison / bar | `annotation_categories`: category, feature_count | CDS dominates, while region and structural sequence features remain auditable. |
| AMR evidence | Which tools support blaTEM-116? | Binary comparison / bar | `amr_evidence`: evidence_source, detected | Bakta, ABRicate/CARD and AMRFinderPlus are positive; RGI is empty. |

## Omitted visual explanations

- No time-series chart: this is a single sample and has no temporal observations.
- No differential-abundance chart: there is no comparison cohort or replicate group.
- No network chart: standard host-link and network tables are empty.
- No circular plasmid map: short-read contigs are not confirmed closed molecules; a circular map would overstate structural certainty.
- Key-contig gene positions use an exact sortable coordinate table because the native report schema has no genomic range-track chart.

## Provenance and data-quality notes

- ABI `inspect` and `validate-result` succeeded for the completed main, follow-up, and isolated AMRFinderPlus outputs used here.
- The main candidate catalog contains 156 consensus rows, 156 abundance rows, 156 geNomad prediction rows and 156 FASTA records.
- Bakta region lengths match candidate FASTA lengths for all 156 records, supporting the order-based mapping `contig_74 → k141_775` and `contig_154 → k141_1187`.
- IntegronFinder 2.0.6 tested 156 candidates; CALIN, complete and In0 were all zero.
- RGI raw output is the two-byte JSON object `{}`; its cross-parser standard-table row in the shared follow-up directory is not treated as independent confirmation.
- ABRicate/CARD and AMRFinderPlus independently report 100% reference coverage and 100% identity for TEM-116 / blaTEM-116 on `k141_775`.
- CoverM TPM is read-mapping based. Very high values may reflect shared/repeated sequence and should not be interpreted as molecule counts without orthogonal validation.
- Captured tool versions include ABI 1.5.11.1, fastp 1.3.5, MEGAHIT 1.2.9, geNomad 1.12.0, Bakta 1.12.0, PlasmidFinder 3.0.3, CoverM 0.7.0 and samtools 1.23.1. ABI provenance marked ABRicate, AMRFinderPlus, IntegronFinder and RGI versions as `not_configured`; operator checks recorded AMRFinderPlus 4.2.7, IntegronFinder 2.0.6 and RGI 3.2.7 outside the canonical version table, so those are not promoted to captured provenance.

## Rebuild

Run from `/home/bker/abi`:

```bash
python analysis_outputs/srr11038083_plasmid_summary_20260811/build_summary_artifact.py
```

The script validates cross-table row counts and Bakta-to-FASTA length mapping before replacing generated CSV, SQLite and artifact JSON outputs.
