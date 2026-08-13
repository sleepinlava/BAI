"""Frozen inputs and acceptance helpers for the preregistered IBD reproduction."""

from __future__ import annotations

import csv
import json
import math
import random
import re
from pathlib import Path
from typing import Any

import numpy as np

CORE_PROJECT = "SRP131166"
CORE_COUNTS = {"NC": 13, "CD": 20, "UC": 20}
PLUSPF_20240605_SOURCE = "https://genome-idx.s3.amazonaws.com/k2_pluspf_20240605.tar.gz"


def _table1_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        next(handle, None)  # Frozen supplementary-table title line.
        return [
            {str(key).strip().lower(): str(value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def freeze_core53(
    table1_path: str | Path,
    output_path: str | Path,
    *,
    reads_root: str | Path,
) -> list[dict[str, str]]:
    """Freeze all NC/UC and the lexicographically first 20 CD runs from SRP131166."""
    project_rows = [row for row in _table1_rows(table1_path) if row.get("project") == CORE_PROJECT]
    selected: list[dict[str, str]] = []
    for group in ("NC", "CD", "UC"):
        candidates = sorted(
            (row for row in project_rows if row.get("group") == group),
            key=lambda row: row.get("run", ""),
        )
        selected.extend(candidates[: CORE_COUNTS[group]])
    root = Path(reads_root)
    rows = [
        {
            "sample_id": row["run"],
            "r1": str(root / f"{row['run']}_1.fastq.gz"),
            "r2": str(root / f"{row['run']}_2.fastq.gz"),
            "group": row["group"],
            "project": row["project"],
            "country": row.get("country", ""),
            "continent": row.get("continent", ""),
        }
        for row in selected
    ]
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    errors = validate_core53_manifest(destination)
    if errors:
        destination.unlink(missing_ok=True)
        raise ValueError("Invalid frozen core53 selection: " + "; ".join(errors))
    return rows


def validate_core53_manifest(path: str | Path) -> list[str]:
    errors: list[str] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        first = handle.readline()
        handle.seek(0)
        rows = list(csv.DictReader(handle, delimiter="\t" if "\t" in first else ","))
    if len(rows) != 53:
        errors.append(f"IBD core manifest must contain exactly 53 samples, got {len(rows)}")
    projects = {str(row.get("project", "")).strip() for row in rows}
    if projects != {CORE_PROJECT}:
        errors.append(
            f"IBD core manifest must contain only project {CORE_PROJECT}, got {sorted(projects)}"
        )
    counts = {
        group: sum(str(row.get("group", "")).strip() == group for row in rows)
        for group in CORE_COUNTS
    }
    if counts != CORE_COUNTS:
        errors.append(f"IBD core group counts must be {CORE_COUNTS}, got {counts}")
    cd_runs = [str(row.get("sample_id", "")).strip() for row in rows if row.get("group") == "CD"]
    if cd_runs != sorted(cd_runs):
        errors.append("IBD core CD runs must be in lexicographic order")
    if len({str(row.get("sample_id", "")).strip() for row in rows}) != len(rows):
        errors.append("IBD core sample_id values must be unique")
    return errors


def validate_pluspf_identity(path: str | Path) -> list[str]:
    identity_path = Path(path)
    if not identity_path.is_file():
        return [f"Kraken2 identity file is missing: {identity_path}"]
    try:
        payload: dict[str, Any] = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Kraken2 identity file is invalid: {exc}"]
    errors: list[str] = []
    version = str(payload.get("version", ""))
    if version != "pluspf_20240605":
        errors.append(
            f"Kraken2 database version must be pluspf_20240605, got {version or 'missing'}"
        )
    source = str(payload.get("source_url", ""))
    if source != PLUSPF_20240605_SOURCE:
        errors.append(
            f"Kraken2 database source must be {PLUSPF_20240605_SOURCE}, got {source or 'missing'}"
        )
    checksum = str(payload.get("archive_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        errors.append("Kraken2 pluspf identity requires a lowercase SHA-256 archive checksum")
    return errors


def _rank(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranked = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranked[order[start:end]] = (start + end - 1) / 2 + 1
        start = end
    return ranked


def _spearman(left: list[float], right: list[float]) -> float:
    if len(left) < 2:
        return float("nan")
    return float(np.corrcoef(_rank(np.asarray(left)), _rank(np.asarray(right)))[0, 1])


def _read_matrix(path: str | Path) -> tuple[list[str], dict[str, np.ndarray]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    samples = list(rows[0])[2:] if rows else []
    matrix = {
        str(row.get("name", "")).strip(): np.asarray(
            [float(row.get(sample) or 0) for sample in samples], dtype=float
        )
        for row in rows
        if str(row.get("name", "")).strip()
    }
    return samples, matrix


def _read_reference(path: str | Path) -> dict[str, dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        next(handle, None)
        rows = list(csv.DictReader(handle))
    reference: dict[str, dict[str, Any]] = {}
    for row in rows:
        genus = str(row.get("Genus", "")).strip()
        if not genus:
            continue
        entry = reference.setdefault(
            genus,
            {key: float(row[key]) for key in ("NC", "CD", "UC", "diff_CD_NC", "diff_UC_NC")},
        )
        for comparison in ("NC_vs_CD", "NC_vs_UC", "CD_vs_UC"):
            value = str(row.get(f"p_value_{comparison}", "")).strip()
            if value:
                entry[f"p_{comparison}"] = value
    return reference


def _dunn(groups: dict[str, list[float]], left: str, right: str) -> float:
    labels = [label for label, values in groups.items() for _ in values]
    values = np.asarray([value for values in groups.values() for value in values], dtype=float)
    if len(values) < 2 or not groups[left] or not groups[right]:
        return 1.0
    ranks = _rank(values)
    means = {
        label: float(np.mean(ranks[[i for i, item in enumerate(labels) if item == label]]))
        for label in groups
    }
    _, tie_counts = np.unique(values, return_counts=True)
    n = len(values)
    tie_term = float(np.sum(tie_counts**3 - tie_counts) / (12 * (n - 1))) if n > 1 else 0
    variance = n * (n + 1) / 12 - tie_term
    denominator = math.sqrt(variance * (1 / len(groups[left]) + 1 / len(groups[right])))
    z = abs(means[left] - means[right]) / denominator if denominator else 0.0
    return math.erfc(z / math.sqrt(2))


def _holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values, key=lambda key: p_values[key])
    adjusted: dict[str, float] = {}
    running = 0.0
    for index, key in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - index) * p_values[key]))
        adjusted[key] = running
    return adjusted


def _permanova(
    matrix: np.ndarray, labels: list[str], permutations: int, seed: int
) -> tuple[float, float]:
    totals = matrix.sum(axis=0)
    relative = np.divide(matrix, totals, out=np.zeros_like(matrix), where=totals > 0).T
    distances = np.zeros((len(labels), len(labels)), dtype=float)
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            denominator = float(np.sum(relative[i] + relative[j]))
            value = (
                float(np.sum(np.abs(relative[i] - relative[j])) / denominator) if denominator else 0
            )
            distances[i, j] = distances[j, i] = value
    centered = (
        -0.5
        * (np.eye(len(labels)) - np.ones((len(labels), len(labels))) / len(labels))
        @ (distances**2)
        @ (np.eye(len(labels)) - np.ones((len(labels), len(labels))) / len(labels))
    )

    def statistic(current: list[str]) -> float:
        design = np.zeros((len(current), len(set(current))))
        for row, label in enumerate(current):
            design[row, sorted(set(current)).index(label)] = 1
        hat = design @ np.linalg.pinv(design.T @ design) @ design.T
        between = float(np.trace(hat @ centered))
        within = float(np.trace((np.eye(len(current)) - hat) @ centered))
        return (
            (between / (design.shape[1] - 1)) / (within / (len(current) - design.shape[1]))
            if within > 0
            else float("inf")
        )

    observed = statistic(labels)
    rng = random.Random(seed)
    exceed = 0
    for _ in range(permutations):
        shuffled = labels[:]
        rng.shuffle(shuffled)
        exceed += statistic(shuffled) >= observed
    return observed, (exceed + 1) / (permutations + 1)


def score_ibd_reproduction(
    genus_table: str | Path,
    manifest_path: str | Path,
    reference_path: str | Path,
    output_path: str | Path,
    *,
    permutations: int = 999,
    seed: int = 20240605,
) -> dict[str, Any]:
    """Score the frozen E1-E5 endpoints without changing preregistered thresholds."""
    samples, taxa = _read_matrix(genus_table)
    with Path(manifest_path).open("r", encoding="utf-8-sig", newline="") as handle:
        first = handle.readline()
        handle.seek(0)
        metadata = {
            row["sample_id"]: row["group"]
            for row in csv.DictReader(handle, delimiter="\t" if "\t" in first else ",")
        }
    labels = [metadata[sample] for sample in samples]
    indices = {
        group: [i for i, label in enumerate(labels) if label == group] for group in CORE_COUNTS
    }
    reference = _read_reference(reference_path)
    shared = sorted(set(taxa) & set(reference))
    means = {
        group: {genus: float(np.mean(taxa[genus][indices[group]])) for genus in shared}
        for group in CORE_COUNTS
    }
    rhos = {
        group: _spearman(
            [means[group][genus] for genus in shared], [reference[genus][group] for genus in shared]
        )
        for group in CORE_COUNTS
    }
    comparisons = {"CD_NC": ("CD", "NC"), "UC_NC": ("UC", "NC")}
    direction_matches = []
    significant_matches = []
    for genus in shared:
        for label, (case, control) in comparisons.items():
            observed = np.sign(means[case][genus] - means[control][genus])
            expected = np.sign(reference[genus][f"diff_{label}"])
            direction_matches.append(observed == expected)
            p_key = "p_NC_vs_CD" if label == "CD_NC" else "p_NC_vs_UC"
            if len(str(reference[genus].get(p_key, "")).replace("ns", "")) >= 2:
                significant_matches.append(observed == expected)
    vectors = np.asarray([taxa[genus] for genus in taxa], dtype=float)
    alpha: dict[str, dict[str, list[float]]] = {
        metric: {group: [] for group in CORE_COUNTS} for metric in ("shannon", "chao1")
    }
    for i, label in enumerate(labels):
        values = vectors[:, i]
        positive = values[values > 0]
        proportions = positive / positive.sum() if positive.size else positive
        singletons = int(np.sum(values == 1))
        doubletons = int(np.sum(values == 2))
        alpha["shannon"][label].append(float(-np.sum(proportions * np.log(proportions))))
        alpha["chao1"][label].append(
            float(len(positive) + (singletons * (singletons - 1)) / (2 * (doubletons + 1)))
        )
    alpha_results = {}
    for metric, groups in alpha.items():
        adjusted = _holm(
            {
                name: _dunn(groups, *pair)
                for name, pair in {
                    "NC_vs_CD": ("NC", "CD"),
                    "NC_vs_UC": ("NC", "UC"),
                    "CD_vs_UC": ("CD", "UC"),
                }.items()
            }
        )
        group_means = {group: float(np.mean(values)) for group, values in groups.items()}
        passed = (
            group_means["NC"] > group_means["CD"]
            and group_means["NC"] > group_means["UC"]
            and adjusted["NC_vs_CD"] < 0.05
            and adjusted["NC_vs_UC"] < 0.05
            and adjusted["CD_vs_UC"] >= 0.05
        )
        alpha_results[metric] = {
            "status": "pass" if passed else "divergent",
            "group_means": group_means,
            "holm_p": adjusted,
        }
    pseudo_f, p_value = _permanova(vectors, labels, permutations, seed)
    e2_rate = float(np.mean(direction_matches)) if direction_matches else 0.0
    e3_rate = float(np.mean(significant_matches)) if significant_matches else 0.0
    endpoints: dict[str, dict[str, Any]] = {
        "E1": {
            "status": "pass" if all(value >= 0.9 for value in rhos.values()) else "divergent",
            "threshold": "rho >= 0.90 for NC/CD/UC",
            "spearman": rhos,
            "shared_genera": len(shared),
        },
        "E2": {
            "status": "pass" if e2_rate >= 0.9 else "divergent",
            "threshold": ">= 0.90",
            "direction_concordance": e2_rate,
        },
        "E3": {
            "status": "pass" if e3_rate >= 0.8 else "divergent",
            "threshold": ">= 0.80",
            "significant_direction_recovery": e3_rate,
            "comparisons": len(significant_matches),
        },
        "E4": {
            "status": "pass"
            if all(item["status"] == "pass" for item in alpha_results.values())
            else "divergent",
            "metrics": alpha_results,
        },
        "E5": {
            "status": "pass" if p_value < 0.05 else "divergent",
            "threshold": "p < 0.05",
            "pseudo_f": pseudo_f,
            "p_value": p_value,
            "permutations": permutations,
            "seed": seed,
        },
    }
    result = {
        "protocol": "ibd_core53",
        "status": "pass"
        if all(item["status"] == "pass" for item in endpoints.values())
        else "divergent",
        "endpoints": endpoints,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
