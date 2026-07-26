aw <- read.delim("reference/airway_counts.tsv", check.names = FALSE)
abi <- read.delim(file.path(Sys.getenv("ABI_DIR"), "04_differential_expression/count_matrix.tsv"), check.names = FALSE)
stopifnot(identical(aw$gene_id, abi$gene_id))
samples <- setdiff(colnames(aw), "gene_id")
stopifnot(identical(samples, setdiff(colnames(abi), "gene_id")))
awm <- as.matrix(aw[, samples]); abim <- as.matrix(abi[, samples])
res <- lapply(samples, function(s) {
  a <- abim[, s]; w <- awm[, s]
  la <- log2(a + 1); lw <- log2(w + 1)
  pos <- a > 0 & w > 0
  data.frame(
    sample = s,
    genes = length(a),
    both_positive = sum(pos),
    pearson_log2 = cor(la, lw, method = "pearson"),
    spearman_log2 = cor(la, lw, method = "spearman"),
    median_ratio_abi_over_aw = median((a/w)[pos]),
    mean_ratio_abi_over_aw = mean((a/w)[pos]),
    abi_total = sum(a), airway_total = sum(w),
    total_ratio = sum(a)/sum(w)
  )
})
m <- do.call(rbind, res)
write.table(m, "outputs/trackA_per_sample_count_parity.tsv", sep = "\t", quote = FALSE, row.names = FALSE)
print(m, digits = 4)
