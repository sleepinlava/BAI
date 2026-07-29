"""Generate information-matched study artifacts from production plugin contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from abi.diagnostics import ERROR_CODES

SNAPSHOT_SCHEMA = "abi.control-validation.contract-snapshot.v1"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _normalize(value: Any) -> Any:
    """Return JSON-safe data with deterministic mapping order."""
    if isinstance(value, Mapping):
        return {str(key): _normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def _tool_contracts(plugin_root: Path) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for path in sorted((plugin_root / "tool_contracts").glob("*.yaml")):
        contract = _load_yaml(path)
        tool_id = str(contract.get("tool_id") or path.stem)
        contracts[tool_id] = contract
    return contracts


def build_contract_snapshot(repo_root: Path, analysis_type: str) -> dict[str, Any]:
    """Build the single knowledge source shared by both experimental conditions."""
    plugin_root = repo_root / "plugins" / analysis_type
    manifest = _load_yaml(plugin_root / "abi-plugin.yaml")
    dag = _load_yaml(plugin_root / "pipeline_dag.yaml")
    registry = _load_yaml(plugin_root / "tool_registry.yaml")
    tables = _load_yaml(plugin_root / "standard_tables.yaml").get("tables", {})
    limitations = _load_yaml(plugin_root / "limitations.yaml").get("limitations", [])
    if not manifest or not dag:
        raise ValueError(f"Unknown or incomplete ABI plugin: {analysis_type}")

    nodes = dag.get("nodes", {})
    stages = [
        {
            "id": node_id,
            "tool_id": node.get("tool_id"),
            "category": node.get("category"),
            "optional": bool(node.get("optional", False)),
        }
        for node_id, node in nodes.items()
    ]
    edges = [
        {"from": dependency, "to": node_id}
        for node_id, node in nodes.items()
        for dependency in node.get("depends_on", [])
    ]

    contracts = _tool_contracts(plugin_root)
    registry_tools = registry.get("tools", [])
    tools = []
    for registered in registry_tools:
        tool_id = str(registered.get("id"))
        contract = contracts.get(tool_id, {})
        inputs = contract.get("inputs") or {
            name: {"required": True} for name in registered.get("inputs", [])
        }
        tools.append(
            {
                "id": tool_id,
                "name": registered.get("name", contract.get("name", tool_id)),
                "description": contract.get("purpose", registered.get("category", "")),
                "parameters": inputs,
                "outputs": contract.get("outputs", {}),
                "resources": contract.get("resources", {}),
                "failure_handling": contract.get("failure_handling", {}),
            }
        )

    output_contracts = []
    for node_id, node in nodes.items():
        for output_name, output in node.get("outputs", {}).items():
            if not isinstance(output, dict):
                continue
            output_contracts.append(
                {
                    "stage": node_id,
                    "output": output_name,
                    "type": output.get("type"),
                    "format": output.get("format"),
                    "path": output.get("path"),
                    "contract": output.get("contract", {}),
                }
            )

    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA,
        "plugin": {
            "analysis_type": manifest.get("plugin_id", analysis_type),
            "display_name": manifest.get("display_name", analysis_type),
            "description": manifest.get("description", ""),
        },
        "platforms": dag.get("platforms", []),
        "stages": stages,
        "dag_edges": edges,
        "tools": tools,
        "output_contracts": output_contracts,
        "error_categories": sorted(ERROR_CODES),
        "standard_tables": tables,
        "limitations": limitations,
    }
    return _normalize(snapshot)


def snapshot_json(snapshot: Mapping[str, Any]) -> str:
    return json.dumps(_normalize(snapshot), indent=2, sort_keys=True) + "\n"


def render_advisory_card(snapshot: Mapping[str, Any]) -> str:
    """Render neutral workflow knowledge without task-specific hints or gold."""
    plugin = snapshot["plugin"]
    lines = [
        f"# {plugin['display_name']}",
        "",
        f"Analysis type: `{plugin['analysis_type']}`",
        "",
        str(plugin["description"]),
        "",
        "## Supported platforms and profiles",
        "",
        ", ".join(f"`{platform}`" for platform in snapshot["platforms"]),
        "",
        "## Stages",
        "",
    ]
    for stage in snapshot["stages"]:
        optional = "optional" if stage["optional"] else "required"
        lines.append(
            f"- `{stage['id']}` — tool `{stage['tool_id']}`; "
            f"category `{stage['category']}`; {optional}"
        )
    lines.extend(["", "## Workflow dataflow", ""])
    if snapshot["dag_edges"]:
        for edge in snapshot["dag_edges"]:
            lines.append(f"- `{edge['from']}` → `{edge['to']}`")
    else:
        lines.append("- No dependency edges declared.")
    lines.extend(["", "## Tools and contracts", ""])
    for tool in snapshot["tools"]:
        lines.append(f"### `{tool['id']}` — {tool['name']}")
        lines.append("")
        lines.append(str(tool["description"]))
        lines.append("")
        lines.append("Inputs/parameters:")
        for name, spec in tool["parameters"].items():
            required = "required" if spec.get("required", False) else "optional"
            details = json.dumps(spec, sort_keys=True)
            lines.append(f"- `{name}` ({required}): `{details}`")
        lines.append("Outputs:")
        for name, spec in tool["outputs"].items():
            lines.append(f"- `{name}`: `{json.dumps(spec, sort_keys=True)}`")
        lines.append(f"Resources: `{json.dumps(tool['resources'], sort_keys=True)}`")
        lines.append(
            f"Failure categories: `{json.dumps(tool['failure_handling'], sort_keys=True)}`"
        )
        lines.append("")
    lines.extend(["## Output acceptance rules", ""])
    for contract in snapshot["output_contracts"]:
        lines.append(
            f"- `{contract['stage']}.{contract['output']}`: "
            f"`{json.dumps(contract, sort_keys=True)}`"
        )
    lines.extend(["", "## Standard tables", ""])
    for name, columns in snapshot["standard_tables"].items():
        lines.append(f"- `{name}`: {', '.join(str(column) for column in columns)}")
    lines.extend(["", "## Stable error categories", ""])
    lines.append(", ".join(f"`{code}`" for code in snapshot["error_categories"]))
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in snapshot["limitations"])
    return "\n".join(lines).rstrip() + "\n"
