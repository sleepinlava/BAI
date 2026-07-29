# RNA-seq Gene Expression Quantification

Analysis type: `rnaseq_expression`

Standard RNA-seq pipeline: QC, alignment, quantification, differential expression, and optional offline GO/Reactome enrichment.

## Supported platforms and profiles

`illumina`

## Stages

- `qc_fastp` — tool `fastp`; category `qc`; required
- `alignment_star` — tool `star`; category `alignment`; required
- `quant_featurecounts` — tool `featurecounts`; category `expression`; required
- `build_matrix` — tool `build_count_matrix`; category `preprocessing`; required
- `de_deseq2` — tool `deseq2`; category `differential_expression`; required
- `enrichment_offline` — tool `rnaseq_enrichment`; category `enrichment`; optional

## Workflow dataflow

- `qc_fastp` → `alignment_star`
- `alignment_star` → `quant_featurecounts`
- `quant_featurecounts` → `build_matrix`
- `build_matrix` → `de_deseq2`
- `de_deseq2` → `enrichment_offline`

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

### `star` — STAR

Align RNA-seq reads to a STAR genome index.

Inputs/parameters:
- `genome_index` (required): `{"required": true, "type": "directory"}`
- `output_prefix` (required): `{"required": true, "type": "string"}`
- `read1` (required): `{"required": true, "type": "file"}`
- `read2` (required): `{"required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `bam`: `{"format": "bam", "type": "file"}`
Resources: `{"cpu": 8, "memory": "32GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_resource": {"hint": "Configure resources.genome_index to a prepared STAR index."}, "nonzero_exit": {"hint": "Inspect the STAR stderr log under provenance/step_logs."}, "tool_not_found": {"hint": "Install STAR in the abi-stats environment."}}`

### `featurecounts` — featureCounts

Count reads overlapping gene annotations from an aligned BAM file.

Inputs/parameters:
- `annotation_gtf` (required): `{"format": "gtf", "required": true, "type": "file"}`
- `bam` (required): `{"format": "bam", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `counts`: `{"format": "txt", "type": "file"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check that the alignment step produced the BAM path in the plan."}, "missing_resource": {"hint": "Configure resources.annotation_gtf to a valid GTF annotation."}, "parse_failed": {"hint": "Check the featureCounts output format before normalizing gene_expression.tsv."}, "tool_not_found": {"hint": "Install featureCounts in the abi-stats environment."}}`

### `build_count_matrix` — Build Count Matrix

Merge per-sample featureCounts outputs into a unified gene-level count matrix and sample metadata file for DESeq2.

Inputs/parameters:
- `count_matrix_script` (required): `{"description": "Path to build_count_matrix.py", "formats": ["py"], "required": true, "type": "file"}`
- `expression_dir` (required): `{"description": "Root directory containing per-sample featureCounts output subdirectories", "required": true, "type": "directory"}`
- `sample_sheet` (required): `{"description": "Sample sheet with sample_id, group, condition columns", "formats": ["tsv"], "required": true, "type": "file"}`
Outputs:
- `count_matrix`: `{"description": "Gene-level count matrix (genes \u00d7 samples)", "format": "tsv", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
- `sample_metadata`: `{"description": "Sample metadata for DESeq2", "format": "tsv", "type": "file"}`
Resources: `{"cpu": 1, "memory": "1GB", "walltime": "00:15:00"}`
Failure categories: `{"execution_error": {"hint": "Check that featureCounts output files have expected format (Geneid column + count column)."}, "missing_input": {"hint": "Verify that all upstream featureCounts steps completed successfully and *.featureCounts.txt files exist."}, "tool_not_found": {"hint": "Python 3 must be available in the rnaseq conda environment."}}`

### `deseq2` — DESeq2

Perform differential gene expression analysis using DESeq2 median-of-ratios normalisation and Wald test.

Inputs/parameters:
- `alpha` (optional): `{"default": 0.05, "type": "number"}`
- `comparison` (required): `{"required": true, "type": "string"}`
- `count_matrix` (required): `{"formats": ["tsv"], "required": true, "type": "file"}`
- `deseq2_script` (required): `{"formats": ["R"], "required": true, "type": "file"}`
- `design` (optional): `{"default": "~ condition", "description": "DESeq2 design formula evaluated against sample-metadata columns. It must include condition; paired experiments may use \"~ donor + condition\".", "type": "string"}`
- `sample_metadata` (required): `{"formats": ["tsv"], "required": true, "type": "file"}`
Outputs:
- `de_results`: `{"format": "tsv", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 1, "memory": "8GB", "walltime": "01:00:00"}`
Failure categories: `{"execution_error": {"hint": "DESeq2 execution failed. Check that sample_metadata groups match count_matrix columns and there are at least 2 replicates per group."}, "missing_input": {"hint": "One or both of count_matrix or sample_metadata files are missing. Verify featureCounts completed successfully."}, "tool_not_found": {"hint": "Rscript or DESeq2 package not available. Ensure R is installed and DESeq2 is installed (BiocManager::install('DESeq2'))."}}`

### `rnaseq_enrichment` — Offline RNA-seq Enrichment

Add GTF gene symbols and run offline GO/Reactome ORA and preranked GSEA.

Inputs/parameters:
- `annotation_gtf` (required): `{"formats": ["gtf"], "required": true, "type": "file"}`
- `de_results` (required): `{"formats": ["tsv"], "required": true, "type": "file"}`
- `enrichment_script` (required): `{"formats": ["py"], "required": true, "type": "file"}`
- `go_gaf` (required): `{"formats": ["gaf.gz"], "required": true, "type": "file"}`
- `go_obo` (required): `{"formats": ["obo"], "required": true, "type": "file"}`
- `reactome_gmt` (required): `{"formats": ["gmt"], "required": true, "type": "file"}`
Outputs:
- `annotated_de`: `{"format": "tsv", "type": "file"}`
- `enrichment_manifest`: `{"format": "json", "type": "file"}`
- `go_gsea`: `{"format": "tsv", "type": "file"}`
- `go_gsea_plot`: `{"format": "tsv", "type": "file"}`
- `go_ora`: `{"format": "tsv", "type": "file"}`
- `go_ora_plot`: `{"format": "tsv", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
- `reactome_gsea`: `{"format": "tsv", "type": "file"}`
- `reactome_gsea_plot`: `{"format": "tsv", "type": "file"}`
- `reactome_ora`: `{"format": "tsv", "type": "file"}`
- `reactome_ora_plot`: `{"format": "tsv", "type": "file"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"execution_error": {"hint": "Check gene identifiers, GTF gene_name attributes, and enrichment resources."}, "missing_input": {"hint": "Configure GRCh37.75 GTF, GO OBO/GAF, and Reactome GMT local paths."}, "tool_not_found": {"hint": "Install the locked rnaseq environment containing gseapy 1.3.0."}}`

## Output acceptance rules

- `qc_fastp.clean_read1`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "clean_read1", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}_R1.clean.fastq.gz", "stage": "qc_fastp", "type": "file"}`
- `qc_fastp.clean_read2`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "clean_read2", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}_R2.clean.fastq.gz", "stage": "qc_fastp", "type": "file"}`
- `qc_fastp.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}", "stage": "qc_fastp", "type": "directory"}`
- `alignment_star.bam`: `{"contract": {"min_size": "1B"}, "format": "bam", "output": "bam", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.Aligned.sortedByCoord.out.bam", "stage": "alignment_star", "type": "file"}`
- `alignment_star.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}", "stage": "alignment_star", "type": "directory"}`
- `quant_featurecounts.counts`: `{"contract": {"min_size": "100B"}, "format": "tsv", "output": "counts", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.featureCounts.txt", "stage": "quant_featurecounts", "type": "file"}`
- `quant_featurecounts.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}", "stage": "quant_featurecounts", "type": "directory"}`
- `build_matrix.count_matrix`: `{"contract": {"min_size": "100B"}, "format": "tsv", "output": "count_matrix", "path": "{outdir}/04_differential_expression/count_matrix.tsv", "stage": "build_matrix", "type": "file"}`
- `build_matrix.sample_metadata`: `{"contract": {"min_size": "20B"}, "format": "tsv", "output": "sample_metadata", "path": "{outdir}/04_differential_expression/sample_metadata.tsv", "stage": "build_matrix", "type": "file"}`
- `build_matrix.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/04_differential_expression", "stage": "build_matrix", "type": "directory"}`
- `de_deseq2.de_results`: `{"contract": {"min_size": "100B"}, "format": "tsv", "output": "de_results", "path": "{outdir}/04_differential_expression/deseq2_results.tsv", "stage": "de_deseq2", "type": "file"}`
- `de_deseq2.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/04_differential_expression", "stage": "de_deseq2", "type": "directory"}`
- `enrichment_offline.annotated_de`: `{"contract": {"min_size": "100B"}, "format": "tsv", "output": "annotated_de", "path": "{outdir}/05_enrichment/annotated_differential_expression.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.go_ora`: `{"contract": {"min_size": "1B"}, "format": "tsv", "output": "go_ora", "path": "{outdir}/05_enrichment/go_overrepresentation.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.reactome_ora`: `{"contract": {"min_size": "1B"}, "format": "tsv", "output": "reactome_ora", "path": "{outdir}/05_enrichment/reactome_overrepresentation.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.go_gsea`: `{"contract": {"min_size": "1B"}, "format": "tsv", "output": "go_gsea", "path": "{outdir}/05_enrichment/go_gsea.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.reactome_gsea`: `{"contract": {"min_size": "1B"}, "format": "tsv", "output": "reactome_gsea", "path": "{outdir}/05_enrichment/reactome_gsea.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.go_ora_plot`: `{"contract": {"min_size": "1B"}, "format": "tsv", "output": "go_ora_plot", "path": "{outdir}/05_enrichment/go_overrepresentation_plot.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.reactome_ora_plot`: `{"contract": {"min_size": "1B"}, "format": "tsv", "output": "reactome_ora_plot", "path": "{outdir}/05_enrichment/reactome_overrepresentation_plot.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.go_gsea_plot`: `{"contract": {"min_size": "1B"}, "format": "tsv", "output": "go_gsea_plot", "path": "{outdir}/05_enrichment/go_gsea_plot.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.reactome_gsea_plot`: `{"contract": {"min_size": "1B"}, "format": "tsv", "output": "reactome_gsea_plot", "path": "{outdir}/05_enrichment/reactome_gsea_plot.tsv", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.enrichment_manifest`: `{"contract": {"min_size": "20B"}, "format": "json", "output": "enrichment_manifest", "path": "{outdir}/05_enrichment/enrichment_manifest.json", "stage": "enrichment_offline", "type": "file"}`
- `enrichment_offline.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/05_enrichment", "stage": "enrichment_offline", "type": "directory"}`

## Standard tables

- `alignment_summary`: sample_id, tool, metric, value, unit, source_file
- `annotated_differential_expression`: gene_id, gene_symbol, baseMean, log2FoldChange, lfcSE, stat, pvalue, padj, comparison, tool, source_file
- `count_matrix`: gene_id, sample_id, count, tool, source_file
- `differential_expression`: gene_id, base_mean, log2_fold_change, lfc_se, stat, pvalue, padj, comparison, tool, source_file
- `gene_expression`: sample_id, gene_id, count, tpm, tool, source_file
- `go_gsea`: source, aspect, direction, term, plot_label, score, es, nes, pvalue, padj, fwer_pvalue, tag_fraction, gene_fraction, gene_symbols, method, tool, source_file
- `go_gsea_plot`: source, aspect, direction, term, plot_label, score, es, nes, pvalue, padj, fwer_pvalue, tag_fraction, gene_fraction, gene_symbols, method, tool, source_file
- `go_overrepresentation`: source, aspect, direction, term, plot_label, score, overlap_count, term_size, selected_size, background_size, fold_enrichment, pvalue, padj, gene_symbols, method, tool, source_file
- `go_overrepresentation_plot`: source, aspect, direction, term, plot_label, score, overlap_count, term_size, selected_size, background_size, fold_enrichment, pvalue, padj, gene_symbols, method, tool, source_file
- `normalized_expression`: sample_id, gene_id, normalized_count, normalization_method, tool, source_file
- `qc_summary`: sample_id, tool, metric, value, unit, source_file
- `reactome_gsea`: source, aspect, direction, term, plot_label, score, es, nes, pvalue, padj, fwer_pvalue, tag_fraction, gene_fraction, gene_symbols, method, tool, source_file
- `reactome_gsea_plot`: source, aspect, direction, term, plot_label, score, es, nes, pvalue, padj, fwer_pvalue, tag_fraction, gene_fraction, gene_symbols, method, tool, source_file
- `reactome_overrepresentation`: source, aspect, direction, term, plot_label, score, overlap_count, term_size, selected_size, background_size, fold_enrichment, pvalue, padj, gene_symbols, method, tool, source_file
- `reactome_overrepresentation_plot`: source, aspect, direction, term, plot_label, score, overlap_count, term_size, selected_size, background_size, fold_enrichment, pvalue, padj, gene_symbols, method, tool, source_file

## Stable error categories

`artifact_missing`, `contract_violation`, `duplicate_sample_id`, `empty_result`, `incomplete_pairs`, `internal_error`, `invalid_config`, `invalid_platform`, `invalid_sample_sheet`, `missing_database`, `missing_input`, `missing_resource`, `missing_sample_id`, `nonzero_exit`, `parse_failed`, `permission_required`, `runtime_not_supported`, `tool_not_found`, `unknown_analysis_type`

## Limitations

- RNA-seq measures steady-state transcript abundance, which does not always correlate with protein expression levels.
- Alignment rates depend on reference genome completeness and annotation quality; unannotated genes or novel transcripts are missed by featureCounts.
- DESeq2 normalisation assumes most genes are not differentially expressed; severe global shifts in expression violate this assumption.
- Differential expression p-values are not corrected for unmeasured confounders (batch effects, sample processing variation) unless explicitly modeled.
- Lowly expressed genes (mean count < 10) have inflated false discovery rates even after multiple testing correction.
- GO/Reactome enrichment is database-release dependent; pathways absent from the configured offline OBO/GAF/GMT snapshots cannot be detected.
- Gene-symbol mapping uses the configured GTF gene_name attribute; missing, duplicated, or retired symbols are excluded from enrichment after deterministic de-duplication.
- ORA depends on the significance threshold and measured-gene universe, while preranked GSEA depends on the chosen ranking statistic and permutation count; neither establishes pathway causality.
- Reference genome version, annotation version, and alignment index version all affect results; these are recorded in the resource manifest.
