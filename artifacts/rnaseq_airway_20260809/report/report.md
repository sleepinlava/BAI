# RNA-seq Gene Expression ABI Report: rnaseq_airway_dex_untreated_retry5_parity

- Analysis type: `rnaseq_expression`
- Planned steps: 27
- Selected tools: build_count_matrix, deseq2, fastp, featurecounts, rnaseq_enrichment, star

## Standard Tables

| Table | Rows | Path |
| --- | ---: | --- |
| `alignment_summary.tsv` | 256 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/alignment_summary.tsv` |
| `annotated_differential_expression.tsv` | 16019 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/annotated_differential_expression.tsv` |
| `count_matrix.tsv` | 509416 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/count_matrix.tsv` |
| `differential_expression.tsv` | 16019 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/differential_expression.tsv` |
| `gene_expression.tsv` | 509416 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/gene_expression.tsv` |
| `go_gsea.tsv` | 3560 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/go_gsea.tsv` |
| `go_gsea_plot.tsv` | 20 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/go_gsea_plot.tsv` |
| `go_overrepresentation.tsv` | 9726 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/go_overrepresentation.tsv` |
| `go_overrepresentation_plot.tsv` | 20 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/go_overrepresentation_plot.tsv` |
| `normalized_expression.tsv` | 128152 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/normalized_expression.tsv` |
| `qc_summary.tsv` | 144 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/qc_summary.tsv` |
| `reactome_gsea.tsv` | 1248 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/reactome_gsea.tsv` |
| `reactome_gsea_plot.tsv` | 11 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/reactome_gsea_plot.tsv` |
| `reactome_overrepresentation.tsv` | 2496 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/reactome_overrepresentation.tsv` |
| `reactome_overrepresentation_plot.tsv` | 18 | `/root/autodl-tmp/abi-real-data/results/rnaseq_airway_abi_test_20260809_12vcpu_62gb_retry1/tables/reactome_overrepresentation_plot.tsv` |

## Known Limitations

1. RNA-seq measures steady-state transcript abundance, which does not always correlate with protein expression levels. (Ref: Schwanhäusser et al., Nature, 2011, doi:10.1038/nature10098; Vogel & Marcotte, Nat Rev Genet, 2012, doi:10.1038/nrg3185)
2. Alignment rates depend on reference genome completeness and annotation quality; unannotated genes or novel transcripts are missed by featureCounts. (Ref: Liao et al., Bioinformatics, 2014, doi:10.1093/bioinformatics/btt656; Ungar et al., Am J Hum Genet, 2024, doi:10.1016/j.ajhg.2024.05.005)
3. DESeq2 normalisation assumes most genes are not differentially expressed; severe global shifts in expression violate this assumption. (Ref: Anders & Huber, Genome Biol, 2010, doi:10.1186/gb-2010-11-10-r106; Love et al., Genome Biol, 2014, doi:10.1186/s13059-014-0550-8)
4. Differential expression p-values are not corrected for unmeasured confounders (batch effects, sample processing variation) unless explicitly modeled. (Ref: Leek & Storey, PLoS Genet, 2007, doi:10.1371/journal.pgen.0030161; Leek et al., Nat Rev Genet, 2010, doi:10.1038/nrg2825)
5. Lowly expressed genes (mean count < 10) have inflated false discovery rates even after multiple testing correction. (Ref: Love et al., Genome Biol, 2014, doi:10.1186/s13059-014-0550-8; Zehetmayer et al., BMC Bioinformatics, 2022, doi:10.1186/s12859-022-04928-z)
6. GO/Reactome enrichment is database-release dependent; pathways absent from the configured offline OBO/GAF/GMT snapshots cannot be detected. (Ref: Wadi et al., Nat Methods, 2016, doi:10.1038/nmeth.3963; Jassal et al., Nucleic Acids Res, 2020, doi:10.1093/nar/gkz1031)
7. Gene-symbol mapping uses the configured GTF gene_name attribute; missing, duplicated, or retired symbols are excluded from enrichment after deterministic de-duplication. (Ref: Oh et al., F1000Research, 2020, doi:10.12688/f1000research.28033.1; Braschi et al., Nucleic Acids Res, 2019, doi:10.1093/nar/gky930)
8. ORA depends on the significance threshold and measured-gene universe, while preranked GSEA depends on the chosen ranking statistic and permutation count; neither establishes pathway causality. (Ref: Subramanian et al., PNAS, 2005, doi:10.1073/pnas.0506580102; Maleki et al., Front Genet, 2020, doi:10.3389/fgene.2020.00654)
9. Reference genome version, annotation version, and alignment index version all affect results; these are recorded in the resource manifest. (Ref: Slabaugh et al., RNA, 2019, doi:10.1261/rna.070227.118; Ungar et al., Am J Hum Genet, 2024, doi:10.1016/j.ajhg.2024.05.005)

Dry-run artifacts prove planning, command rendering, provenance, and table contracts only; biological conclusions require real tool outputs.
