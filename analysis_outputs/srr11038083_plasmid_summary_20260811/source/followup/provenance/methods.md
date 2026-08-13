# Methods

## Software Versions

| Tool | Executable | Version | Status |
|------|-----------|---------|--------|
| abricate | abricate | not_configured | not_configured |
| amrfinderplus | amrfinder | not_configured | not_configured |
| bakta | bakta | bakta 1.12.0 | captured |
| fastp | fastp | fastp 1.3.5 | captured |
| genomad | genomad | geNomad, version 1.12.0 | captured |
| integronfinder | integron_finder | not_configured | not_configured |
| megahit | megahit | MEGAHIT v1.2.9 | captured |
| plasmidfinder | python | 3.0.3 | captured |
| report_markdown | abi | 1.5.11.1 | captured |
| rgi | rgi | not_configured | not_configured |

## Reference Databases

| Resource | Version | Source | Path |
|----------|---------|--------|------|
| abricate | not_captured | not_configured | /root/autodl-tmp/resources/autoplasm/abricate |
| amrfinderplus | not_captured | not_configured | /root/autodl-tmp/resources/autoplasm/amrfinderplus/latest |
| auto_download | not_captured | not_configured | False |
| bakta | not_captured | not_configured | /root/autodl-tmp/resources/autoplasm/bakta_v6_full/db |
| blast | not_configured | not_configured | BLAST_DB_NOT_CONFIGURED |
| card | not_captured | not_configured | /root/autodl-tmp/resources/autoplasm/card |
| checkm2 | not_captured | not_configured | checkm2 |
| copla | not_configured | not_configured | {'refgraph': 'COPLA_REFGRAPH_NOT_CONFIGURED', 'reflist': 'COPLA_REFLIST_NOT_CONFIGURED', 'version': ''} |
| eggnog_mapper | not_captured | not_configured | eggnog_mapper |
| genomad | not_captured | not_configured | /root/autodl-tmp/resources/autoplasm/genomad/genomad_db |
| gtdbtk | not_captured | not_configured | gtdbtk/release232 |
| kraken2 | not_captured | not_configured | kraken2 |
| metaphlan | not_captured | not_configured | metaphlan |
| mob_suite | not_captured | not_configured | mob_suite/data |
| plasme | not_captured | not_configured | PLASMe/DB |
| plasmidfinder | not_captured | not_configured | /root/autodl-tmp/resources/autoplasm/plasmidfinder_db/DB |
| plasmidhostfinder | not_configured | not_configured | PLASMIDHOSTFINDER_DB_NOT_CONFIGURED |
| plasx | not_captured | not_configured | {'annotations': 'PlasX', 'model': 'PlasX', 'version': ''} |

## Commands Executed

| Step ID | Tool | Command | Status |
|---------|------|---------|--------|
| SRR11038083_qc_fastp | fastp | `fastp -i /root/autodl-tmp/abi-real-data/raw/plasmid_scapp/SRR11038083_1.fastq.gz -I /root/autodl-tmp/abi-real-data/raw/plasmid_scapp/SRR11038083_2.fastq.gz -o /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/01_qc/SRR11038083/SRR11038083_R1.clean.fastq.gz -O /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/01_qc/SRR11038083/SRR11038083_R2.clean.fastq.gz --thread 12 --html /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/01_qc/SRR11038083/SRR11038083.fastp.html --json /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/01_qc/SRR11038083/SRR11038083.fastp.json` | resumed |
| SRR11038083_assembly_megahit | megahit | `megahit -1 /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/01_qc/SRR11038083/SRR11038083_R1.clean.fastq.gz -2 /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/01_qc/SRR11038083/SRR11038083_R2.clean.fastq.gz -o /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/02_assembly/SRR11038083 -t 12 --memory 66571993088` | resumed |
| SRR11038083_plasmid_detection_genomad | genomad | `genomad end-to-end --cleanup --restart --threads 12 /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/02_assembly/SRR11038083/final.contigs.fa /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/04_plasmid_detection/SRR11038083 /root/autodl-tmp/resources/autoplasm/genomad/genomad_db` | resumed |
| SRR11038083_plasmid_consensus_internal | internal | `abi internal metagenomic_plasmid.plasmid_consensus --scope worker --step-id SRR11038083_plasmid_consensus_internal` | success |
| SRR11038083_annotation_abricate | abricate | `abricate --threads 12 --db card /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/04_plasmid_detection/SRR11038083/plasmid_contigs.fasta > /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/08_annotation/SRR11038083/SRR11038083.card.tsv` | success |
| SRR11038083_annotation_amrfinderplus | amrfinderplus | `amrfinder -n /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/04_plasmid_detection/SRR11038083/plasmid_contigs.fasta -d /root/autodl-tmp/resources/autoplasm/amrfinderplus/latest -o /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/08_annotation/SRR11038083/SRR11038083.amrfinder.tsv` | resumed |
| SRR11038083_annotation_bakta | bakta | `bakta --db /root/autodl-tmp/resources/autoplasm/bakta_v6_full/db --output /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/08_annotation/SRR11038083 --threads 12 --force --skip-sorf /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/04_plasmid_detection/SRR11038083/plasmid_contigs.fasta` | resumed |
| SRR11038083_annotation_integronfinder | integronfinder | `integron_finder --outdir /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/08_annotation/SRR11038083 /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/04_plasmid_detection/SRR11038083/plasmid_contigs.fasta` | success |
| SRR11038083_annotation_rgi | rgi | `rgi main --input_sequence /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/04_plasmid_detection/SRR11038083/plasmid_contigs.fasta --output_file /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/08_annotation/SRR11038083/SRR11038083.rgi.tsv --input_type contig --num_threads 12` | success |
| SRR11038083_typing_plasmidfinder | plasmidfinder | `python -m plasmidfinder -i /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/04_plasmid_detection/SRR11038083/plasmid_contigs.fasta -o /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume/06_plasmid_typing/SRR11038083 -p /root/autodl-tmp/resources/autoplasm/plasmidfinder_db/DB --legacy -x` | success |
| report_markdown | report_markdown | `abi report --type metagenomic_plasmid --result-dir /root/autodl-tmp/abi-real-data/results/metagenomic_plasmid_srr11038083_candidate_followup_20260811_resume` | success |

## Interpretation Notes

- All tools were executed with the parameters recorded above.
- Tool versions marked as `not_configured` had no version recorded (the version command was empty or not configured).
- Tool versions marked as `not_captured` could not be captured, for example because the tool was mocked or an unexpected failure occurred.
- Tool versions marked as `capture_failed (...)` had a version command but it returned a non-zero exit code or did not match the expected pattern.
- Reference databases marked as `not_configured` were not provided; those marked as `not_captured` lack recorded version information.

*Generated by ABI methods provenance system.*
