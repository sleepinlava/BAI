"""Snakemake ABI runtime backend."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping

from abi.dag import ABIDAG, infer_dag
from abi.execution_policy import ExecutionPolicy, ResourceOverride
from abi.exporters import SnakemakeExporter
from abi.exporters.snakemake import _marker_path, marker_dir_for
from abi.results import ABIResultWriter
from abi.resume import runtime_resume_identity, validate_stored_resume_identity
from abi.runtimes.base import RuntimeOptions, RuntimeResult
from abi.runtimes.nextflow import _dag_summary
from abi.schemas import ABIError
from abi.timeouts import (
    DEFAULT_TOOL_TIMEOUT_SECONDS,
    mapping_block,
    timeout_from_env_or_value,
)
from abi.tools import validate_container_images_ready


class SnakemakeRuntime:
    """Run ABI plans through generated Snakemake Snakefiles."""

    def __init__(self, plugin: Any, *, options: RuntimeOptions | None = None) -> None:
        self.plugin = plugin
        self.options = options or RuntimeOptions(engine="snakemake", smoke=True)
        self.exporter = SnakemakeExporter()

    def _execution_policy(self) -> ExecutionPolicy:
        return ExecutionPolicy(
            mamba_root=self.options.mamba_root,
            container_image=self.options.container_image,
            container_runtime=self.options.container_runtime,
            resource_profile=self.options.resource_profile,
            invocation_overrides=ResourceOverride(
                cpu=self.options.cpu_override,
                memory=self.options.memory_override,
                walltime=self.options.walltime_override,
                accelerator=self.options.accelerator_override,
            ),
        )

    def check(self) -> None:
        resolve_snakemake_bin(self.options.snakemake_bin)

    def dry_run(self, plan: object, config: Mapping[str, Any]) -> RuntimeResult:
        result_dir = Path(str(config["outdir"]))
        snakemake_dir = result_dir / "snakemake"
        snakefile_path = self.options.workflow or snakemake_dir / "Snakefile"
        dag = infer_dag(getattr(plan, "steps", []), sequential_fallback=True)
        self.exporter.write(
            plan,
            config,
            self.plugin.registry(),
            snakefile_path,
            smoke=self.options.smoke,
            mamba_root=self.options.mamba_root,
            dag=dag,
            execution_policy=self._execution_policy(),
            plugin_id=str(getattr(self.plugin, "plugin_id", getattr(plan, "analysis_type", ""))),
        )
        writer = ABIResultWriter(self.plugin, self.plugin.registry())
        outputs = writer.write(
            plan=plan,
            config=config,
            command_rows=_command_rows(
                plan,
                self.plugin.registry(),
                self.exporter,
                dag=dag,
                return_code=0,
                smoke=self.options.smoke,
                marker_dir=marker_dir_for(config, plan),
                dry_run=True,
            ),
            status="dry_run",
            return_code=0,
            engine="snakemake",
            smoke=self.options.smoke,
            container_image=self.options.container_image,
            container_runtime=self.options.container_runtime,
            extra_summary={"snakefile": str(snakefile_path), "dag": _dag_summary(dag)},
            extra_environment=_snakemake_environment(
                snakefile_path=snakefile_path,
                options=self.options,
            ),
        )
        outputs["snakefile"] = snakefile_path
        return RuntimeResult(status="dry_run", return_code=0, outputs=outputs)

    def run(self, plan: object, config: Mapping[str, Any]) -> RuntimeResult:
        registry = self.plugin.registry()
        result_dir = Path(str(config["outdir"]))
        validate_container_images_ready(
            plan,
            registry,
            config=config,
            cli_image=self.options.container_image,
            runtime=self.options.container_runtime,
        )
        if self.options.resume:
            snakemake_dir = result_dir / "snakemake"
            _reject_unsafe_resume(
                result_dir,
                runtime_resume_identity(
                    plan,
                    config,
                    registry,
                    smoke=self.options.smoke,
                    plan_id=str(getattr(self.options, "confirmed_plan_id", "") or ""),
                    cli_image=self.options.container_image,
                    container_runtime=self.options.container_runtime,
                ),
                cache_paths=(snakemake_dir,),
            )
        snakemake_dir = result_dir / "snakemake"
        snakefile_path = self.options.workflow or snakemake_dir / "Snakefile"
        stdout_path = snakemake_dir / "snakemake.stdout.log"
        stderr_path = snakemake_dir / "snakemake.stderr.log"
        snakemake_bin = resolve_snakemake_bin(self.options.snakemake_bin)
        dag = infer_dag(getattr(plan, "steps", []), sequential_fallback=True)

        snakefile_path = self.exporter.write(
            plan,
            config,
            registry,
            snakefile_path,
            smoke=self.options.smoke,
            mamba_root=self.options.mamba_root,
            dag=dag,
            execution_policy=self._execution_policy(),
            plugin_id=str(getattr(self.plugin, "plugin_id", getattr(plan, "analysis_type", ""))),
        )
        snakemake_dir.mkdir(parents=True, exist_ok=True)
        cores = _cores_for(plan, config, self.options)
        command = [
            str(snakemake_bin),
            "--snakefile",
            str(snakefile_path),
            "--cores",
            str(cores),
            "--rerun-incomplete",
            "--printshellcmds",
        ]

        with (
            stdout_path.open("w", encoding="utf-8") as stdout_handle,
            stderr_path.open("w", encoding="utf-8") as stderr_handle,
        ):
            timeout_seconds = _snakemake_timeout_seconds(config, self.options)
            timeout_error: subprocess.TimeoutExpired | None = None
            try:
                result = subprocess.run(
                    command,
                    cwd=snakemake_dir,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    text=True,
                    check=False,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                timeout_error = exc

        if timeout_error is not None:
            _write_timeout_result(
                self,
                plan,
                config,
                registry,
                snakefile_path=snakefile_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                command=command,
                dag=dag,
                marker_dir=marker_dir_for(config, plan),
                timeout_seconds=timeout_seconds,
            )
            raise ABIError(
                "Snakemake run timed out after "
                f"{timeout_seconds:g}s; stdout: {stdout_path}; stderr: {stderr_path}"
            ) from timeout_error

        marker_dir = marker_dir_for(config, plan)
        status = "success" if result.returncode == 0 else "failed"
        writer = ABIResultWriter(self.plugin, registry)
        outputs = writer.write(
            plan=plan,
            config=config,
            command_rows=_command_rows(
                plan,
                registry,
                self.exporter,
                dag=dag,
                return_code=result.returncode,
                smoke=self.options.smoke,
                marker_dir=marker_dir,
                dry_run=False,
            ),
            status=status,
            return_code=result.returncode,
            engine="snakemake",
            smoke=self.options.smoke,
            resume=self.options.resume,
            plan_id=str(getattr(self.options, "confirmed_plan_id", "") or ""),
            container_image=self.options.container_image,
            container_runtime=self.options.container_runtime,
            extra_summary={
                "snakefile": str(snakefile_path),
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "command": " ".join(command),
                "cores": cores,
                "dag": _dag_summary(dag),
            },
            extra_environment=_snakemake_environment(
                snakefile_path=snakefile_path,
                options=self.options,
            ),
        )
        outputs.update(
            {
                "snakefile": snakefile_path,
                "snakemake_stdout": stdout_path,
                "snakemake_stderr": stderr_path,
            }
        )
        if result.returncode != 0:
            raise ABIError(
                f"Snakemake run failed with exit code {result.returncode}; stderr: {stderr_path}"
            )
        return RuntimeResult(status=status, return_code=result.returncode, outputs=outputs)


def _snakemake_timeout_seconds(
    config: Mapping[str, Any],
    options: RuntimeOptions,
) -> float | None:
    execution = mapping_block(config, "execution")
    value = options.timeout_seconds
    if value is None:
        value = execution.get("snakemake_timeout_seconds")
    if value is None:
        value = execution.get("tool_timeout_seconds")
    return timeout_from_env_or_value(
        "ABI_SNAKEMAKE_TIMEOUT_SECONDS",
        value,
        default=DEFAULT_TOOL_TIMEOUT_SECONDS,
    )


def _reject_unsafe_resume(
    result_dir: Path,
    current: Mapping[str, Any],
    *,
    cache_paths: tuple[Path, ...] = (),
) -> None:
    reasons = validate_stored_resume_identity(result_dir, current, cache_paths=cache_paths)
    if reasons:
        raise ABIError(
            "Refusing Snakemake resume because execution identity changed or is incomplete: "
            + "; ".join(reasons)
        )


def _write_timeout_result(
    runtime: SnakemakeRuntime,
    plan: object,
    config: Mapping[str, Any],
    registry: Any,
    *,
    snakefile_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    command: list[str],
    dag: ABIDAG,
    marker_dir: Path,
    timeout_seconds: float | None,
) -> Dict[str, Path]:
    writer = ABIResultWriter(runtime.plugin, registry)
    return writer.write(
        plan=plan,
        config=config,
        command_rows=_command_rows(
            plan,
            registry,
            runtime.exporter,
            dag=dag,
            return_code=-1,
            smoke=runtime.options.smoke,
            marker_dir=marker_dir,
            dry_run=False,
            status_override="timeout",
            reason_override=(
                "Snakemake engine timeout; engine termination was confirmed by "
                "subprocess timeout handling; downstream scheduler state is unknown"
            ),
        ),
        status="timeout",
        return_code=-1,
        engine="snakemake",
        smoke=runtime.options.smoke,
        resume=runtime.options.resume,
        plan_id=str(getattr(runtime.options, "confirmed_plan_id", "") or ""),
        container_image=runtime.options.container_image,
        container_runtime=runtime.options.container_runtime,
        extra_summary={
            "snakefile": str(snakefile_path),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "command": " ".join(command),
            "termination": {
                "request": "timeout",
                "requested": True,
                "confirmed": True,
                "scope": "snakemake_engine_process",
                "downstream_status": "unknown",
                "timeout_seconds": timeout_seconds,
            },
        },
        extra_environment=_snakemake_environment(
            snakefile_path=snakefile_path,
            options=runtime.options,
        ),
    )


def resolve_snakemake_bin(snakemake_bin: Path | None) -> Path:
    """Resolve the snakemake executable from options, env, or PATH.

    No dedicated conda env is created for Snakemake (mirrors the decision to
    keep the repository's environment count stable): the binary is expected
    on PATH or provided explicitly.
    """
    candidates = []
    if snakemake_bin:
        candidates.append(snakemake_bin)
    env_value = os.environ.get("ABI_SNAKEMAKE_BIN")
    if env_value:
        candidates.append(Path(env_value))
    path_value = shutil.which("snakemake")
    if path_value:
        candidates.append(Path(path_value))
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ABIError(
        "Snakemake executable was not found. Install it (e.g. `pip install snakemake` "
        "or into an existing tool environment), set ABI_SNAKEMAKE_BIN, or pass "
        "RuntimeOptions.snakemake_bin."
    )


def _cores_for(plan: Any, config: Mapping[str, Any], options: RuntimeOptions) -> int:
    for value in (options.cpu_override, getattr(plan, "threads", None), config.get("threads")):
        if value:
            return max(1, int(value))
    return 1


def _command_rows(
    plan: Any,
    registry: Any,
    exporter: SnakemakeExporter,
    *,
    dag: ABIDAG,
    return_code: int,
    smoke: bool,
    marker_dir: Path,
    dry_run: bool,
    status_override: str | None = None,
    reason_override: str = "",
) -> list[dict[str, Any]]:
    rows = []
    fallback_status = "dry_run" if dry_run else ("success" if return_code == 0 else "failed")
    for binding in dag.bindings:
        step = binding.step
        status = status_override or _status_from_marker(
            marker_dir, binding.process_name, fallback=fallback_status, dry_run=dry_run
        )
        step_return_code: int | str = "" if dry_run else (0 if status == "success" else return_code)
        rows.append(
            {
                "step_id": step.step_id,
                "sample_id": step.sample_id,
                "step_name": step.step_name,
                "tool_id": step.tool_id,
                "category": step.category,
                "command": exporter.command_for_step(step, registry, smoke=smoke),
                "status": status,
                "return_code": step_return_code,
                "remote_scheduler_job_id": "",
                "reason": (
                    reason_override
                    if reason_override
                    else ("" if status in {"success", "dry_run"} else "Snakemake rule failed")
                ),
                "parsed_status": "smoke" if smoke and status == "success" else "",
                "standard_tables": "",
            }
        )
    return rows


def _status_from_marker(
    marker_dir: Path, process_name: str, *, fallback: str, dry_run: bool
) -> str:
    """Recover per-step status from the rule's ``.done`` marker file."""
    if dry_run:
        return fallback
    if _marker_path(marker_dir, process_name).exists():
        return "success"
    return fallback


def _snakemake_environment(
    *,
    snakefile_path: Path,
    options: RuntimeOptions,
) -> Dict[str, Any]:
    return {
        "snakefile": str(snakefile_path),
        "snakemake_bin": str(options.snakemake_bin or ""),
    }
