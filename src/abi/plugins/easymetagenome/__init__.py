"""EasyMetagenome-inspired ABI-native P0 shotgun metagenomics plugin."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from abi._shared import _execute_generic_dry_run, _parse_fastp, _resolve_path
from abi.config import PLUGIN_ROOT, PROJECT_ROOT, compact_overrides, deep_merge, load_yaml
from abi.report import write_plugin_report
from abi.schemas import ABIExecutionPlan, ABISample, ABISampleContext
from abi.tools import ToolRegistry
from abi.workflow import WorkflowCatalog

from .adapters import ManifestValidator
from .handlers import handlers as easymeta_handlers
from .reproduction import validate_core53_manifest, validate_pluspf_identity
from .workflow import P0Workflow

__all__ = ["EasyMetagenomePlugin", "ManifestValidator", "P0Workflow"]


class EasyMetagenomePlugin:
    plugin_id = "easymetagenome"
    display_name = "EasyMetagenome-style P0"
    description = "ABI-native fastp, KneadData, Kraken2, Bracken, diversity, and reporting DAG."
    report_title = "EasyMetagenome-style P0 ABI Report"

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
    ) -> Dict[str, Any]:
        del profile
        del db_profile
        config = load_yaml(self.root / "config_default.yaml")
        if config_path:
            config = deep_merge(config, load_yaml(config_path))
        config = deep_merge(config, compact_overrides(overrides))
        workflow = dict(config.get("workflow", {}))
        preset = str(workflow.get("preset", "p0_taxonomy"))
        resolved_workflow = WorkflowCatalog.for_plugin(
            self.plugin_id, plugin_root=self.root
        ).resolve(preset)
        workflow.setdefault("include_nodes", list(resolved_workflow.include_nodes))
        workflow["required_resources"] = list(resolved_workflow.required_resources)
        workflow["functional_enabled"] = "functional" in resolved_workflow.capabilities
        workflow["taxonomy_enabled"] = "taxonomy" in resolved_workflow.capabilities
        config["workflow"] = workflow
        raw_input_config = config.get("input", {})
        if not isinstance(raw_input_config, Mapping) or not raw_input_config.get("sample_sheet"):
            raise ValueError("easymetagenome requires input.sample_sheet")
        input_config = dict(raw_input_config)
        input_config["sample_sheet"] = str(
            _resolve_path(input_config["sample_sheet"], base_dirs=[PROJECT_ROOT])
        )
        config["input"] = input_config
        if int(config.get("threads", 0)) < 1:
            raise ValueError("threads must be at least 1")
        config["humann_samples_dir"] = str(Path(str(config["outdir"])) / "04_function/sample")
        return config

    def check_resources(
        self,
        config: Mapping[str, Any],
        *,
        resource_ids: Optional[Sequence[str]] = None,
    ) -> list[dict[str, Any]]:
        from abi.resources import check_generic_resources

        return check_generic_resources(self.plugin_id, config, resource_ids=resource_ids)

    def setup_resources(
        self,
        config: Mapping[str, Any],
        *,
        resource_ids: Optional[Sequence[str]] = None,
        dry_run: bool = False,
        mock: bool = False,
    ) -> list[dict[str, Any]]:
        from abi.resources import setup_manual_resource_bundle

        return setup_manual_resource_bundle(
            self.plugin_id,
            config,
            resource_ids=resource_ids,
            dry_run=dry_run,
            mock=mock,
        )

    def build_sample_context(
        self, config: Mapping[str, Any], *, check_files: bool = True
    ) -> ABISampleContext:
        path = config["input"]["sample_sheet"]
        try:
            records = ManifestValidator.validate(path, check_files=check_files)
        except (FileNotFoundError, ValueError):
            if check_files:
                raise
            records = []
        if not records:
            samples = [
                ABISample(
                    sample_id="SAMPLE_NOT_CONFIGURED",
                    platform="illumina",
                    read1="READ1_NOT_CONFIGURED",
                    read2="READ2_NOT_CONFIGURED",
                )
            ]
        else:
            samples = [
                ABISample(
                    sample_id=record.sample_id,
                    platform="illumina",
                    read1=record.r1,
                    read2=record.r2,
                    group=record.group or None,
                    attributes={
                        "r1_url": record.r1_url,
                        "r2_url": record.r2_url,
                        "r1_md5": record.r1_md5,
                        "r2_md5": record.r2_md5,
                        "r1_bytes": record.r1_bytes,
                        "r2_bytes": record.r2_bytes,
                    },
                )
                for record in records
            ]
        groups = {sample.group for sample in samples if sample.group}
        return ABISampleContext(
            samples=samples,
            multi_sample=len(samples) > 1,
            has_groups=len(groups) >= 2,
            enable_sample_analysis=len(samples) > 1,
        )

    def build_plan(
        self, config: Mapping[str, Any], *, check_files: bool = True
    ) -> ABIExecutionPlan:
        from abi.dag_planner import build_plan_from_dag

        return build_plan_from_dag(
            self.root / "pipeline_dag.yaml",
            config,
            self.build_sample_context(config, check_files=check_files),
        )

    def preflight(
        self,
        config: Mapping[str, Any],
        *,
        engine: str,
        check_runtime: bool = True,
    ) -> Mapping[str, Any]:
        del engine
        checks: list[dict[str, Any]] = []
        reproduction = config.get("reproduction", {})
        try:
            samples = ManifestValidator.validate(config["input"]["sample_sheet"], check_files=True)
            checks.append({"name": "manifest", "status": "pass", "sample_count": len(samples)})
        except (FileNotFoundError, ValueError) as exc:
            checks.append({"name": "manifest", "status": "fail", "message": str(exc)})
        protocol = reproduction.get("protocol") if isinstance(reproduction, Mapping) else None
        if protocol == "ibd_core53":
            try:
                manifest_errors = validate_core53_manifest(
                    config["input"]["sample_sheet"],
                    table1_path=reproduction.get("frozen_table1"),
                    require_ena_metadata=True,
                )
            except (OSError, ValueError) as exc:
                manifest_errors = [str(exc)]
            checks.append(
                {
                    "name": "ibd_core53_manifest",
                    "status": "fail" if manifest_errors else "pass",
                    "errors": manifest_errors,
                }
            )
        if protocol == "ibd_core53":
            kraken_policy = str(reproduction.get("kraken2_policy", "pluspf_20240605_exact"))
            if kraken_policy == "cloud_current":
                kraken_db = Path(str(config.get("resources", {}).get("kraken2_db", "")))
                missing = [
                    name
                    for name in ("hash.k2d", "opts.k2d", "taxo.k2d")
                    if not (kraken_db / name).is_file()
                ]
                checks.append(
                    {
                        "name": "kraken2_cloud_current_compatibility",
                        "status": "fail" if missing else "pass",
                        "path": str(kraken_db),
                        "missing": missing,
                        "compatibility": "non_exact_literature_resource",
                        "warning": (
                            "Cloud-current Kraken2 is an explicit substitution for PlusPF "
                            "20240605; results are not database-version-exact."
                        ),
                    }
                )
            else:
                identity_path = reproduction.get("kraken2_identity")
                if not identity_path:
                    kraken_db = config.get("resources", {}).get("kraken2_db", "")
                    identity_path = Path(str(kraken_db)) / ".abi_resource_identity.json"
                identity_errors = validate_pluspf_identity(
                    identity_path,
                    resource_path=config.get("resources", {}).get("kraken2_db", ""),
                )
                checks.append(
                    {
                        "name": "pluspf_20240605_identity",
                        "status": "fail" if identity_errors else "pass",
                        "path": str(identity_path),
                        "errors": identity_errors,
                    }
                )
        resources = config.get("resources", {})
        workflow = config.get("workflow", {})
        taxonomy_enabled = (
            bool(workflow.get("taxonomy_enabled")) if isinstance(workflow, Mapping) else True
        )
        functional_enabled = (
            bool(workflow.get("functional_enabled")) if isinstance(workflow, Mapping) else False
        )
        required_resources = list(workflow.get("required_resources", []))
        for name in required_resources:
            value = resources.get(name) if isinstance(resources, Mapping) else None
            path = Path(str(value or ""))
            valid = bool(value) and "NOT_CONFIGURED" not in str(value) and path.exists()
            checks.append(
                {
                    "name": name,
                    "status": "pass" if valid else "fail",
                    "path": str(path),
                }
            )
        if check_runtime:
            taxonomy_tools = {"seqkit", "fastp", "kneaddata", "kraken2", "bracken"}
            functional_tools = {
                "seqkit",
                "fastp",
                "kneaddata",
                "humann4",
                "humann_join_tables",
                "humann_renorm_table",
                "humann_regroup_table",
                "humann_split_stratified_table",
            }
            selected_tools = (taxonomy_tools if taxonomy_enabled else set()) | (
                functional_tools if functional_enabled else set()
            )
            for result in self.registry().check_tools(config=config):
                if str(result.get("tool_id")) not in selected_tools:
                    continue
                installed = bool(result.get("installed"))
                resource_status = str(result.get("resource_status", "ok"))
                checks.append(
                    {
                        "name": str(result.get("tool_id", "tool")),
                        "status": (
                            "pass"
                            if installed and resource_status in {"ok", "not_required"}
                            else "fail"
                        ),
                        "details": result,
                    }
                )
        failures = [item for item in checks if item["status"] == "fail"]
        return {
            "plugin": self.plugin_id,
            "status": "fail" if failures else "pass",
            "checks": checks,
            "recommendations": [f"Fix failed preflight check: {item['name']}" for item in failures],
        }

    def internal_handlers(self):
        return easymeta_handlers()

    def published_outputs(self, plan: Any) -> Dict[str, Path]:
        report_kinds = {
            "collect_report": "taxonomy",
            "collect_ibd_reproduction_report": "reproduction",
            "functional_report": "functional",
            "publish_functional_report": "functional",
        }
        reports: dict[str, dict[str, Path]] = {}
        for step in plan.steps:
            kind = report_kinds.get(step.step_id)
            if kind is None:
                continue
            for label in ("manifest", "markdown"):
                path = Path(str(step.outputs.get(f"report_{label}", "")))
                if path.is_file():
                    reports.setdefault(kind, {})[label] = path
        outputs = {
            f"{kind}_report_{label}": path
            for kind, paths in reports.items()
            for label, path in paths.items()
        }
        complete_reports = [
            paths for paths in reports.values() if set(paths) == {"manifest", "markdown"}
        ]
        if len(complete_reports) == 1:
            outputs.update({f"report_{label}": path for label, path in complete_reports[0].items()})
        return outputs

    def registry(self) -> ToolRegistry:
        return ToolRegistry.from_path(self.root / "tool_registry.yaml")

    def execute_dry_run(self, plan: Any, config: Mapping[str, Any]) -> Dict[str, Path]:
        return _execute_generic_dry_run(self, plan, config)

    def table_schemas(self) -> Mapping[str, Iterable[str]]:
        return load_yaml(self.root / "standard_tables.yaml").get("tables", {})

    def validate_result_dir(
        self,
        result_dir: str | Path,
        *,
        allow_empty_tables: bool = True,
    ) -> Mapping[str, Any]:
        """Apply workflow-preset-aware non-empty table validation."""
        if allow_empty_tables:
            return {"errors": []}

        root = Path(result_dir)
        config_path = root / "provenance" / "config.resolved.yaml"
        if not config_path.is_file():
            return {"errors": []}
        config = load_yaml(config_path)
        workflow = config.get("workflow", {})
        preset = (
            str(workflow.get("preset", "p0_taxonomy"))
            if isinstance(workflow, Mapping)
            else "p0_taxonomy"
        )
        required_by_preset = {
            "p0_taxonomy": (
                "qc_summary",
                "host_removal_summary",
                "taxonomy_abundance",
            ),
            "p1_humann4": (
                "qc_summary",
                "host_removal_summary",
                "functional_abundance",
            ),
            "full_read_based": tuple(self.table_schemas()),
        }
        required_tables = required_by_preset.get(preset, tuple(self.table_schemas()))
        empty_tables = []
        for table_name in required_tables:
            table_path = root / "tables" / f"{table_name}.tsv"
            if not table_path.is_file():
                continue
            with table_path.open("r", encoding="utf-8", newline="") as handle:
                if not any(csv.DictReader(handle, delimiter="\t")):
                    empty_tables.append(table_name)
        errors = []
        if empty_tables:
            errors.append("Empty standard table(s): " + ", ".join(sorted(empty_tables)))
        return {"errors": errors}

    def parse_outputs(
        self, tool_id: str, output_dir: str | Path, sample_id: str
    ) -> Mapping[str, Iterable[Mapping[str, Any]]]:
        root = Path(output_dir)
        if tool_id == "seqkit":
            return {"qc_summary": _parse_seqkit(root, sample_id)}
        if tool_id == "fastp":
            return {"qc_summary": _parse_fastp(root, sample_id)}
        if tool_id == "kneaddata":
            return {"host_removal_summary": _parse_kneaddata(root, sample_id)}
        if tool_id == "kraken2":
            return {"taxonomy_abundance": _parse_kraken2(root, sample_id)}
        if tool_id == "bracken":
            return {"taxonomy_abundance": _parse_bracken(root, sample_id)}
        if tool_id in {
            "humann4",
            "humann_join_tables",
            "humann_renorm_table",
            "humann_regroup_table",
            "humann_split_stratified_table",
        }:
            return {"functional_abundance": _parse_humann(root, tool_id, sample_id)}
        return {}

    # ── Compliance audit (P2-3: plugin-owned checkpoints) ────────────────

    def compliance_checks(
        self,
        result_dir: str | Path,
        config: Mapping[str, Any],
    ) -> Dict[str, Mapping[str, Any]]:
        """Return the IBD-reproduction compliance checkpoints for this result.

        Moved here from core ``abi.compliance.audit_result`` (P2-3): the
        endpoint-scores artifact layout, the ``ibd_core53_reproduction``
        preset name, and the core53 manifest preflight check are this
        plugin's domain knowledge — the core audit only merges the result.
        """
        root = Path(result_dir)

        def _read_json(path: Path) -> Dict[str, Any]:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {}
            return value if isinstance(value, dict) else {}

        checks: Dict[str, Mapping[str, Any]] = {}
        formal_ibd = config.get("workflow", {}).get("preset") == "ibd_core53_reproduction"
        endpoints_path = root / "05_statistics" / "ibd_core53_endpoint_scores.json"
        endpoints = _read_json(endpoints_path)
        endpoint_check = {
            "pass": set(endpoints.get("endpoints", {})) == {"E1", "E2", "E3", "E4", "E5"}
            and endpoints.get("status") in {"pass", "divergent"},
            "status": endpoints.get("status", "missing"),
            "path": str(endpoints_path),
        }
        if formal_ibd:
            try:
                preflight = self.preflight(config, engine="local", check_runtime=False)
                manifest_check = next(
                    (
                        check
                        for check in preflight.get("checks", [])
                        if check.get("name") == "ibd_core53_manifest"
                    ),
                    {"status": "fail", "errors": ["IBD core53 preflight check is missing"]},
                )
                manifest_errors = list(manifest_check.get("errors", []))
            except (OSError, KeyError, ValueError) as exc:
                # A malformed reproduction config IS a compliance failure —
                # the audit must report it, not crash.
                # 畸形的复现配置本身就是合规失败——审计报告之而非崩溃。
                manifest_errors = [f"{type(exc).__name__}: {exc}"]
            checks["core53_manifest"] = {"pass": not manifest_errors, "errors": manifest_errors}
        if formal_ibd or endpoints_path.exists():
            checks["E1_E5"] = endpoint_check
        return checks

    def write_report(self, plan: Any, result_dir: str | Path) -> Dict[str, Path]:
        return write_plugin_report(self, plan, result_dir)

    def documented_workflow(self) -> P0Workflow:
        return P0Workflow.from_yaml(self.root / "workflows" / "preprocessing_kraken2_bracken.yaml")


def _parse_seqkit(root: Path, sample_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.seqkit.tsv")):
        try:
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                for record in csv.DictReader(handle, delimiter="\t"):
                    for metric, value in record.items():
                        if metric == "file":
                            continue
                        rows.append(
                            {
                                "sample_id": sample_id,
                                "tool": "seqkit",
                                "metric": metric,
                                "value": value or "",
                                "unit": "",
                                "source_file": str(path),
                            }
                        )
        except (OSError, csv.Error):
            continue
    return rows


def _fastq_record_count(path: Path) -> int:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle) // 4


def _parse_kneaddata(root: Path, sample_id: str) -> list[dict[str, Any]]:
    candidates = sorted(root.glob("*paired_1.fastq*"))
    if not candidates:
        return []
    path = candidates[0]
    try:
        count = _fastq_record_count(path)
    except OSError:
        return []
    return [
        {
            "sample_id": sample_id,
            "dehost_read_pairs": count,
            "tool": "kneaddata",
            "source_file": str(path),
        }
    ]


def _parse_kraken2(root: Path, sample_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.kraken2.report")):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    fields = line.rstrip("\n").split("\t")
                    if len(fields) < 6:
                        continue
                    rows.append(
                        {
                            "sample_id": sample_id,
                            "name": fields[5].strip(),
                            "taxonomy_id": fields[4].strip(),
                            "taxonomy_level": fields[3].strip(),
                            "fraction_total_reads": fields[0].strip(),
                            "fraction_classified_reads": "",
                            "new_est_reads": "",
                            "kraken_assigned_reads": fields[2].strip(),
                            "added_reads": "",
                            "tool": "kraken2",
                            "source_file": str(path),
                        }
                    )
        except OSError:
            continue
    return rows


def _parse_bracken(root: Path, sample_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.brk")):
        try:
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                for record in csv.DictReader(handle, delimiter="\t"):
                    rows.append(
                        {
                            "sample_id": sample_id,
                            "name": record.get("name", ""),
                            "taxonomy_id": record.get("taxonomy_id", ""),
                            "taxonomy_level": record.get("taxonomy_lvl", ""),
                            "fraction_total_reads": record.get("fraction_total_reads", ""),
                            "fraction_classified_reads": record.get(
                                "fraction_classified_reads", ""
                            ),
                            "new_est_reads": record.get("new_est_reads", ""),
                            "kraken_assigned_reads": record.get("kraken_assigned_reads", ""),
                            "added_reads": record.get("added_reads", ""),
                            "tool": "bracken",
                            "source_file": str(path),
                        }
                    )
        except (OSError, csv.Error):
            continue
    return rows


def _parse_humann(root: Path, tool_id: str, fallback_sample_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.tsv")):
        try:
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                reader = csv.reader(handle, delimiter="\t")
                header: list[str] | None = None
                for values in reader:
                    if not values:
                        continue
                    if values[0].startswith("#"):
                        if len(values) > 1:
                            header = values
                        continue
                    if header is None:
                        continue
                    feature_id = values[0]
                    feature_type = _humann_feature_type(path)
                    for column, value in zip(header[1:], values[1:]):
                        sample_id = column.rsplit("-RPKs", 1)[0].lstrip("#")
                        rows.append(
                            {
                                "sample_id": sample_id or fallback_sample_id,
                                "feature_type": feature_type,
                                "feature_id": feature_id,
                                "value": value,
                                "stratified": "|" in feature_id,
                                "tool": tool_id,
                                "source_file": str(path),
                            }
                        )
        except (OSError, csv.Error):
            continue
    return rows


def _humann_feature_type(path: Path) -> str:
    name = path.name.lower()
    if "pathabundance" in name:
        return "pathway"
    if "pathcoverage" in name:
        return "pathway_coverage"
    if "ko" in name:
        return "ko"
    return "gene_family"
