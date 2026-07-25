"""Export ABI execution plans to Snakemake Snakefiles."""

from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Mapping

from abi.config import PROJECT_ROOT
from abi.dag import ABIDAG, StepBinding, infer_dag
from abi.errors import ToolError
from abi.execution_policy import ExecutionPolicy
from abi.exporters.nextflow import (
    _absolute_path,
    _command_text,
    _output_setup_lines,
    _transitive_downstream,
)
from abi.internal import internal_handler_spec
from abi.tools import ToolRegistry


def marker_dir_for(
    config: Mapping[str, Any],
    plan: Any,
    *,
    project_root: str | Path | None = None,
) -> Path:
    """Return the directory holding per-step ``.done`` marker files.

    Markers are the Snakemake analogue of Nextflow's trigger channels: every
    rule touches one marker on success, and downstream rules declare upstream
    markers as inputs.  The runtime also reads them to recover per-step
    status after a run.
    """
    root = Path(project_root or PROJECT_ROOT).resolve()
    outdir = str(config.get("outdir") or getattr(plan, "outdir", "") or "results")
    path = Path(outdir)
    if not path.is_absolute():
        path = (root / path).resolve()
    return path / ".abi_snakemake" / "markers"


def _marker_path(marker_dir: Path, process_name: str) -> Path:
    return marker_dir / f"{process_name}.done"


class SnakemakeExporter:
    """Render an ABI execution plan as a Snakemake Snakefile."""

    def export(
        self,
        plan: Any,
        config: Mapping[str, Any],
        registry: ToolRegistry,
        *,
        smoke: bool = False,
        project_root: str | Path | None = None,
        mamba_root: str | Path | None = None,
        dag: ABIDAG | None = None,
        execution_policy: ExecutionPolicy | None = None,
        plugin_id: str | None = None,
    ) -> str:
        """Generate a complete Snakefile."""
        root = Path(project_root or PROJECT_ROOT).resolve()
        policy = execution_policy or ExecutionPolicy()
        abi_dag = dag or infer_dag(
            getattr(plan, "steps", []),
            project_root=root,
            sequential_fallback=True,
        )
        self._check_internal_dependencies(abi_dag)
        marker_dir = marker_dir_for(config, plan, project_root=root)
        sections = [
            self._header(plan, smoke=smoke),
            # Snakemake runs the first rule by default, so ``rule all`` leads.
            self._rule_all(abi_dag, marker_dir=marker_dir),
            self._rule_definitions(
                abi_dag,
                registry,
                smoke=smoke,
                project_root=root,
                config=config,
                execution_policy=policy,
                plugin_id=plugin_id or str(getattr(plan, "analysis_type", "")),
                marker_dir=marker_dir,
            ),
        ]
        return "\n\n".join(section for section in sections if section).rstrip() + "\n"

    def write(
        self,
        plan: Any,
        config: Mapping[str, Any],
        registry: ToolRegistry,
        output_path: str | Path,
        *,
        smoke: bool = False,
        project_root: str | Path | None = None,
        mamba_root: str | Path | None = None,
        dag: ABIDAG | None = None,
        execution_policy: ExecutionPolicy | None = None,
        plugin_id: str | None = None,
    ) -> Path:
        """Write the generated Snakefile to disk."""
        path = Path(output_path)
        rendered = self.export(
            plan,
            config,
            registry,
            smoke=smoke,
            project_root=project_root,
            mamba_root=mamba_root,
            dag=dag,
            execution_policy=execution_policy,
            plugin_id=plugin_id,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        os.replace(temporary, path)
        return path

    def command_for_step(
        self,
        step: Any,
        registry: ToolRegistry,
        *,
        smoke: bool = False,
        project_root: str | Path | None = None,
    ) -> str:
        """Return the displayed shell command for one ABI step."""
        if smoke:
            return f"abi-snakemake-smoke --step-id {shlex.quote(str(getattr(step, 'step_id', '')))}"
        root = Path(project_root or PROJECT_ROOT).resolve()
        return _command_text(step, registry, project_root=root)

    @staticmethod
    def _check_internal_dependencies(dag: ABIDAG) -> None:
        """Raise :exc:`ToolError` for every **driver**-scoped internal step.

        Worker-scoped handlers generate Snakefile rules that call
        ``abi run-step``.  Driver-scoped handlers do not have a verified
        Snakemake execution path, so exporting one would silently skip
        required work — same policy as the Nextflow exporter.
        """
        affected: list[str] = []
        for binding in dag.bindings:
            tool_id = str(getattr(binding.step, "tool_id", ""))
            if tool_id != "internal":
                continue
            _handler_id, scope = internal_handler_spec(binding.step)
            if scope == "worker":
                # Supported — will generate a Snakemake rule.
                continue
            step_id = str(getattr(binding.step, "step_id", "?"))
            handler_id = _handler_id or "?"
            downstream = _transitive_downstream(dag, step_id)
            suffix = f"; downstream: {', '.join(downstream)}" if downstream else ""
            affected.append(f"  step {step_id} (handler {handler_id!r}){suffix}")

        if affected:
            raise ToolError(
                "Snakemake export blocked: driver-scoped internal handlers are not "
                "executed by the Snakemake runtime and must not be skipped silently.\n"
                + "\n".join(affected)
                + "\n\nRun the workflow with a runtime that executes driver handlers."
            )

    def _header(self, plan: Any, *, smoke: bool) -> str:
        analysis_type = getattr(plan, "analysis_type", "")
        project_name = getattr(plan, "project_name", "")
        mode = "smoke" if smoke else "real"
        return "\n".join(
            [
                "# Generated by ABI SnakemakeExporter.",
                f"# Project: {project_name}",
                f"# Analysis type: {analysis_type}",
                f"# Export mode: {mode}",
            ]
        )

    def _rule_all(self, dag: ABIDAG, *, marker_dir: Path) -> str:
        if not dag.topological_order:
            return "\n".join(
                [
                    "rule all:",
                    "    shell:",
                    "        \"echo 'ABI plan has no exportable external steps'\"",
                ]
            )
        lines = ["rule all:", "    input:"]
        for step_id in dag.topological_order:
            binding = dag.binding_for(step_id)
            marker = _marker_path(marker_dir, binding.process_name)
            lines.append(f"        {_python_literal(str(marker))},")
        return "\n".join(lines)

    def _rule_definitions(
        self,
        dag: ABIDAG,
        registry: ToolRegistry,
        *,
        smoke: bool,
        project_root: Path,
        config: Mapping[str, Any],
        execution_policy: ExecutionPolicy,
        plugin_id: str,
        marker_dir: Path,
    ) -> str:
        rules = []
        for step_id in dag.topological_order:
            binding = dag.binding_for(step_id)
            tool_id = str(getattr(binding.step, "tool_id", ""))
            if tool_id == "internal":
                _handler_id, scope = internal_handler_spec(binding.step)
                if scope == "driver":
                    # Driver handlers run on the control node before
                    # Snakemake starts — they have no rule.
                    continue
                # Worker-scoped internal handler → generate a rule that
                # calls abi run-step (same contract as the Nextflow C09 path).
                rules.append(
                    self._internal_worker_rule(
                        binding,
                        smoke=smoke,
                        config=config,
                        plugin_id=plugin_id,
                        marker_dir=marker_dir,
                    )
                )
                continue
            rules.append(
                self._step_to_rule(
                    binding,
                    dag,
                    registry,
                    smoke=smoke,
                    project_root=project_root,
                    config=config,
                    execution_policy=execution_policy,
                    marker_dir=marker_dir,
                )
            )
        return "\n\n".join(rules)

    def _step_to_rule(
        self,
        binding: StepBinding,
        dag: ABIDAG,
        registry: ToolRegistry,
        *,
        smoke: bool,
        project_root: Path,
        config: Mapping[str, Any],
        execution_policy: ExecutionPolicy,
        marker_dir: Path,
    ) -> str:
        step = binding.step
        process_name = binding.process_name
        command = (
            _smoke_command_text(step, project_root=project_root)
            if smoke
            else _command_text(step, registry, project_root=project_root)
        )
        setup_lines = _output_setup_lines(getattr(step, "outputs", {}), project_root=project_root)
        step_token = _shell_token(str(getattr(step, "step_id", process_name)))
        done_marker = f"__ABI_STEP_DONE_{step_token}__"
        script_lines = [
            "set -euo pipefail",
            *setup_lines,
            command,
            f"echo {shlex.quote(done_marker)}",
        ]
        script = "\n".join(f"        {line}" for line in script_lines if line)
        # Snakemake shell strings undergo .format()-style substitution, so
        # literal braces (e.g. bash ${var}) must be doubled.
        script = _escape_braces(script)

        lines = [f"rule {process_name}:"]
        if binding.dependencies:
            lines.append("    input:")
            for dependency in binding.dependencies:
                dependency_marker = _marker_path(
                    marker_dir, dag.binding_for(dependency).process_name
                )
                lines.append(f"        {_python_literal(str(dependency_marker))},")
        lines.append("    output:")
        lines.append(
            f"        touch({_python_literal(str(_marker_path(marker_dir, process_name)))})"
        )
        lines.extend(
            self._resource_directive_lines(
                binding, registry, config=config, execution_policy=execution_policy
            )
        )
        if not smoke:
            conda_env = _conda_env_path(step, registry, project_root=project_root)
            if conda_env is not None:
                lines.append("    conda:")
                lines.append(f"        {_python_literal(str(conda_env))}")
        lines.append("    shell:")
        lines.append(f'        """\n{script}\n        """')
        return "\n".join(lines)

    def _internal_worker_rule(
        self,
        binding: StepBinding,
        *,
        smoke: bool,
        config: Mapping[str, Any],
        plugin_id: str,
        marker_dir: Path,
    ) -> str:
        """Generate a Snakemake rule for a worker-scoped internal handler.

        The rule writes a step payload, invokes ``abi run-step``, and touches
        the step marker.  This reuses the existing step runner and CLI path
        so there is exactly one execution path (mirrors the Nextflow C09
        process).
        """
        step = binding.step
        process_name = binding.process_name
        step_id = str(getattr(step, "step_id", process_name))
        outdir = getattr(step, "outputs", {}).get("output_dir", ".abi-work")

        if smoke:
            cmd = "abi-snakemake-smoke --step-id " + step_id
            payload_section = "printf '{}\\n' > .abi_result.json\n"
        else:
            provenance_dir = getattr(step, "provenance_dir", None) or config.get(
                "provenance_dir", Path(str(config.get("outdir", outdir))) / "provenance"
            )
            payload = {
                "plugin_id": plugin_id,
                "step": step.to_dict(),
                "config": dict(config),
                "provenance_dir": str(provenance_dir),
                "result_path": ".abi_result.json",
            }
            payload_json = json.dumps(payload, indent=2, default=str)
            payload_section = (
                f"cat > .abi_payload.json <<'ABI_PAYLOAD'\n{payload_json}\nABI_PAYLOAD\n"
                "chmod 600 .abi_payload.json\n"
            )
            cmd = "abi run-step --payload-file .abi_payload.json"

        done_marker = f"__ABI_STEP_DONE_{_shell_token(step_id)}__"
        script_lines = [
            "set -euo pipefail",
            f"mkdir -p {shlex.quote(str(outdir))}",
            f"mkdir -p {shlex.quote(str(outdir))}/provenance/step_logs",
            payload_section,
            cmd,
            f"echo {shlex.quote(done_marker)}",
        ]
        script = "\n".join(f"        {line}" for line in script_lines if line)
        script = _escape_braces(script)

        lines = [f"rule {process_name}:"]
        lines.append("    output:")
        lines.append(
            f"        touch({_python_literal(str(_marker_path(marker_dir, process_name)))})"
        )
        lines.append("    threads: 1")
        lines.append("    shell:")
        lines.append(f'        """\n{script}\n        """')
        return "\n".join(lines)

    def _resource_directive_lines(
        self,
        binding: StepBinding,
        registry: ToolRegistry,
        *,
        config: Mapping[str, Any] | None = None,
        execution_policy: ExecutionPolicy | None = None,
    ) -> list[str]:
        """Render Snakemake ``threads:``/``resources:`` lines for one rule.

        Uses the sentinel-based ``resolve_resources_v2`` (C06) so explicit
        overrides are preserved even when they equal the default value —
        same policy as the Nextflow exporter.
        """
        from abi.execution_policy import resolve_resources_v2
        from abi.tools import ResourceSpec

        step = binding.step
        tool_id = getattr(step, "tool_id", "")
        meta = registry.get(tool_id) if tool_id else {}
        policy = execution_policy or ExecutionPolicy()
        spec = resolve_resources_v2(
            tool_id,
            meta,
            config=config,
            cli_overrides=policy.invocation_overrides,
            resource_profile=policy.resource_profile,
            resource_profiles_dir=policy.resource_profiles_dir,
        )

        # Only emit non-default values / 只输出非默认值
        lines = [f"    threads: {spec.cpu}"]
        defaults = ResourceSpec()
        resources: list[str] = []
        if spec.memory != defaults.memory:
            mem_mb = _size_to_mb(spec.memory)
            if mem_mb is not None:
                resources.append(f"mem_mb={mem_mb}")
        if spec.walltime != defaults.walltime:
            minutes = _walltime_to_minutes(spec.walltime)
            if minutes is not None:
                resources.append(f"runtime={minutes}")
        if spec.disk and spec.disk != defaults.disk:
            disk_mb = _size_to_mb(spec.disk)
            if disk_mb is not None:
                resources.append(f"disk_mb={disk_mb}")
        if spec.accelerator:
            resources.append(f"gpu={_gpu_count(spec.accelerator)}")
        if resources:
            lines.append("    resources:")
            lines.append("        " + ", ".join(resources))
        return lines


def _conda_env_path(step: Any, registry: ToolRegistry, *, project_root: Path) -> Path | None:
    """Return the env YAML for the step's tool→env binding, if one exists."""
    tool_id = str(getattr(step, "tool_id", ""))
    if not registry.has(tool_id):
        return None
    env_name = str(registry.get(tool_id).get("env_name", ""))
    if not env_name:
        return None
    candidate = project_root / "envs" / f"{env_name}.yml"
    return candidate if candidate.exists() else None


def _smoke_command_text(step: Any, *, project_root: Path) -> str:
    outputs = getattr(step, "outputs", {})
    lines = [f"echo 'ABI Snakemake smoke step: {shlex.quote(str(getattr(step, 'step_id', '')))}'"]
    for key, value in sorted(outputs.items()):
        if value in (None, ""):
            continue
        path = _absolute_path(str(value), project_root)
        if path.suffix:
            output_path = shlex.quote(str(path))
            lines.append(f"printf 'ABI Snakemake smoke output for {key}\\n' > {output_path}")
        else:
            lines.append(f"touch {shlex.quote(str(path / '.abi_smoke_marker'))}")
    return "\n        ".join(lines)


def _size_to_mb(value: str) -> int | None:
    """Convert ``"16GB"``/``"500MB"``/``"1TB"`` to integer megabytes."""
    match = re.match(r"(\d+)\s*(GB|MB|TB|G|M|T)", value.upper().replace(" ", ""))
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit in ("M", "MB"):
        return amount
    if unit in ("G", "GB"):
        return amount * 1024
    return amount * 1024 * 1024


def _walltime_to_minutes(value: str) -> int | None:
    """Convert ``"HH:MM:SS"`` (or plain minutes) to integer minutes."""
    parts = value.split(":")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
        return hours * 60 + minutes + (1 if seconds else 0)
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes + (1 if seconds else 0)
    if len(numbers) == 1:
        return numbers[0]
    return None


def _gpu_count(accelerator: str) -> int:
    match = re.search(r"(\d+)$", accelerator)
    return int(match.group(1)) if match else 1


def _shell_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").upper()
    return token or "ABI_STEP"


def _python_literal(value: str) -> str:
    """Return a double-quoted string literal valid in Snakefile Python."""
    return json.dumps(value)


def _escape_braces(script: str) -> str:
    """Double literal braces so Snakemake shell substitution leaves them alone."""
    return script.replace("{", "{{").replace("}", "}}")
