# WGS Bacterial Genome Analysis

Analysis type: `wgs_bacteria`

Clinical/food/environmental bacterial isolate analysis: QC (fastp) → assembly (SPAdes) → annotation (Prokka) → MLST → AMR profiling.

## Supported platforms and profiles

`illumina`

## Stages

- `qc_fastp` — tool `fastp`; category `qc`; required
- `assembly_spades` — tool `spades`; category `assembly`; required
- `annotation_prokka` — tool `prokka`; category `annotation`; required
- `mlst` — tool `mlst`; category `typing`; required
- `amr` — tool `amrfinderplus`; category `amr`; required

## Workflow dataflow

- `qc_fastp` → `assembly_spades`
- `assembly_spades` → `annotation_prokka`
- `assembly_spades` → `mlst`
- `annotation_prokka` → `amr`

## Tools and contracts

### `fastp` — fastp

Trim and quality-control paired-end RNA-seq reads.

Inputs/parameters:
- `read1` (required): `{"formats": ["fastq", "fastq.gz"], "required": true, "type": "file"}`
- `read2` (required): `{"formats": ["fastq", "fastq.gz"], "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"default": 4, "minimum": 1, "type": "integer"}`
Outputs:
- `clean_read1`: `{"format": "fastq.gz", "type": "file"}`
- `clean_read2`: `{"format": "fastq.gz", "type": "file"}`
- `html_report`: `{"format": "html", "type": "file"}`
- `json_report`: `{"format": "json", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check sample sheet read1/read2 paths."}, "nonzero_exit": {"hint": "Read provenance/step_logs/{step_id}.stderr.log."}, "tool_not_found": {"hint": "Install fastp in the abi-qc environment."}}`

### `spades` — SPAdes

De novo genome assembly from paired-end Illumina reads using SPAdes in isolate mode.

Inputs/parameters:
- `clean_read1` (required): `{"formats": ["fastq", "fastq.gz"], "required": true, "type": "file"}`
- `clean_read2` (required): `{"formats": ["fastq", "fastq.gz"], "required": true, "type": "file"}`
- `memory_gb` (optional): `{"default": 80, "minimum": 1, "type": "integer"}`
- `threads` (optional): `{"default": 4, "minimum": 1, "type": "integer"}`
Outputs:
- `contigs_fasta`: `{"format": "fasta", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
- `scaffolds_fasta`: `{"format": "fasta", "type": "file"}`
Resources: `{"cpu": 16, "memory": "64GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Cleaned FASTQ files not found. Verify fastp completed successfully."}, "tool_not_found": {"hint": "SPAdes not found. Install: conda install -c bioconda spades"}}`

### `prokka` — Prokka

Rapid prokaryotic genome annotation producing GFF, GenBank, and protein FASTA files.

Inputs/parameters:
- `assembly_fasta` (required): `{"formats": ["fasta"], "required": true, "type": "file"}`
- `genus` (optional): `{"required": false, "type": "string"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `species` (optional): `{"required": false, "type": "string"}`
- `threads` (optional): `{"default": 4, "minimum": 1, "type": "integer"}`
Outputs:
- `faa`: `{"format": "fasta", "type": "file"}`
- `gbk`: `{"format": "gbk", "type": "file"}`
- `gff`: `{"format": "gff", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Assembly FASTA not found. Verify SPAdes completed successfully."}, "tool_not_found": {"hint": "Prokka not found. Install: conda install -c bioconda prokka"}}`

### `mlst` — MLST

Multi-locus sequence typing (MLST) for bacterial isolates using the PubMLST scheme database.

Inputs/parameters:
- `assembly_fasta` (required): `{"formats": ["fasta"], "required": true, "type": "file"}`
- `scheme` (optional): `{"required": false, "type": "string"}`
Outputs:
- `mlst_tsv`: `{"format": "tsv", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Assembly FASTA not found. Verify SPAdes completed successfully."}, "tool_not_found": {"hint": "mlst not found. Install: conda install -c bioconda mlst"}}`

### `amrfinderplus` — AMRFinderPlus

Identify antimicrobial resistance genes, stress response genes, and virulence factors in bacterial protein sequences.

Inputs/parameters:
- `amrfinder_db` (required): `{"required": true, "type": "directory"}`
- `prokka_faa` (required): `{"formats": ["fasta", "faa"], "required": true, "type": "file"}`
- `prokka_gff` (optional): `{"formats": ["gff"], "required": false, "type": "file"}`
- `threads` (optional): `{"default": 4, "minimum": 1, "type": "integer"}`
Outputs:
- `amr_tsv`: `{"format": "tsv", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Prokka protein FASTA or GFF not found. Verify Prokka completed successfully."}, "tool_not_found": {"hint": "AMRFinderPlus not found. Install: conda install -c bioconda ncbi-amrfinderplus"}}`

## Output acceptance rules

- `qc_fastp.clean_read1`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "clean_read1", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}_R1.clean.fastq.gz", "stage": "qc_fastp", "type": "file"}`
- `qc_fastp.clean_read2`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "clean_read2", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}_R2.clean.fastq.gz", "stage": "qc_fastp", "type": "file"}`
- `qc_fastp.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}", "stage": "qc_fastp", "type": "directory"}`
- `assembly_spades.contigs_fasta`: `{"contract": {"min_size": "1KB"}, "format": "fasta", "output": "contigs_fasta", "path": "{outdir}/{category_dir}/{sample_id}/contigs.fasta", "stage": "assembly_spades", "type": "file"}`
- `assembly_spades.scaffolds_fasta`: `{"contract": {}, "format": "fasta", "output": "scaffolds_fasta", "path": "{outdir}/{category_dir}/{sample_id}/scaffolds.fasta", "stage": "assembly_spades", "type": "file"}`
- `assembly_spades.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}", "stage": "assembly_spades", "type": "directory"}`
- `annotation_prokka.faa`: `{"contract": {"min_size": "100B"}, "format": "fasta", "output": "faa", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.faa", "stage": "annotation_prokka", "type": "file"}`
- `annotation_prokka.gff`: `{"contract": {"min_size": "100B"}, "format": "gff", "output": "gff", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.gff", "stage": "annotation_prokka", "type": "file"}`
- `annotation_prokka.gbk`: `{"contract": {}, "format": "gbk", "output": "gbk", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.gbk", "stage": "annotation_prokka", "type": "file"}`
- `annotation_prokka.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}", "stage": "annotation_prokka", "type": "directory"}`
- `mlst.mlst_tsv`: `{"contract": {"min_size": "50B"}, "format": "tsv", "output": "mlst_tsv", "path": "{outdir}/{category_dir}/{sample_id}/mlst.tsv", "stage": "mlst", "type": "file"}`
- `mlst.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}", "stage": "mlst", "type": "directory"}`
- `amr.amr_tsv`: `{"contract": {"min_size": "50B"}, "format": "tsv", "output": "amr_tsv", "path": "{outdir}/{category_dir}/{sample_id}/amr.tsv", "stage": "amr", "type": "file"}`
- `amr.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}", "stage": "amr", "type": "directory"}`

## Standard tables

- `amr_profile`: sample_id, gene_symbol, sequence_name, scope, element_type, element_subtype, target_class, target_subclass, method, coverage_pct, identity_pct, tool, source_file
- `genome_annotation`: sample_id, feature_id, feature_type, start, end, strand, product, gene_name, ec_number, tool, source_file
- `genome_assembly_stats`: sample_id, total_length, num_contigs, n50, max_contig_length, gc_content, coverage, tool, source_file
- `mlst_profile`: sample_id, scheme, sequence_type, allele_1, allele_2, allele_3, allele_4, allele_5, allele_6, allele_7, clonal_complex, tool, source_file
- `qc_summary`: sample_id, tool, metric, value, unit, source_file

## Stable error categories

`artifact_missing`, `contract_violation`, `duplicate_sample_id`, `empty_result`, `incomplete_pairs`, `internal_error`, `invalid_config`, `invalid_platform`, `invalid_sample_sheet`, `missing_database`, `missing_input`, `missing_resource`, `missing_sample_id`, `nonzero_exit`, `parse_failed`, `permission_required`, `runtime_not_supported`, `tool_not_found`, `unknown_analysis_type`

## Limitations

- Short-read assembly (SPAdes) may fragment genomes with extensive repetitive elements (e.g., transposases, IS elements); long-read sequencing improves assembly contiguity.
- AMR gene presence does not guarantee phenotypic resistance; expression, copy number, and regulatory mutations affect resistance phenotype.
- MLST typing is scheme-dependent; isolates may have novel allelic profiles not in the reference database (indicated as 'unknown' or 'nearest match').
- Plasmid replicon detection via PlasmidFinder is limited to known replicon types; novel or divergent plasmid types may be missed.
- Annotation (Prokka/Bakta) transfers annotations from reference databases; gene names and functions are computational predictions, not experimental validations.
- This pipeline is designed for bacterial isolate WGS (single genome per sample), not metagenomic mixtures.
- Database versions (AMRFinder DB, PubMLST, PlasmidFinder DB) are recorded in the resource manifest and affect results.
