"""Stable diagnostics for managed external workflow failures."""

from __future__ import annotations

from typing import Iterable, Mapping

from abi.external_workflows.models import ExternalTaskAttempt


def classify_external_failure(
    attempt: ExternalTaskAttempt, *, stderr: str = ""
) -> Mapping[str, object]:
    text = stderr.lower()
    if attempt.exit_code in {"137", "143"} or any(
        marker in text for marker in ("out of memory", "oom-kill", "cannot allocate memory")
    ):
        code = "RESOURCE_EXHAUSTED"
        hint = "Increase memory for the failed process and resume from the recorded run."
    elif any(
        marker in text for marker in ("database not found", "missing database", "no such database")
    ):
        code = "DATABASE_MISSING"
        hint = "Configure the required database snapshot before retrying."
    elif any(
        marker in text for marker in ("pull access denied", "unable to pull", "manifest unknown")
    ):
        code = "TOOL_OR_CONTAINER_UNAVAILABLE"
        hint = "Verify the pinned container digest and runtime registry access."
    else:
        code = "EXTERNAL_TASK_FAILED"
        hint = "Inspect the archived task command and stderr, then resume with a new ABI run ID."
    return {
        "error_code": code,
        "process": attempt.process_name,
        "sample_id": attempt.sample_id,
        "attempt": attempt.attempt,
        "exit_code": attempt.exit_code,
        "command_path": attempt.command_path,
        "stderr_path": attempt.stderr_path,
        "diagnostic_hints": [hint],
    }


def failed_attempt_diagnostics(
    attempts: Iterable[ExternalTaskAttempt],
) -> list[Mapping[str, object]]:
    return [classify_external_failure(row) for row in attempts if row.status == "FAILED"]


def summarize_run_diagnostics(
    attempts: Iterable[ExternalTaskAttempt],
    *,
    unmapped_policy: str = "warn",
) -> Mapping[str, object]:
    """Aggregate run-level diagnostics: failed attempts and unmapped processes."""
    failures = failed_attempt_diagnostics(attempts)
    unmapped = [row for row in attempts if row.process_class == "unmapped"]
    primary = failures[0]["error_code"] if failures else None
    if primary is None and unmapped and unmapped_policy == "fail":
        primary = "UNMAPPED_PROCESSES"
    return {
        "schema_version": "abi.external-diagnostics.v1",
        "primary_error_code": primary,
        "failed_attempts": failures,
        "unmapped_processes": {
            "policy": unmapped_policy,
            "count": len(unmapped),
            "process_names": sorted({row.process_name for row in unmapped}),
        },
    }
