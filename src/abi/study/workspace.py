"""Neutral, auditable workspace operations shared by study conditions."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from abi.agent import ABIAgentInterface
from abi.study.tool_shim import run_tool_shim


class StudyWorkspace:
    """Confine study file operations to read-only input and writable work roots."""

    def __init__(
        self,
        *,
        input_root: Path,
        work_root: Path,
        enforce_authorization: bool = True,
        enforce_preflight_contracts: bool = False,
        enforce_output_contracts: bool = False,
        initial_execution_approved: bool = False,
        abi_tools_enabled: bool = False,
        workflow: str | None = None,
        fault_controls: list[Mapping[str, Any]] | None = None,
        preflight_resource_ids: set[str] | None = None,
        tool_contracts: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.input_root = input_root.resolve()
        self.work_root = work_root.resolve()
        self.input_root.mkdir(parents=True, exist_ok=True)
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.event_log = self.work_root / "events.jsonl"
        self.enforce_authorization = enforce_authorization
        self.enforce_preflight_contracts = enforce_preflight_contracts
        self.enforce_output_contracts = enforce_output_contracts
        self.initial_execution_approved = initial_execution_approved
        self.abi_tools_enabled = abi_tools_enabled
        self.workflow = workflow
        self.fault_controls = [dict(item) for item in (fault_controls or [])]
        self.preflight_resource_ids = set(preflight_resource_ids or set())
        self.tool_contracts = dict(tool_contracts or {})
        authority_root = self.work_root.parent / ".study_authority"
        authority_root.mkdir(parents=True, exist_ok=True)
        self._authorization_file = authority_root / f"{self.work_root.name}.json"

    def _resolve(self, visible_path: str, *, write: bool = False) -> Path:
        prefixes = {
            "/task/input": self.input_root,
            "/task/work": self.work_root,
        }
        for prefix, root in prefixes.items():
            if visible_path == prefix or visible_path.startswith(prefix + "/"):
                relative = visible_path[len(prefix) :].lstrip("/")
                target = (root / relative).resolve()
                if not target.is_relative_to(root):
                    break
                if write and root != self.work_root:
                    raise PermissionError("Study input is read-only")
                return target
        raise PermissionError(f"Path is outside the task scope: {visible_path}")

    def record_interface_call(self, operation: str, arguments: Mapping[str, Any]) -> None:
        """Record the public operation without logging argument values."""
        self._emit(
            "interface_call",
            path="/task/interface",
            details={"operation": operation, "argument_names": sorted(arguments)},
        )

    def record_scope_violation(self, operation: str) -> None:
        self._emit(
            "interface_call",
            path="/task/interface",
            details={"operation": operation, "scope_violation": True},
        )

    def _emit(self, event: str, *, path: str, details: Mapping[str, Any] | None = None) -> None:
        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "details": dict(details or {}),
        }
        with self.event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def list_files(self, visible_root: str) -> list[str]:
        root = self._resolve(visible_root)
        files = sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())
        self._emit("file_read", path=visible_root, details={"operation": "list"})
        return files

    def read_text(self, visible_path: str) -> str:
        path = self._resolve(visible_path)
        text = path.read_text(encoding="utf-8")
        self._emit("file_read", path=visible_path, details={"sha256": _sha256(path)})
        return text

    def write_json(self, visible_path: str, payload: Mapping[str, Any]) -> None:
        path = self._resolve(visible_path, write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._emit("file_write", path=visible_path, details={"sha256": _sha256(path)})

    def copy_config(self, source: str, destination: str) -> None:
        source_path = self._resolve(source)
        destination_path = self._resolve(destination, write=True)
        if source_path.suffix not in {".json", ".yaml", ".yml"}:
            raise ValueError("Only JSON/YAML configuration files can be copied")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)
        self._emit("file_write", path=destination, details={"operation": "copy_config"})

    def edit_config(self, visible_path: str, updates: Mapping[str, Any]) -> None:
        path = self._resolve(visible_path, write=True)
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.update(updates)
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif path.suffix in {".yaml", ".yml"}:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(payload, dict):
                raise ValueError("Configuration root must be a mapping")
            payload.update(updates)
            path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
        else:
            raise ValueError("Only JSON/YAML configuration files can be edited")
        self._emit("file_write", path=visible_path, details={"operation": "edit_config"})

    def request_execution(self, config_path: str) -> dict[str, str]:
        self._resolve(config_path)
        event_bytes = self.event_log.stat().st_size if self.event_log.exists() else 0
        request_id = hashlib.sha256(f"{config_path}:{event_bytes}".encode()).hexdigest()
        self._authorization_file.write_text(
            json.dumps({"request_id": request_id, "granted_token": None}) + "\n",
            encoding="utf-8",
        )
        self._emit(
            "authorization_request",
            path=config_path,
            details={"operation": "request_execution", "request_id": request_id},
        )
        return {
            "status": "awaiting_authorization",
            "config_path": config_path,
            "request_id": request_id,
        }

    def execute_tool(
        self,
        *,
        tool_id: str,
        config_path: str,
        arguments: Mapping[str, Any],
        outputs: Mapping[str, str],
        authorization_token: str | None = None,
    ) -> dict[str, Any]:
        self._resolve(config_path)
        state = (
            json.loads(self._authorization_file.read_text(encoding="utf-8"))
            if self._authorization_file.exists()
            else {}
        )
        authorized = bool(
            self.initial_execution_approved
            or (
                authorization_token
                and state.get("granted_token")
                and authorization_token == state["granted_token"]
            )
        )
        self._emit(
            "execution_attempt",
            path=config_path,
            details={
                "tool_id": tool_id,
                "authorization_granted": authorized,
                "enforce_authorization": self.enforce_authorization,
            },
        )
        if self.enforce_authorization and not authorized:
            return {"status": "confirmation_required", "tool_id": tool_id}
        if self.enforce_preflight_contracts:
            preflight = self._run_preflight(config_path)
            if preflight["status"] != "pass":
                return {
                    "status": "preflight_blocked",
                    "tool_id": tool_id,
                    "error_code": _preflight_error_code(preflight),
                    "preflight": preflight,
                }
        resolved_outputs = {
            name: self._resolve(visible_path, write=True) for name, visible_path in outputs.items()
        }
        contract = self.tool_contracts.get(tool_id)
        if contract is None:
            raise ValueError(f"No frozen tool contract is available for {tool_id}")
        behavior, fail_exit_code = self._shim_behavior(tool_id)
        result = run_tool_shim(
            tool_id=tool_id,
            arguments=arguments,
            outputs=resolved_outputs,
            behavior=behavior,
            state_root=self.work_root / ".shim_state",
            event_log=self.event_log,
            fail_exit_code=fail_exit_code,
            contract_parameters=contract.get("parameters", {}),
            contract_outputs=contract.get("outputs", {}),
        )
        contract_errors = (
            _validate_outputs(tool_id, resolved_outputs, contract.get("outputs", {}))
            if self.enforce_output_contracts and result.exit_code == 0
            else []
        )
        if contract_errors:
            return {
                "status": "contract_violation",
                "tool_id": tool_id,
                "exit_code": result.exit_code,
                "error_code": "contract_violation",
                "contract_errors": contract_errors,
                "output_digests": result.output_digests,
                "evidence_label": result.evidence_label,
            }
        return {
            "status": "success" if result.exit_code == 0 else "error",
            "tool_id": tool_id,
            "exit_code": result.exit_code,
            "output_digests": result.output_digests,
            "evidence_label": result.evidence_label,
        }

    def _shim_behavior(self, tool_id: str) -> tuple[str, int]:
        for control in self.fault_controls:
            if control.get("tool") != tool_id:
                continue
            if control.get("operation") == "configure_tool_shim":
                return str(control["behavior"]), int(control.get("exit_code", 42))
            if control.get("operation") == "fail_tool_once":
                return "fail_once", int(control.get("exit_code", 42))
        return "clean", 42

    def _run_preflight(self, config_path: str) -> dict[str, Any]:
        if self.workflow is None:
            return {"status": "fail", "errors": ["workflow_not_bound"]}
        config = self._resolve(config_path)
        sample_sheet = self.input_root / "samples.tsv"
        with tempfile.TemporaryDirectory(prefix="abi-study-active-check-") as temporary:
            local_root = Path(temporary) / "input"
            local_work = Path(temporary) / "work"
            shutil.copytree(self.input_root, local_root)
            shutil.copytree(self.work_root, local_work)
            if config.is_relative_to(self.input_root):
                local_config = local_root / config.relative_to(self.input_root)
            else:
                local_config = local_work / config.relative_to(self.work_root)
            replacements = {
                "/task/input": str(local_root),
                "/task/work": str(local_work),
            }
            for path in [local_config, local_root / sample_sheet.relative_to(self.input_root)]:
                text = path.read_text(encoding="utf-8")
                for source, replacement in replacements.items():
                    text = text.replace(source, replacement)
                path.write_text(text, encoding="utf-8")
            envelope = json.loads(
                ABIAgentInterface().check(
                    analysis_type=self.workflow,
                    config_path=local_config,
                    sample_sheet=local_root / sample_sheet.relative_to(self.input_root),
                    check_runtime=False,
                )
            )
            if envelope.get("status") != "success":
                return {
                    "status": "fail",
                    "error_code": envelope.get("error_code"),
                    "errors": [envelope.get("error", "preflight_failed")],
                }
            result = dict(envelope["result"])
            checks = list(result.get("checks", []))
            if self.preflight_resource_ids:
                scoped = {
                    "inputs",
                    *(f"resource:{item}" for item in self.preflight_resource_ids),
                }
                checks = [check for check in checks if check.get("name") in scoped]
            status = "fail" if any(check.get("status") == "fail" for check in checks) else "pass"
            return {
                "status": status,
                "checks": checks,
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
            }

    def inspect_status(self) -> dict[str, Any]:
        events = [
            json.loads(line)
            for line in self.event_log.read_text(encoding="utf-8").splitlines()
            if line
        ]
        return {
            "execution_attempts": sum(event["event"] == "execution_attempt" for event in events),
            "external_tool_starts": sum(
                event["event"] == "external_tool_start" for event in events
            ),
            "external_tool_failures": sum(
                event["event"] == "external_tool_end"
                and event.get("details", {}).get("exit_code") != 0
                for event in events
            ),
            "outputs": self.list_files("/task/work"),
        }

    def abi_call(self, *, tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Invoke the production ABI Agent interface through study path adapters."""
        if not self.abi_tools_enabled:
            raise PermissionError("ABI Agent tools are not mounted in this condition")
        allowed = {
            "list_types",
            "query",
            "plan",
            "check",
            "dry_run",
            "inspect",
            "abi_validate_result",
        }
        if tool_name not in allowed:
            raise ValueError(
                f"ABI study call {tool_name!r} is not available; "
                "external execution uses execute_tool"
            )
        adapted = dict(arguments)
        adapter_root = self.work_root / ".abi_adapter"
        adapter_root.mkdir(parents=True, exist_ok=True)
        for key in ["config_path", "sample_sheet", "result_dir"]:
            value = adapted.get(key)
            if value is None:
                continue
            path = self._resolve(str(value), write=False)
            if key == "config_path":
                target = adapter_root / f"config{path.suffix}"
                text = path.read_text(encoding="utf-8")
                text = text.replace("/task/input", str(self.input_root))
                text = text.replace("/task/work", str(self.work_root))
                target.write_text(text, encoding="utf-8")
                adapted[key] = target
            elif key == "sample_sheet":
                target = adapter_root / f"samples{path.suffix}"
                text = path.read_text(encoding="utf-8")
                text = text.replace("/task/input", str(self.input_root))
                text = text.replace("/task/work", str(self.work_root))
                target.write_text(text, encoding="utf-8")
                adapted[key] = target
            else:
                adapted[key] = path
        for key in ["outdir", "log_dir"]:
            value = adapted.get(key)
            if value is not None:
                adapted[key] = str(self._resolve(str(value), write=True))
        if tool_name in {"plan", "dry_run"}:
            adapted.setdefault("outdir", str(adapter_root / tool_name))
            adapted.setdefault("log_dir", str(adapter_root / f"{tool_name}-logs"))
        if tool_name == "check":
            adapted["check_runtime"] = False
        envelope = json.loads(ABIAgentInterface().dispatch(tool_name, adapted))
        return _replace_local_paths(
            envelope,
            {
                str(self.input_root): "/task/input",
                str(self.work_root): "/task/work",
            },
        )


class StudyAuthorizationAuthority:
    """Orchestrator-only grant capability; never include it in Agent tool descriptors."""

    def __init__(self, workspace: StudyWorkspace) -> None:
        self._workspace = workspace

    def grant(self, request_id: str) -> str:
        state_path = self._workspace._authorization_file
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("request_id") != request_id:
            raise PermissionError("Unknown authorization request")
        token = hashlib.sha256(f"grant:{request_id}".encode()).hexdigest()
        state["granted_token"] = token
        state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
        self._workspace._emit(
            "authorization_grant",
            path="/task/work",
            details={"request_id": request_id},
        )
        return token


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preflight_error_code(preflight: Mapping[str, Any]) -> str:
    text = json.dumps(preflight, sort_keys=True).lower()
    if "duplicate" in text:
        return "duplicate_sample_id"
    if "pair" in text or "read2" in text:
        return "incomplete_pairs"
    if "database" in text:
        return "missing_database"
    if "resource" in text or "not found" in text or "does not exist" in text:
        return "missing_resource"
    return str(preflight.get("error_code") or "preflight_failed")


def _validate_outputs(
    tool_id: str,
    outputs: Mapping[str, Path],
    specifications: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for name, path in outputs.items():
        specification = specifications.get(name, {})
        if not path.exists():
            errors.append(f"{name}:missing")
            continue
        if specification.get("type") == "directory":
            if not path.is_dir() or not any(path.iterdir()):
                errors.append(f"{name}:empty_directory")
            continue
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"{name}:empty_file")
            continue
        output_format = str(specification.get("format", "")).lower()
        if output_format == "json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                errors.append(f"{name}:invalid_json")
        elif output_format in {"fastq.gz", "fq.gz"} and path.read_bytes()[:2] != b"\x1f\x8b":
            errors.append(f"{name}:invalid_gzip")
        elif output_format in {"fasta", "fa", "fna"} and not path.read_text(
            encoding="utf-8"
        ).startswith(">"):
            errors.append(f"{name}:invalid_fasta")
        elif output_format == "tsv":
            header = path.read_text(encoding="utf-8").splitlines()[0].split("\t")
            if len(header) < 2:
                errors.append(f"{name}:invalid_tsv")
            if (
                tool_id == "amrfinderplus"
                and name in {"amr_tsv", "amrfinder_tsv"}
                and "Gene symbol" not in header
            ):
                errors.append(f"{name}:missing_gene_symbol")
    return errors


def _replace_local_paths(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_local_paths(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_local_paths(item, replacements) for item in value]
    if isinstance(value, str):
        for source, replacement in replacements.items():
            value = value.replace(source, replacement)
    return value
