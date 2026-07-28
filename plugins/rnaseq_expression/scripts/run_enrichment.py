#!/usr/bin/env python3
"""Offline gene-symbol annotation, GO/Reactome ORA, and preranked GSEA."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import hypergeom


def bh_adjust(pvalues: pd.Series) -> pd.Series:
    values = pvalues.to_numpy(dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = np.minimum.accumulate((ranked * len(values) / np.arange(1, len(values) + 1))[::-1])[
        ::-1
    ]
    adjusted = np.minimum(adjusted, 1.0)
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return pd.Series(result, index=pvalues.index)


def parse_gtf_symbols(gtf: Path, wanted: set[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    gene_id_re = re.compile(r'gene_id "([^"]+)"')
    gene_name_re = re.compile(r'gene_name "([^"]+)"')
    with gtf.open() as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.split("\t", 8)
            if len(fields) < 9 or fields[2] != "gene":
                continue
            match_id = gene_id_re.search(fields[8])
            match_name = gene_name_re.search(fields[8])
            if match_id and match_name and match_id.group(1) in wanted:
                mapping[match_id.group(1)] = match_name.group(1)
    return mapping


def parse_go_ontology(
    go_obo: Path,
) -> tuple[dict[str, tuple[str, str]], dict[str, set[str]]]:
    names: dict[str, tuple[str, str]] = {}
    parents: dict[str, set[str]] = defaultdict(set)
    current: dict[str, object] = {}

    def store_term() -> None:
        term_id = str(current.get("id", ""))
        if term_id.startswith("GO:") and "name" in current and current.get("is_obsolete") != "true":
            names[term_id] = (
                str(current["name"]),
                str(current.get("namespace", "unknown")),
            )
            parents[term_id].update(current.get("parents", set()))

    with go_obo.open() as handle:
        for raw in handle:
            line = raw.rstrip()
            if line == "[Term]":
                store_term()
                current = {"parents": set()}
            elif not line:
                store_term()
                current = {}
            elif line.startswith("is_a: GO:"):
                parent = line.split()[1]
                current.setdefault("parents", set()).add(parent)
            elif line.startswith("relationship: part_of GO:"):
                parent = line.split()[2]
                current.setdefault("parents", set()).add(parent)
            elif ": " in line:
                key, value = line.split(": ", 1)
                if key in {"id", "name", "namespace", "is_obsolete"}:
                    current[key] = value
    store_term()
    return names, dict(parents)


def parse_go_names(go_obo: Path) -> dict[str, tuple[str, str]]:
    return parse_go_ontology(go_obo)[0]


def _go_ancestors(go_id: str, parents: dict[str, set[str]]) -> set[str]:
    found: set[str] = set()
    pending = list(parents.get(go_id, set()))
    while pending:
        parent = pending.pop()
        if parent in found:
            continue
        found.add(parent)
        pending.extend(parents.get(parent, set()))
    return found


def parse_go_sets(
    go_gaf: Path,
    universe: set[str],
    names: dict[str, tuple[str, str]],
    parents: dict[str, set[str]] | None = None,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    sets: dict[str, set[str]] = defaultdict(set)
    aspects: dict[str, str] = {}
    aspect_name = {"P": "BP", "F": "MF", "C": "CC"}
    with gzip.open(go_gaf, "rt") as handle:
        for line in handle:
            if line.startswith("!"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9 or "NOT" in fields[3].split("|"):
                continue
            symbol, go_id, aspect = fields[2], fields[4], fields[8]
            if symbol not in universe or go_id not in names or aspect not in aspect_name:
                continue
            target_ids = {go_id} | _go_ancestors(go_id, parents or {})
            for target_id in target_ids:
                if target_id not in names:
                    continue
                term_name, namespace = names[target_id]
                label = f"{target_id} | {term_name}"
                sets[label].add(symbol)
                aspects[label] = {
                    "biological_process": "BP",
                    "molecular_function": "MF",
                    "cellular_component": "CC",
                }.get(namespace, aspect_name[aspect])
    return dict(sets), aspects


def parse_reactome_sets(
    reactome_gmt: Path, universe: set[str]
) -> tuple[dict[str, set[str]], dict[str, str]]:
    sets: dict[str, set[str]] = {}
    stable_ids: dict[str, str] = {}
    with reactome_gmt.open() as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                continue
            name, stable_id, *genes = fields
            members = set(genes) & universe
            label = f"{stable_id} | {name}"
            sets[label] = members
            stable_ids[label] = stable_id
    return sets, stable_ids


def ora(
    selected: set[str],
    universe: set[str],
    gene_sets: dict[str, set[str]],
    source: str,
    direction: str,
    metadata: dict[str, str] | None = None,
    *,
    min_size: int,
    max_size: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    n_background = len(universe)
    n_selected = len(selected)
    for term, raw_members in gene_sets.items():
        members = raw_members & universe
        term_size = len(members)
        if term_size < min_size or term_size > max_size:
            continue
        overlap = selected & members
        pvalue = float(hypergeom.sf(len(overlap) - 1, n_background, term_size, n_selected))
        expected = n_selected * term_size / n_background
        rows.append(
            {
                "source": source,
                "aspect": metadata.get(term, "") if metadata else "",
                "direction": direction,
                "term": term,
                "overlap_count": len(overlap),
                "term_size": term_size,
                "selected_size": n_selected,
                "background_size": n_background,
                "fold_enrichment": len(overlap) / expected if expected else np.nan,
                "pvalue": pvalue,
                "overlap_genes": ",".join(sorted(overlap)),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["padj"] = bh_adjust(result["pvalue"])
    return result.sort_values(["padj", "pvalue", "term"])


def run_prerank(
    ranking: pd.DataFrame,
    gene_sets: dict[str, set[str]],
    source: str,
    aspect: str,
    *,
    min_size: int,
    max_size: int,
    permutations: int,
    seed: int,
    threads: int,
) -> pd.DataFrame:
    try:
        import gseapy as gp
    except ImportError as exc:
        raise RuntimeError(
            "rnaseq_enrichment requires gseapy==1.3.0 in the rnaseq environment"
        ) from exc

    eligible = {
        name: sorted(genes)
        for name, genes in gene_sets.items()
        if min_size <= len(genes) <= max_size
    }
    result = gp.prerank(
        rnk=ranking[["symbol", "stat"]],
        gene_sets=eligible,
        min_size=min_size,
        max_size=max_size,
        permutation_num=permutations,
        weight=1.0,
        ascending=False,
        threads=threads,
        seed=seed,
        outdir=None,
        no_plot=True,
        verbose=True,
    ).res2d.copy()
    rename = {
        "Term": "term",
        "ES": "es",
        "NES": "nes",
        "NOM p-val": "pvalue",
        "FDR q-val": "padj",
        "FWER p-val": "fwer_pvalue",
        "Tag %": "tag_fraction",
        "Gene %": "gene_fraction",
        "Lead_genes": "leading_edge_genes",
    }
    result = result.rename(columns=rename)
    result["source"] = source
    result["aspect"] = aspect
    result["direction"] = np.where(result["nes"].astype(float) >= 0, "up", "down")
    keep = [
        "source",
        "aspect",
        "direction",
        "term",
        "es",
        "nes",
        "pvalue",
        "padj",
        "fwer_pvalue",
        "tag_fraction",
        "gene_fraction",
        "leading_edge_genes",
    ]
    return result[keep].sort_values(["padj", "pvalue", "term"])


def _top_by_direction(
    table: pd.DataFrame,
    top_n: int,
    *,
    max_padj: float,
) -> pd.DataFrame:
    if table.empty:
        return table
    significant = table.copy()
    significant["padj"] = pd.to_numeric(significant["padj"], errors="coerce")
    significant["pvalue"] = pd.to_numeric(significant["pvalue"], errors="coerce")
    significant = significant[significant["padj"].lt(max_padj)]
    ordered = significant.sort_values(["direction", "padj", "pvalue", "term"])
    return ordered.groupby("direction", sort=False, group_keys=False).head(top_n)


def _add_plot_columns(table: pd.DataFrame, method: str) -> pd.DataFrame:
    result = table.copy()
    if result.empty:
        return result
    result["gene_symbols"] = result.get("overlap_genes", result.get("leading_edge_genes", ""))
    if method == "ORA":
        adjusted = pd.to_numeric(result["padj"], errors="coerce").clip(lower=1e-300)
        result["score"] = -np.log10(adjusted)
    else:
        result["score"] = pd.to_numeric(result["nes"], errors="coerce")
    term_label = result["term"].str.replace(r"^[^|]+\|\s*", "", regex=True)
    genes = result["gene_symbols"].fillna("").astype(str).str.replace(";", ",", regex=False)
    genes = genes.str.split(",").str[:2].str.join(",")
    result["plot_label"] = (
        term_label.str.slice(0, 32) + " [" + result["direction"].astype(str) + ": " + genes + "]"
    )
    result["method"] = method
    return result


def _write_table(table: pd.DataFrame, path: Path, columns: list[str]) -> None:
    output = table.reindex(columns=columns)
    output.to_csv(path, sep="\t", index=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_record(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": _sha256(path)}


def _gtf_header(path: Path) -> list[str]:
    header: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("#"):
                break
            header.append(line.rstrip())
            if len(header) >= 50:
                break
    return header


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline gene-symbol annotation, GO/Reactome ORA, and preranked GSEA."
    )
    parser.add_argument("--de-results", required=True, type=Path)
    parser.add_argument("--annotation-gtf", required=True, type=Path)
    parser.add_argument("--go-obo", required=True, type=Path)
    parser.add_argument("--go-gaf", required=True, type=Path)
    parser.add_argument("--reactome-gmt", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--annotation-release", default="GRCh37.75")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--rank-column", default="stat")
    parser.add_argument("--permutations", type=int, default=1000)
    parser.add_argument("--gsea-fdr", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--min-size", type=int, default=15)
    parser.add_argument("--max-size", type=int, default=500)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--threads", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not np.isfinite(args.gsea_fdr) or not 0 < args.gsea_fdr <= 1:
        raise ValueError("--gsea-fdr must be in the interval (0, 1]")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    de = pd.read_csv(args.de_results, sep="\t")
    required = {"gene_id", "log2FoldChange", "padj", args.rank_column}
    missing = sorted(required - set(de.columns))
    if missing:
        raise ValueError(f"DESeq2 result is missing required columns: {missing}")

    gene_ids = de["gene_id"].astype(str).str.split(".").str[0]
    symbol_map = parse_gtf_symbols(args.annotation_gtf, set(gene_ids))
    de["gene_id"] = gene_ids
    de["gene_symbol"] = de["gene_id"].map(symbol_map).fillna("")
    de["comparison"] = de.get("comparison", "")
    de.to_csv(args.output_dir / "annotated_differential_expression.tsv", sep="\t", index=False)

    ranked = de[de["gene_symbol"].ne("") & de[args.rank_column].notna()].copy()
    ranked["abs_rank"] = pd.to_numeric(ranked[args.rank_column], errors="coerce").abs()
    ranked = ranked.sort_values("abs_rank", ascending=False).drop_duplicates("gene_symbol")
    ranked = ranked.dropna(subset=[args.rank_column]).sort_values(args.rank_column, ascending=False)
    ranking_universe = set(ranked["gene_symbol"])
    ora_ranked = ranked[ranked["padj"].notna()].copy()
    ora_universe = set(ora_ranked["gene_symbol"])
    up = set(
        ora_ranked.loc[
            ora_ranked["padj"].lt(args.alpha) & ora_ranked["log2FoldChange"].gt(0),
            "gene_symbol",
        ]
    )
    down = set(
        ora_ranked.loc[
            ora_ranked["padj"].lt(args.alpha) & ora_ranked["log2FoldChange"].lt(0),
            "gene_symbol",
        ]
    )

    go_names, go_parents = parse_go_ontology(args.go_obo)
    go_sets, go_aspects = parse_go_sets(args.go_gaf, ranking_universe, go_names, go_parents)
    reactome_sets, reactome_ids = parse_reactome_sets(args.reactome_gmt, ranking_universe)
    ora_tables: list[pd.DataFrame] = []
    for source, sets, metadata in (
        ("GO", go_sets, go_aspects),
        ("Reactome", reactome_sets, reactome_ids),
    ):
        source_results = []
        for direction, selected in (("up", up), ("down", down)):
            source_results.append(
                ora(
                    selected,
                    ora_universe,
                    sets,
                    source,
                    direction,
                    metadata,
                    min_size=args.min_size,
                    max_size=args.max_size,
                )
            )
        available = [table for table in source_results if not table.empty]
        combined = pd.concat(available, ignore_index=True) if available else pd.DataFrame()
        ora_tables.append(_add_plot_columns(combined, "ORA"))

    ranking = ranked[["gene_symbol", args.rank_column]].rename(
        columns={"gene_symbol": "symbol", args.rank_column: "stat"}
    )
    go_bp = {term: genes for term, genes in go_sets.items() if go_aspects[term] == "BP"}
    gsea_tables = []
    for source, aspect, sets in (
        ("GO", "BP", go_bp),
        ("Reactome", "", reactome_sets),
    ):
        result = run_prerank(
            ranking,
            sets,
            source,
            aspect,
            min_size=args.min_size,
            max_size=args.max_size,
            permutations=args.permutations,
            seed=args.seed,
            threads=args.threads,
        )
        gsea_tables.append(_add_plot_columns(result, "GSEA"))

    ora_columns = [
        "source",
        "aspect",
        "direction",
        "term",
        "plot_label",
        "score",
        "overlap_count",
        "term_size",
        "selected_size",
        "background_size",
        "fold_enrichment",
        "pvalue",
        "padj",
        "gene_symbols",
        "method",
    ]
    gsea_columns = [
        "source",
        "aspect",
        "direction",
        "term",
        "plot_label",
        "score",
        "es",
        "nes",
        "pvalue",
        "padj",
        "fwer_pvalue",
        "tag_fraction",
        "gene_fraction",
        "gene_symbols",
        "method",
    ]
    _write_table(ora_tables[0], args.output_dir / "go_overrepresentation.tsv", ora_columns)
    _write_table(ora_tables[1], args.output_dir / "reactome_overrepresentation.tsv", ora_columns)
    _write_table(gsea_tables[0], args.output_dir / "go_gsea.tsv", gsea_columns)
    _write_table(gsea_tables[1], args.output_dir / "reactome_gsea.tsv", gsea_columns)
    _write_table(
        _top_by_direction(ora_tables[0], args.top_n, max_padj=args.alpha),
        args.output_dir / "go_overrepresentation_plot.tsv",
        ora_columns,
    )
    _write_table(
        _top_by_direction(ora_tables[1], args.top_n, max_padj=args.alpha),
        args.output_dir / "reactome_overrepresentation_plot.tsv",
        ora_columns,
    )
    _write_table(
        _top_by_direction(gsea_tables[0], args.top_n, max_padj=args.gsea_fdr),
        args.output_dir / "go_gsea_plot.tsv",
        gsea_columns,
    )
    _write_table(
        _top_by_direction(gsea_tables[1], args.top_n, max_padj=args.gsea_fdr),
        args.output_dir / "reactome_gsea_plot.tsv",
        gsea_columns,
    )

    manifest = {
        "method": "offline GO/Reactome ORA and GSEApy prerank",
        "annotation_release": args.annotation_release,
        "rank_column": args.rank_column,
        "alpha": args.alpha,
        "permutations": args.permutations,
        "gsea_plot_fdr": args.gsea_fdr,
        "seed": args.seed,
        "min_size": args.min_size,
        "max_size": args.max_size,
        "top_n_per_direction": args.top_n,
        "ranked_gene_symbols": len(ranking_universe),
        "ora_background_symbols": len(ora_universe),
        "significant_up_symbols": len(up),
        "significant_down_symbols": len(down),
        "resources": {
            "annotation_gtf": _resource_record(args.annotation_gtf),
            "go_obo": _resource_record(args.go_obo),
            "go_gaf": _resource_record(args.go_gaf),
            "reactome_gmt": _resource_record(args.reactome_gmt),
        },
        "gtf_header": _gtf_header(args.annotation_gtf),
        "software": {
            package: importlib.metadata.version(package)
            for package in ("gseapy", "numpy", "pandas", "scipy")
        },
        "script": _resource_record(Path(__file__)),
    }
    (args.output_dir / "enrichment_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
