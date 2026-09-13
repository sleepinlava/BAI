"""Loader and local P0 runner for the documented EasyMetagenome DAG format."""

from __future__ import annotations

import itertools
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence

import yaml

from .adapters import (
    ManifestValidator,
    SampleRecord,
)


class WorkflowDefinitionError(ValueError):
    """The workflow YAML is structurally invalid."""


def _namespace(value: Any) -> Any:
    if isinstance(value, Mapping):
        return SimpleNamespace(**{str(key): _namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_namespace(item) for item in value]
    return value


class _FormatContext(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render(value: Any, context: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format_map(_FormatContext(context))
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _render(item, context) for key, item in value.items()}
    return value


def _absolutize(value: Any, workdir: Path) -> Any:
    if not isinstance(value, str) or not value or value.startswith("{"):
        return value
    if value.startswith(("${", "~")) or "*" in value:
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    if value.startswith(("result/", "temp/", "seq/")):
        return str(workdir / path)
    return value


class P0Workflow:
    """Parse, expand, dry-run, and execute the document's list-style nodes."""

    required_node_fields = frozenset({"id", "tool", "stage", "inputs", "outputs", "checks"})

    def __init__(self, spec: Mapping[str, Any], source: Path | None = None) -> None:
        self.spec = dict(spec)
        self.source = source
        raw_nodes = self.spec.get("nodes")
        if isinstance(raw_nodes, Mapping):
            nodes = [{"id": node_id, **dict(data)} for node_id, data in raw_nodes.items()]
        elif isinstance(raw_nodes, list):
            nodes = [dict(item) for item in raw_nodes]
        else:
            raise WorkflowDefinitionError("Workflow requires a nodes list or mapping")
        self.nodes = nodes
        self._validate()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "P0Workflow":
        source = Path(path)
        data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        if not isinstance(data, Mapping):
            raise WorkflowDefinitionError("Workflow YAML must be a mapping")
        return cls(data, source)

    def _validate(self) -> None:
        ids: list[str] = []
        for node in self.nodes:
            # command_template is optional only for ABI internal nodes.
            required = self.required_node_fields - (
                {"checks"} if str(node.get("tool", "")).startswith("abi.internal.") else set()
            )
            missing = sorted(field for field in required if field not in node)
            if missing:
                raise WorkflowDefinitionError(
                    f"Node {node.get('id', '<unknown>')} is missing: {', '.join(missing)}"
                )
            ids.append(str(node["id"]))
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise WorkflowDefinitionError(f"Duplicate node ids: {', '.join(duplicates)}")
        known = set(ids)
        for node in self.nodes:
            unknown = set(node.get("depends_on", [])) - known
            if unknown:
                raise WorkflowDefinitionError(
                    f"Node {node['id']} has unknown dependencies: {sorted(unknown)}"
                )
        self.topological_nodes()  # cycle check

    def topological_nodes(self) -> list[dict[str, Any]]:
        remaining = {str(node["id"]): dict(node) for node in self.nodes}
        ordered: list[dict[str, Any]] = []
        completed: set[str] = set()
        while remaining:
            ready = [
                node_id
                for node_id, node in remaining.items()
                if set(node.get("depends_on", [])) <= completed
            ]
            if not ready:
                raise WorkflowDefinitionError(
                    f"Workflow contains a dependency cycle: {sorted(remaining)}"
                )
            for node_id in ready:
                ordered.append(remaining.pop(node_id))
                completed.add(node_id)
        return ordered

    @staticmethod
    def _iterations(
        node: Mapping[str, Any], samples: Sequence[SampleRecord]
    ) -> Iterable[dict[str, Any]]:
        mapping = node.get("map_over")
        if not mapping:
            yield {}
            return
        if mapping == "samples":
            for sample in samples:
                yield {"sample": sample.as_dict()}
            return
        if isinstance(mapping, Mapping):
            dimensions: list[tuple[str, Sequence[Any]]] = []
            for key, value in mapping.items():
                if value == "samples" or key == "samples":
                    dimensions.append(("sample", [sample.as_dict() for sample in samples]))
                else:
                    singular = str(key).removesuffix("s")
                    dimensions.append((singular, list(value)))
            for values in itertools.product(*(dimension[1] for dimension in dimensions)):
                yield {dimensions[index][0]: item for index, item in enumerate(values)}
            return
        raise WorkflowDefinitionError(f"Unsupported map_over in node {node['id']}")

    def plan(
        self,
        manifest: str | Path,
        workdir: str | Path,
        *,
        db_registry: str | Path | None = None,
        threads: int = 16,
        check_files: bool = True,
    ) -> list[dict[str, Any]]:
        samples = ManifestValidator.validate(manifest, check_files=check_files)
        root = Path(workdir).resolve()
        db_data: dict[str, Any] = {}
        if db_registry:
            db_data = yaml.safe_load(Path(db_registry).read_text(encoding="utf-8")) or {}
            path = str(db_data.get("path", ""))
            db_data = {"kraken2": {**db_data, "path": path}}
        records: list[dict[str, Any]] = []
        for node in self.topological_nodes():
            for iteration in self._iterations(node, samples):
                sample = iteration.get("sample")
                context: dict[str, Any] = {
                    "sample": _namespace(sample or {}),
                    "sample_id": (sample or {}).get("sample_id", "all"),
                    "tax_level": iteration.get("tax_level", ""),
                    "project": _namespace({"workdir": str(root)}),
                    "db": _namespace(db_data),
                    "inputs": _namespace(
                        {"manifest": str(Path(manifest).resolve()), "database_registry": db_data}
                    ),
                }
                inputs = _render(node.get("inputs", {}), context)
                outputs = _render(
                    node.get("outputs", {}), {**context, "inputs": _namespace(inputs)}
                )
                params = _render(
                    node.get("params", {}),
                    {**context, "inputs": _namespace(inputs), "outputs": _namespace(outputs)},
                )
                inputs = {key: _absolutize(value, root) for key, value in inputs.items()}
                outputs = {key: _absolutize(value, root) for key, value in outputs.items()}
                render_context = {
                    **context,
                    "inputs": _namespace(inputs),
                    "outputs": _namespace(outputs),
                    "params": _namespace({"threads": threads, **params}),
                }
                command_template = node.get("command_template")
                command = (
                    _render(command_template, render_context)
                    if command_template
                    else f"abi internal {node['id']}"
                )
                checks = []
                for item in node.get("checks", []):
                    if isinstance(item, Mapping) and item.get("exists"):
                        checks.append(_absolutize(_render(item["exists"], render_context), root))
                suffix = ""
                if sample:
                    suffix += f":{sample['sample_id']}"
                if iteration.get("tax_level"):
                    suffix += f":{iteration['tax_level']}"
                records.append(
                    {
                        "node": str(node["id"]) + suffix,
                        "node_id": str(node["id"]),
                        "tool": str(node["tool"]),
                        "command": str(command),
                        "inputs": inputs,
                        "outputs": outputs,
                        "checks": checks,
                        "depends_on": list(node.get("depends_on", [])),
                        "params": params,
                        "resources": dict(node.get("resources", {})),
                        "on_fail": dict(node.get("on_fail", {})),
                    }
                )
        return records

    def dry_run(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        kwargs.setdefault("check_files", True)
        return self.plan(*args, **kwargs)
