# Publication evidence package for ABI

This note defines a submission package that lets editors and independent researchers inspect the
biological analyses and the software process behind the ABI paper. It is an evidence package, not a
claim that fraud is impossible. The strongest design combines independent repository records,
complete machine-readable inputs and outputs, an immutable software snapshot, run-level provenance,
and transparent limitations.

## Policy basis

- Nature Portfolio requires the minimum dataset needed to interpret, verify, and extend a study,
  with accession numbers or other unique identifiers in a Data Availability statement. It prefers
  large data in public repositories rather than journal supplements and recommends depositing
  central custom code in a DOI-minting repository. [Nature reporting and availability policy](https://www.nature.com/nature/editorial-policies/reporting-standards)
- PLOS requires the data needed to replicate findings and, for PLOS Computational Biology,
  author-generated code directly related to the findings. It recommends persistent identifiers,
  documentation, dependency information, and an open-source license. [PLOS data policy](https://journals.plos.org/ploscompbiol/s/data-availability),
  [PLOS code policy](https://journals.plos.org/ploscompbiol/s/code-availability)
- The FAIR principles support persistent identifiers, rich metadata, standard retrieval protocols,
  clear licences, and detailed provenance. FAIR means that an object can be found and reused; it is
  not a certification that its scientific content is true. [GO FAIR principles](https://www.go-fair.org/fair-principles/)

## What to submit

Do not put large FASTQ files or an entire Git repository into journal Supplementary Information.
Submit a compact index and source-data package to the journal, and archive the complete evidence
bundle in appropriate public repositories.

### Canonical run selection

For each case study, use the most recent **valid completed real-data run** as the canonical evidence
source. Recency must be determined from run metadata, not filesystem modification time. A candidate
run replaces the previous canonical run only when `abi inspect` confirms real execution,
`abi validate-result` passes the applicable contract, required standard tables are nonempty, and
`tool_versions.tsv` records the actual tool identities used by that run.

Keep earlier runs as historical audit evidence, especially when they document a failure or repair,
but do not use their incomplete provenance as the basis of current manuscript claims. Record the
selected run ID, completion timestamp, validation timestamp, ABI commit, and evidence-manifest hash
in `evidence_index.tsv`; never choose a run from a date-like directory name alone.

### 1. Biological source and sample evidence

| Artifact | Minimum content | Why it matters |
| --- | --- | --- |
| `evidence_index.tsv` | Every claim, figure/table, source file, run ID, repository identifier, SHA-256, and limitation | Connects manuscript statements to inspectable evidence |
| `sample_metadata.tsv` | Stable sample ID; BioProject, BioSample, SRA/GEO accession; group; source; country; batch; platform; library layout; inclusion/exclusion; consent/access status | Exposes sample identity, batch structure, and confounding |
| Raw-data deposition | FASTQ or instrument-level raw data and metadata in SRA; controlled access for non-consented human data | Creates a third-party accession and preserves minimally processed reads |
| Processed-data deposition | Complete count/abundance/feature matrices, not only selected significant rows; GEO for functional-genomics studies | Allows results and statistics to be recomputed |
| `protocols/` | Sampling, extraction, library construction, QC, analysis protocol, deviations, and versions; preferably a citable protocol DOI | Records what was done before computation |
| `controls_and_exclusions.tsv` | Positive/negative controls, failed samples, outliers, exclusion reason, and whether the rule was predefined | Prevents selective reporting of successful samples |
| `source_data/` | One machine-readable TSV/CSV per figure panel, including all observations, IDs, statistics, confidence intervals, and exclusion flags | Makes every plotted value auditable |
| Original images, if applicable | Uncropped/unprocessed gels, blots, microscopy files, acquisition metadata, and processing scripts | Permits image-integrity review |

NCBI describes SRA metadata through Study/BioProject, Sample/BioSample, Experiment, and Run objects,
with public accessions for the archived records. GEO high-throughput submissions require study/sample
metadata plus raw and processed data; processed data should include the quantitative values used to
draw conclusions. [SRA metadata model](https://www.ncbi.nlm.nih.gov/sra/docs/submitmeta/),
[SRA submission guidance](https://www.ncbi.nlm.nih.gov/sra/docs/submit/),
[GEO sequencing guidance](https://www.ncbi.nlm.nih.gov/geo/info/seq.html)

For human data, do not publish identifiers or sequence data contrary to consent or law. State the
reason for controlled access, the repository, access criteria, and request procedure. NCBI explicitly
directs human data lacking consent for public release away from public SRA. Nature likewise requires
precise disclosure of controlled-access conditions.

If the study contains gels, blots, or microscopy, retain the original files. Nature Portfolio may
request unprocessed files and requires unprocessed gel/blot images with accepted life-science papers;
processing tools and manipulations must be disclosed. [Nature image-integrity policy](https://www.nature.com/npjhydrosph/editorial-policies/image-integrity)

### 2. Analysis and ABI provenance

For each claim-bearing run, archive:

- the resolved sample manifest, input accessions, file sizes, and input SHA-256 values;
- `execution_plan.json`, resolved configuration, DAG/plugin declarations, and schema versions;
- `commands.tsv`, step status, timestamps, exit codes, stdout/stderr, and failed/retried steps;
- `tool_versions.tsv`, reference assembly identifiers, database versions, download URLs, and database
  checksums;
- complete standard output tables, contract-validation results, reports, and `limitations.yaml`;
- random seeds, thread counts, numerical-library/hardware details where they can affect output;
- the scripts and exact source tables used to calculate statistics and generate every figure; and
- a top-level `MANIFEST.sha256` covering every deposited file.

Preserve failures and corrections rather than replacing them silently. A correction record should
identify the invalid artifact, failure mechanism, fixing commit, regenerated artifact, and both
hashes. This is especially important for the SCAPP v1-to-v2 scoring correction described in the
paper.

### 3. Software release and build evidence

Archive the exact paper version, not only the moving default branch:

1. Create a versioned source release tied to one Git commit and tag.
2. Deposit that release in Zenodo and cite the **version-specific DOI** in the paper. Zenodo creates
   both a DOI for each version and a concept DOI for all versions; the concept DOI resolves to the
   latest version and therefore does not identify the exact reviewed bytes. [Zenodo DOI versioning](https://zenodo.org/help/versioning)
3. Archive the source in Software Heritage and cite a release/directory SWHID with origin and anchor
   qualifiers. SWHIDs are content-derived identifiers over archived software objects.
   [Software Heritage SWHID specification](https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html)
4. Include the source archive, wheel/sdist, lock files, Dockerfile, container image digest, database
   lock, SBOM if available, and SHA-256 manifest.
5. Include CI workflow definitions, machine-readable unit/integration/smoke results, contract lint,
   coverage report, package checks, and known failures. Screenshots alone are not sufficient.
6. Prefer signed build provenance/attestations for released packages and images. SLSA provenance
   records where, when, and how an artifact was produced and supports verification and rebuilding.
   [SLSA build provenance specification](https://slsa.dev/spec/v1.2/build-provenance)

For a major revision of deposited content, create a new DOI and link versions rather than replacing
the cited object. [DataCite versioning guidance](https://support.datacite.org/docs/versioning)

## ABI repository assets to include

The current repository contains a frozen local evidence surface for the newest completed real-data
runs. Every final claim must bind to one of these dated directories, not to an undated or superseded
retry directory. The synchronized snapshot is indexed in
`analysis_outputs/canonical_runs_20260819/README.md` and frozen by its `SHA256SUMS` manifest.

- Canonical RNA-seq: `analysis_outputs/canonical_runs_20260819/rnaseq_airway_20260809/`.
- Canonical WGS: `analysis_outputs/canonical_runs_20260819/wgs_st93_20260810/`.
- Canonical plasmid main and follow-up evidence:
  `analysis_outputs/canonical_runs_20260819/metagenomic_plasmid_20260810/`,
  `metagenomic_plasmid_followup_20260811/`, and `metagenomic_plasmid_amrfinder_20260811/` beneath
  the same root.
- Canonical EasyMetagenome evidence:
  `analysis_outputs/canonical_runs_20260819/easymetagenome_real30_20260814/`.
- The superseded local bundles `downloads/rnaseq_retry5/`, `downloads/wgs_st93_mrsa_retry/`, and
  `downloads/plasmid_scapp_core_retry7/` were retired after checksum comparison and validation.
- `downloads/abi_scapp/` is retained because the latest plasmid main run excluded SCAPP under its
  resolved configuration and therefore is not an equivalent replacement for the SCAPP-node
  benchmark. `downloads/scapp_original/` remains the external comparison baseline.
- Claim-level bindings: `metrics.tsv` and `docs/paper_examples/manifests/*.evidence-manifest.json`.
- Biological source tables: `docs/paper_examples/*.tsv`, the SCAPP v2 machine-readable evidence
  directory, and `downloads/scapp_original/three_way_comparison.tsv`.
- Figure evidence: `analysis_outputs/rnaseq_wgs_scapp_publication_figures_20260816/` and
  `analysis_outputs/easymetagenome_real30_publication_figures_20260816/`, including source/figure
  manifests and figure-building scripts.
- Verification code: `scripts/build_paper_provenance.py`, `scripts/verify_paper_evidence.py`, and
  their regression tests.

The 30-sample EasyMetagenome cohort is classified as an **auditable real run**. Its execution plan,
277 successful commands, step logs, standard tables, checksum records, cleanup receipts, and reports
are synchronized in the canonical snapshot. ABI result validation succeeds.

This classification does not require strict environment-reproduction certification. The run-local
`tool_versions.tsv` reports five P0 executables as `not_configured`; Git identity, a strict runtime
lock, and complete database identities are also absent. These are disclosed audit findings.

The header-only `functional_abundance.tsv` is expected because the run covers P0 taxonomy. Do not
claim a functional-profile analysis or a fully version-locked reproduction. A later strict rerun is
an optional enhancement, not a prerequisite for using this run as the paper's audit case.

## Recommended archive layout

```text
Supplementary_Evidence_Package/
  README.md
  evidence_index.tsv
  sample_metadata.tsv
  controls_and_exclusions.tsv
  figure_manifest.tsv
  source_data/
  protocols/
  runs/<case>/
    execution_plan.json
    provenance/
    tables/
    validation/
    report/
  reproduction/
  software_release/
  MANIFEST.sha256
  SIGNATURES/
```

The journal supplement should contain `README.md`, the indexes, compact source-data tables, and
links to accessions/DOIs/SWHIDs. The repository deposit should contain the complete package.

## What the evidence does and does not prove

| Evidence | Supports | Does not establish by itself |
| --- | --- | --- |
| Public SRA/GEO accession and metadata | A third party received and serves identified files and metadata | That the biological sample or original sequence was not fabricated |
| SHA-256 manifest | The checked bytes match the frozen manifest | Who created the bytes or whether their content is scientifically truthful |
| DOI | Persistent identification and citation of a deposited object | Quality, correctness, peer review, or originality |
| Git commit/tag | Identification and history within that Git repository | Immutability if history/tags can be rewritten |
| SWHID/external source archive | Content identity and independent preservation of source | Correctness of the algorithms or analyses |
| Signature or build attestation | Link between an artifact, signer/builder, source, and build process | Biological validity or freedom from malicious/incorrect source |
| Passing CI/tests | The published tests passed in the recorded environment | Exhaustive software correctness or scientific validity |
| Container/lock file | A substantially specified runtime environment | Freedom from hardware, concurrency, random, or external-database drift |
| Reproducing the same output | Computational repeatability for the frozen inputs and method | Unbiased design, appropriate cohort, correct truth set, or generalizable biology |

The strongest defense against fabrication is therefore cumulative: contemporaneous instrument and
laboratory records; documented sample custody and ethics; public accession timestamps; raw and
processed data; controls and failed samples; complete code and provenance; independent archival
anchors; and, ideally, an independent clean-environment rerun. In the terminology of the US Office
of Research Integrity, fabrication is making up data/results and falsification includes changing or
omitting data so the research record is inaccurate; integrity mechanisms must address the full
research record, not only the final files. [ORI definition of research misconduct](https://ori.hhs.gov/definition-research-misconduct)
