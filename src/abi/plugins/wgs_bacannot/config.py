"""Pinned compatibility and configuration validation."""

from __future__ import annotations

from typing import Any, Mapping

PINNED_REVISION = "v3.4.4"
PINNED_COMMIT_SHA = "a78ddb0bffe75139adf1f443260d6d5b1987fe27"
SUPPORTED_PROFILES = {"docker", "singularity"}
ALLOWED_KEYS = {
    "": {
        "project_name",
        "mode",
        "threads",
        "outdir",
        "log_dir",
        "workflow",
        "input",
        "modules",
        "resources",
        "audit",
        "execution",
        "dry_run",
        "mock_tools",
    },
    "workflow": {"source", "revision", "commit_sha", "profile", "resume"},
    "input": {"sample_sheet", "platform", "mode"},
    "modules": {"assembly", "annotation", "mlst", "amr"},
    "resources": {
        "runtime_resource_root",
        "bacannot_db",
        "database_snapshot_id",
        "database_sha256",
        "max_cpus",
        "max_memory",
        "max_time",
    },
    "audit": {"level", "retain_success_command_evidence"},
    "execution": {"nextflow_timeout_seconds", "progress"},
}


def validate_config(config: Mapping[str, Any]) -> None:
    _reject_unknown_keys(config)
    workflow = _mapping(config, "workflow")
    revision = str(workflow.get("revision", ""))
    commit_sha = str(workflow.get("commit_sha", ""))
    if revision != PINNED_REVISION or commit_sha != PINNED_COMMIT_SHA:
        raise ValueError(
            "Unsupported Bacannot revision; production integration requires "
            f"{PINNED_REVISION}@{PINNED_COMMIT_SHA}"
        )
    profile = str(workflow.get("profile", ""))
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Unsupported Bacannot profile: {profile}")
    if not isinstance(workflow.get("resume"), bool):
        raise ValueError("wgs_bacannot workflow.resume must be a boolean")
    input_block = _mapping(config, "input")
    if input_block.get("platform") != "illumina" or input_block.get("mode") != "paired_end":
        raise ValueError("wgs_bacannot v1 supports only Illumina paired-end input")
    if not input_block.get("sample_sheet"):
        raise ValueError("wgs_bacannot requires input.sample_sheet")
    modules = _mapping(config, "modules")
    for required in ("assembly", "annotation", "mlst"):
        if modules.get(required) is not True:
            raise ValueError(f"wgs_bacannot v1 requires modules.{required}=true")
    if not isinstance(modules.get("amr"), bool):
        raise ValueError("wgs_bacannot modules.amr must be a boolean")
    resources = _mapping(config, "resources")
    if not isinstance(resources.get("max_cpus"), int) or resources["max_cpus"] < 1:
        raise ValueError("wgs_bacannot resources.max_cpus must be a positive integer")
    for key in ("bacannot_db", "max_memory", "max_time"):
        if not isinstance(resources.get(key), str) or not resources[key].strip():
            raise ValueError(f"wgs_bacannot resources.{key} must be a non-empty string")
    database_sha256 = resources.get("database_sha256", "")
    if database_sha256 and (
        not isinstance(database_sha256, str)
        or len(database_sha256) != 64
        or any(char not in "0123456789abcdef" for char in database_sha256)
    ):
        raise ValueError("wgs_bacannot resources.database_sha256 must be lowercase SHA-256")
    audit = _mapping(config, "audit")
    if audit.get("level") != "task_contracts":
        raise ValueError("wgs_bacannot production integration requires audit.level=task_contracts")
    if audit.get("retain_success_command_evidence") is not True:
        raise ValueError("wgs_bacannot requires audit.retain_success_command_evidence=true")


def _reject_unknown_keys(config: Mapping[str, Any]) -> None:
    blocks: list[tuple[str, Mapping[str, Any]]] = [("", config)]
    for name in ("workflow", "input", "modules", "resources", "audit", "execution"):
        value = config.get(name)
        if isinstance(value, Mapping):
            blocks.append((name, value))
    for name, block in blocks:
        unknown = sorted(set(block) - ALLOWED_KEYS[name])
        if unknown:
            location = name or "root"
            raise ValueError(f"Unknown wgs_bacannot config key(s) in {location}: {unknown}")


def _mapping(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"wgs_bacannot {key} must be a mapping")
    return value
