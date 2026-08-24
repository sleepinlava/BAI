"""Versioned public models for managed external workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ExternalWorkflowSpec:
    """Immutable execution boundary supplied by an external-workflow plugin."""

    engine: str
    workflow_id: str
    source: str
    revision: str
    commit_sha: str
    entrypoint: str
    argv: tuple[str, ...]
    work_dir: str
    profile: str
    resume: bool = False
    audit_level: str = "task_contracts"
    expected_process_classes: tuple[str, ...] = ()
    evidence_enabled: bool = True
    schema_version: str = "abi.external-workflow-spec.v1"

    def __post_init__(self) -> None:
        if self.engine != "nextflow":
            raise ValueError(f"Unsupported external workflow engine: {self.engine}")
        if not self.commit_sha or len(self.commit_sha) != 40:
            raise ValueError("External workflow commit_sha must be an immutable 40-character SHA")
        if self.audit_level not in {"wrapper", "task_trace", "task_contracts"}:
            raise ValueError(f"Unknown external workflow audit level: {self.audit_level}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExternalPlanSnapshot:
    """Pre-execution identity and configuration snapshot."""

    external_workflow_id: str
    abi_version: str
    abi_commit: str
    plugin_version: str
    contract_version: str
    workflow: Mapping[str, Any]
    runtime: Mapping[str, Any]
    resolved_config: Mapping[str, Any]
    inputs: Sequence[Mapping[str, Any]]
    containers: Sequence[Mapping[str, Any]]
    databases: Sequence[Mapping[str, Any]]
    modules: Mapping[str, bool]
    argv: Sequence[str]
    plan_fidelity: Mapping[str, str] = field(
        default_factory=lambda: {
            "declared": "external_workflow_with_expected_process_classes",
            "observed": "task_attempt_level",
        }
    )
    schema_version: str = "abi.external-plan-snapshot.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExternalTaskAttempt:
    """One immutable Nextflow task attempt; records are never folded by process."""

    external_workflow_id: str
    task_id: str
    task_hash: str
    process_name: str
    process_class: str
    sample_id: str
    attempt: int
    status: str
    exit_code: str = ""
    executor: str = ""
    native_id: str = ""
    container_ref: str = ""
    container_digest: str = ""
    work_dir: str = ""
    command_path: str = ""
    stdout_path: str = ""
    stderr_path: str = ""
    submit_time: str = ""
    start_time: str = ""
    complete_time: str = ""
    duration_ms: int | None = None
    requested_cpus: float | None = None
    requested_memory_bytes: int | None = None
    peak_rss_bytes: int | None = None
    peak_vmem_bytes: int | None = None
    raw_trace_row_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExternalProcessContract:
    """Versioned expectations for a process class and its published artifacts."""

    contract_id: str
    contract_version: str
    process_class: str
    enabled_when: str
    process_patterns: tuple[str, ...]
    min_successful_per_sample: int = 1
    max_successful_final_per_sample: int | None = None
    accepted_statuses: tuple[str, ...] = ("COMPLETED", "CACHED")
    required_outputs: tuple[Mapping[str, Any], ...] = ()
    publish: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExternalRunEvidence:
    """Evidence-bundle identity and collection status."""

    external_workflow_id: str
    manifest_path: str
    task_attempts_path: str
    complete: bool
    collection_errors: tuple[Mapping[str, Any], ...] = ()
    schema_version: str = "abi.external-run-evidence.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
