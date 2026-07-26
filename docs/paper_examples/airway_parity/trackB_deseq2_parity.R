suppressPackageStartupMessages(library(DESeq2))
aw <- read.delim("reference/airway_counts.tsv", check.names = FALSE)
cd <- read.delim("reference/airway_coldata.tsv")
cts <- as.matrix(aw[, cd$run]); rownames(cts) <- aw$gene_id
coldata <- data.frame(cell = factor(cd$cell), dex = factor(cd$dex, levels = c("untrt", "trt")),
                      row.names = cd$run)
dds <- DESeqDataSetFromMatrix(countData = cts, colData = coldata, design = ~ cell + dex)
dds <- DESeq(dds)
res <- results(dds, contrast = c("dex", "trt", "untrt"), alpha = 0.05)
resdf <- data.frame(gene_id = rownames(res), as.data.frame(res), check.names = FALSE)
write.table(resdf, "outputs/trackB_airway_deseq2_results.tsv", sep = "\t", quote = FALSE, row.names = FALSE)

abi <- read.delim(file.path(Sys.getenv("ABI_DIR"), "04_differential_expression/deseq2_results.tsv"))
m <- merge(abi[, c("gene_id", "log2FoldChange", "pvalue", "padj")],
           resdf[, c("gene_id", "log2FoldChange", "pvalue", "padj")],
           by = "gene_id", suffixes = c("_abi", "_aw"))
tested <- !is.na(m$pvalue_abi) & !is.na(m$pvalue_aw)
mt <- m[tested, ]
sig_abi <- !is.na(m$padj_abi) & m$padj_abi < 0.05
sig_aw  <- !is.na(m$padj_aw)  & m$padj_aw  < 0.05
summ <- data.frame(
  metric = c("genes_compared", "tested_both", "log2fc_pearson", "log2fc_spearman",
             "direction_concordance", "abi_sig_fdr05", "airway_sig_fdr05",
             "sig_intersection", "sig_jaccard"),
  value = c(nrow(m), nrow(mt),
            cor(mt$log2FoldChange_abi, mt$log2FoldChange_aw, method = "pearson"),
            cor(mt$log2FoldChange_abi, mt$log2FoldChange_aw, method = "spearman"),
            mean(sign(mt$log2FoldChange_abi) == sign(mt$log2FoldChange_aw)),
            sum(sig_abi), sum(sig_aw), sum(sig_abi & sig_aw),
            sum(sig_abi & sig_aw) / sum(sig_abi | sig_aw))
)
write.table(summ, "outputs/trackB_de_parity_summary.tsv", sep = "\t", quote = FALSE, row.names = FALSE)
write.table(m, "outputs/trackB_de_gene_level_comparison.tsv", sep = "\t", quote = FALSE, row.names = FALSE)
print(summ, digits = 4)
