"""Managed Bacannot v3.4.4 integration for bacterial isolate WGS."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from abi._shared import _resolve_path
from abi.config import PLUGIN_ROOT, PROJECT_ROOT, compact_overrides, deep_merge, load_yaml
from abi.external_workflows.models import ExternalProcessContract, ExternalWorkflowSpec
from abi.report import write_plugin_report
from abi.schemas import ABIExecutionPlan
from abi.tools import ToolRegistry

from .config import PINNED_COMMIT_SHA, validate_config
from .process_map import load_process_contracts, map_process_class
from .samples import BacannotSampleSheet, convert_sample_sheet, load_sample_context


class WGSBacannotPlugin:
    """Expose a pinned Bacannot workflow through the ABI lifecycle."""

    plugin_id = "wgs_bacannot"
    display_name = "Bacannot Bacterial Genome Analysis"
    description = (
        "Managed Bacannot v3.4.4 bacterial WGS with task-attempt evidence and "
        "assembly, annotation, MLST, and AMR contracts."
    )
    report_title = "Bacannot Bacterial Genome ABI Report"
    external_parser_version = "bacannot-3.4.4-parser-v1"
    external_evidence_namespace = "bacannot"
    external_samplesheet_name = "bacannot_samplesheet.yaml"

    @property
    def root(self) -> Path:
        return PLUGIN_ROOT / self.plugin_id

    def load_config(
        self,
        config_path: str | Path | None = None,
        *,
        profile: str | None = None,
        db_profile: str | None = None,
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        del db_profile
        config = load_yaml(self.root / "config_default.yaml")
        if config_path:
            config = deep_merge(config, load_yaml(config_path))
        config = deep_merge(config, compact_overrides(overrides))
        if profile and profile not in {"default", "dry_run"}:
            config.setdefault("workflow", {})["profile"] = profile
        self._resolve_paths(config)
        validate_config(config)
        return config

    def _resolve_paths(self, config: dict[str, Any]) -> None:
        input_block = config.get("input")
        if isinstance(input_block, dict) and input_block.get("sample_sheet"):
            input_block["sample_sheet"] = str(
                _resolve_path(input_block["sample_sheet"], base_dirs=[PROJECT_ROOT])
            )
        resources = config.get("resources")
        if isinstance(resources, dict):
            for key in ("bacannot_db", "runtime_resource_root"):
                value = resources.get(key)
                if value and "NOT_CONFIGURED" not in str(value):
                    resources[key] = str(_resolve_path(value, base_dirs=[PROJECT_ROOT]))
        for key in ("outdir", "log_dir"):
            if config.get(key):
                config[key] = str(_resolve_path(config[key], base_dirs=[PROJECT_ROOT]))

    def build_sample_context(self, config: Mapping[str, Any], *, check_files: bool = True) -> Any:
        return load_sample_context(str(config["input"]["sample_sheet"]), check_files=check_files)

    def build_plan(
        self, config: Mapping[str, Any], *, check_files: bool = True
    ) -> ABIExecutionPlan:
        from abi.dag_planner import build_plan_from_dag

        context = self.build_sample_context(config, check_files=check_files)
        plan = build_plan_from_dag(self.root / "pipeline_dag.yaml", config, context)
        raw_output = Path(str(config["outdir"])) / "raw" / "bacannot"
        plan.managed_output_roots = [str(raw_output)]
        return plan

    def convert_sample_sheet(
        self,
        source: str | Path,
        destination: str | Path,
        *,
        check_files: bool = True,
    ) -> BacannotSampleSheet:
        return convert_sample_sheet(source, destination, check_files=check_files)

    def external_workflow_spec(
        self,
        config: Mapping[str, Any],
        plan: ABIExecutionPlan,
    ) -> ExternalWorkflowSpec:
        workflow = config["workflow"]
        result_dir = Path(str(config["outdir"]))
        generated_sheet = result_dir / "provenance" / "bacannot_samplesheet.yaml"
        output_dir = result_dir / "raw" / "bacannot"
        argv = (
            "nextflow",
            "run",
            str(workflow["source"]),
            "-r",
            str(workflow["commit_sha"]),
            "--input",
            str(generated_sheet),
            "--bacannot_db",
            str(config["resources"]["bacannot_db"]),
            "--output",
            str(output_dir),
            "--max_cpus",
            str(config["resources"]["max_cpus"]),
            "--max_memory",
            str(config["resources"]["max_memory"]),
            "--max_time",
            str(config["resources"]["max_time"]),
            "--skip_resistance_search",
            str(not bool(config["modules"]["amr"])).lower(),
            "--skip_virulence_search",
            "true",
            "--skip_plasmid_search",
            "true",
            "--skip_iceberg_search",
            "true",
            "--skip_prophage_search",
            "true",
            "--skip_kofamscan",
            "true",
            "--skip_antismash",
            "true",
            "--skip_sourmash",
            "true",
            "--skip_circos",
            "true",
            "--skip_integron_finder",
            "true",
        )
        return ExternalWorkflowSpec(
            engine="nextflow",
            workflow_id=f"wgs_bacannot:{plan.project_name}",
            source=str(workflow["source"]),
            revision=str(workflow["revision"]),
            commit_sha=str(workflow["commit_sha"]),
            entrypoint="main.nf",
            argv=argv,
            work_dir=str(result_dir / "nextflow" / "work"),
            profile=str(workflow["profile"]),
            resume=bool(workflow["resume"]),
            audit_level=str(config["audit"]["level"]),
            expected_process_classes=("assembly", "annotation", "mlst", "amr"),
        )

    def external_process_contracts(
        self, config: Mapping[str, Any]
    ) -> list[ExternalProcessContract]:
        # Selection is evaluated when results are normalized/validated so
        # disabled contracts remain visible as ``not_selected`` evidence.
        del config
        return load_process_contracts(self.root / "process_contracts")

    def map_external_process(self, process_name: str) -> str:
        contracts = load_process_contracts(self.root / "process_contracts")
        return map_process_class(process_name, contracts)

    def normalize_external_outputs(
        self,
        config: Mapping[str, Any],
        attempts: Iterable[Any],
    ) -> Mapping[str, Path]:
        from .parser import normalize_bacannot_outputs

        result_root = Path(str(config["outdir"]))
        return normalize_bacannot_outputs(
            result_root / "raw" / "bacannot",
            result_root,
            attempts,
            self.external_process_contracts(config),
            self.table_schemas(),
            modules=config["modules"],
            sample_ids=[sample.sample_id for sample in self.build_sample_context(config).samples],
        )

    def external_snapshot_metadata(self, config: Mapping[str, Any]) -> Mapping[str, Any]:
        resources = config["resources"]
        return {
            "plugin_version": "1",
            "contract_version": "bacannot-3.4.4-v1",
            "containers": [],
            "databases": [
                {
                    "database_id": "bacannot_db",
                    "path": str(resources["bacannot_db"]),
                    "snapshot_id": str(resources.get("database_snapshot_id", "")),
                    "sha256": str(resources.get("database_sha256", "")),
                    "sha256_unavailable_reason": (
                        "database_sha256 was not configured"
                        if not resources.get("database_sha256")
                        else ""
                    ),
                }
            ],
            "container_resolution": {
                "status": "deferred_to_pinned_nextflow_process_config",
                "reason": "Bacannot uses multiple process containers resolved by Nextflow.",
            },
        }

    def preflight(
        self,
        config: Mapping[str, Any],
        *,
        engine: str,
        check_runtime: bool = True,
    ) -> Mapping[str, Any]:
        checks: list[dict[str, str]] = []
        if engine not in {"nextflow", "hpc"}:
            checks.append(
                {
                    "status": "fail",
                    "code": "runtime_not_supported",
                    "message": "wgs_bacannot requires the nextflow or hpc engine",
                }
            )
        database = Path(str(config["resources"]["bacannot_db"]))
        if not database.is_dir():
            checks.append(
                {
                    "status": "fail",
                    "code": "DATABASE_MISSING",
                    "message": f"Bacannot database directory is missing: {database}",
                }
            )
        if check_runtime:
            from abi.runtimes.nextflow import resolve_nextflow_bin

            try:
                resolve_nextflow_bin(None, None)
            except Exception as exc:
                checks.append(
                    {
                        "status": "fail",
                        "code": "TOOL_OR_CONTAINER_UNAVAILABLE",
                        "message": str(exc),
                    }
                )
        return {
            "plugin": self.plugin_id,
            "status": "fail" if checks else "pass",
            "checks": checks,
            "compatibility": {
                "bacannot_commit": PINNED_COMMIT_SHA,
                "production_ready": False,
            },
        }

    def registry(self) -> ToolRegistry:
        return ToolRegistry.from_path(self.root / "tool_registry.yaml")

    def execute_dry_run(self, plan: Any, config: Mapping[str, Any]) -> dict[str, Path]:
        from abi.external_workflows.runtime import ManagedExternalNextflowRuntime
        from abi.runtimes.base import RuntimeOptions

        result = ManagedExternalNextflowRuntime(
            self, RuntimeOptions(engine="nextflow", smoke=True)
        ).dry_run(plan, config)
        return result.outputs

    def table_schemas(self) -> Mapping[str, Iterable[str]]:
        return load_yaml(self.root / "standard_tables.yaml").get("tables", {})

    def parse_outputs(
        self, tool_id: str, output_dir: str | Path, sample_id: str
    ) -> Mapping[str, Iterable[Mapping[str, Any]]]:
        del tool_id, output_dir, sample_id
        return {}

    def validate_result_dir(
        self, result_dir: str | Path, *, allow_empty_tables: bool = True
    ) -> Mapping[str, Any]:
        from .validation import validate_bacannot_result

        return validate_bacannot_result(
            result_dir,
            load_process_contracts(self.root / "process_contracts"),
            allow_empty_tables=allow_empty_tables,
        )

    def write_report(self, plan: Any, result_dir: str | Path) -> dict[str, Path]:
        return write_plugin_report(self, plan, result_dir)

    def published_outputs(self, plan: Any) -> Mapping[str, Path]:
        root = Path(str(plan.outdir))
        candidates = {
            "task_attempts": root / "provenance" / "task_attempts.tsv",
            "evidence_manifest": root / "provenance" / "evidence_manifest.json",
            "external_plan_snapshot": root / "provenance" / "external_plan_snapshot.json",
        }
        return {key: value for key, value in candidates.items() if value.is_file()}


__all__ = ["WGSBacannotPlugin"]
