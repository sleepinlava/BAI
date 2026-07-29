"""Deterministic fixture factory for the ABI control-layer study."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from abi.agent import ABIAgentInterface
from abi.study.artifacts import build_contract_snapshot

NORMALIZED_MTIME = 1767225600  # 2026-01-01T00:00:00Z


def _yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return payload


def _visible_to_local(root: Path, visible_path: str) -> Path:
    prefix = "/task/input"
    if visible_path != prefix and not visible_path.startswith(prefix + "/"):
        raise ValueError(f"Fixture path must be below {prefix}: {visible_path}")
    path = (root / "input" / visible_path[len(prefix) :].lstrip("/")).resolve()
    if not path.is_relative_to((root / "input").resolve()):
        raise ValueError(f"Fixture path escapes input root: {visible_path}")
    return path


def _set_nested(mapping: dict[str, Any], dotted_key: str, value: Any) -> None:
    cursor = mapping
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        child = cursor.setdefault(part, {})
        if not isinstance(child, dict):
            raise ValueError(f"Cannot set nested key through scalar: {dotted_key}")
        cursor = child
    cursor[parts[-1]] = value


def _materialize_base(repo_root: Path, destination: Path, recipe: Mapping[str, Any]) -> None:
    input_root = destination / "input"
    reads_root = input_root / "reads"
    resources_root = input_root / "resources"
    reads_root.mkdir(parents=True, exist_ok=True)
    resources_root.mkdir(parents=True, exist_ok=True)

    sources = recipe["sources"]
    config = _yaml(repo_root / str(sources["plugin_config"]))
    config["outdir"] = "/task/work/results"
    config["log_dir"] = "/task/work/logs"
    _set_nested(config, "input.sample_sheet", "/task/input/samples.tsv")
    for key, value in recipe.get("config_overrides", {}).items():
        _set_nested(config, str(key), value)

    resource_manifest: dict[str, Any] = {}
    for resource_id, resource in recipe.get("resource_shims", {}).items():
        visible = str(resource["path"])
        local = _visible_to_local(destination, visible)
        if local.suffix:
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text(f"{resource['identity']}\n", encoding="utf-8")
        else:
            local.mkdir(parents=True, exist_ok=True)
            (local / "IDENTITY").write_text(f"{resource['identity']}\n", encoding="utf-8")
            for required_file in resource.get("required_files", []):
                required_path = local / str(required_file)
                required_path.parent.mkdir(parents=True, exist_ok=True)
                required_path.write_text(
                    f"{resource['identity']} synthetic control-flow fixture\n",
                    encoding="utf-8",
                )
        _set_nested(config, str(resource["config_key"]), visible)
        resource_manifest[resource_id] = {
            "path": visible,
            "identity": resource["identity"],
        }
    (input_root / "config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=True), encoding="utf-8"
    )
    (resources_root / "resource_manifest.json").write_text(
        json.dumps(resource_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    samples = recipe["samples"]
    columns = recipe.get(
        "sample_sheet_columns",
        [
            "sample_id",
            "group",
            "platform",
            "read1",
            "read2",
            "long_reads",
            "assembly",
            "technology",
            "host_reference",
            "notes",
        ],
    )
    fixed = recipe.get("fixed_values", {})
    rows = []
    for sample in samples:
        sample_id = str(sample["sample_id"])
        shutil.copyfile(repo_root / str(sources["read1"]), reads_root / f"{sample_id}_R1.fastq")
        shutil.copyfile(repo_root / str(sources["read2"]), reads_root / f"{sample_id}_R2.fastq")
        row = {**fixed, **sample}
        row["read1"] = f"/task/input/reads/{sample_id}_R1.fastq"
        row["read2"] = f"/task/input/reads/{sample_id}_R2.fastq"
        rows.append(row)
    with (input_root / "samples.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _apply_fault(fixture: Path, operation: Mapping[str, Any]) -> None:
    name = operation["operation"]
    target = operation.get("target")
    if name in {"remove", "remove_directory"}:
        path = _visible_to_local(fixture, str(target))
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    elif name == "replace_yaml_value":
        path = _visible_to_local(fixture, str(target))
        config = _yaml(path)
        _set_nested(config, str(operation["key"]), operation["value"])
        path.write_text(yaml.safe_dump(config, sort_keys=True), encoding="utf-8")
    elif name == "duplicate_tsv_row":
        path = _visible_to_local(fixture, str(target))
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
    elif name in {
        "configure_tool_shim",
        "mark_steps_completed",
        "fail_tool_once",
        "provide_unique_valid_candidate",
        "retain_configured_path",
    }:
        # Control-flow faults are orchestrator state, not Agent-visible evidence.
        # Trials mount only ``input/``; ``fixture_control.json`` is copied into the
        # private authority directory by the harness.
        state_path = fixture / "fixture_control.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else []
        state.append(dict(operation))
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"Unsupported fault operation: {name}")


def _hash_tree(root: Path) -> list[dict[str, str]]:
    rows = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        rows.append({"path": str(path.relative_to(root)), "sha256": _sha256(path)})
    return rows


def _write_manifest(
    fixture: Path,
    *,
    task_id: str,
    expected_valid: bool,
    fault_operations: list[Mapping[str, Any]],
    pre_fault_twin_sha256: str,
) -> None:
    payload = {
        "schema_version": "abi.control-validation.fixture.v1",
        "task_id": task_id,
        "expected_valid": expected_valid,
        "fault_operations": fault_operations,
        "pre_fault_twin_sha256": pre_fault_twin_sha256,
        "files": _hash_tree(fixture / "input"),
    }
    (fixture / "fixture_manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _deterministic_archive(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.chmod(0o644)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for path in sorted([source, *source.rglob("*")]):
            info = archive.gettarinfo(str(path), arcname=str(path.relative_to(source.parent)))
            info.uid = info.gid = 0
            info.uname = info.gname = "task"
            info.mtime = NORMALIZED_MTIME
            if path.is_file():
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
            else:
                archive.addfile(info)
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(buffer.getvalue())


def build_fixtures(
    *,
    repo_root: Path,
    study_root: Path,
    output_root: Path,
    task_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Materialize clean twins, task faults, hidden gold, hashes, and archives."""
    recipes = _yaml(study_root / "fixture_recipes.yaml")["recipes"]
    tasks = _yaml(study_root / "tasks.yaml")["tasks"]
    selected = [task for task in tasks if task_ids is None or task["task_id"] in task_ids]
    output_root.mkdir(parents=True, exist_ok=True)
    built = []
    for task in selected:
        task_id = str(task["task_id"])
        recipe = recipes[task["base_fixture"]["recipe"]]
        clean_relative = Path(str(task["base_fixture"]["clean_twin"])).relative_to("fixtures")
        clean = output_root / clean_relative
        fault = clean.with_name(clean.name.removesuffix("_clean") + "_fault")
        if clean.exists():
            shutil.rmtree(clean)
        if fault.exists():
            shutil.rmtree(fault)
        _materialize_base(repo_root, clean, recipe)
        (clean / "fixture_control.json").write_text("[]\n", encoding="utf-8")
        shutil.copytree(clean, fault)
        clean_twin_digest = _tree_digest(clean)
        fault_twin_digest = _tree_digest(fault)
        if clean_twin_digest != fault_twin_digest:
            raise ValueError(f"Clean/fault twins differ before fault injection for {task_id}")
        for operation in task.get("fault", {}).get("setup", []):
            _apply_fault(fault, operation)
        has_fault = bool(task.get("fault", {}).get("setup"))
        operations = list(task.get("fault", {}).get("setup", []))
        _write_manifest(
            clean,
            task_id=task_id,
            expected_valid=True,
            fault_operations=[],
            pre_fault_twin_sha256=clean_twin_digest,
        )
        _write_manifest(
            fault,
            task_id=task_id,
            expected_valid=not has_fault,
            fault_operations=operations,
            pre_fault_twin_sha256=fault_twin_digest,
        )

        snapshot = build_contract_snapshot(repo_root, str(task["workflow"]))
        compiled_plan = _compile_clean_plan(clean, task)
        gold_root = output_root / "gold" / task_id
        gold_root.mkdir(parents=True, exist_ok=True)
        gold = {
            "task_id": task_id,
            "hidden_root_cause": task.get("hidden_root_cause")
            or task.get("fault", {}).get("hidden_root_cause"),
            "gold": task["gold"],
            "compiled_plan": compiled_plan,
            "contract_plan_summary": {
                "analysis_type": task["workflow"],
                "stages": snapshot["stages"],
                "dag_edges": snapshot["dag_edges"],
            },
            "clean_input_sha256": _hash_tree(clean / "input"),
            "fault_input_sha256": _hash_tree(fault / "input"),
            "pre_fault_twin_sha256": clean_twin_digest,
        }
        (gold_root / "gold.json").write_text(
            json.dumps(gold, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (gold_root / "compiled_plan.json").write_text(
            json.dumps(gold["compiled_plan"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (gold_root / "expected_terminal_state.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "terminal_state": task["gold"]["terminal_state"],
                    "root_cause": gold["hidden_root_cause"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _write_hash_tsv(gold_root / "input_sha256.tsv", gold["clean_input_sha256"])
        _write_hash_tsv(
            gold_root / "resource_sha256.tsv",
            [row for row in gold["clean_input_sha256"] if row["path"].startswith("resources/")],
        )
        (gold_root / "expected_events.json").write_text(
            json.dumps(
                {
                    "forbidden_events": task.get("forbidden_events", []),
                    "authorization": task["authorization"],
                    "execution_mode": task["execution_mode"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        clean_result = verify_fixture(clean)
        fault_result = verify_fixture(fault)
        task_assay = _run_task_fixture_assay(
            clean=clean,
            fault=fault,
            task=task,
            compiled_plan=compiled_plan,
            snapshot=snapshot,
            preflight_resource_ids=set(recipe.get("preflight_resource_ids", [])),
        )
        (gold_root / "fixture_assay.json").write_text(
            json.dumps(task_assay, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if (
            not clean_result["assay_pass"]
            or not fault_result["assay_pass"]
            or not task_assay["passed"]
        ):
            details = {
                "clean_fixture": clean_result,
                "fault_fixture": fault_result,
                "task_assay": task_assay,
            }
            raise ValueError(
                f"Fixture assay failed for {task_id}: "
                f"{json.dumps(details, sort_keys=True, default=str)}"
            )
        _deterministic_archive(fault, output_root / "archives" / f"{task_id}.tar.gz")
        built.append(task_id)
    return {"task_count": len(built), "task_ids": built}


def verify_fixture(fixture: Path) -> dict[str, Any]:
    """Verify hashes and return the declared assay expectation."""
    manifest = json.loads((fixture / "fixture_manifest.json").read_text(encoding="utf-8"))
    actual = {row["path"]: row["sha256"] for row in _hash_tree(fixture / "input")}
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    hashes_match = actual == expected
    operations = manifest.get("fault_operations", [])
    fault_detected = bool(operations) and all(
        _operation_present(fixture, operation) for operation in operations
    )
    observed_valid = not fault_detected
    expected_valid = bool(manifest["expected_valid"])
    return {
        "hashes_match": hashes_match,
        "valid": observed_valid if hashes_match else False,
        "assay_pass": hashes_match and observed_valid == expected_valid,
        "fault_detected": fault_detected,
        "task_id": manifest["task_id"],
    }


def _operation_present(fixture: Path, operation: Mapping[str, Any]) -> bool:
    name = operation["operation"]
    if name in {"remove", "remove_directory"}:
        return not _visible_to_local(fixture, str(operation["target"])).exists()
    if name == "replace_yaml_value":
        payload: Any = _yaml(_visible_to_local(fixture, str(operation["target"])))
        for part in str(operation["key"]).split("."):
            if not isinstance(payload, dict) or part not in payload:
                return False
            payload = payload[part]
        return payload == operation["value"]
    if name == "duplicate_tsv_row":
        path = _visible_to_local(fixture, str(operation["target"]))
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        sample_ids = [row.get("sample_id") for row in rows]
        return len(sample_ids) != len(set(sample_ids))
    state_path = fixture / "fixture_control.json"
    if name in {
        "configure_tool_shim",
        "mark_steps_completed",
        "fail_tool_once",
        "provide_unique_valid_candidate",
        "retain_configured_path",
    }:
        if not state_path.exists():
            return False
        state = json.loads(state_path.read_text(encoding="utf-8"))
        recorded = dict(operation) in state
        if name == "provide_unique_valid_candidate":
            return recorded and _visible_to_local(fixture, str(operation["target"])).exists()
        return recorded
    return False


def _write_hash_tsv(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _compile_clean_plan(clean: Path, task: Mapping[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="abi-study-plan-") as temporary:
        outdir = Path(temporary) / "work"
        envelope = json.loads(
            ABIAgentInterface().plan(
                analysis_type=str(task["workflow"]),
                config_path=clean / "input" / "config.yaml",
                sample_sheet=clean / "input" / "samples.tsv",
                outdir=str(outdir),
                check_files=False,
            )
        )
        if envelope.get("status") != "success":
            raise ValueError(
                f"Clean plan compilation failed for {task['task_id']}: {envelope.get('error_code')}"
            )
        compiled_path = Path(envelope["result"]["compiled_plan_path"])
        compiled = json.loads(compiled_path.read_text(encoding="utf-8"))
        return _replace_path_prefixes(
            compiled,
            {
                str(clean / "input"): "/task/input",
                str(outdir): "/task/work/gold-plan",
                temporary: "/task/work",
            },
        )


def _replace_path_prefixes(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_path_prefixes(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_path_prefixes(item, replacements) for item in value]
    if isinstance(value, str):
        for source, replacement in replacements.items():
            value = value.replace(source, replacement)
    return value


def _normalize_assay_evidence(value: Any, replacements: Mapping[str, str]) -> Any:
    """Remove runtime-only values from frozen fixture-assay evidence."""
    if isinstance(value, dict):
        return {
            key: _normalize_assay_evidence(item, replacements)
            for key, item in value.items()
            if key not in {"date", "last_checked_at", "validated_at"}
        }
    if isinstance(value, list):
        return [_normalize_assay_evidence(item, replacements) for item in value]
    if isinstance(value, str):
        return _replace_path_prefixes(value, replacements)
    return value


def _run_task_fixture_assay(
    *,
    clean: Path,
    fault: Path,
    task: Mapping[str, Any],
    compiled_plan: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    preflight_resource_ids: set[str],
) -> dict[str, Any]:
    clean_preflight = _local_preflight(
        clean,
        str(task["workflow"]),
        resource_ids=preflight_resource_ids,
    )
    fault_preflight = _local_preflight(
        fault,
        str(task["workflow"]),
        resource_ids=preflight_resource_ids,
    )
    category = str(task["category"])
    has_fault = bool(task.get("fault", {}).get("setup"))
    clean_ready = clean_preflight.get("status") == "pass"
    fault_ready = fault_preflight.get("status") == "pass"
    expected_fault_ready = not (
        has_fault
        and (
            category == "preflight"
            or task.get("fault", {}).get("class") == "recoverable_resource_path"
        )
    )

    required_nodes = set(task["gold"].get("required_nodes", []))
    step_ids = [str(step.get("step_id", "")) for step in compiled_plan.get("steps", [])]
    compiled_tools = {str(step.get("tool_id", "")) for step in compiled_plan.get("steps", [])}
    stage_tools = {str(stage["id"]): str(stage["tool_id"]) for stage in snapshot["stages"]}
    plan_nodes_valid = all(
        any(step_id == node or step_id.endswith(f"_{node}") for step_id in step_ids)
        or stage_tools.get(node) in compiled_tools
        for node in required_nodes
    )
    required_design = set(task["gold"].get("required_design_terms", []))
    design_values = [
        str(step.get("params", {}).get("design", "")) for step in compiled_plan.get("steps", [])
    ]
    design_valid = all(any(term in design for design in design_values) for term in required_design)
    fault_operations_valid = not has_fault or all(
        _operation_present(fault, operation) for operation in task.get("fault", {}).get("setup", [])
    )
    passed = (
        clean_ready
        and fault_ready == expected_fault_ready
        and plan_nodes_valid
        and design_valid
        and fault_operations_valid
    )
    return {
        "passed": passed,
        "clean_preflight": clean_preflight,
        "fault_preflight": fault_preflight,
        "expected_fault_ready": expected_fault_ready,
        "plan_nodes_valid": plan_nodes_valid,
        "design_valid": design_valid,
        "fault_operations_valid": fault_operations_valid,
    }


def _local_preflight(
    fixture: Path,
    workflow: str,
    *,
    resource_ids: set[str],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="abi-study-check-") as temporary:
        local_root = Path(temporary) / "input"
        shutil.copytree(fixture / "input", local_root)
        replacements = {
            "/task/input": str(local_root),
            "/task/work": str(Path(temporary) / "work"),
        }
        for name in ["config.yaml", "samples.tsv"]:
            path = local_root / name
            text = path.read_text(encoding="utf-8")
            for source, replacement in replacements.items():
                text = text.replace(source, replacement)
            path.write_text(text, encoding="utf-8")
        envelope = json.loads(
            ABIAgentInterface().check(
                analysis_type=workflow,
                config_path=local_root / "config.yaml",
                sample_sheet=local_root / "samples.tsv",
                check_runtime=False,
            )
        )
        if envelope.get("status") != "success":
            return {
                "status": "error",
                "error_code": envelope.get("error_code"),
                "error": envelope.get("error"),
            }
        result = envelope["result"]
        checks = list(result.get("checks", []))
        if resource_ids:
            scoped_names = {"inputs", *(f"resource:{item}" for item in resource_ids)}
            checks = [check for check in checks if check.get("name") in scoped_names]
            result_status = (
                "fail" if any(check.get("status") == "fail" for check in checks) else "pass"
            )
        else:
            result_status = result.get("status", "pass")
        evidence = {
            "status": result_status,
            "checks": checks,
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        }
        return _normalize_assay_evidence(
            evidence,
            {
                str(local_root): "/task/input",
                str(Path(temporary) / "work"): "/task/work",
                temporary: "/task",
            },
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for row in _hash_tree(root):
        digest.update(row["path"].encode())
        digest.update(row["sha256"].encode())
    return digest.hexdigest()
