#!/usr/bin/env python3
"""Build supplementary RNA-seq figures from ABI canonical result tables."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/abi-rnaseq-matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parent
TABLES = ROOT / "tables"
META = ROOT / "04_differential_expression" / "sample_metadata.tsv"
OUT = ROOT / "supplementary_figures"
OUT.mkdir(exist_ok=True)

sns.set_theme(style="whitegrid", context="talk")
PALETTE = {"untreated": "#4C78A8", "dex": "#E45756"}


def save_figure(fig: plt.Figure, stem: str) -> None:
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"{stem}.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)


def short_term(value: str, width: int = 48) -> str:
    label = value.split(" | ", 1)[-1]
    return label if len(label) <= width else label[: width - 1] + "…"


expression = pd.read_csv(TABLES / "normalized_expression.tsv", sep="\t")
metadata = pd.read_csv(META, sep="\t").set_index("sample_id")
de = pd.read_csv(TABLES / "annotated_differential_expression.tsv", sep="\t")

matrix = expression.pivot(index="gene_id", columns="sample_id", values="normalized_count")
matrix = matrix.loc[:, metadata.index]
log_matrix = np.log2(matrix + 1.0)

# PCA on the 5,000 most variable genes. Genes are centered but not variance-scaled.
variable_genes = log_matrix.var(axis=1).nlargest(min(5000, len(log_matrix))).index
x = log_matrix.loc[variable_genes].T.to_numpy(dtype=float, copy=True)
x -= x.mean(axis=0, keepdims=True)
u, s, _ = np.linalg.svd(x, full_matrices=False)
scores = u[:, :2] * s[:2]
explained = (s**2) / np.sum(s**2) * 100.0
pca = pd.DataFrame(scores, index=metadata.index, columns=["PC1", "PC2"]).join(metadata)
pca.to_csv(OUT / "pca_scores.tsv", sep="\t")

fig, ax = plt.subplots(figsize=(9, 7))
for condition, frame in pca.groupby("condition", sort=False):
    ax.scatter(frame.PC1, frame.PC2, s=130, color=PALETTE[condition], label=condition)
    for sample_id, row in frame.iterrows():
        ax.annotate(f"{sample_id}\n{row['donor']}", (row.PC1, row.PC2), xytext=(6, 5),
                    textcoords="offset points", fontsize=8)
ax.axhline(0, color="#BBBBBB", lw=0.8)
ax.axvline(0, color="#BBBBBB", lw=0.8)
ax.set(xlabel=f"PC1 ({explained[0]:.1f}%)", ylabel=f"PC2 ({explained[1]:.1f}%)",
       title="PCA of log2 normalized expression (top 5,000 variable genes)")
ax.legend(title="Condition")
save_figure(fig, "01_pca_expression_corrected")

# Sample-to-sample correlation across the same variable genes.
corr = log_matrix.loc[variable_genes].corr(method="pearson")
corr.to_csv(OUT / "sample_correlation.tsv", sep="\t")
sample_labels = [f"{sid}\n{metadata.loc[sid, 'condition']}\n{metadata.loc[sid, 'donor']}" for sid in corr.index]
fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(corr, cmap="vlag", vmin=0.85, vmax=1.0, square=True, annot=True, fmt=".3f",
            xticklabels=sample_labels, yticklabels=sample_labels, ax=ax,
            cbar_kws={"label": "Pearson correlation"})
ax.set_title("Sample correlation (top 5,000 variable genes)")
ax.tick_params(axis="x", rotation=45, labelsize=8)
ax.tick_params(axis="y", rotation=0, labelsize=8)
save_figure(fig, "02_sample_correlation")

# Proper top-DEG heatmap with samples in columns and row-wise z scores.
sig = de[(de.padj < 0.05) & de.stat.notna()].copy()
top = sig.assign(abs_stat=sig.stat.abs()).nlargest(30, "abs_stat")
top_ids = [g for g in top.gene_id if g in log_matrix.index]
heat = log_matrix.loc[top_ids]
heat = heat.sub(heat.mean(axis=1), axis=0).div(heat.std(axis=1).replace(0, np.nan), axis=0)
symbol_map = de.drop_duplicates("gene_id").set_index("gene_id").gene_symbol
heat.index = [symbol_map.get(g) if pd.notna(symbol_map.get(g)) else g for g in top_ids]
fig, ax = plt.subplots(figsize=(11, 11))
sns.heatmap(heat, cmap="vlag", center=0, vmin=-2.5, vmax=2.5,
            xticklabels=sample_labels, yticklabels=True, ax=ax,
            cbar_kws={"label": "Row z-score of log2 normalized count"})
ax.set(title="Top 30 differential genes", xlabel="Sample / condition / donor", ylabel="Gene")
ax.tick_params(axis="x", rotation=45, labelsize=8)
ax.tick_params(axis="y", rotation=0, labelsize=9)
save_figure(fig, "03_top30_deg_heatmap_corrected")

# Volcano plot with gene symbols and explicit thresholds.
plot_de = de.dropna(subset=["log2FoldChange", "padj"]).copy()
plot_de["minus_log10_padj"] = -np.log10(plot_de.padj.clip(lower=np.finfo(float).tiny))
plot_de["class"] = "NS"
plot_de.loc[(plot_de.padj < 0.05) & (plot_de.log2FoldChange >= 1), "class"] = "Up"
plot_de.loc[(plot_de.padj < 0.05) & (plot_de.log2FoldChange <= -1), "class"] = "Down"
fig, ax = plt.subplots(figsize=(11, 8))
for cls, color in (("NS", "#BDBDBD"), ("Down", "#4C78A8"), ("Up", "#E45756")):
    frame = plot_de[plot_de["class"] == cls]
    ax.scatter(frame.log2FoldChange, frame.minus_log10_padj, s=14, alpha=0.58,
               color=color, label=f"{cls} (n={len(frame):,})", linewidth=0)
labels = pd.concat([
    plot_de[plot_de["class"] == "Up"].nsmallest(8, "padj"),
    plot_de[plot_de["class"] == "Down"].nsmallest(8, "padj"),
]).drop_duplicates("gene_id")
for _, row in labels.iterrows():
    label = row.gene_symbol if pd.notna(row.gene_symbol) else row.gene_id
    ax.annotate(label, (row.log2FoldChange, row.minus_log10_padj), xytext=(4, 4),
                textcoords="offset points", fontsize=8)
ax.axvline(-1, ls="--", lw=1, color="#777777")
ax.axvline(1, ls="--", lw=1, color="#777777")
ax.axhline(-math.log10(0.05), ls="--", lw=1, color="#777777")
ax.set(xlabel="log2 fold change (dex / untreated)", ylabel="−log10 adjusted p-value",
       title="Differential expression: dexamethasone versus untreated")
ax.legend(frameon=True)
save_figure(fig, "04_volcano_gene_symbols")


def pathway_panel(path: Path, method: str, stem: str, title: str) -> None:
    data = pd.read_csv(path, sep="\t")
    if method == "ORA":
        chosen = pd.concat([
            data[data.direction == "down"].nsmallest(6, "padj"),
            data[data.direction == "up"].nsmallest(6, "padj"),
        ])
        chosen["value"] = chosen.fold_enrichment
        xlabel = "Fold enrichment"
        size = np.clip(-np.log10(chosen.padj.clip(lower=1e-300)) * 18, 45, 300)
    else:
        chosen = pd.concat([
            data[data.direction == "down"].nsmallest(6, "padj"),
            data[data.direction == "up"].nsmallest(6, "padj"),
        ])
        chosen["value"] = chosen.nes
        xlabel = "Normalized enrichment score (NES)"
        size = np.clip(-np.log10(chosen.padj.clip(lower=1e-300)) * 40, 50, 320)
    chosen = chosen.sort_values("value")
    labels = [f"{short_term(t)} [{d}]" for t, d in zip(chosen.term, chosen.direction)]
    colors = [PALETTE["dex"] if d == "up" else PALETTE["untreated"] for d in chosen.direction]
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.scatter(chosen.value, np.arange(len(chosen)), s=size, c=colors, alpha=0.85,
               edgecolor="white", linewidth=0.6)
    ax.set_yticks(np.arange(len(chosen)), labels)
    ax.axvline(0 if method == "GSEA" else 1, color="#777777", lw=1, ls="--")
    ax.set(xlabel=xlabel, ylabel="", title=title)
    ax.text(0.99, 0.01, "Point size: −log10(FDR)", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=9, color="#555555")
    save_figure(fig, stem)


pathway_panel(TABLES / "go_overrepresentation_plot.tsv", "ORA", "05_go_ora_dotplot",
              "GO over-representation: strongest up/down terms")
pathway_panel(TABLES / "reactome_overrepresentation_plot.tsv", "ORA", "06_reactome_ora_dotplot",
              "Reactome over-representation: strongest up/down pathways")
pathway_panel(TABLES / "go_gsea_plot.tsv", "GSEA", "07_go_gsea_diverging",
              "GO preranked GSEA: strongest up/down terms")
pathway_panel(TABLES / "reactome_gsea_plot.tsv", "GSEA", "08_reactome_gsea_diverging",
              "Reactome preranked GSEA: strongest up/down pathways")

summary = {
    "samples": int(matrix.shape[1]),
    "genes_in_normalized_matrix": int(matrix.shape[0]),
    "pca_variable_genes": int(len(variable_genes)),
    "pc1_variance_percent": float(explained[0]),
    "pc2_variance_percent": float(explained[1]),
    "significant_padj_lt_0_05": int((de.padj < 0.05).sum()),
    "up_padj_lt_0_05_lfc_ge_1": int(((de.padj < 0.05) & (de.log2FoldChange >= 1)).sum()),
    "down_padj_lt_0_05_lfc_le_minus1": int(((de.padj < 0.05) & (de.log2FoldChange <= -1)).sum()),
    "input_sha256": {},
}
for path in [TABLES / "normalized_expression.tsv", TABLES / "annotated_differential_expression.tsv",
             TABLES / "go_overrepresentation_plot.tsv", TABLES / "reactome_overrepresentation_plot.tsv",
             TABLES / "go_gsea_plot.tsv", TABLES / "reactome_gsea_plot.tsv", META]:
    summary["input_sha256"][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
(OUT / "supplementary_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
