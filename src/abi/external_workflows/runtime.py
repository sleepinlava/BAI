"""Managed Nextflow execution for ABI external-workflow plugins."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping

from abi.config import PROJECT_ROOT
from abi.external_workflows.diagnostics import summarize_run_diagnostics
from abi.external_workflows.evidence import (
    archive_evidence_files,
    sha256_file,
    sync_manifest_artifacts,
)
from abi.external_workflows.nextflow import import_nextflow_trace, write_task_attempts_tsv
from abi.results import ABIResultWriter
from abi.resume import runtime_resume_identity, validate_stored_resume_identity
from abi.runtimes.base import RuntimeOptions, RuntimeResult
from abi.schemas import ABIError
from abi.timeouts import DEFAULT_TOOL_TIMEOUT_SECONDS, mapping_block, timeout_from_env_or_value
from abi.tools import container_image_identities, validate_container_images_ready


class ManagedExternalNextflowRuntime:
    """Run a pinned upstream workflow while retaining ABI-owned evidence."""

    def __init__(self, plugin: Any, options: RuntimeOptions) -> None:
        self.plugin = plugin
        self.options = options

    def dry_run(self, plan: Any, config: Mapping[str, Any]) -> RuntimeResult:
        layout = self._layout(config)
        sheet = self.plugin.convert_sample_sheet(
            config["input"]["sample_sheet"], layout["samplesheet"], check_files=True
        )
        spec = self.plugin.external_workflow_spec(config, plan)
        snapshot = self._write_snapshot(
            plan, config, spec, sheet.sha256, layout["snapshot"], argv=spec.argv
        )
        writer = ABIResultWriter(self.plugin, self.plugin.registry())
        outputs = writer.write(
            plan=plan,
            config=config,
            command_rows=[self._parent_command_row(plan, spec.argv, "dry_run", "")],
            status="dry_run",
            return_code=0,
            engine="nextflow",
            smoke=self.options.smoke,
            resume=self.options.resume,
            plan_id=str(getattr(self.options, "confirmed_plan_id", "") or ""),
            extra_summary={
                "managed_external_workflow": True,
                "plan_fidelity": snapshot["plan_fidelity"],
                "argv": list(spec.argv),
            },
        )
        outputs.update(
            {
                "external_plan_snapshot": layout["snapshot"],
                "bacannot_samplesheet": layout["samplesheet"],
            }
        )
        return RuntimeResult(status="dry_run", return_code=0, outputs=outputs)

    def run(self, plan: Any, config: Mapping[str, Any]) -> RuntimeResult:
        from abi.runtimes.nextflow import parse_nextflow_trace, resolve_nextflow_bin

        layout = self._layout(config)
        sheet = self.plugin.convert_sample_sheet(
            config["input"]["sample_sheet"], layout["samplesheet"], check_files=True
        )
        spec = self.plugin.external_workflow_spec(config, plan)
        if self.options.resume and not spec.resume:
            spec = replace(spec, resume=True)
        registry = self.plugin.registry()
        external_container_rows = self._validate_container_readiness(plan, config, spec, registry)
        resume_requested = bool(self.options.resume or spec.resume)
        if resume_requested:
            current_identity = runtime_resume_identity(
                plan,
                config,
                registry,
                smoke=self.options.smoke,
                plan_id=str(getattr(self.options, "confirmed_plan_id", "") or ""),
                cli_image=self.options.container_image,
                container_runtime=self.options.container_runtime,
                extra_containers=external_container_rows,
            )
            reasons = validate_stored_resume_identity(
                layout["root"],
                current_identity,
                cache_paths=(layout["nextflow_dir"], layout["work_dir"], layout["nxf_home"]),
            )
            if reasons:
                raise ABIError(
                    "Refusing managed Nextflow resume because execution identity changed or "
                    "is incomplete: " + "; ".join(reasons)
                )
        lineage = self._archive_previous_run(spec, layout)
        nextflow_bin = resolve_nextflow_bin(self.options.nextflow_bin, self.options.mamba_root)
        command = self._command(nextflow_bin, spec, layout)
        snapshot = self._write_snapshot(
            plan,
            config,
            spec,
            sheet.sha256,
            layout["snapshot"],
            argv=command,
            run_id=lineage["run_id"],
            lineage=lineage["snapshot_fields"],
        )
        layout["nextflow_dir"].mkdir(parents=True, exist_ok=True)
        layout["work_dir"].mkdir(parents=True, exist_ok=True)
        layout["nxf_home"].mkdir(parents=True, exist_ok=True)
        layout["stdout"].parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["NXF_HOME"] = str(layout["nxf_home"])
        environment.setdefault("NXF_ANSI_LOG", "false")
        return_code = 1
        execution_error: Exception | None = None
        timeout_error: subprocess.TimeoutExpired | None = None
        timeout_seconds = self._timeout(config)
        try:
            with (
                layout["stdout"].open("w", encoding="utf-8") as stdout,
                layout["stderr"].open("w", encoding="utf-8") as stderr,
            ):
                completed = subprocess.run(
                    command,
                    cwd=layout["nextflow_dir"],
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    check=False,
                    timeout=timeout_seconds,
                )
                return_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            timeout_error = exc
            execution_error = exc
            return_code = -1
        except Exception as exc:
            execution_error = exc

        sources = [
            (layout["snapshot"], "external_plan_snapshot"),
            (layout["trace"], "nextflow_trace"),
            (layout["report"], "nextflow_report"),
            (layout["timeline"], "nextflow_timeline"),
            (layout["dag"], "nextflow_dag"),
            (layout["log"], "nextflow_log"),
            (layout["stdout"], "workflow_stdout"),
            (layout["stderr"], "workflow_stderr"),
            (layout["samplesheet"], "generated_samplesheet"),
        ]
        bundle_manifest = archive_evidence_files(
            sources,
            layout["external_bundle"],
            collector_version="abi-external-nextflow-v1",
        )
        evidence_manifest = self._promote_manifest(bundle_manifest, layout["evidence_manifest"])
        archived_trace = self._archived_evidence_path(
            evidence_manifest, evidence_type="nextflow_trace"
        )
        attempts = import_nextflow_trace(
            archived_trace,
            external_workflow_id=lineage["run_id"],
            process_mapper=getattr(self.plugin, "map_external_process", None),
        )
        attempts = self._archive_task_logs(attempts, layout, evidence_manifest)
        task_attempts = write_task_attempts_tsv(attempts, layout["task_attempts"])
        self._append_archived_evidence(
            task_attempts,
            evidence_type="task_attempts",
            layout=layout,
            manifest_path=evidence_manifest,
        )
        diagnostics = summarize_run_diagnostics(
            attempts, unmapped_policy=self._unmapped_policy(config)
        )
        diagnostics_path = layout["provenance"] / "diagnostics.json"
        diagnostics_path.write_text(
            json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        normalized_outputs: Mapping[str, Path] = {}
        validation: Mapping[str, Any] = {"valid": False, "errors": []}
        if return_code == 0 and execution_error is None:
            try:
                normalize_outputs = getattr(self.plugin, "normalize_external_outputs")
                normalized_outputs = normalize_outputs(config, attempts)
                validation = self.plugin.validate_result_dir(config["outdir"])
            except Exception as exc:
                validation = {
                    "valid": False,
                    "errors": [
                        {
                            "error_code": "OUTPUT_PARSE_FAILED",
                            "parser_version": str(
                                getattr(self.plugin, "external_parser_version", "unknown")
                            ),
                            "message": str(exc),
                        }
                    ],
                }
        validation_path = Path(str(config["outdir"])) / "validation.json"
        validation_path.write_text(
            json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        status = (
            "timeout"
            if timeout_error is not None
            else (
                "success"
                if return_code == 0 and execution_error is None and validation.get("valid") is True
                else "failed"
            )
        )
        termination = (
            {
                "request": "timeout",
                "requested": True,
                "confirmed": True,
                "scope": "managed_nextflow_engine_process",
                "downstream_status": "unknown",
                "timeout_seconds": timeout_seconds,
            }
            if timeout_error is not None
            else None
        )
        writer = ABIResultWriter(self.plugin, self.plugin.registry())
        outputs = writer.write(
            plan=plan,
            config=config,
            command_rows=[self._parent_command_row(plan, command, status, return_code)],
            status=status,
            return_code=return_code,
            engine="nextflow",
            smoke=self.options.smoke,
            resume=resume_requested,
            plan_id=str(getattr(self.options, "confirmed_plan_id", "") or ""),
            container_image=self.options.container_image,
            container_runtime=self.options.container_runtime,
            extra_container_identities=external_container_rows,
            trace_rows=parse_nextflow_trace(archived_trace),
            extra_summary={
                "managed_external_workflow": True,
                "plan_fidelity": snapshot["plan_fidelity"],
                "argv": command,
                "task_attempt_count": len(attempts),
                "evidence_complete": json.loads(evidence_manifest.read_text(encoding="utf-8"))[
                    "complete"
                ],
                "resume": spec.resume,
                "resume_lineage": lineage["snapshot_fields"],
                "resume_reconciliation": _resume_reconciliation(attempts),
                "diagnostics": diagnostics,
                **({"termination": termination} if termination is not None else {}),
            },
            extra_environment={
                "external_workflow": spec.to_dict(),
                "work_dir": str(layout["work_dir"]),
                "nxf_home": str(layout["nxf_home"]),
            },
        )
        outputs.update(
            {
                "task_attempts": task_attempts,
                "evidence_manifest": evidence_manifest,
                "external_plan_snapshot": layout["snapshot"],
                "diagnostics": diagnostics_path,
                "bacannot_samplesheet": layout["samplesheet"],
                "nextflow_trace": layout["trace"],
                "nextflow_report": layout["report"],
                "nextflow_timeline": layout["timeline"],
                "nextflow_dag": layout["dag"],
                "nextflow_log": layout["log"],
                "validation": validation_path,
            }
        )
        outputs.update(normalized_outputs)
        if execution_error is not None or return_code != 0 or validation.get("valid") is not True:
            raise self._failure_error(
                return_code, execution_error, validation, diagnostics, evidence_manifest
            ) from execution_error
        return RuntimeResult(status=status, return_code=return_code, outputs=outputs)

    def _external_container_rows(
        self,
        plan: Any,
        config: Mapping[str, Any],
        spec: Any,
    ) -> list[dict[str, str]]:
        """Return the plugin-declared process images with stable identities."""
        hook = getattr(self.plugin, "external_container_images", None)
        if callable(hook):
            declared = hook(config, plan)
        else:
            metadata_hook = getattr(self.plugin, "external_snapshot_metadata", None)
            metadata = dict(metadata_hook(config)) if callable(metadata_hook) else {}
            declared = metadata.get("containers", [])
        rows: list[dict[str, str]] = []
        for index, entry in enumerate(declared or ()):
            if isinstance(entry, str):
                image = entry
                tool_id = f"external:{index}"
                digest = ""
            elif isinstance(entry, Mapping):
                image = str(entry.get("image") or entry.get("ref") or entry.get("path") or "")
                tool_id = str(entry.get("tool_id") or entry.get("id") or f"external:{index}")
                digest = str(entry.get("digest") or entry.get("sha256") or "")
            else:
                continue
            if image:
                rows.append(
                    {
                        "tool_id": tool_id,
                        "image": image,
                        "runtime": str(self.options.container_runtime or spec.profile),
                        "digest": digest,
                    }
                )
        return rows

    def _validate_container_readiness(
        self,
        plan: Any,
        config: Mapping[str, Any],
        spec: Any,
        registry: Any,
    ) -> list[dict[str, str]]:
        """Validate both ABI-declared and managed-workflow container images."""
        validate_container_images_ready(
            plan,
            registry,
            config=config,
            cli_image=self.options.container_image,
            runtime=self.options.container_runtime,
        )
        rows = self._external_container_rows(plan, config, spec)
        if not rows and not self.options.smoke:
            raise ABIError(
                "Managed external Nextflow does not expose a finite local container image "
                "set; declare external_container_images before starting a real run so "
                "ABI can refuse implicit image downloads"
            )
        if rows:
            from types import SimpleNamespace

            image_plan = SimpleNamespace(
                steps=[SimpleNamespace(tool_id=row["tool_id"]) for row in rows]
            )
            image_registry = SimpleNamespace(
                has=lambda _tool_id: True,
                get=lambda tool_id: {
                    "container_image": next(
                        row["image"] for row in rows if row["tool_id"] == tool_id
                    )
                },
            )
            return container_image_identities(
                image_plan,
                image_registry,
                # The plugin hook is authoritative for the managed workflow.
                # Do not pass the ABI config's default_image/tool_images here:
                # those settings describe ABI-owned steps and could make the
                # readiness check inspect a different image than the pinned
                # external workflow actually launches.
                config={},
                runtime=self.options.container_runtime or spec.profile,
                require_ready=True,
            )
        return rows

    def _write_snapshot(
        self,
        plan: Any,
        config: Mapping[str, Any],
        spec: Any,
        samplesheet_sha256: str,
        destination: Path,
        *,
        argv: Any,
        run_id: str | None = None,
        lineage: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        inputs = []
        for sample in plan.samples:
            for role in ("read1", "read2", "long_reads", "assembly"):
                value = getattr(sample, role, None)
                if not value:
                    continue
                path = Path(str(value))
                inputs.append(
                    {
                        "sample_id": sample.sample_id,
                        "role": role,
                        "path": str(path.resolve(strict=False)),
                        "size": path.stat().st_size if path.is_file() else None,
                        "mtime_ns": path.stat().st_mtime_ns if path.is_file() else None,
                        "sha256": sha256_file(path) if path.is_file() else "",
                    }
                )
        try:
            abi_version = version("abi-agent")
        except PackageNotFoundError:
            abi_version = "source-tree"
        metadata_hook = getattr(self.plugin, "external_snapshot_metadata", None)
        metadata = dict(metadata_hook(config)) if callable(metadata_hook) else {}
        lineage = dict(lineage or {})
        payload = {
            "schema_version": "abi.external-plan-snapshot.v1",
            "external_workflow_id": run_id or spec.workflow_id,
            "abi_version": abi_version,
            "abi_commit": self._abi_commit(),
            "plugin_version": str(metadata.get("plugin_version", "1")),
            "contract_version": str(metadata.get("contract_version", "unknown")),
            "workflow": {
                "source": spec.source,
                "revision": spec.revision,
                "commit_sha": spec.commit_sha,
                "entrypoint": spec.entrypoint,
            },
            "runtime": {
                "engine": spec.engine,
                "profile": spec.profile,
                "nextflow_version": metadata.get(
                    "nextflow_version",
                    {"status": "unavailable", "reason": "runtime not resolved during planning"},
                ),
                "java_version": metadata.get(
                    "java_version",
                    {"status": "unavailable", "reason": "runtime not resolved during planning"},
                ),
                "process_inspect": metadata.get(
                    "process_inspect",
                    {
                        "status": "unavailable",
                        "reason": "pinned workflow process graph is observed in the task trace",
                    },
                ),
            },
            "resolved_config": config,
            "generated_samplesheet_sha256": samplesheet_sha256,
            "resumes_run_id": lineage.get("resumes_run_id"),
            "previous_run_archive": lineage.get("previous_run_archive"),
            "inputs": inputs,
            "containers": list(metadata.get("containers", [])),
            "container_resolution": metadata.get("container_resolution", {}),
            "databases": list(metadata.get("databases", [])),
            "modules": dict(config["modules"]),
            "argv": list(argv),
            "plan_fidelity": {
                "declared": "external_workflow_with_expected_process_classes",
                "observed": "task_attempt_level",
            },
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return payload

    @staticmethod
    def _abi_commit() -> str:
        configured = os.environ.get("ABI_GIT_COMMIT", "").strip()
        if configured:
            return configured
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return completed.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return "unavailable:not-a-git-worktree"

    def _archive_previous_run(self, spec: Any, layout: Mapping[str, Path]) -> dict[str, Any]:
        """Preserve the previous run's evidence before this run rewrites it.

        Resume runs must link to, never mutate, the original run's evidence; a
        fresh re-run into the same outdir archives the previous evidence too so
        raw provenance is never silently overwritten.
        """
        base = str(spec.workflow_id)
        lineage: dict[str, Any] = {
            "run_id": base,
            "snapshot_fields": {"resumes_run_id": None, "previous_run_archive": None},
        }
        previous_snapshot = layout["snapshot"]
        if not previous_snapshot.is_file():
            return lineage
        try:
            previous = json.loads(previous_snapshot.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        previous_id = str(previous.get("external_workflow_id") or base)
        previous_runs = layout["provenance"] / "previous_runs"
        archive_root = previous_runs / _safe_archive_name(previous_id)
        archive_root.mkdir(parents=True, exist_ok=True)
        bundle_source = layout["external_bundle"]
        if bundle_source.is_dir():
            shutil.copytree(
                bundle_source,
                archive_root / bundle_source.relative_to(layout["provenance"]),
                dirs_exist_ok=True,
            )
        for name in (
            "external_plan_snapshot.json",
            "task_attempts.tsv",
            "evidence_manifest.json",
            "validation.json",
            "diagnostics.json",
        ):
            source = layout["provenance"] / name
            if source.is_file():
                shutil.copyfile(source, archive_root / name)
        # ABI may also keep a standalone result archive in this shared
        # directory.  Only count archives created for this external workflow;
        # unrelated ``unidentified-*`` or UUID-named ABI archives must not
        # change the external task-attempt identity.
        archive_prefix = _safe_archive_name(base)
        archived_count = sum(
            1
            for entry in previous_runs.iterdir()
            if entry.is_dir()
            and (entry.name == archive_prefix or entry.name.startswith(f"{archive_prefix}-r"))
        )
        lineage["run_id"] = f"{base}-r{archived_count}"
        lineage["snapshot_fields"] = {
            "resumes_run_id": previous_id if spec.resume else None,
            "previous_run_archive": archive_root.relative_to(layout["root"]).as_posix(),
        }
        return lineage

    @staticmethod
    def _failure_error(
        return_code: int,
        execution_error: Exception | None,
        validation: Mapping[str, Any],
        diagnostics: Mapping[str, Any],
        evidence_manifest: Path,
    ) -> ABIError:
        parts: list[str] = []
        if execution_error is not None:
            parts.append(f"Managed external Nextflow raised {type(execution_error).__name__}")
        if return_code != 0:
            parts.append(f"Managed external Nextflow exited with {return_code}")
        primary = str(diagnostics.get("primary_error_code") or "")
        if primary:
            parts.append(f"primary_error_code={primary}")
        failures = diagnostics.get("failed_attempts") or []
        if failures:
            first = dict(failures[0])
            parts.append(
                "failed task: process={process} sample={sample_id} attempt={attempt} "
                "exit_code={exit_code} stderr={stderr_path}".format(
                    **{
                        key: first.get(key, "")
                        for key in (
                            "process",
                            "sample_id",
                            "attempt",
                            "exit_code",
                            "stderr_path",
                        )
                    }
                )
            )
        if (
            execution_error is None
            and return_code == 0
            and isinstance(validation, Mapping)
            and validation.get("valid") is not True
        ):
            errors = validation.get("errors") or []
            if errors:
                first = dict(errors[0])
                detail = first.get("error_code") or first.get("message") or "validation error"
                parts.append(
                    f"L3 result validation failed ({detail}); "
                    "hints: " + "; ".join(str(h) for h in first.get("diagnostic_hints", []))
                )
            else:
                parts.append("L3 result validation failed")
        parts.append(f"diagnostics and evidence: {evidence_manifest}")
        return ABIError("; ".join(parts))

    @staticmethod
    def _unmapped_policy(config: Mapping[str, Any]) -> str:
        audit = mapping_block(config, "audit")
        return str(audit.get("unmapped_policy", "warn"))

    @staticmethod
    def _archived_evidence_path(manifest_path: Path, *, evidence_type: str) -> Path:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        for row in payload.get("files", []):
            if row.get("type") == evidence_type and row.get("complete") is True:
                return manifest_path.parent / str(row["path"])
        return manifest_path.parent / f"missing-{evidence_type}"

    @staticmethod
    def _command(nextflow_bin: Path, spec: Any, layout: Mapping[str, Path]) -> list[str]:
        argv = list(spec.argv)
        command = [str(nextflow_bin), "-log", str(layout["log"]), *argv[1:]]
        command.extend(
            [
                "-work-dir",
                str(layout["work_dir"]),
                "-with-trace",
                str(layout["trace"]),
                "-with-report",
                str(layout["report"]),
                "-with-timeline",
                str(layout["timeline"]),
                "-with-dag",
                str(layout["dag"]),
                "-profile",
                spec.profile,
            ]
        )
        if spec.resume:
            command.append("-resume")
        return command

    @staticmethod
    def _parent_command_row(
        plan: Any, command: Any, status: str, return_code: Any
    ) -> dict[str, Any]:
        step = plan.steps[0]
        rendered = " ".join(str(value) for value in command)
        return {
            "step_id": step.step_id,
            "sample_id": "",
            "step_name": step.step_name,
            "tool_id": step.tool_id,
            "category": step.category,
            "command": rendered,
            "status": status,
            "return_code": return_code,
            "reason": (
                ""
                if status in {"success", "dry_run"}
                else (
                    "External workflow timeout; engine termination was confirmed; "
                    "downstream status is unknown"
                    if status == "timeout"
                    else "External workflow failed"
                )
            ),
            "parsed_status": "",
            "standard_tables": "",
        }

    @staticmethod
    def _promote_manifest(source: Path, destination: Path) -> Path:
        payload = json.loads(source.read_text(encoding="utf-8"))
        bundle_prefix = source.parent.relative_to(destination.parent).as_posix()
        for row in payload["files"]:
            row["path"] = f"{bundle_prefix}/{row['path']}"
        sync_manifest_artifacts(payload)
        destination.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return destination

    @staticmethod
    def _archive_task_logs(
        attempts: list[Any],
        layout: Mapping[str, Path],
        manifest_path: Path,
    ) -> list[Any]:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        archived_attempts = []
        collected_at = datetime.now(timezone.utc).isoformat()
        for row in attempts:
            source_root = Path(row.work_dir)
            if not source_root.is_absolute():
                source_root = layout["nextflow_dir"] / source_root
            if not source_root.is_dir() and row.task_hash:
                source_root = layout["work_dir"] / row.task_hash
            target_root = (
                layout["external_bundle"]
                / "task_logs"
                / f"task-{row.task_id or 'unknown'}-attempt-{row.attempt}"
            )
            target_root.mkdir(parents=True, exist_ok=True)
            archived: dict[str, str] = {}
            for source_name, field_name in (
                (".command.sh", "command_path"),
                (".command.out", "stdout_path"),
                (".command.err", "stderr_path"),
                (".exitcode", "exitcode_path"),
            ):
                source = source_root / source_name
                target = target_root / source_name
                complete = source.is_file()
                if complete:
                    shutil.copyfile(source, target)
                relative = target.relative_to(layout["provenance"]).as_posix()
                manifest["files"].append(
                    {
                        "source": str(source.resolve(strict=False)),
                        "type": f"task_{field_name}",
                        "collected_at": collected_at,
                        "collector_version": "abi-external-nextflow-v1",
                        "complete": complete,
                        "parse_status": "not_parsed",
                        "path": relative,
                        "size": target.stat().st_size if complete else 0,
                        "sha256": sha256_file(target) if complete else "",
                    }
                )
                if complete:
                    archived[field_name] = relative
            archived_attempts.append(
                replace(
                    row,
                    command_path=archived.get("command_path", ""),
                    stdout_path=archived.get("stdout_path", ""),
                    stderr_path=archived.get("stderr_path", ""),
                )
            )
        manifest["complete"] = all(item.get("complete") for item in manifest["files"])
        sync_manifest_artifacts(manifest)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return archived_attempts

    @staticmethod
    def _append_archived_evidence(
        source: Path,
        *,
        evidence_type: str,
        layout: Mapping[str, Path],
        manifest_path: Path,
    ) -> None:
        target = layout["external_bundle"] / "raw" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].append(
            {
                "source": str(source.resolve(strict=False)),
                "type": evidence_type,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "collector_version": "abi-external-nextflow-v1",
                "complete": True,
                "parse_status": "parsed",
                "path": target.relative_to(layout["provenance"]).as_posix(),
                "size": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        )
        manifest["complete"] = all(item.get("complete") for item in manifest["files"])
        sync_manifest_artifacts(manifest)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _layout(self, config: Mapping[str, Any]) -> dict[str, Path]:
        root = Path(str(config["outdir"]))
        provenance = root / "provenance"
        nextflow_dir = root / "nextflow"
        namespace = str(
            getattr(
                self.plugin,
                "external_evidence_namespace",
                getattr(self.plugin, "plugin_id", "workflow"),
            )
        )
        samplesheet_name = str(
            getattr(self.plugin, "external_samplesheet_name", "external_samplesheet.yaml")
        )
        return {
            "root": root,
            "provenance": provenance,
            "nextflow_dir": nextflow_dir,
            "work_dir": nextflow_dir / "work",
            "nxf_home": nextflow_dir / "nxf_home",
            "trace": nextflow_dir / "raw" / "nextflow_trace.tsv",
            "report": nextflow_dir / "raw" / "nextflow_report.html",
            "timeline": nextflow_dir / "raw" / "nextflow_timeline.html",
            "dag": nextflow_dir / "raw" / "nextflow_dag.html",
            "log": nextflow_dir / "raw" / "nextflow.log",
            "stdout": nextflow_dir / "raw" / "workflow.stdout.log",
            "stderr": nextflow_dir / "raw" / "workflow.stderr.log",
            "samplesheet": provenance / samplesheet_name,
            "snapshot": provenance / "external_plan_snapshot.json",
            "task_attempts": provenance / "task_attempts.tsv",
            "evidence_manifest": provenance / "evidence_manifest.json",
            "external_bundle": provenance / "external" / namespace,
        }

    def _timeout(self, config: Mapping[str, Any]) -> float | None:
        execution = mapping_block(config, "execution")
        value = self.options.timeout_seconds or execution.get("nextflow_timeout_seconds")
        return timeout_from_env_or_value(
            "ABI_NEXTFLOW_TIMEOUT_SECONDS",
            value,
            default=DEFAULT_TOOL_TIMEOUT_SECONDS,
        )


def _resume_reconciliation(attempts: list[Any]) -> dict[str, int]:
    """Report CACHED vs re-executed attempts so resume outcomes stay auditable."""
    cached = sum(1 for row in attempts if row.status == "CACHED")
    return {"cached": cached, "executed": len(attempts) - cached, "total": len(attempts)}


def _safe_archive_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return name or "previous-run"
