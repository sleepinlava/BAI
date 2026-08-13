from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
DERIVED = ROOT / "derived"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write empty derived dataset: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(datasets: dict[str, list[dict[str, object]]]) -> None:
    path = DERIVED / "analysis.sqlite"
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        for table, rows in datasets.items():
            if not rows:
                continue
            fields = list(rows[0])
            column_types: list[str] = []
            for field in fields:
                values = [row[field] for row in rows if row[field] is not None]
                if values and all(isinstance(value, bool | int) for value in values):
                    column_types.append("INTEGER")
                elif values and all(isinstance(value, int | float) for value in values):
                    column_types.append("REAL")
                else:
                    column_types.append("TEXT")
            columns_sql = ", ".join(
                f'"{field}" {column_type}'
                for field, column_type in zip(fields, column_types, strict=True)
            )
            connection.execute(f'CREATE TABLE "{table}" ({columns_sql})')
            placeholders = ", ".join("?" for _ in fields)
            connection.executemany(
                f'INSERT INTO "{table}" VALUES ({placeholders})',
                [[row[field] for field in fields] for row in rows],
            )
        connection.commit()
    finally:
        connection.close()


def fasta_records(path: Path) -> list[tuple[str, int]]:
    records: list[tuple[str, int]] = []
    name: str | None = None
    length = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith(">"):
                if name is not None:
                    records.append((name, length))
                name = line[1:].split()[0]
                length = 0
            else:
                length += len(line)
    if name is not None:
        records.append((name, length))
    return records


def base_contig(value: str) -> str:
    return value.split()[0]


def as_float(value: str) -> float:
    return float(value) if value not in {"", None} else 0.0


def source(source_id: str, label: str, path: str, description: str) -> dict[str, object]:
    table = Path(path).stem
    return {
        "id": source_id,
        "label": label,
        "path": "derived/analysis.sqlite",
        "query": {
            "engine": "sqlite",
            "language": "sql",
            "description": description,
            "sql": f'SELECT * FROM "{table}"',
            "tables_used": [table],
            "filters": ["固定样本快照：SRR11038083"],
        },
    }


def main() -> None:
    main_tables = SOURCE / "main" / "tables"
    follow_tables = SOURCE / "followup" / "tables"
    amrf_tables = SOURCE / "amrfinder" / "tables"

    fasta = fasta_records(SOURCE / "main" / "plasmid_contigs.fasta")
    consensus = read_tsv(main_tables / "plasmid_consensus.tsv")
    abundance = read_tsv(main_tables / "abundance.tsv")
    predictions = [
        row
        for row in read_tsv(main_tables / "plasmid_predictions.tsv")
        if row["tool"] == "genomad"
    ]
    typing = read_tsv(main_tables / "plasmid_typing.tsv")
    annotations = read_tsv(main_tables / "annotations.tsv")
    sample_qc = read_tsv(main_tables / "sample_qc.tsv")[0]
    assembly_qc = read_tsv(main_tables / "assembly_qc.tsv")[0]
    follow_amr = read_tsv(follow_tables / "amr_genes.tsv")
    amrf_amr = read_tsv(amrf_tables / "amr_genes.tsv")
    command_rows: list[dict[str, object]] = []
    for run_label in ("main", "followup", "amrfinder"):
        for row in read_tsv(SOURCE / run_label / "provenance" / "commands.tsv"):
            command_rows.append({"run_label": run_label, **row})

    if not (len(fasta) == len(consensus) == len(abundance) == len(predictions) == 156):
        raise ValueError("Candidate row counts do not agree at 156")

    abundance_by_id = {row["contig_id"]: row for row in abundance}
    prediction_by_id = {row["contig_id"]: row for row in predictions}
    consensus_by_id = {row["contig_id"]: row for row in consensus}

    typing_by_id: dict[str, list[dict[str, str]]] = {}
    for row in typing:
        typing_by_id.setdefault(base_contig(row["contig_id"]), []).append(row)

    region_lengths = {
        int(row["contig_id"].split("_")[1]): int(row["end"])
        for row in annotations
        if row["category"] == "region" and row["contig_id"].startswith("contig_")
    }
    if len(region_lengths) != 156:
        raise ValueError("Bakta region mapping does not contain 156 contigs")
    for index, (_, length) in enumerate(fasta, start=1):
        if region_lengths[index] != length:
            raise ValueError(f"Bakta-to-FASTA order mapping failed at contig_{index}")

    candidate_rows: list[dict[str, object]] = []
    for rank, (contig_id, length) in enumerate(fasta, start=1):
        abundance_row = abundance_by_id[contig_id]
        prediction = prediction_by_id[contig_id]
        types = typing_by_id.get(contig_id, [])
        type_ids = "; ".join(sorted({row["type_id"] for row in types})) or "未分型"
        candidate_rows.append(
            {
                "contig_id": contig_id,
                "fasta_order": rank,
                "length_bp": length,
                "length_kb": round(length / 1000, 3),
                "plasmid_score": round(as_float(prediction["score"]), 4),
                "topology": prediction["circularity"],
                "coverage": round(as_float(abundance_row["coverage"]), 4),
                "tpm": round(as_float(abundance_row["tpm"]), 4),
                "log10_tpm": round(math.log10(as_float(abundance_row["tpm"]) + 1), 4),
                "replicon_type": type_ids,
                "typed": "已分型" if types else "未分型",
                "finding_group": (
                    "blaTEM-116 候选" if contig_id == "k141_775" else
                    "arsB–arsC–arsH 候选" if contig_id == "k141_1187" else "其他候选"
                ),
            }
        )

    candidate_rows.sort(key=lambda row: str(row["contig_id"]))
    lengths = [int(row["length_bp"]) for row in candidate_rows]
    tpms = [float(row["tpm"]) for row in candidate_rows]

    length_bins = [
        ("<1 kb", 0, 1000),
        ("1–2 kb", 1000, 2000),
        ("2–5 kb", 2000, 5000),
        ("5–10 kb", 5000, 10000),
        ("≥10 kb", 10000, math.inf),
    ]
    length_distribution = []
    for order, (label, low, high) in enumerate(length_bins, start=1):
        count = sum(low <= length < high for length in lengths)
        length_distribution.append(
            {
                "bin": label,
                "bin_order": order,
                "candidate_count": count,
                "candidate_share": round(count / len(lengths), 4),
                "denominator": len(lengths),
            }
        )

    abundance_ranked = sorted(candidate_rows, key=lambda row: float(row["tpm"]), reverse=True)
    top_abundance = []
    for rank, row in enumerate(abundance_ranked[:12], start=1):
        top_abundance.append(
            {
                "rank": rank,
                "contig_id": row["contig_id"],
                "tpm": row["tpm"],
                "coverage": row["coverage"],
                "length_bp": row["length_bp"],
                "replicon_type": row["replicon_type"],
                "finding_group": row["finding_group"],
            }
        )

    typing_counts = Counter(row["type_id"] for row in typing)
    typing_distribution = [
        {
            "replicon_type": type_id,
            "hit_count": count,
            "unique_contigs": len(
                {base_contig(row["contig_id"]) for row in typing if row["type_id"] == type_id}
            ),
            "scheme": "PlasmidFinder",
        }
        for type_id, count in sorted(typing_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    category_counts = Counter(row["category"] or "未分类" for row in annotations)
    annotation_categories = [
        {
            "category": category,
            "feature_count": count,
            "feature_share": round(count / len(annotations), 4),
            "total_features": len(annotations),
        }
        for category, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    amr_evidence = [
        {
            "evidence_source": "Bakta",
            "target": "blaTEM-116",
            "detected": 1,
            "identity_pct": None,
            "coverage_pct": None,
            "interpretation": "功能注释命中",
        },
        {
            "evidence_source": "ABRicate / CARD",
            "target": follow_amr[0]["gene"],
            "detected": 1,
            "identity_pct": float(follow_amr[0]["identity"]),
            "coverage_pct": float(follow_amr[0]["coverage"]),
            "interpretation": "数据库序列命中",
        },
        {
            "evidence_source": "AMRFinderPlus",
            "target": amrf_amr[0]["gene"],
            "detected": 1,
            "identity_pct": float(amrf_amr[0]["identity"]),
            "coverage_pct": float(amrf_amr[0]["coverage"]),
            "interpretation": "独立数据库序列命中",
        },
        {
            "evidence_source": "RGI",
            "target": "未检出",
            "detected": 0,
            "identity_pct": None,
            "coverage_pct": None,
            "interpretation": "原始输出为空对象 {}",
        },
    ]

    feature_map = []
    for row in annotations:
        if row["contig_id"] not in {"contig_74", "contig_154"} or row["category"] == "region":
            continue
        mapped_contig = "k141_775" if row["contig_id"] == "contig_74" else "k141_1187"
        feature_map.append(
            {
                "contig_id": mapped_contig,
                "start": int(row["start"]),
                "end": int(row["end"]),
                "strand": row["strand"] or "未定",
                "gene": row["gene"],
                "product": row["product"].replace("%2C", ","),
                "category": row["category"],
                "feature_length_bp": int(row["end"]) - int(row["start"]) + 1,
            }
        )
    feature_map.sort(key=lambda row: (str(row["contig_id"]), int(row["start"])))

    integron_rows = []
    with (SOURCE / "followup" / "plasmid_contigs.summary").open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#") or line.startswith("ID_replicon") or not line.strip():
                continue
            contig_id, calin, complete, in0, topology, size = line.rstrip("\n").split("\t")
            integron_rows.append(
                {
                    "contig_id": contig_id,
                    "CALIN": int(calin),
                    "complete": int(complete),
                    "In0": int(in0),
                    "topology": topology,
                    "size_bp": int(size),
                    "integron_positive": int(calin) + int(complete) + int(in0) > 0,
                }
            )
    if len(integron_rows) != 156:
        raise ValueError("IntegronFinder summary does not contain 156 candidates")
    integron_positive = sum(bool(row["integron_positive"]) for row in integron_rows)

    k775 = next(row for row in candidate_rows if row["contig_id"] == "k141_775")
    k1187 = next(row for row in candidate_rows if row["contig_id"] == "k141_1187")
    k775_rank = next(i for i, row in enumerate(abundance_ranked, start=1) if row["contig_id"] == "k141_775")
    k1187_rank = next(i for i, row in enumerate(abundance_ranked, start=1) if row["contig_id"] == "k141_1187")

    summary = [{
        "raw_reads": int(sample_qc["raw_reads"]),
        "clean_reads": int(sample_qc["clean_reads"]),
        "read_retention": round(int(sample_qc["clean_reads"]) / int(sample_qc["raw_reads"]), 6),
        "q30_rate": float(sample_qc["q30"]),
        "assembly_contigs": 3641,
        "assembly_n50_bp": int(assembly_qc["n50"]),
        "assembly_total_bp": int(assembly_qc["total_length"]),
        "candidate_count": len(candidate_rows),
        "candidate_total_bp": sum(lengths),
        "candidate_median_bp": round(statistics.median(lengths), 1),
        "candidate_max_bp": max(lengths),
        "typed_contigs": len(typing_by_id),
        "typing_hits": len(typing),
        "bakta_features": len(annotations),
        "amr_candidate_count": 1,
        "integron_positive": integron_positive,
        "integron_tested": len(integron_rows),
        "median_tpm": round(statistics.median(tpms), 4),
        "k141_775_tpm": k775["tpm"],
        "k141_775_abundance_rank": k775_rank,
        "k141_1187_tpm": k1187["tpm"],
        "k141_1187_abundance_rank": k1187_rank,
    }]

    write_csv(DERIVED / "summary.csv", summary)
    write_csv(DERIVED / "candidate_detail.csv", candidate_rows)
    write_csv(DERIVED / "length_distribution.csv", length_distribution)
    write_csv(DERIVED / "top_abundance.csv", top_abundance)
    write_csv(DERIVED / "typing_distribution.csv", typing_distribution)
    write_csv(DERIVED / "annotation_categories.csv", annotation_categories)
    write_csv(DERIVED / "amr_evidence.csv", amr_evidence)
    write_csv(DERIVED / "feature_map.csv", feature_map)
    write_csv(DERIVED / "integron_summary.csv", integron_rows)
    write_sqlite({
        "summary": summary,
        "candidate_detail": candidate_rows,
        "key_contigs": [
            row for row in candidate_rows if row["contig_id"] in {"k141_775", "k141_1187"}
        ],
        "length_distribution": length_distribution,
        "top_abundance": top_abundance,
        "typing_distribution": typing_distribution,
        "annotation_categories": annotation_categories,
        "amr_evidence": amr_evidence,
        "feature_map": feature_map,
        "integron_summary": integron_rows,
        "commands": command_rows,
    })

    generated_at = "2026-08-11T23:00:12+08:00"
    sources = [
        source("derived_summary", "ABI 派生汇总", "derived/summary.csv", "从 ABI 标准表计算样本、候选质粒、分型、AMR 与整合子汇总指标。"),
        source("candidate_detail", "候选质粒明细", "derived/candidate_detail.csv", "合并 plasmid_consensus、geNomad predictions、CoverM abundance、PlasmidFinder typing 与候选 FASTA。"),
        source("length_distribution", "候选长度分布", "derived/length_distribution.csv", "按预设区间统计 156 个最终质粒候选的长度分布。"),
        source("top_abundance", "候选丰度排名", "derived/top_abundance.csv", "按 CoverM TPM 对候选质粒降序排列并保留前 12 名。"),
        source("typing_distribution", "PlasmidFinder 分型分布", "derived/typing_distribution.csv", "统计 PlasmidFinder 复制子类型命中数和独特 contig 数。"),
        source("annotation_categories", "Bakta 注释类别", "derived/annotation_categories.csv", "统计 Bakta 标准 annotations 表中的功能要素类别。"),
        source("amr_evidence", "AMR 工具证据矩阵", "derived/amr_evidence.csv", "汇总 Bakta、ABRicate/CARD、AMRFinderPlus 和 RGI 对 blaTEM-116 的独立证据。"),
        source("feature_map", "关键 contig 功能坐标", "derived/feature_map.csv", "基于候选 FASTA 顺序与 Bakta region 长度一致性映射 contig_74→k141_775、contig_154→k141_1187。"),
        source("integron_summary", "IntegronFinder 候选汇总", "derived/integron_summary.csv", "解析 IntegronFinder 2.0.6 summary，统计 CALIN、complete 与 In0。"),
        source("abi_provenance", "ABI provenance", "source/main/provenance/commands.tsv", "ABI 主流程、下游补充流程和 AMRFinderPlus 恢复流程的执行状态与工具命令。"),
    ]

    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "SRR11038083 宏基因组质粒分析图表汇总",
            "description": "ABI 标准结果驱动的候选质粒、丰度、分型、功能注释与耐药证据技术报告。",
            "generatedAt": generated_at,
            "sources": sources,
            "cards": [
                {"id": "clean_reads", "description": "fastp 清洗后保留的读段数。", "dataset": "summary", "sourceId": "derived_summary", "metrics": [{"label": "清洗后 reads", "field": "clean_reads", "format": "number"}, {"label": "保留率", "field": "read_retention", "format": "percent"}]},
                {"id": "candidates", "description": "geNomad 最终质粒候选数。", "dataset": "summary", "sourceId": "derived_summary", "metrics": [{"label": "质粒候选", "field": "candidate_count", "format": "number"}, {"label": "总长度 bp", "field": "candidate_total_bp", "format": "number"}]},
                {"id": "typed", "description": "具有 PlasmidFinder 复制子命中的独特候选。", "dataset": "summary", "sourceId": "derived_summary", "metrics": [{"label": "已分型 contigs", "field": "typed_contigs", "format": "number"}, {"label": "分型命中", "field": "typing_hits", "format": "number"}]},
                {"id": "amr", "description": "获得独立序列数据库支持的 AMR 候选数量。", "dataset": "summary", "sourceId": "derived_summary", "metrics": [{"label": "AMR 候选", "field": "amr_candidate_count", "format": "number"}, {"label": "整合子阳性", "field": "integron_positive", "format": "number"}]},
                {"id": "annotation", "description": "Bakta 标准表中记录的全部功能要素。", "dataset": "summary", "sourceId": "derived_summary", "metrics": [{"label": "Bakta 要素", "field": "bakta_features", "format": "number"}, {"label": "中位候选长度 bp", "field": "candidate_median_bp", "format": "number"}]},
            ],
            "charts": [
                {"id": "length_chart", "title": "质粒候选长度分布", "subtitle": "156 个最终候选，分箱单位为 bp/kb。", "type": "bar", "dataset": "length_distribution", "sourceId": "length_distribution", "encodings": {"x": {"field": "bin", "type": "ordinal", "label": "长度区间"}, "y": {"field": "candidate_count", "type": "quantitative", "label": "候选数"}}, "valueFormat": "number", "layout": "full"},
                {"id": "length_abundance_scatter", "title": "候选长度与相对丰度", "subtitle": "每点为一个候选；纵轴为 log10(TPM+1)，突出两个关键 contig。", "type": "scatter", "dataset": "candidate_detail", "sourceId": "candidate_detail", "encodings": {"x": {"field": "length_kb", "type": "quantitative", "label": "长度 (kb)"}, "y": {"field": "log10_tpm", "type": "quantitative", "label": "log10(TPM+1)"}, "color": {"field": "finding_group", "type": "nominal", "label": "证据组"}}, "layout": "full"},
                {"id": "top_abundance_chart", "title": "高丰度质粒候选", "subtitle": "CoverM TPM 排名前 12；用于识别样本中的优势候选。", "type": "bar", "dataset": "top_abundance", "sourceId": "top_abundance", "encodings": {"x": {"field": "contig_id", "type": "nominal", "label": "候选 contig"}, "y": {"field": "tpm", "type": "quantitative", "label": "TPM"}}, "valueFormat": "number", "layout": "full"},
                {"id": "typing_chart", "title": "PlasmidFinder 复制子类型分布", "subtitle": "9 条命中记录覆盖 8 个独特候选；Col(MG828) 出现 3 次。", "type": "bar", "dataset": "typing_distribution", "sourceId": "typing_distribution", "encodings": {"x": {"field": "replicon_type", "type": "nominal", "label": "复制子类型"}, "y": {"field": "hit_count", "type": "quantitative", "label": "命中数"}}, "valueFormat": "number", "layout": "full"},
                {"id": "annotation_chart", "title": "Bakta 功能要素类别", "subtitle": "602 条标准注释记录，region 行保留用于候选边界核验。", "type": "bar", "dataset": "annotation_categories", "sourceId": "annotation_categories", "encodings": {"x": {"field": "category", "type": "nominal", "label": "注释类别"}, "y": {"field": "feature_count", "type": "quantitative", "label": "要素数"}}, "valueFormat": "number", "layout": "full"},
                {"id": "amr_chart", "title": "blaTEM-116 工具证据", "subtitle": "1 表示检出，0 表示未检出；IntegronFinder 不属于 ARG 检测工具，单独报告。", "type": "bar", "dataset": "amr_evidence", "sourceId": "amr_evidence", "encodings": {"x": {"field": "evidence_source", "type": "nominal", "label": "证据来源"}, "y": {"field": "detected", "type": "quantitative", "label": "检出状态"}}, "valueFormat": "number", "layout": "full"},
            ],
            "tables": [
                {"id": "key_contigs", "title": "关键候选质粒明细", "subtitle": "AMR 与砷抗性候选的长度、丰度、分型与 geNomad 分数。", "dataset": "key_contigs", "sourceId": "candidate_detail", "defaultSort": {"field": "contig_id", "direction": "asc"}, "density": "spacious", "layout": "full", "columns": [{"field": "contig_id", "label": "Contig", "type": "text"}, {"field": "finding_group", "label": "证据组", "type": "text"}, {"field": "length_bp", "label": "长度 bp", "format": "number"}, {"field": "plasmid_score", "label": "geNomad 分数", "format": "number"}, {"field": "tpm", "label": "TPM", "format": "number"}, {"field": "replicon_type", "label": "复制子类型", "type": "text"}, {"field": "topology", "label": "末端结构", "type": "text"}]},
                {"id": "amr_table", "title": "AMR 证据矩阵", "subtitle": "数据库序列命中与功能注释并列展示；空结果不视为反向证明。", "dataset": "amr_evidence", "sourceId": "amr_evidence", "defaultSort": {"field": "detected", "direction": "desc"}, "density": "spacious", "layout": "full", "columns": [{"field": "evidence_source", "label": "工具/数据库", "type": "text"}, {"field": "target", "label": "目标", "type": "text"}, {"field": "detected", "label": "检出", "format": "number"}, {"field": "identity_pct", "label": "一致性 %", "format": "number"}, {"field": "coverage_pct", "label": "覆盖度 %", "format": "number"}, {"field": "interpretation", "label": "证据类型", "type": "text"}]},
                {"id": "feature_table", "title": "关键 contig 功能坐标", "subtitle": "k141_775 与 k141_1187 的 Bakta 功能要素，按坐标排序。", "dataset": "feature_map", "sourceId": "feature_map", "defaultSort": {"field": "start", "direction": "asc"}, "density": "dense", "layout": "full", "columns": [{"field": "contig_id", "label": "Contig", "type": "text"}, {"field": "start", "label": "起点", "format": "number"}, {"field": "end", "label": "终点", "format": "number"}, {"field": "strand", "label": "链", "type": "text"}, {"field": "gene", "label": "基因/要素", "type": "text"}, {"field": "product", "label": "产物", "type": "text"}, {"field": "category", "label": "类别", "type": "text"}]},
                {"id": "candidate_table", "title": "候选质粒审计表", "subtitle": "全部 156 个最终候选，可按长度、丰度、分数和分型状态检查。", "dataset": "candidate_detail", "sourceId": "candidate_detail", "defaultSort": {"field": "tpm", "direction": "desc"}, "density": "dense", "layout": "full", "columns": [{"field": "contig_id", "label": "Contig", "type": "text"}, {"field": "length_bp", "label": "长度 bp", "format": "number"}, {"field": "plasmid_score", "label": "geNomad 分数", "format": "number"}, {"field": "coverage", "label": "覆盖度", "format": "number"}, {"field": "tpm", "label": "TPM", "format": "number"}, {"field": "topology", "label": "末端结构", "type": "text"}, {"field": "replicon_type", "label": "复制子类型", "type": "text"}, {"field": "finding_group", "label": "证据组", "type": "text"}]},
            ],
            "blocks": [
                {"id": "title", "type": "markdown", "body": "# SRR11038083 宏基因组质粒分析图表汇总"},
                {"id": "technical_summary", "type": "markdown", "body": "## 技术摘要\n\nABI 从 **34.3M 条清洗后 reads** 组装并筛得 **156 个质粒候选**。核心发现是 `k141_775` 上的 `blaTEM-116`：Bakta、ABRicate/CARD 与独立 AMRFinderPlus 均支持该位点，其中两个序列数据库工具均为 **100% 覆盖、100% 一致性**。该 contig 同时具有 Col(pHAD28) 分型、复制相关要素、oriT 与 MobA，提示具备质粒复制和潜在动员相关结构，但本分析未检测到整合子，也不能由序列结果直接推断耐药表型或真实水平转移。"},
                {"id": "headline_metrics", "type": "metric-strip", "cardIds": ["clean_reads", "candidates", "typed", "amr", "annotation"]},
                {"id": "candidate_section", "type": "markdown", "body": "## 156 个候选呈现小型质粒片段为主、丰度跨度大的结构\n\n长度分布用于判断候选目录的完整性与碎片化程度；长度–丰度散点则把结构规模与样本内相对丰度放在同一观察尺度。`k141_775` 和 `k141_1187` 均位于中等长度、较高丰度区域，但不是样本丰度最高的候选，因此其生物学重要性来自功能负载而非单纯优势度。"},
                {"id": "length_chart_block", "type": "chart", "chartId": "length_chart", "layout": "full"},
                {"id": "scatter_block", "type": "chart", "chartId": "length_abundance_scatter", "layout": "full"},
                {"id": "abundance_section", "type": "markdown", "body": "## 优势候选与关键功能候选并不完全重合\n\nTop 12 TPM 排名显示样本中存在少数高丰度候选。AMR 与砷抗性 contig 需要在完整排名中结合功能解释，不能仅凭丰度高低判定风险。"},
                {"id": "abundance_chart_block", "type": "chart", "chartId": "top_abundance_chart", "layout": "full"},
                {"id": "typing_section", "type": "markdown", "body": "## PlasmidFinder 仅覆盖候选目录的一小部分\n\n156 个候选中只有 8 个独特 contig 获得复制子分型，说明大多数候选没有被当前 PlasmidFinder 数据库命名。`k141_775` 的 Col(pHAD28) 命中一致性为 92.37%，应视为类型相似性证据，而不是完整质粒闭环鉴定。"},
                {"id": "typing_chart_block", "type": "chart", "chartId": "typing_chart", "layout": "full"},
                {"id": "annotation_section", "type": "markdown", "body": "## Bakta 注释显示复制、动员与稳定维持要素广泛存在\n\n602 条标准注释不仅包括 CDS，也保留 region、oriT、oriC 和 ncRNA 等结构要素。类别分布用于说明注释组成；具体功能判断仍以基因级坐标表为准。"},
                {"id": "annotation_chart_block", "type": "chart", "chartId": "annotation_chart", "layout": "full"},
                {"id": "amr_section", "type": "markdown", "body": "## `k141_775` 的 `blaTEM-116` 获得双数据库独立确认\n\nABRicate/CARD 与 AMRFinderPlus 都在 `k141_775` 的约 2.15–3.01 kb 区间给出 100% 覆盖和 100% 一致性命中；Bakta 同位点功能注释一致。RGI 原始结果为 `{}`，这反映工具/阈值差异，不能抵消两个阳性数据库证据。"},
                {"id": "amr_chart_block", "type": "chart", "chartId": "amr_chart", "layout": "full"},
                {"id": "amr_table_block", "type": "table", "tableId": "amr_table", "layout": "full"},
                {"id": "key_contigs_block", "type": "table", "tableId": "key_contigs", "layout": "full"},
                {"id": "arsenic_section", "type": "markdown", "body": "## `k141_1187` 携带连续的砷抗性模块而非抗生素 ARG\n\nBakta 在 `k141_1187` 上注释出相邻的 `arsB–arsC–arsH`，并伴随调控、动员核酸酶和毒素–抗毒素相关要素。这支持该候选可能参与金属/砷胁迫适应；它不应计入抗生素耐药基因数量，也未获得 ABRicate/CARD 或 AMRFinderPlus 的抗生素 ARG 命中。"},
                {"id": "feature_table_block", "type": "table", "tableId": "feature_table", "layout": "full"},
                {"id": "scope_section", "type": "markdown", "body": "## 分析范围、数据与指标定义\n\n**分析对象：** SRR11038083 单一样本；结论是样本内描述性结果，不包含组间差异或流行率推断。\n\n**质粒候选：** geNomad 阳性且进入 ABI 最终 consensus 的 contig，共 156 个。**丰度：** CoverM 输出的 TPM 与 coverage。**分型：** PlasmidFinder 复制子数据库命中。**AMR 阳性：** 至少一个专用 AMR 数据库工具给出序列命中；功能注释单独保留。**整合子阳性：** IntegronFinder 的 CALIN、complete 或 In0 任一大于 0。"},
                {"id": "method_section", "type": "markdown", "body": "## 方法与稳健性检查\n\n流程依次包含 fastp 质控、MEGAHIT 组装、geNomad 候选检测、ABI consensus、PlasmidFinder 分型、Bakta 功能注释、CoverM 丰度估计，以及 ABRicate/CARD、AMRFinderPlus、RGI 和 IntegronFinder 的下游核验。三套 ABI 结果均经过 `inspect` 与 `validate-result`；独立 AMRFinderPlus 恢复为真实执行、单步骤 return code 0。Bakta 的 `contig_74` 与 `contig_154` 通过候选 FASTA 顺序和 156/156 region 长度一致性映射回 `k141_775` 与 `k141_1187`。"},
                {"id": "limitations_section", "type": "markdown", "body": "## 局限性、不确定性与反证\n\n- 单一样本不能支持群体流行率、疾病关联或因果结论。\n- 短读长组装的候选多为线性 contig；`No terminal repeats` 不等于真实线性质粒，DTR 也不自动证明闭环。\n- 绝大多数候选仅由 geNomad 单工具支持，病毒/质粒边界可能存在歧义。\n- PlasmidFinder 未命名不等于非质粒；数据库覆盖范围有限。\n- RGI 空结果与 ABRicate/AMRFinderPlus 阳性并存，说明算法、数据库和阈值敏感性不同。\n- IntegronFinder 对 156 个候选均为阴性，只能说明未检测到整合子，不能排除其他移动遗传元件。\n- `blaTEM-116` 的序列存在并不等同于表达、酶活性、ESBL 表型或临床耐药；需要培养和药敏实验。\n- AMRFinderPlus 隔离恢复曾提示缺少输入 checksum 二次核验；其解析路径、真实命令和输出坐标已人工核对。"},
                {"id": "next_steps", "type": "markdown", "body": "## 推荐的下一步\n\n1. 对 `k141_775` 与 `k141_1187` 进行长读长或混合组装，验证完整闭环结构和宿主背景。\n2. 对 `blaTEM-116` 进行定量 PCR、转录验证和 β-内酰胺药敏/酶活实验，区分基因存在与功能表型。\n3. 使用接合或动员实验验证 `oriT`/MobA 相关结构是否具有实际转移能力。\n4. 扩展到同队列多样本，比较候选检出率、丰度和宿主关联，避免对单样本过度外推。\n5. 对砷抗性模块开展金属胁迫培养或表达验证，明确其生态适应意义。"},
                {"id": "further_questions", "type": "markdown", "body": "## 仍待回答的问题\n\n- `k141_775` 是否为完整 Col(pHAD28)-like 质粒，还是共享复制子片段的重组 contig？\n- `blaTEM-116` 在该样本中是否表达，并产生可测的 β-内酰胺耐药表型？\n- `k141_1187` 的砷抗性模块由何种微生物宿主携带，是否在金属暴露环境中富集？\n- 两个关键 contig 的覆盖度是否来自单一质粒实体，还是近缘重复序列的读段共比对？"},
                {"id": "candidate_audit_block", "type": "table", "tableId": "candidate_table", "layout": "full"},
            ],
        },
        "snapshot": {
            "version": 1,
            "generatedAt": generated_at,
            "status": "ready",
            "datasets": {
                "summary": summary,
                "candidate_detail": candidate_rows,
                "key_contigs": [row for row in candidate_rows if row["contig_id"] in {"k141_775", "k141_1187"}],
                "length_distribution": length_distribution,
                "top_abundance": top_abundance,
                "typing_distribution": typing_distribution,
                "annotation_categories": annotation_categories,
                "amr_evidence": amr_evidence,
                "feature_map": feature_map,
                "integron_summary": integron_rows,
            },
        },
        "sources": sources,
        "package_info": {"root": ".", "manifestPath": "artifact.json", "snapshotPath": "artifact.json"},
    }
    (ROOT / "artifact.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
