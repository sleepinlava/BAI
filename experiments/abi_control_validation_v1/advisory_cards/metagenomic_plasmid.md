# Metagenomic Plasmid Analysis

Analysis type: `metagenomic_plasmid`

AutoPlasm adapter using the existing plasmid-analysis planner and executor.

## Supported platforms and profiles

`illumina`, `ont`, `pacbio_hifi`, `hybrid`, `assembly`

## Stages

- `long_reads_provided` — tool `internal`; category `basecalling`; optional
- `basecalling_dorado` — tool `dorado`; category `basecalling`; optional
- `long_read_bam_to_fastq` — tool `samtools_fastq`; category `basecalling`; optional
- `qc_fastp` — tool `fastp`; category `qc`; required
- `qc_fastqc_raw` — tool `fastqc`; category `qc`; optional
- `qc_fastqc_clean` — tool `fastqc`; category `qc`; optional
- `qc_multiqc_illumina` — tool `multiqc`; category `qc`; optional
- `qc_nanoplot` — tool `nanoplot`; category `qc`; required
- `qc_filtlong` — tool `filtlong`; category `qc`; required
- `qc_multiqc_ont` — tool `multiqc`; category `qc`; optional
- `qc_hifiadapterfilt` — tool `hifiadapterfilt`; category `qc`; required
- `qc_multiqc_hifi` — tool `multiqc`; category `qc`; optional
- `host_removal_bowtie2` — tool `bowtie2_host_removal`; category `host_removal`; optional
- `host_removal_minimap2_long` — tool `minimap2_host_removal`; category `host_removal`; optional
- `assembly_megahit` — tool `megahit`; category `assembly`; required
- `assembly_metaspades` — tool `metaspades`; category `assembly`; optional
- `assembly_metaflye` — tool `metaflye`; category `assembly`; required
- `assembly_hifiasm` — tool `hifiasm_meta`; category `assembly`; required
- `assembly_opera_ms` — tool `opera_ms`; category `assembly`; required
- `assembly_provided` — tool `internal`; category `assembly`; required
- `polishing_medaka` — tool `medaka`; category `polishing`; optional
- `assembly_qc_quast` — tool `quast`; category `assembly_qc`; required
- `contig_coverage_bowtie2` — tool `bowtie2`; category `contig_coverage`; required
- `contig_coverage_minimap2` — tool `minimap2`; category `contig_coverage`; required
- `contig_coverage_samtools` — tool `samtools`; category `contig_coverage`; required
- `contig_coverage_coverm` — tool `coverm`; category `contig_coverage`; required
- `plasmid_detect_genomad` — tool `genomad`; category `plasmid_detection`; required
- `plasmid_detect_plasme` — tool `plasme`; category `plasmid_detection`; optional
- `plasmid_detect_plasx` — tool `plasx`; category `plasmid_detection`; optional
- `plasmid_detect_platon` — tool `platon`; category `plasmid_detection`; optional
- `plasmid_detect_scapp` — tool `scapp`; category `plasmid_detection`; optional
- `plasmid_consensus` — tool `internal`; category `plasmid_consensus`; required
- `plasmid_structure` — tool `internal`; category `plasmid_detection`; required
- `plasmid_binning_plasmaag` — tool `plasmaag`; category `plasmid_binning`; optional
- `plasmid_binning_gplas2` — tool `gplas2`; category `plasmid_binning`; optional
- `plasmid_binning_mob_recon` — tool `mob_suite`; category `plasmid_binning`; optional
- `typing_plasmidfinder` — tool `plasmidfinder`; category `typing`; required
- `typing_mob_typer` — tool `mob_typer`; category `typing`; required
- `typing_copla` — tool `copla`; category `typing`; optional
- `host_prediction_metaphlan` — tool `metaphlan`; category `host_prediction`; optional
- `host_prediction_kraken2` — tool `kraken2`; category `host_prediction`; optional
- `host_prediction_plasmidhostfinder` — tool `plasmidhostfinder`; category `host_prediction`; optional
- `annotation_prodigal` — tool `prodigal`; category `annotation`; optional
- `annotation_bakta` — tool `bakta`; category `annotation`; required
- `annotation_amrfinderplus` — tool `amrfinderplus`; category `annotation`; required
- `annotation_abricate` — tool `abricate`; category `annotation`; optional
- `annotation_isescan` — tool `isescan`; category `annotation`; optional
- `annotation_integronfinder` — tool `integronfinder`; category `annotation`; optional
- `annotation_mob_suite` — tool `mob_suite`; category `annotation`; optional
- `mag_metabat2` — tool `metabat2`; category `mag_host_genomes`; optional
- `mag_checkm2` — tool `checkm2`; category `mag_host_genomes`; optional
- `mag_gtdbtk` — tool `gtdbtk`; category `mag_host_genomes`; optional
- `host_plasmid_link_coabundance` — tool `internal`; category `host_plasmid_linking`; optional
- `host_plasmid_link_sequence` — tool `internal`; category `host_plasmid_linking`; optional
- `host_plasmid_link_crispr` — tool `minced`; category `host_plasmid_linking`; optional
- `host_plasmid_link_longread` — tool `internal`; category `host_plasmid_linking`; optional
- `abundance_bowtie2` — tool `bowtie2`; category `abundance`; required
- `abundance_minimap2` — tool `minimap2`; category `abundance`; required
- `abundance_samtools` — tool `samtools`; category `abundance`; required
- `abundance_coverm` — tool `coverm`; category `abundance`; required
- `abundance_bowtie2_short` — tool `bowtie2`; category `abundance`; required
- `abundance_samtools_short` — tool `samtools`; category `abundance`; required
- `abundance_coverm_short` — tool `coverm`; category `abundance`; required
- `abundance_minimap2_long` — tool `minimap2`; category `abundance`; required
- `abundance_samtools_long` — tool `samtools`; category `abundance`; required
- `abundance_coverm_long` — tool `coverm`; category `abundance`; required
- `multisample_diversity` — tool `internal`; category `diversity`; optional
- `multisample_differential_abundance` — tool `internal`; category `statistics`; optional
- `multisample_differential_deseq2` — tool `deseq2_plasmid`; category `statistics`; optional
- `multisample_network_prepare` — tool `internal`; category `network`; optional
- `multisample_network_fastspar` — tool `fastspar`; category `network`; optional
- `plasmid_catalog_prepare` — tool `internal`; category `comparative_genomics`; required
- `comparative_mmseqs2` — tool `mmseqs2`; category `comparative_genomics`; optional
- `comparative_blast` — tool `blast`; category `comparative_genomics`; optional
- `comparative_mummer` — tool `mummer`; category `comparative_genomics`; optional
- `comparative_clinker` — tool `clinker`; category `comparative_genomics`; optional
- `visualization_clinker_gene_maps` — tool `clinker`; category `visualization`; optional
- `visualization_pycirclize` — tool `pycirclize`; category `visualization`; optional
- `visualization_network` — tool `pyvis`; category `visualization`; optional
- `assembly_hybridspades` — tool `hybridspades`; category `assembly`; optional
- `plasmid_binning_scapp` — tool `scapp`; category `plasmid_binning`; optional
- `plasmid_binning_recycler` — tool `recycler`; category `plasmid_binning`; optional
- `typing_conjscan` — tool `conjscan`; category `typing`; optional
- `typing_macsyfinder` — tool `macsyfinder`; category `typing`; optional
- `annotation_rgi` — tool `rgi`; category `annotation`; optional
- `annotation_eggnog_mapper` — tool `eggnog_mapper`; category `annotation`; optional
- `mag_concoct` — tool `concoct`; category `mag_host_genomes`; optional
- `mag_semibin` — tool `semibin`; category `mag_host_genomes`; optional
- `mag_das_tool` — tool `das_tool`; category `mag_host_genomes`; optional
- `visualization_dna_features` — tool `dna_features_viewer`; category `visualization`; optional
- `report_markdown` — tool `report_markdown`; category `report`; required

## Workflow dataflow

- `qc_fastp` → `qc_fastqc_clean`
- `qc_fastp` → `qc_multiqc_illumina`
- `qc_fastqc_raw` → `qc_multiqc_illumina`
- `qc_fastqc_clean` → `qc_multiqc_illumina`
- `long_reads_provided` → `qc_nanoplot`
- `basecalling_dorado` → `qc_nanoplot`
- `long_read_bam_to_fastq` → `qc_nanoplot`
- `long_reads_provided` → `qc_filtlong`
- `basecalling_dorado` → `qc_filtlong`
- `long_read_bam_to_fastq` → `qc_filtlong`
- `qc_nanoplot` → `qc_multiqc_ont`
- `qc_filtlong` → `qc_multiqc_ont`
- `long_reads_provided` → `qc_hifiadapterfilt`
- `long_read_bam_to_fastq` → `qc_hifiadapterfilt`
- `qc_hifiadapterfilt` → `qc_multiqc_hifi`
- `qc_fastp` → `host_removal_bowtie2`
- `qc_filtlong` → `host_removal_minimap2_long`
- `qc_hifiadapterfilt` → `host_removal_minimap2_long`
- `host_removal_bowtie2` → `assembly_megahit`
- `host_removal_bowtie2` → `assembly_metaspades`
- `host_removal_minimap2_long` → `assembly_metaflye`
- `host_removal_minimap2_long` → `assembly_hifiasm`
- `host_removal_bowtie2` → `assembly_opera_ms`
- `host_removal_minimap2_long` → `assembly_opera_ms`
- `assembly_metaflye` → `polishing_medaka`
- `assembly_megahit` → `assembly_qc_quast`
- `assembly_metaspades` → `assembly_qc_quast`
- `assembly_metaflye` → `assembly_qc_quast`
- `assembly_hifiasm` → `assembly_qc_quast`
- `assembly_opera_ms` → `assembly_qc_quast`
- `assembly_provided` → `assembly_qc_quast`
- `polishing_medaka` → `assembly_qc_quast`
- `assembly_megahit` → `contig_coverage_bowtie2`
- `assembly_metaspades` → `contig_coverage_bowtie2`
- `assembly_opera_ms` → `contig_coverage_bowtie2`
- `assembly_provided` → `contig_coverage_bowtie2`
- `assembly_metaflye` → `contig_coverage_minimap2`
- `assembly_hifiasm` → `contig_coverage_minimap2`
- `assembly_opera_ms` → `contig_coverage_minimap2`
- `polishing_medaka` → `contig_coverage_minimap2`
- `contig_coverage_bowtie2` → `contig_coverage_samtools`
- `contig_coverage_minimap2` → `contig_coverage_samtools`
- `contig_coverage_samtools` → `contig_coverage_coverm`
- `assembly_megahit` → `plasmid_detect_genomad`
- `assembly_metaspades` → `plasmid_detect_genomad`
- `assembly_metaflye` → `plasmid_detect_genomad`
- `assembly_hifiasm` → `plasmid_detect_genomad`
- `assembly_opera_ms` → `plasmid_detect_genomad`
- `assembly_provided` → `plasmid_detect_genomad`
- `polishing_medaka` → `plasmid_detect_genomad`
- `assembly_qc_quast` → `plasmid_detect_plasme`
- `assembly_qc_quast` → `plasmid_detect_plasx`
- `assembly_qc_quast` → `plasmid_detect_platon`
- `assembly_metaspades` → `plasmid_detect_scapp`
- `host_removal_bowtie2` → `plasmid_detect_scapp`
- `plasmid_detect_genomad` → `plasmid_consensus`
- `plasmid_detect_plasme` → `plasmid_consensus`
- `plasmid_detect_plasx` → `plasmid_consensus`
- `plasmid_detect_platon` → `plasmid_consensus`
- `plasmid_detect_scapp` → `plasmid_consensus`
- `plasmid_consensus` → `plasmid_structure`
- `plasmid_consensus` → `plasmid_binning_plasmaag`
- `plasmid_consensus` → `plasmid_binning_gplas2`
- `plasmid_consensus` → `plasmid_binning_mob_recon`
- `plasmid_consensus` → `typing_plasmidfinder`
- `plasmid_consensus` → `typing_mob_typer`
- `plasmid_consensus` → `typing_copla`
- `host_removal_bowtie2` → `host_prediction_metaphlan`
- `host_removal_minimap2_long` → `host_prediction_metaphlan`
- `host_removal_bowtie2` → `host_prediction_kraken2`
- `plasmid_consensus` → `host_prediction_plasmidhostfinder`
- `plasmid_consensus` → `annotation_prodigal`
- `plasmid_consensus` → `annotation_bakta`
- `plasmid_consensus` → `annotation_amrfinderplus`
- `plasmid_consensus` → `annotation_abricate`
- `plasmid_consensus` → `annotation_isescan`
- `plasmid_consensus` → `annotation_integronfinder`
- `plasmid_consensus` → `annotation_mob_suite`
- `contig_coverage_samtools` → `mag_metabat2`
- `mag_metabat2` → `mag_checkm2`
- `mag_checkm2` → `mag_gtdbtk`
- `plasmid_consensus` → `host_plasmid_link_coabundance`
- `contig_coverage_coverm` → `host_plasmid_link_coabundance`
- `host_prediction_metaphlan` → `host_plasmid_link_coabundance`
- `plasmid_consensus` → `host_plasmid_link_sequence`
- `mag_gtdbtk` → `host_plasmid_link_sequence`
- `mag_gtdbtk` → `host_plasmid_link_crispr`
- `plasmid_consensus` → `host_plasmid_link_longread`
- `contig_coverage_coverm` → `host_plasmid_link_longread`
- `plasmid_consensus` → `abundance_bowtie2`
- `host_removal_bowtie2` → `abundance_bowtie2`
- `plasmid_consensus` → `abundance_minimap2`
- `host_removal_minimap2_long` → `abundance_minimap2`
- `abundance_bowtie2` → `abundance_samtools`
- `abundance_minimap2` → `abundance_samtools`
- `abundance_samtools` → `abundance_coverm`
- `plasmid_consensus` → `abundance_bowtie2_short`
- `host_removal_bowtie2` → `abundance_bowtie2_short`
- `abundance_bowtie2_short` → `abundance_samtools_short`
- `abundance_samtools_short` → `abundance_coverm_short`
- `plasmid_consensus` → `abundance_minimap2_long`
- `host_removal_minimap2_long` → `abundance_minimap2_long`
- `abundance_minimap2_long` → `abundance_samtools_long`
- `abundance_samtools_long` → `abundance_coverm_long`
- `contig_coverage_coverm` → `multisample_diversity`
- `contig_coverage_coverm` → `multisample_differential_abundance`
- `abundance_coverm` → `multisample_differential_deseq2`
- `abundance_coverm` → `multisample_network_prepare`
- `multisample_network_prepare` → `multisample_network_fastspar`
- `plasmid_consensus` → `plasmid_catalog_prepare`
- `plasmid_catalog_prepare` → `comparative_mmseqs2`
- `plasmid_consensus` → `comparative_blast`
- `plasmid_consensus` → `comparative_mummer`
- `annotation_bakta` → `comparative_clinker`
- `annotation_bakta` → `visualization_clinker_gene_maps`
- `comparative_clinker` → `visualization_clinker_gene_maps`
- `annotation_bakta` → `visualization_pycirclize`
- `typing_plasmidfinder` → `visualization_pycirclize`
- `typing_mob_typer` → `visualization_pycirclize`
- `host_plasmid_link_coabundance` → `visualization_network`
- `host_plasmid_link_sequence` → `visualization_network`
- `multisample_network_fastspar` → `visualization_network`
- `host_removal_bowtie2` → `assembly_hybridspades`
- `host_removal_minimap2_long` → `assembly_hybridspades`
- `plasmid_consensus` → `plasmid_binning_scapp`
- `plasmid_consensus` → `plasmid_binning_recycler`
- `contig_coverage_samtools` → `plasmid_binning_recycler`
- `plasmid_consensus` → `typing_conjscan`
- `plasmid_consensus` → `typing_macsyfinder`
- `plasmid_consensus` → `annotation_rgi`
- `plasmid_consensus` → `annotation_eggnog_mapper`
- `contig_coverage_coverm` → `mag_concoct`
- `contig_coverage_samtools` → `mag_semibin`
- `mag_metabat2` → `mag_das_tool`
- `mag_concoct` → `mag_das_tool`
- `annotation_bakta` → `visualization_dna_features`
- `plasmid_consensus` → `report_markdown`
- `plasmid_structure` → `report_markdown`
- `plasmid_binning_plasmaag` → `report_markdown`
- `plasmid_binning_gplas2` → `report_markdown`
- `plasmid_binning_mob_recon` → `report_markdown`
- `typing_plasmidfinder` → `report_markdown`
- `typing_mob_typer` → `report_markdown`
- `typing_copla` → `report_markdown`
- `annotation_bakta` → `report_markdown`
- `annotation_amrfinderplus` → `report_markdown`
- `annotation_abricate` → `report_markdown`
- `annotation_isescan` → `report_markdown`
- `annotation_integronfinder` → `report_markdown`
- `host_prediction_metaphlan` → `report_markdown`
- `host_prediction_kraken2` → `report_markdown`
- `host_plasmid_link_coabundance` → `report_markdown`
- `host_plasmid_link_sequence` → `report_markdown`
- `host_plasmid_link_crispr` → `report_markdown`
- `host_plasmid_link_longread` → `report_markdown`
- `contig_coverage_coverm` → `report_markdown`
- `multisample_diversity` → `report_markdown`
- `multisample_differential_abundance` → `report_markdown`
- `multisample_differential_deseq2` → `report_markdown`
- `multisample_network_fastspar` → `report_markdown`
- `comparative_mmseqs2` → `report_markdown`
- `comparative_blast` → `report_markdown`
- `comparative_mummer` → `report_markdown`
- `comparative_clinker` → `report_markdown`
- `visualization_clinker_gene_maps` → `report_markdown`
- `visualization_pycirclize` → `report_markdown`
- `visualization_network` → `report_markdown`
- `assembly_qc_quast` → `report_markdown`
- `contig_coverage_coverm` → `report_markdown`

## Tools and contracts

### `dorado` — Dorado

Basecall ONT POD5 signal into FASTQ before downstream read analysis.

Inputs/parameters:
- `pod5` (required): `{"required": true, "type": "path"}`
Outputs:
- `long_reads`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "24:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check the POD5 file or directory path."}, "nonzero_exit": {"hint": "Inspect stderr and verify the selected model is available."}, "tool_not_found": {"hint": "Install Dorado in the autoplasm-qc environment."}}`

### `samtools_fastq` — samtools fastq

Convert a supplied long-read BAM into FASTQ for the read workflow.

Inputs/parameters:
- `bam` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `long_reads`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check the BAM input path."}, "nonzero_exit": {"hint": "Validate the BAM with samtools quickcheck and inspect stderr."}, "tool_not_found": {"hint": "Install samtools in the autoplasm-abundance environment."}}`

### `fastp` — fastp

Trim and quality-control paired-end metagenomic reads.

Inputs/parameters:
- `read1` (required): `{"required": true, "type": "file"}`
- `read2` (required): `{"required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `clean_read1`: `{"format": "fastq.gz", "type": "file"}`
- `clean_read2`: `{"format": "fastq.gz", "type": "file"}`
- `html_report`: `{"format": "html", "type": "file"}`
- `json_report`: `{"format": "json", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check sample sheet read1/read2 paths."}, "nonzero_exit": {"hint": "Read the fastp stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install fastp in the autoplasm-qc environment."}}`

### `fastqc` — FastQC

Generate read-level QC summaries for paired short reads.

Inputs/parameters:
- `read1` (required): `{"required": true, "type": "file"}`
- `read2` (required): `{"required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check paired FASTQ paths before running FastQC."}, "parse_failed": {"hint": "Check the FastQC output directory layout."}, "tool_not_found": {"hint": "Install fastqc in the autoplasm-qc environment."}}`

### `multiqc` — MultiQC

Aggregate QC outputs into a single report directory.

Inputs/parameters:
- `multiqc_filename` (required): `{"required": true, "type": "string"}`
- `output_dir` (required): `{"required": true, "type": "directory"}`
- `project_outdir` (required): `{"required": true, "type": "directory"}`
Outputs:
- `multiqc_report`: `{"format": "html", "type": "file"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Run read QC before MultiQC aggregation."}, "tool_not_found": {"hint": "Install multiqc in the autoplasm-qc environment."}}`

### `nanoplot` — NanoPlot

Run NanoPlot as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `long_reads` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install NanoPlot in the autoplasm-qc environment."}}`

### `filtlong` — Filtlong

Run Filtlong as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `long_reads` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install filtlong in the autoplasm-qc environment."}}`

### `hifiadapterfilt` — HiFiAdapterFilt

Run HiFiAdapterFilt as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `long_reads` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install hifiadapterfilt.sh in the autoplasm-qc environment."}}`

### `megahit` — MEGAHIT

Assemble paired-end metagenomic reads into contigs.

Inputs/parameters:
- `memory_bytes` (optional): `{"default": 96636764160, "minimum": 1, "type": "integer"}`
- `read1` (required): `{"required": true, "type": "file"}`
- `read2` (required): `{"required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `assembly`: `{"format": "fasta", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 16, "memory": "64GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check cleaned read paths from the QC step."}, "nonzero_exit": {"hint": "Inspect the MEGAHIT stderr log and assembly output directory."}, "tool_not_found": {"hint": "Install megahit in the autoplasm-assembly environment."}}`

### `metaspades` — metaSPAdes

Run metaSPAdes as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `read1` (required): `{"required": true, "type": "path"}`
- `read2` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 16, "memory": "64GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install metaspades.py in the autoplasm-assembly environment."}}`

### `metaflye` — metaFlye

Run metaFlye as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `long_reads` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 16, "memory": "64GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install flye in the autoplasm-assembly environment."}}`

### `hifiasm_meta` — hifiasm

Run hifiasm as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `long_reads` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 16, "memory": "64GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install hifiasm in the autoplasm-assembly environment."}}`

### `opera_ms` — OPERA-MS

Run OPERA-MS as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `long_reads` (required): `{"required": true, "type": "path"}`
- `read1` (required): `{"required": true, "type": "path"}`
- `read2` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 16, "memory": "64GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install OPERA-MS.pl in the autoplasm-assembly environment."}}`

### `quast` — metaQUAST

Summarize metagenomic assembly quality metrics.

Inputs/parameters:
- `assembly` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check that the assembly step wrote the expected FASTA."}, "tool_not_found": {"hint": "Install metaquast.py in the autoplasm-assembly environment."}}`

### `medaka` — Medaka

Optionally polish an ONT metaFlye assembly with the corresponding reads.

Inputs/parameters:
- `assembly` (required): `{"required": true, "type": "path"}`
- `long_reads` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check the filtered ONT reads and metaFlye assembly paths."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs and verify model compatibility."}, "tool_not_found": {"hint": "Install medaka in the autoplasm-assembly environment."}}`

### `genomad` — geNomad

Detect plasmid-like sequences from assembled contigs.

Inputs/parameters:
- `assembly` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `database` (required): `{"required": true, "type": "directory"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
- `plasmid_summary`: `{"format": "tsv", "type": "file"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_database": {"hint": "Configure the geNomad database resource path."}, "missing_input": {"hint": "Check assembly FASTA path."}, "parse_failed": {"hint": "Check geNomad plasmid summary TSV output."}}`

### `plasme` — PLASMe

Run PLASMe as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `assembly` (required): `{"required": true, "type": "path"}`
- `database` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install PLASMe.py in the autoplasm-plasmid-detect environment."}}`

### `plasx` — PlasX

Run PlasX as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `annotations` (required): `{"required": true, "type": "path"}`
- `gene_calls` (required): `{"required": true, "type": "path"}`
- `model` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install plasx in the autoplasm-plasmid-detect environment."}}`

### `plasmidfinder` — PlasmidFinder

Run PlasmidFinder as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `assembly` (required): `{"required": true, "type": "path"}`
- `database` (required): `{"required": true, "type": "path"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install the plasmidfinder Python module in the autoplasm-annotation environment."}}`

### `plasmaag` — PlasMAAG

Run PlasMAAG as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `reads_contigs_table` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install plasmaag in the autoplasm-plasmid-binning environment."}}`

### `gplas2` — gplas2

Run gplas2 as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `assembly_graph` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `plasmid_predictions`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install gplas2 in the autoplasm-plasmid-binning environment."}}`

### `mob_typer` — MOB-typer

Run MOB-typer as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `database` (required): `{"required": true, "type": "directory"}`
- `plasmid_contigs` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install mob_typer in the autoplasm-annotation environment."}}`

### `copla` — COPLA

Run COPLA as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `plasmid_contigs` (required): `{"required": true, "type": "path"}`
- `refgraph` (required): `{"required": true, "type": "path"}`
- `reflist` (required): `{"required": true, "type": "path"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install copla in the autoplasm-annotation environment."}}`

### `plasmidhostfinder` — PlasmidHostFinder

Run PlasmidHostFinder as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `database` (required): `{"required": true, "type": "path"}`
- `level` (required): `{"required": true, "type": "path"}`
- `plasmid_contigs` (required): `{"required": true, "type": "path"}`
- `threshold` (required): `{"required": true, "type": "path"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "32GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install plasmidhostfinder.py in the autoplasm-annotation environment."}}`

### `prodigal` — Prodigal

Gene calling on plasmid contigs — predicts protein-coding genes.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `faa`: `{"format": "faa", "type": "file"}`
- `ffn`: `{"format": "ffn", "type": "file"}`
- `gff`: `{"format": "gff", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs path from plasmid consensus step."}, "nonzero_exit": {"hint": "Inspect Prodigal stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install prodigal in the autoplasm-annotation environment."}}`

### `bakta` — Bakta

Annotate predicted plasmid contigs.

Inputs/parameters:
- `database` (required): `{"required": true, "type": "directory"}`
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_database": {"hint": "Configure the Bakta database path."}, "missing_input": {"hint": "Check plasmid_contigs output from plasmid detection."}, "parse_failed": {"hint": "Check Bakta TSV outputs."}}`

### `abricate` — ABRicate

Screen plasmid contigs against curated gene databases.

Inputs/parameters:
- `abricate_db` (required): `{"required": true, "type": "string"}`
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `annotations_tsv`: `{"format": "tsv", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "parse_failed": {"hint": "Check ABRicate TSV output."}, "tool_not_found": {"hint": "Install abricate in the autoplasm-annotation environment."}}`

### `amrfinderplus` — AMRFinderPlus

Detect antimicrobial resistance features in plasmid contigs.

Inputs/parameters:
- `database` (required): `{"required": true, "type": "string"}`
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `amrfinder_tsv`: `{"format": "tsv", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "tool_not_found": {"hint": "Install amrfinder in the autoplasm-annotation environment."}}`

### `mob_suite` — MOB-suite

Run MOB-suite as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `database` (required): `{"required": true, "type": "path"}`
- `plasmid_contigs` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install mob_recon in the autoplasm-annotation environment."}}`

### `isescan` — ISEScan

Detect insertion sequences in plasmid contigs.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "tool_not_found": {"hint": "Install isescan.py in the autoplasm-annotation environment."}}`

### `integronfinder` — IntegronFinder

Detect integrons and related mobile elements in plasmid contigs.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "tool_not_found": {"hint": "Install integron_finder in the autoplasm-integronfinder environment."}}`

### `bowtie2_host_removal` — Bowtie2 host removal

Remove host-mapping Illumina read pairs when a host reference is supplied.

Inputs/parameters:
- `host_reference` (required): `{"required": true, "type": "path"}`
- `read1` (required): `{"required": true, "type": "path"}`
- `read2` (required): `{"required": true, "type": "path"}`
Outputs:
- `clean_read1`: `{"type": "path"}`
- `clean_read2`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check paired reads and the host reference FASTA."}, "nonzero_exit": {"hint": "Inspect stderr and the generated host index files."}, "tool_not_found": {"hint": "Install Bowtie2 in the autoplasm-abundance environment."}}`

### `minimap2_host_removal` — minimap2 host removal

Retain unmapped ONT or HiFi reads when a host reference is supplied.

Inputs/parameters:
- `host_reference` (required): `{"required": true, "type": "path"}`
- `long_reads` (required): `{"required": true, "type": "path"}`
Outputs:
- `clean_long_reads`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check long reads and the host reference FASTA."}, "nonzero_exit": {"hint": "Inspect stderr and validate the host reference."}, "tool_not_found": {"hint": "Install minimap2 and samtools in the autoplasm-abundance environment."}}`

### `bowtie2` — bowtie2

Build a plasmid contig index and align paired reads for abundance estimation.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `read1` (required): `{"required": true, "type": "file"}`
- `read2` (required): `{"required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `alignment`: `{"format": "sam", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs and paired read paths."}, "tool_not_found": {"hint": "Install bowtie2 in the autoplasm-abundance environment."}}`

### `minimap2` — minimap2

Run minimap2 as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `long_reads` (required): `{"required": true, "type": "path"}`
- `minimap2_preset` (required): `{"required": true, "type": "path"}`
- `plasmid_contigs` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `alignment`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install minimap2 in the autoplasm-abundance environment."}}`

### `samtools` — samtools

Sort read alignments before abundance quantification.

Inputs/parameters:
- `alignment` (required): `{"format": "sam", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `bam`: `{"format": "bam", "type": "file"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check bowtie2/minimap2 alignment output."}, "tool_not_found": {"hint": "Install samtools in the autoplasm-abundance environment."}}`

### `coverm` — CoverM

Estimate coverage and abundance for plasmid contigs.

Inputs/parameters:
- `bam` (required): `{"format": "bam", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `abundance`: `{"format": "tsv", "type": "file"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check sorted BAM path."}, "parse_failed": {"hint": "Check CoverM TSV output."}, "tool_not_found": {"hint": "Install coverm in the autoplasm-abundance environment."}}`

### `kraken2` — Kraken2

Run Kraken2 as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `database` (required): `{"required": true, "type": "path"}`
- `read1` (required): `{"required": true, "type": "path"}`
- `read2` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "32GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install kraken2 in the stats environment."}}`

### `metaphlan` — MetaPhlAn

Estimate source community taxonomy from read inputs.

Inputs/parameters:
- `database` (required): `{"required": true, "type": "directory"}`
- `metaphlan_input` (required): `{"required": true, "type": "string"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
- `profile`: `{"format": "tsv", "type": "file"}`
Resources: `{"cpu": 8, "memory": "32GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_database": {"hint": "Configure the MetaPhlAn database directory."}, "tool_not_found": {"hint": "Install metaphlan in the stats environment."}}`

### `fastspar` — FastSpar

Infer sparse correlation networks from plasmid abundance tables.

Inputs/parameters:
- `abundance_table` (optional): `{"format": "tsv", "required": false, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `correlation`: `{"format": "tsv", "type": "file"}`
- `covariance`: `{"format": "tsv", "type": "file"}`
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check the plasmid abundance table path."}, "tool_not_found": {"hint": "Install fastspar in the stats environment."}}`

### `deseq2_plasmid` — DESeq2 plasmid differential abundance

Test plasmid count differences between adequately replicated sample groups.

Inputs/parameters:
- `abundance_table` (required): `{"required": true, "type": "path"}`
- `sample_metadata` (required): `{"required": true, "type": "path"}`
Outputs:
- `differential_plasmids`: `{"type": "path"}`
Resources: `{"cpu": 4, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_abundance.tsv and the sample-sheet group column."}, "nonzero_exit": {"hint": "Inspect stderr and verify integer-like raw counts and group replication."}, "tool_not_found": {"hint": "Install R, DESeq2, and Rscript in the stats environment."}}`

### `blast` — BLAST+

Run BLAST+ as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `database` (required): `{"required": true, "type": "path"}`
- `plasmid_contigs` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install blastn in the autoplasm-annotation environment."}}`

### `mmseqs2` — MMseqs2

Run MMseqs2 as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `plasmid_contigs` (required): `{"required": true, "type": "path"}`
- `threads` (required): `{"required": true, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install mmseqs in the autoplasm-annotation environment."}}`

### `mummer` — MUMmer/nucmer

Run MUMmer/nucmer as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `plasmid_contigs` (required): `{"required": true, "type": "path"}`
- `reference_plasmids` (required): `{"required": true, "type": "path"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install nucmer in the autoplasm-annotation environment."}}`

### `clinker` — clinker

Run clinker as registered by the metagenomic_plasmid plugin.

Inputs/parameters:
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `genbank_files`: `{"type": "path"}`
- `output_dir`: `{"type": "path"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check planned input paths and prerequisite upstream steps."}, "nonzero_exit": {"hint": "Inspect provenance/step_logs for stderr and rerun after fixing inputs or environment."}, "tool_not_found": {"hint": "Install clinker in the autoplasm-visualization environment."}}`

### `report_markdown` — AutoPlasm Markdown report

Render the AutoPlasm markdown report from ABI result artifacts.

Inputs/parameters:
- `project_outdir` (required): `{"required": true, "type": "directory"}`
Outputs:
- `report_md`: `{"format": "markdown", "type": "file"}`
Resources: `{"cpu": 1, "memory": "2GB", "walltime": "00:30:00"}`
Failure categories: `{"artifact_missing": {"hint": "Run plan or dry-run before report generation."}, "nonzero_exit": {"hint": "Check report inputs under tables/ and provenance/."}}`

### `metabat2` — MetaBAT2

Metagenomic binning of assembled contigs using coverage and composition.

Inputs/parameters:
- `assembly` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `bam` (required): `{"format": "bam", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check assembly FASTA and sorted BAM paths."}, "nonzero_exit": {"hint": "Inspect MetaBAT2 stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install metabat2 in the stats environment."}}`

### `checkm2` — CheckM2

Quality assessment of metagenomic bins (completeness, contamination).

Inputs/parameters:
- `mag_bins` (required): `{"required": true, "type": "directory"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check MAG bins directory path."}, "nonzero_exit": {"hint": "Inspect CheckM2 log in provenance/step_logs."}, "tool_not_found": {"hint": "Install CheckM2 in the isolated autoplasm-checkm2 environment."}}`

### `gtdbtk` — GTDB-Tk

Taxonomic classification of MAGs against the GTDB reference tree.

Inputs/parameters:
- `mag_bins` (required): `{"required": true, "type": "directory"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_database": {"hint": "Configure GTDB-Tk database with 'gtdbtk db download'."}, "missing_input": {"hint": "Check MAG bins directory path."}, "nonzero_exit": {"hint": "Inspect GTDB-Tk log in provenance/step_logs."}, "tool_not_found": {"hint": "Install gtdbtk in the stats environment."}}`

### `minced` — MinCED

CRISPR spacer discovery for host-plasmid linkage evidence.

Inputs/parameters:
- `host_genomes` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check host genome and plasmid contig paths."}, "nonzero_exit": {"hint": "Inspect MinCED stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install minced in the autoplasm-annotation environment."}}`

### `pycirclize` — pyCirclize

Generate circular plasmid maps from annotations and typing data.

Inputs/parameters:
- `annotations` (required): `{"format": "tsv", "required": true, "type": "file"}`
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `typing` (required): `{"format": "tsv", "required": true, "type": "file"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 2, "memory": "4GB", "walltime": "00:30:00"}`
Failure categories: `{"missing_input": {"hint": "Check annotations TSV, typing TSV, and plasmid contig paths."}, "nonzero_exit": {"hint": "Inspect Python stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install pycirclize in the autoplasm-visualization environment."}}`

### `pyvis` — pyvis

Generate interactive host-plasmid interaction network graphs.

Inputs/parameters:
- `host_plasmid_links` (required): `{"format": "tsv", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 2, "memory": "4GB", "walltime": "00:30:00"}`
Failure categories: `{"missing_input": {"hint": "Check host-plasmid links TSV path."}, "nonzero_exit": {"hint": "Inspect Python stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install pyvis in the autoplasm-visualization environment."}}`

### `platon` — Platon

Plasmid contig detection and typing from assembled contigs.

Inputs/parameters:
- `assembly` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `database` (optional): `{"required": false, "type": "directory"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_database": {"hint": "Configure Platon database path in resources."}, "missing_input": {"hint": "Check assembly FASTA path."}, "nonzero_exit": {"hint": "Inspect Platon stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install platon in the autoplasm-plasmid-detect environment."}}`

### `scapp` — SCAPP

Plasmid detection from the SPAdes assembly graph using SCAPP confident cycles.

Inputs/parameters:
- `assembly_graph` (required): `{"format": "fastg", "required": true, "type": "file"}`
- `max_k` (optional): `{"minimum": 1, "type": "integer"}`
- `read1` (required): `{"format": "fastq.gz", "required": true, "type": "file"}`
- `read2` (required): `{"format": "fastq.gz", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `scapp_predictions`: `{"format": "fasta", "type": "file"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check the SPAdes FASTG assembly graph and paired-end read paths."}, "nonzero_exit": {"hint": "Inspect SCAPP stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install SCAPP in the autoplasm-scapp environment."}}`

### `recycler` — Recycler

Plasmid reconstruction from assembly graph cycles.

Inputs/parameters:
- `assembly_graph` (required): `{"format": "gfa", "required": true, "type": "file"}`
- `bam` (required): `{"format": "bam", "required": true, "type": "file"}`
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check assembly graph, plasmid contigs, and BAM paths."}, "nonzero_exit": {"hint": "Inspect Recycler stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install Recycler in the autoplasm-plasmid-binning environment."}}`

### `conjscan` — CONJscan

Detection of conjugative systems in plasmid sequences via MacSyFinder.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "nonzero_exit": {"hint": "Inspect MacSyFinder stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install MacSyFinder + CONJscan in the autoplasm-annotation environment."}}`

### `macsyfinder` — MacSyFinder

Macromolecular system detection in plasmid sequences.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "8GB", "walltime": "02:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "nonzero_exit": {"hint": "Inspect MacSyFinder stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install MacSyFinder in the autoplasm-annotation environment."}}`

### `rgi` — RGI/CARD

Resistance Gene Identifier against the CARD database.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_database": {"hint": "Download CARD database with 'rgi load --card_json'."}, "missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "nonzero_exit": {"hint": "Inspect RGI stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install rgi in the autoplasm-rgi environment."}}`

### `eggnog_mapper` — eggNOG-mapper

Functional annotation of plasmid CDS against eggNOG orthologous groups.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 8, "memory": "16GB", "walltime": "04:00:00"}`
Failure categories: `{"missing_database": {"hint": "Download eggNOG database with 'download_eggnog_data.py'."}, "missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "nonzero_exit": {"hint": "Inspect eggNOG-mapper stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install eggnog-mapper in the autoplasm-annotation environment."}}`

### `concoct` — CONCOCT

Composition and coverage based metagenomic binning.

Inputs/parameters:
- `abundance` (required): `{"format": "tsv", "required": true, "type": "file"}`
- `assembly` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check assembly FASTA and coverage TSV paths."}, "nonzero_exit": {"hint": "Inspect CONCOCT stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install concoct in the stats environment."}}`

### `semibin` — SemiBin

Deep learning-based metagenomic binning with semi-supervised learning.

Inputs/parameters:
- `assembly` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `bam` (required): `{"format": "bam", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check assembly FASTA and BAM paths."}, "nonzero_exit": {"hint": "Inspect SemiBin stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install SemiBin in the stats environment."}}`

### `das_tool` — DAS Tool

Meta-binner aggregator: selects optimal bins from multiple binning tools.

Inputs/parameters:
- `assembly` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 4, "memory": "4GB", "walltime": "01:00:00"}`
Failure categories: `{"missing_input": {"hint": "Ensure MetaBAT2 and CONCOCT have completed."}, "nonzero_exit": {"hint": "Inspect DAS Tool stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install das_tool in the stats environment."}}`

### `hybridspades` — hybridSPAdes

Hybrid short + long read metagenomic assembly via SPAdes meta mode.

Inputs/parameters:
- `long_reads` (required): `{"format": "fastq", "required": true, "type": "file"}`
- `read1` (required): `{"format": "fastq", "required": true, "type": "file"}`
- `read2` (required): `{"format": "fastq", "required": true, "type": "file"}`
- `threads` (optional): `{"minimum": 1, "type": "integer"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 16, "memory": "64GB", "walltime": "08:00:00"}`
Failure categories: `{"missing_input": {"hint": "Check read1, read2, and long_reads paths."}, "nonzero_exit": {"hint": "Inspect SPAdes log in provenance/step_logs."}, "tool_not_found": {"hint": "Install spades in the autoplasm-assembly environment."}}`

### `dna_features_viewer` — dna-features-viewer

Generate linear DNA feature maps from annotated plasmid contigs.

Inputs/parameters:
- `plasmid_contigs` (required): `{"format": "fasta", "required": true, "type": "file"}`
- `sample_id` (required): `{"required": true, "type": "string"}`
Outputs:
- `output_dir`: `{"type": "directory"}`
Resources: `{"cpu": 2, "memory": "4GB", "walltime": "00:30:00"}`
Failure categories: `{"missing_input": {"hint": "Check plasmid_contigs FASTA path."}, "nonzero_exit": {"hint": "Inspect Python stderr log in provenance/step_logs."}, "tool_not_found": {"hint": "Install dna_features_viewer + biopython in the autoplasm-visualization environment."}}`

## Output acceptance rules

- `long_reads_provided.long_reads`: `{"contract": {"exempt": true, "reason": "Passthrough of user-provided long reads; no new file is produced"}, "format": "fastq", "output": "long_reads", "path": null, "stage": "long_reads_provided", "type": "file"}`
- `basecalling_dorado.long_reads`: `{"contract": {"extensions": [".fastq"], "file_exists": true, "min_size": "1KB"}, "format": "fastq", "output": "long_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.dorado.fastq", "stage": "basecalling_dorado", "type": "file"}`
- `long_read_bam_to_fastq.long_reads`: `{"contract": {"extensions": [".fastq"], "file_exists": true, "min_size": "1KB"}, "format": "fastq", "output": "long_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.bam.fastq", "stage": "long_read_bam_to_fastq", "type": "file"}`
- `qc_fastp.clean_read1`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "clean_read1", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}_R1.clean.fastq.gz", "stage": "qc_fastp", "type": "file"}`
- `qc_fastp.clean_read2`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "clean_read2", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}_R2.clean.fastq.gz", "stage": "qc_fastp", "type": "file"}`
- `qc_fastp.html_report`: `{"contract": {}, "format": "html", "output": "html_report", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.fastp.html", "stage": "qc_fastp", "type": "file"}`
- `qc_fastp.json_report`: `{"contract": {"required_keys": ["summary"], "schema": {"summary.after_filtering.total_reads": {"min": 0, "type": "integer"}, "summary.before_filtering.total_reads": {"min": 0, "type": "integer"}}}, "format": "json", "output": "json_report", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.fastp.json", "stage": "qc_fastp", "type": "file"}`
- `qc_fastqc_raw.output_dir`: `{"contract": {"min_size": 1024}, "format": null, "output": "output_dir", "path": null, "stage": "qc_fastqc_raw", "type": "directory"}`
- `qc_fastqc_clean.output_dir`: `{"contract": {"min_size": 1024}, "format": null, "output": "output_dir", "path": null, "stage": "qc_fastqc_clean", "type": "directory"}`
- `qc_multiqc_illumina.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "qc_multiqc_illumina", "type": "directory"}`
- `qc_multiqc_illumina.multiqc_report`: `{"contract": {"extensions": [".html"], "file_exists": true, "min_size": "1KB"}, "format": "html", "output": "multiqc_report", "path": "{outdir}/{category_dir}/multiqc_illumina_report.html", "stage": "qc_multiqc_illumina", "type": "file"}`
- `qc_nanoplot.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "qc_nanoplot", "type": "directory"}`
- `qc_filtlong.filtered_long_reads`: `{"contract": {"min_size": "1KB"}, "format": "fastq", "output": "filtered_long_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.filtlong.fastq", "stage": "qc_filtlong", "type": "file"}`
- `qc_filtlong.analysis_long_reads`: `{"contract": {}, "format": "fastq", "output": "analysis_long_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.filtlong.fastq", "stage": "qc_filtlong", "type": "file"}`
- `qc_multiqc_ont.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "qc_multiqc_ont", "type": "directory"}`
- `qc_multiqc_ont.multiqc_report`: `{"contract": {"extensions": [".html"], "file_exists": true, "min_size": "1KB"}, "format": "html", "output": "multiqc_report", "path": "{outdir}/{category_dir}/multiqc_ont_report.html", "stage": "qc_multiqc_ont", "type": "file"}`
- `qc_hifiadapterfilt.filtered_hifi_reads`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "filtered_hifi_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.hifiadapterfilt.fastq.gz", "stage": "qc_hifiadapterfilt", "type": "file"}`
- `qc_hifiadapterfilt.filtered_long_reads`: `{"contract": {}, "format": "fastq.gz", "output": "filtered_long_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.hifiadapterfilt.fastq.gz", "stage": "qc_hifiadapterfilt", "type": "file"}`
- `qc_hifiadapterfilt.analysis_long_reads`: `{"contract": {}, "format": "fastq.gz", "output": "analysis_long_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.hifiadapterfilt.fastq.gz", "stage": "qc_hifiadapterfilt", "type": "file"}`
- `qc_multiqc_hifi.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "qc_multiqc_hifi", "type": "directory"}`
- `qc_multiqc_hifi.multiqc_report`: `{"contract": {"extensions": [".html"], "file_exists": true, "min_size": "1KB"}, "format": "html", "output": "multiqc_report", "path": "{outdir}/{category_dir}/multiqc_hifi_report.html", "stage": "qc_multiqc_hifi", "type": "file"}`
- `host_removal_bowtie2.clean_read1`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "clean_read1", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.host_removed.1.fastq.gz", "stage": "host_removal_bowtie2", "type": "file"}`
- `host_removal_bowtie2.clean_read2`: `{"contract": {"min_size": "1KB"}, "format": "fastq.gz", "output": "clean_read2", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.host_removed.2.fastq.gz", "stage": "host_removal_bowtie2", "type": "file"}`
- `host_removal_bowtie2.host_reads`: `{"contract": {}, "format": "fastq.gz", "output": "host_reads", "path": null, "stage": "host_removal_bowtie2", "type": "file"}`
- `host_removal_bowtie2.alignment_rate`: `{"contract": {}, "format": "log", "output": "alignment_rate", "path": null, "stage": "host_removal_bowtie2", "type": "file"}`
- `host_removal_minimap2_long.clean_long_reads`: `{"contract": {"min_size": "1KB"}, "format": "fastq", "output": "clean_long_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.host_removed.fastq", "stage": "host_removal_minimap2_long", "type": "file"}`
- `host_removal_minimap2_long.analysis_long_reads`: `{"contract": {}, "format": "fastq", "output": "analysis_long_reads", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.host_removed.fastq", "stage": "host_removal_minimap2_long", "type": "file"}`
- `host_removal_minimap2_long.host_reads`: `{"contract": {}, "format": "fastq", "output": "host_reads", "path": null, "stage": "host_removal_minimap2_long", "type": "file"}`
- `assembly_megahit.assembly`: `{"contract": {"min_contigs": 1, "min_size": "500B"}, "format": "fasta", "output": "assembly", "path": "{outdir}/{category_dir}/{sample_id}/final.contigs.fa", "stage": "assembly_megahit", "type": "file"}`
- `assembly_megahit.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "assembly_megahit", "type": "directory"}`
- `assembly_metaspades.assembly`: `{"contract": {"min_contigs": 1, "min_size": "500B"}, "format": "fasta", "output": "assembly", "path": "{outdir}/{category_dir}/{sample_id}/contigs.fasta", "stage": "assembly_metaspades", "type": "file"}`
- `assembly_metaspades.assembly_graph`: `{"contract": {}, "format": "fastg", "output": "assembly_graph", "path": "{outdir}/{category_dir}/{sample_id}/assembly_graph.fastg", "stage": "assembly_metaspades", "type": "file"}`
- `assembly_metaspades.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "assembly_metaspades", "type": "directory"}`
- `assembly_metaflye.assembly`: `{"contract": {"min_contigs": 1, "min_size": "500B"}, "format": "fasta", "output": "assembly", "path": "{outdir}/{category_dir}/{sample_id}/assembly.fasta", "stage": "assembly_metaflye", "type": "file"}`
- `assembly_metaflye.assembly_graph`: `{"contract": {}, "format": "gfa", "output": "assembly_graph", "path": "{outdir}/{category_dir}/{sample_id}/assembly_graph.gfa", "stage": "assembly_metaflye", "type": "file"}`
- `assembly_metaflye.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "assembly_metaflye", "type": "directory"}`
- `assembly_hifiasm.assembly`: `{"contract": {"min_contigs": 1, "min_size": "500B"}, "format": "fasta", "output": "assembly", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.hifiasm.fasta", "stage": "assembly_hifiasm", "type": "file"}`
- `assembly_hifiasm.assembly_graph`: `{"contract": {}, "format": "gfa", "output": "assembly_graph", "path": null, "stage": "assembly_hifiasm", "type": "file"}`
- `assembly_hifiasm.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "assembly_hifiasm", "type": "directory"}`
- `assembly_opera_ms.assembly`: `{"contract": {"min_contigs": 1, "min_size": "500B"}, "format": "fasta", "output": "assembly", "path": "{outdir}/{category_dir}/{sample_id}/contigs.fasta", "stage": "assembly_opera_ms", "type": "file"}`
- `assembly_opera_ms.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "assembly_opera_ms", "type": "directory"}`
- `assembly_provided.assembly`: `{"contract": {"exempt": true, "reason": "Passthrough of user-provided assembly FASTA; no new file is produced"}, "format": "fasta", "output": "assembly", "path": null, "stage": "assembly_provided", "type": "file"}`
- `polishing_medaka.assembly`: `{"contract": {"extensions": [".fasta"], "file_exists": true, "min_contigs": 1, "min_size": "500B"}, "format": "fasta", "output": "assembly", "path": "{outdir}/{category_dir}/{sample_id}/consensus.fasta", "stage": "polishing_medaka", "type": "file"}`
- `polishing_medaka.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "polishing_medaka", "type": "directory"}`
- `assembly_qc_quast.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "assembly_qc_quast", "type": "directory"}`
- `assembly_qc_quast.quast_report`: `{"contract": {"extensions": [".tsv"], "file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "quast_report", "path": "{outdir}/{category_dir}/{sample_id}/report.tsv", "stage": "assembly_qc_quast", "type": "file"}`
- `contig_coverage_bowtie2.alignment`: `{"contract": {"min_size": "100B"}, "format": "sam", "output": "alignment", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.plasmid_alignment.sam", "stage": "contig_coverage_bowtie2", "type": "file"}`
- `contig_coverage_minimap2.alignment`: `{"contract": {"min_size": "100B"}, "format": "sam", "output": "alignment", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.plasmid_alignment.sam", "stage": "contig_coverage_minimap2", "type": "file"}`
- `contig_coverage_samtools.bam`: `{"contract": {"min_size": "100B"}, "format": "bam", "output": "bam", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.contig_alignment.bam", "stage": "contig_coverage_samtools", "type": "file"}`
- `contig_coverage_coverm.coverage_table`: `{"contract": {"min_size": "0B"}, "format": "tsv", "output": "coverage_table", "path": null, "stage": "contig_coverage_coverm", "type": "file"}`
- `contig_coverage_coverm.abundance_tsv`: `{"contract": {}, "format": "tsv", "output": "abundance_tsv", "path": null, "stage": "contig_coverage_coverm", "type": "file"}`
- `plasmid_detect_genomad.plasmid_summary`: `{"contract": {"min_size": "50B"}, "format": "tsv", "output": "plasmid_summary", "path": "{outdir}/{category_dir}/{sample_id}/contigs_summary/contigs_plasmid_summary.tsv", "stage": "plasmid_detect_genomad", "type": "file"}`
- `plasmid_detect_genomad.plasmid_contigs`: `{"contract": {"min_size": "50B"}, "format": "fasta", "output": "plasmid_contigs", "path": "{outdir}/{category_dir}/{sample_id}/contigs_summary/contigs_plasmid.fna", "stage": "plasmid_detect_genomad", "type": "file"}`
- `plasmid_detect_genomad.virus_summary`: `{"contract": {"min_size": "50B"}, "format": "tsv", "output": "virus_summary", "path": "{outdir}/{category_dir}/{sample_id}/contigs_summary/contigs_virus_summary.tsv", "stage": "plasmid_detect_genomad", "type": "file"}`
- `plasmid_detect_plasme.plasme_predictions`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "plasme_predictions", "path": null, "stage": "plasmid_detect_plasme", "type": "file"}`
- `plasmid_detect_plasx.plasx_predictions`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "plasx_predictions", "path": null, "stage": "plasmid_detect_plasx", "type": "file"}`
- `plasmid_detect_platon.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "plasmid_detect_platon", "type": "directory"}`
- `plasmid_detect_scapp.scapp_predictions`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "fasta", "output": "scapp_predictions", "path": "{outdir}/{category_dir}/{sample_id}/scapp/assembly_graph.confident_cycs.fasta", "stage": "plasmid_detect_scapp", "type": "file"}`
- `plasmid_consensus.plasmid_contigs`: `{"contract": {"min_size": "100B"}, "format": "fasta", "output": "plasmid_contigs", "path": "{outdir}/04_plasmid_detection/{sample_id}/plasmid_contigs.fasta", "stage": "plasmid_consensus", "type": "file"}`
- `plasmid_binning_plasmaag.plasmid_bins`: `{"contract": {"min_files": 1}, "format": null, "output": "plasmid_bins", "path": null, "stage": "plasmid_binning_plasmaag", "type": "directory"}`
- `plasmid_binning_gplas2.plasmid_bins`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "plasmid_bins", "path": null, "stage": "plasmid_binning_gplas2", "type": "file"}`
- `plasmid_binning_mob_recon.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "plasmid_binning_mob_recon", "type": "directory"}`
- `typing_plasmidfinder.typing_results`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "typing_results", "path": null, "stage": "typing_plasmidfinder", "type": "file"}`
- `typing_mob_typer.typing_results`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "typing_results", "path": null, "stage": "typing_mob_typer", "type": "file"}`
- `typing_copla.typing_results`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "typing_results", "path": null, "stage": "typing_copla", "type": "file"}`
- `host_prediction_metaphlan.taxonomy_profile`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "taxonomy_profile", "path": null, "stage": "host_prediction_metaphlan", "type": "file"}`
- `host_prediction_kraken2.kraken_report`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "kraken_report", "path": null, "stage": "host_prediction_kraken2", "type": "file"}`
- `host_prediction_plasmidhostfinder.host_predictions`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "host_predictions", "path": null, "stage": "host_prediction_plasmidhostfinder", "type": "file"}`
- `annotation_prodigal.gene_calls`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "gff", "output": "gene_calls", "path": null, "stage": "annotation_prodigal", "type": "file"}`
- `annotation_prodigal.protein_seqs`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "faa", "output": "protein_seqs", "path": null, "stage": "annotation_prodigal", "type": "file"}`
- `annotation_prodigal.nucleotide_seqs`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "ffn", "output": "nucleotide_seqs", "path": null, "stage": "annotation_prodigal", "type": "file"}`
- `annotation_bakta.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "annotation_bakta", "type": "directory"}`
- `annotation_bakta.annotations`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "annotations", "path": null, "stage": "annotation_bakta", "type": "file"}`
- `annotation_amrfinderplus.arg_vf_results`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "arg_vf_results", "path": null, "stage": "annotation_amrfinderplus", "type": "file"}`
- `annotation_abricate.screening_results`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "screening_results", "path": null, "stage": "annotation_abricate", "type": "file"}`
- `annotation_isescan.is_results`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "is_results", "path": null, "stage": "annotation_isescan", "type": "file"}`
- `annotation_integronfinder.integron_results`: `{"contract": {"min_files": 1}, "format": null, "output": "integron_results", "path": null, "stage": "annotation_integronfinder", "type": "directory"}`
- `annotation_mob_suite.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "annotation_mob_suite", "type": "directory"}`
- `mag_metabat2.mag_bins`: `{"contract": {"min_files": 1}, "format": null, "output": "mag_bins", "path": null, "stage": "mag_metabat2", "type": "directory"}`
- `mag_checkm2.quality_report`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "quality_report", "path": null, "stage": "mag_checkm2", "type": "file"}`
- `mag_gtdbtk.taxonomy`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "taxonomy", "path": null, "stage": "mag_gtdbtk", "type": "file"}`
- `host_plasmid_link_coabundance.coabundance_links`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "coabundance_links", "path": null, "stage": "host_plasmid_link_coabundance", "type": "file"}`
- `host_plasmid_link_sequence.sequence_similarity_links`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "sequence_similarity_links", "path": null, "stage": "host_plasmid_link_sequence", "type": "file"}`
- `host_plasmid_link_crispr.crispr_links`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "crispr_links", "path": null, "stage": "host_plasmid_link_crispr", "type": "file"}`
- `host_plasmid_link_longread.longread_bridge_links`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "longread_bridge_links", "path": null, "stage": "host_plasmid_link_longread", "type": "file"}`
- `abundance_bowtie2.alignment`: `{"contract": {"min_size": "100B"}, "format": "sam", "output": "alignment", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.plasmid_alignment.sam", "stage": "abundance_bowtie2", "type": "file"}`
- `abundance_minimap2.alignment`: `{"contract": {"min_size": "100B"}, "format": "sam", "output": "alignment", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.plasmid_alignment.sam", "stage": "abundance_minimap2", "type": "file"}`
- `abundance_samtools.bam`: `{"contract": {"min_size": "100B"}, "format": "bam", "output": "bam", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.plasmid_alignment.bam", "stage": "abundance_samtools", "type": "file"}`
- `abundance_coverm.abundance`: `{"contract": {"extensions": [".tsv"], "file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "abundance", "path": "{outdir}/{category_dir}/{sample_id}/{sample_id}.coverm.tsv", "stage": "abundance_coverm", "type": "file"}`
- `abundance_bowtie2_short.alignment`: `{"contract": {"extensions": [".sam"], "file_exists": true, "min_size": "100B"}, "format": "sam", "output": "alignment", "path": "{outdir}/{category_dir}/{sample_id}/short/{sample_id}.short.sam", "stage": "abundance_bowtie2_short", "type": "file"}`
- `abundance_bowtie2_short.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}/short", "stage": "abundance_bowtie2_short", "type": "directory"}`
- `abundance_samtools_short.bam`: `{"contract": {"extensions": [".bam"], "file_exists": true, "min_size": "100B"}, "format": "bam", "output": "bam", "path": "{outdir}/{category_dir}/{sample_id}/short/{sample_id}.short.bam", "stage": "abundance_samtools_short", "type": "file"}`
- `abundance_samtools_short.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}/short", "stage": "abundance_samtools_short", "type": "directory"}`
- `abundance_coverm_short.abundance`: `{"contract": {"extensions": [".tsv"], "file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "abundance", "path": "{outdir}/{category_dir}/{sample_id}/short/{sample_id}.short.coverm.tsv", "stage": "abundance_coverm_short", "type": "file"}`
- `abundance_coverm_short.tpm_table`: `{"contract": {}, "format": "tsv", "output": "tpm_table", "path": "{outdir}/{category_dir}/{sample_id}/short/{sample_id}.short.tpm.tsv", "stage": "abundance_coverm_short", "type": "file"}`
- `abundance_coverm_short.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}/short", "stage": "abundance_coverm_short", "type": "directory"}`
- `abundance_minimap2_long.alignment`: `{"contract": {"extensions": [".sam"], "file_exists": true, "min_size": "100B"}, "format": "sam", "output": "alignment", "path": "{outdir}/{category_dir}/{sample_id}/long/{sample_id}.long.sam", "stage": "abundance_minimap2_long", "type": "file"}`
- `abundance_minimap2_long.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}/long", "stage": "abundance_minimap2_long", "type": "directory"}`
- `abundance_samtools_long.bam`: `{"contract": {"extensions": [".bam"], "file_exists": true, "min_size": "100B"}, "format": "bam", "output": "bam", "path": "{outdir}/{category_dir}/{sample_id}/long/{sample_id}.long.bam", "stage": "abundance_samtools_long", "type": "file"}`
- `abundance_samtools_long.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}/long", "stage": "abundance_samtools_long", "type": "directory"}`
- `abundance_coverm_long.abundance`: `{"contract": {"extensions": [".tsv"], "file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "abundance", "path": "{outdir}/{category_dir}/{sample_id}/long/{sample_id}.long.coverm.tsv", "stage": "abundance_coverm_long", "type": "file"}`
- `abundance_coverm_long.tpm_table`: `{"contract": {}, "format": "tsv", "output": "tpm_table", "path": "{outdir}/{category_dir}/{sample_id}/long/{sample_id}.long.tpm.tsv", "stage": "abundance_coverm_long", "type": "file"}`
- `abundance_coverm_long.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": "{outdir}/{category_dir}/{sample_id}/long", "stage": "abundance_coverm_long", "type": "directory"}`
- `multisample_diversity.diversity_metrics`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "diversity_metrics", "path": null, "stage": "multisample_diversity", "type": "file"}`
- `multisample_differential_abundance.differential_abundance_results`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "differential_abundance_results", "path": null, "stage": "multisample_differential_abundance", "type": "file"}`
- `multisample_differential_deseq2.differential_plasmids`: `{"contract": {"extensions": [".tsv"], "file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "differential_plasmids", "path": "{outdir}/{category_dir}/differential_plasmids.tsv", "stage": "multisample_differential_deseq2", "type": "file"}`
- `multisample_network_prepare.network_input`: `{"contract": {"extensions": [".tsv"], "file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "network_input", "path": "{outdir}/{category_dir}/fastspar_input.tsv", "stage": "multisample_network_prepare", "type": "file"}`
- `multisample_network_fastspar.correlation`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "correlation", "path": null, "stage": "multisample_network_fastspar", "type": "file"}`
- `multisample_network_fastspar.covariance`: `{"contract": {}, "format": "tsv", "output": "covariance", "path": null, "stage": "multisample_network_fastspar", "type": "file"}`
- `plasmid_catalog_prepare.combined_plasmids`: `{"contract": {"extensions": [".fasta"], "file_exists": true, "min_size": "100B"}, "format": "fasta", "output": "combined_plasmids", "path": "{outdir}/{category_dir}/plasmid_catalog_input.fasta", "stage": "plasmid_catalog_prepare", "type": "file"}`
- `comparative_mmseqs2.clusters`: `{"contract": {"extensions": [".tsv"], "file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "clusters", "path": "{outdir}/{category_dir}/plasmid_catalog_cluster.tsv", "stage": "comparative_mmseqs2", "type": "file"}`
- `comparative_mmseqs2.representatives`: `{"contract": {}, "format": "fasta", "output": "representatives", "path": "{outdir}/{category_dir}/plasmid_catalog_rep_seq.fasta", "stage": "comparative_mmseqs2", "type": "file"}`
- `comparative_blast.blast_results`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "blast_results", "path": null, "stage": "comparative_blast", "type": "file"}`
- `comparative_mummer.coords`: `{"contract": {"file_exists": true, "min_size": "0B"}, "format": "tsv", "output": "coords", "path": null, "stage": "comparative_mummer", "type": "file"}`
- `comparative_clinker.clinker_html`: `{"contract": {"file_exists": true, "min_size": "1KB"}, "format": "html", "output": "clinker_html", "path": null, "stage": "comparative_clinker", "type": "file"}`
- `visualization_clinker_gene_maps.gene_maps`: `{"contract": {"file_exists": true, "min_size": "1KB"}, "format": "html", "output": "gene_maps", "path": null, "stage": "visualization_clinker_gene_maps", "type": "file"}`
- `visualization_pycirclize.circular_maps`: `{"contract": {"file_exists": true, "min_size": "100B"}, "format": "png", "output": "circular_maps", "path": null, "stage": "visualization_pycirclize", "type": "file"}`
- `visualization_network.network_html`: `{"contract": {"file_exists": true, "min_size": "1KB"}, "format": "html", "output": "network_html", "path": null, "stage": "visualization_network", "type": "file"}`
- `assembly_hybridspades.assembly`: `{"contract": {"min_contigs": 1, "min_size": "500B"}, "format": "fasta", "output": "assembly", "path": "{outdir}/{category_dir}/{sample_id}/contigs.fasta", "stage": "assembly_hybridspades", "type": "file"}`
- `assembly_hybridspades.output_dir`: `{"contract": {}, "format": null, "output": "output_dir", "path": null, "stage": "assembly_hybridspades", "type": "directory"}`
- `plasmid_binning_scapp.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "plasmid_binning_scapp", "type": "directory"}`
- `plasmid_binning_recycler.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "plasmid_binning_recycler", "type": "directory"}`
- `typing_conjscan.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "typing_conjscan", "type": "directory"}`
- `typing_macsyfinder.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "typing_macsyfinder", "type": "directory"}`
- `annotation_rgi.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "annotation_rgi", "type": "directory"}`
- `annotation_eggnog_mapper.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "annotation_eggnog_mapper", "type": "directory"}`
- `mag_concoct.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "mag_concoct", "type": "directory"}`
- `mag_semibin.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "mag_semibin", "type": "directory"}`
- `mag_das_tool.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "mag_das_tool", "type": "directory"}`
- `visualization_dna_features.output_dir`: `{"contract": {"min_files": 1}, "format": null, "output": "output_dir", "path": null, "stage": "visualization_dna_features", "type": "directory"}`
- `report_markdown.report_md`: `{"contract": {"file_exists": true, "min_size": "1KB"}, "format": "markdown", "output": "report_md", "path": null, "stage": "report_markdown", "type": "file"}`
- `report_markdown.report_html`: `{"contract": {"file_exists": true, "min_size": "1KB"}, "format": "html", "output": "report_html", "path": null, "stage": "report_markdown", "type": "file"}`
- `report_markdown.methods_md`: `{"contract": {"file_exists": true, "min_size": "1KB"}, "format": "markdown", "output": "methods_md", "path": null, "stage": "report_markdown", "type": "file"}`

## Standard tables

- `abundance`: sample_id, feature_id, contig_id, coverage, tpm, rpkm, mapped_reads, length_bp, tool, source_file
- `alignment_summary`: sample_id, tool, artifact_type, record_count, mapped_records, unmapped_records, size_bytes, source_file
- `amr_genes`: sample_id, contig_id, gene, drug_class, identity, coverage, tool, source_file
- `analysis_status`: module, status, reason, sample_count, eligible_sample_count, group_counts, threshold
- `annotations`: sample_id, contig_id, start, end, strand, gene, product, drug_class, category, tool, evidence, identity, coverage, source_file
- `artifacts`: sample_id, tool, artifact_type, path, size_bytes, description
- `assembly_qc`: sample_id, assembler, contig_count, n50, total_length, max_contig, gc_content, source_file, warnings
- `assembly_summary`: sample_id, tool, metric, value, unit, source_file
- `bin_to_contig`: sample_id, bin_id, contig_id, membership_score, tool, source_file
- `comparative_hits`: sample_id, query_id, subject_id, identity, coverage, e_value, bit_score, alignment_length, tool, evidence, source_file
- `differential_abundance`: feature_id, contig_id, group_a, group_b, mean_a, mean_b, log2_fold_change, statistic, p_value, q_value, method, warnings
- `differential_plasmids`: plasmid_id, group_a, group_b, log2_fold_change, p_value, q_value, method, warnings
- `host_plasmid_links`: sample_id, plasmid_id, host_id, evidence_type, evidence_level, score, is_prediction, source_file
- `host_predictions`: sample_id, contig_id, host_taxon, method, confidence, evidence, tool, source_file
- `host_profile`: sample_id, taxon_name, taxon_id, rank, relative_abundance, tool, source_file
- `mag_quality`: sample_id, bin_id, completeness, contamination, taxonomy, tool, source_file
- `mge_elements`: sample_id, contig_id, element_id, element_type, start, end, tool, source_file
- `network_edges`: source, target, correlation, covariance, p_value, q_value, method, evidence, warnings, source_file
- `network_nodes`: node_id, node_type, sample_count, mean_abundance, degree, evidence, source_file
- `plasmid_abundance`: sample_id, plasmid_id, coverage, rpkm, tpm, raw_count, mapper, source_file
- `plasmid_annotation`: sample_id, contig_id, gene_id, start, end, strand, gene, product, functional_label, tool, source_file
- `plasmid_bins`: sample_id, bin_id, method, contig_count, total_length_bp, confidence, evidence, source_file
- `plasmid_catalog`: cluster_id, representative_id, member_id, sample_id, length_bp, circularity, identity, coverage, method, source_file
- `plasmid_consensus`: sample_id, contig_id, final_plasmid_call, decision_strategy, support_tools, support_count, total_tools, confidence_score, weighted_score, weight_threshold, tool_weights, contig_length, evidence, warnings
- `plasmid_predictions`: sample_id, contig_id, tool, evidence_level, score, confidence, contig_length, circularity, evidence, warnings, source_file
- `plasmid_structure`: sample_id, plasmid_id, length_bp, is_circular, terminal_overlap_bp, method, warnings, source_file
- `plasmid_typing`: sample_id, contig_id, typing_scheme, type_id, mobility, confidence, tool, evidence, source_file
- `qc_summary`: sample_id, tool, metric, value, unit, source_file
- `sample_diversity`: sample_id, comparison_sample_id, metric, value, method, group, source_file, warnings
- `sample_qc`: sample_id, tool, raw_reads, clean_reads, q30, gc_content, filter_rate, source_file, warnings
- `visualization_outputs`: sample_id, output_type, path, tool, description

## Stable error categories

`artifact_missing`, `contract_violation`, `duplicate_sample_id`, `empty_result`, `incomplete_pairs`, `internal_error`, `invalid_config`, `invalid_platform`, `invalid_sample_sheet`, `missing_database`, `missing_input`, `missing_resource`, `missing_sample_id`, `nonzero_exit`, `parse_failed`, `permission_required`, `runtime_not_supported`, `tool_not_found`, `unknown_analysis_type`

## Limitations

- Plasmid detection via geNomad uses a score threshold (default 0.7); low-score contigs may be missed or incorrectly classified.
- Assembly from metagenomic short reads can produce chimeric contigs that confound plasmid length estimates.
- AMR gene presence does not guarantee phenotypic resistance; expression level, copy number, and host background all influence resistance phenotype.
- Plasmid abundance estimates via CoverM depend on read mapping rates and contig coverage evenness; highly repetitive plasmid sequences may inflate abundance.
- Host prediction from metagenomic data is correlative and should be validated with culture-based or Hi-C experiments before publication claims.
- Taxonomic profiling (MetaPhlAn, Kraken2) is database-dependent; organisms absent from the reference database cannot be detected.
- Mobile element detection (ISEScan, IntegronFinder) has false-positive rates that increase in low-complexity or repeat-rich regions.
- This pipeline does not distinguish between chromosomal and plasmid-borne copies of identical genes (e.g., AMR genes present in both locations).
- Database versions (geNomad DB, Bakta DB, AMRFinder DB, Kraken2 DB) are recorded in the resource manifest but change over time; results are valid only for the versions listed.
- Dry-run results prove only structural validity (planning, command rendering, provenance); biological conclusions require real tool outputs with validated inputs.
