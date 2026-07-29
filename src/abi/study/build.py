"""Top-level generation of frozen study inputs."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import subprocess
from pathlib import Path
from typing import Any, Mapping

import tomlkit
import yaml

from abi.study.artifacts import (
    build_contract_snapshot,
    render_advisory_card,
    snapshot_json,
)
from abi.study.fixtures import build_fixtures
from abi.study.operation_schemas import schemas_for_operations

SEMANTIC_FIELDS = [
    "analysis_type",
    "workflow_description",
    "platforms",
    "dag_stages",
    "dag_edges",
    "tool_ids",
    "parameter_names",
    "required_parameters",
    "default_values",
    "input_types",
    "output_types",
    "resource_requirements",
    "expected_artifacts",
    "output_acceptance_rules",
    "error_categories",
    "standard_tables",
    "limitations",
]


def build_study_artifacts(
    *,
    repo_root: Path,
    study_root: Path,
    output_root: Path,
    generate_fixtures: bool = True,
) -> dict[str, Any]:
    study = yaml.safe_load((study_root / "study.yaml").read_text(encoding="utf-8"))
    workflows = list(study["workflows"])
    # Capture the source identity before generated artifacts make an in-repository
    # output directory appear dirty.
    audit = _audit(repo_root, workflows)
    snapshots = output_root / "contract_snapshot"
    cards = output_root / "advisory_cards"
    validators = output_root / "validators"
    shims = output_root / "tool_shims"
    pilot = output_root / "pilot_tasks"
    frozen = output_root / "frozen"
    for path in [snapshots, cards, validators, shims, pilot, frozen]:
        path.mkdir(parents=True, exist_ok=True)

    all_tools: dict[str, dict[str, Any]] = {}
    for workflow in workflows:
        snapshot = build_contract_snapshot(repo_root, workflow)
        (snapshots / f"{workflow}.json").write_text(snapshot_json(snapshot), encoding="utf-8")
        (cards / f"{workflow}.md").write_text(render_advisory_card(snapshot), encoding="utf-8")
        for tool in snapshot["tools"]:
            all_tools.setdefault(tool["id"], tool)

    _write_coverage(output_root / "semantic_coverage.tsv", workflows)
    (validators / "README.md").write_text(
        "# Study validators\n\n"
        "Deterministic grading rules are defined by `scoring.yaml` and implemented "
        "by `abi-study grade`. Hidden task gold is generated under `fixtures/gold/` "
        "and must not be mounted into an Agent trial.\n",
        encoding="utf-8",
    )
    (shims / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "abi.control-validation.tool-shims.v1",
                "tools": sorted(all_tools),
                "behaviors": [
                    "clean",
                    "exit_zero_with_empty_gene_counts",
                    "exit_zero_with_missing_required_gene_symbol_column",
                    "exit_zero_with_missing_required_result_files",
                    "fail_once",
                    "resume",
                ],
                "evidence_label": "synthetic_control_flow_evidence_not_biological_validity",
                "network_allowed": False,
                "workspace_operations": [
                    "list_files",
                    "read_text",
                    "write_json",
                    "copy_config",
                    "edit_config",
                    "request_execution",
                    "execute_tool",
                    "inspect_status",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    common_operations = [
        "list_files",
        "read_text",
        "write_json",
        "copy_config",
        "edit_config",
        "request_execution",
        "execute_tool",
        "inspect_status",
    ]
    (shims / "interface_schema.json").write_text(
        json.dumps(schemas_for_operations(common_operations), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (shims / "golden_contracts.json").write_text(
        json.dumps(
            {
                tool_id: {
                    "parameters": tool["parameters"],
                    "outputs": tool["outputs"],
                    "golden_request": {
                        name: f"<{name}>"
                        for name, spec in tool["parameters"].items()
                        if spec.get("required", False)
                    },
                    "golden_response": {
                        "exit_code": 0,
                        "evidence_label": (
                            "synthetic_control_flow_evidence_not_biological_validity"
                        ),
                        "outputs": sorted(tool["outputs"]),
                    },
                }
                for tool_id, tool in sorted(all_tools.items())
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (pilot / "README.md").write_text(
        "# Pilot tasks\n\nPilot tasks must use IDs, files, values, and prompts that do "
        "not occur in the confirmatory task set.\n",
        encoding="utf-8",
    )
    fixtures_summary: dict[str, Any]
    if generate_fixtures:
        fixtures_summary = build_fixtures(
            repo_root=repo_root,
            study_root=study_root,
            output_root=output_root / "fixtures",
        )
    else:
        fixtures_summary = {"status": "reused_existing"}
    (frozen / "phase0_environment.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tasks_data = yaml.safe_load((study_root / "tasks.yaml").read_text(encoding="utf-8"))["tasks"]
    _write_randomization(frozen / "randomization.tsv", study, tasks_data)
    (frozen / "preregistration.yaml").write_text(
        yaml.safe_dump(
            {
                "study_id": study["study_id"],
                "status": "generated_not_frozen",
                "primary_question": study["primary_question"],
                "conditions": list(study["conditions"]),
                "sampling": study["sampling"],
                "randomization": study["randomization"],
                "stopping": study["stopping"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (output_root / "runs" / "pilot").mkdir(parents=True, exist_ok=True)
    (output_root / "runs" / "confirmatory").mkdir(parents=True, exist_ok=True)
    _write_sha256s(output_root, frozen / "SHA256SUMS")
    for archive in (output_root / "fixtures" / "archives").glob("*.tar.gz"):
        archive.chmod(0o444)
    return {
        "workflows": workflows,
        "snapshot_count": len(workflows),
        "tool_count_in_selected_workflows": len(all_tools),
        "fixtures": fixtures_summary,
        "phase0": audit,
    }


def _write_coverage(path: Path, workflows: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "workflow",
                "source_field",
                "source_location",
                "abi_surface",
                "advisory_surface",
                "semantic_match",
                "reviewer",
                "notes",
            ]
        )
        for workflow in workflows:
            for field in SEMANTIC_FIELDS:
                writer.writerow(
                    [
                        workflow,
                        field,
                        f"contract_snapshot/{workflow}.json",
                        f"ABI tools derived from snapshot field {field}",
                        f"advisory_cards/{workflow}.md",
                        "pending_second_review",
                        "TBD",
                        "Generated from one source; human semantic audit required.",
                    ]
                )


def record_semantic_review(path: Path, reviewer: str) -> int:
    """Record an independent all-pass semantic review in the generated TSV."""
    if not reviewer.strip():
        raise ValueError("Reviewer label cannot be empty")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        row["semantic_match"] = "pass"
        row["reviewer"] = reviewer
        row["notes"] = "Independently reviewed against snapshot and advisory card."
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    checksum_file = path.parent / "frozen" / "SHA256SUMS"
    if checksum_file.parent.exists():
        _write_sha256s(path.parent, checksum_file)
    return len(rows)


def _audit(repo_root: Path, workflows: list[str]) -> dict[str, Any]:
    project = tomlkit.parse((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    environments = yaml.safe_load((repo_root / "environments.yaml").read_text(encoding="utf-8"))
    environment_count = len(environments.get("environments", environments))
    registered_tool_count = sum(
        len(assignments) for assignments in environments.get("tool_assignments", {}).values()
    )
    commit = _git(repo_root, "rev-parse", "HEAD")
    dirty = bool(_git(repo_root, "status", "--porcelain"))
    return {
        "abi_version": project["project"]["version"],
        "git_commit": commit,
        "git_clean": not dirty,
        "environment_count": environment_count,
        "registered_tool_count": registered_tool_count,
        "selected_workflows": workflows,
        "intentionally_excluded_resources": ["viral_viwrap"],
        "strict_runtime_lock": {
            "status": "not_created" if dirty else "requires_provisioned_runtime",
            "reason": (
                "Formal locks require scripts/cloud/prepare_release_lock.sh on the "
                "provisioned cloud host and a clean release commit."
            ),
        },
    }


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_randomization(
    path: Path, study: Mapping[str, Any], tasks: list[Mapping[str, Any]]
) -> None:
    rng = random.Random(study["randomization"]["randomization_seed"])
    rows = []
    conditions = list(study["run_matrix"]["primary_model"]["conditions"])
    for task in tasks:
        for seed in study["sampling"]["seeds"]:
            order = conditions.copy()
            rng.shuffle(order)
            for position, condition in enumerate(order, start=1):
                rows.append([task["task_id"], "primary", seed, position, condition])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["task_id", "model_id", "seed", "position", "condition"])
        writer.writerows(rows)


def _write_sha256s(root: Path, destination: Path) -> None:
    included_roots = [
        "advisory_cards",
        "contract_snapshot",
        "fixtures",
        "pilot_tasks",
        "tool_shims",
        "validators",
    ]
    files = [
        path
        for path in [root / "semantic_coverage.tsv", root / "study.yaml", root / "tasks.yaml"]
        if path.exists()
    ]
    for relative_root in included_roots:
        files.extend(path for path in (root / relative_root).rglob("*") if path.is_file())
    files.extend(
        path for path in destination.parent.rglob("*") if path.is_file() and path != destination
    )
    lines = []
    for path in sorted(set(files)):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root)}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
