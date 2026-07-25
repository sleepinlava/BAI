#!/usr/bin/env python3
"""Audit output-contract coverage across built-in plugin ``pipeline_dag.yaml`` files.

For each built-in plugin under ``plugins/`` this script reports how many DAG
nodes declare at least one output ``contract:`` block (enforced by
``abi.contracts.step_contract.validate_output_contract``) and how many do not.
Every uncovered node is classified as either:

- ``internal_or_aggregation`` — executed in-process by the executor
  (``tool_id: internal``, an ``internal_handler:`` key, or an inline
  ``params._internal_handler`` mapping).  These are candidates for the planned
  explicit ``contract: {exempt: true, reason: ...}`` mechanism instead of
  file-based output contracts.
- ``external_tool`` — dispatched to an external executable and therefore
  needs per-output ``contract:`` declarations.  The node's declared outputs
  (name, type, format, path template) are included so contract authors know
  which files to assert.

Output: JSON report on stdout, human-readable summary on stderr.

Usage::

    python scripts/audit_contract_coverage.py
    python scripts/audit_contract_coverage.py --plugins-dir plugins --pretty
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _is_internal_node(node: Mapping[str, Any]) -> bool:
    """Return True when the executor runs this node in-process (no external tool)."""
    if str(node.get("tool_id", "")) == "internal":
        return True
    if node.get("internal_handler"):
        return True
    params = node.get("params")
    if isinstance(params, Mapping) and isinstance(params.get("_internal_handler"), Mapping):
        return True
    return False


def _output_info(name: str, spec: Any) -> dict[str, Any]:
    """Normalize one declared output entry for the report."""
    if not isinstance(spec, Mapping):
        return {"name": str(name), "type": None, "format": None, "path": None, "contract": None}
    contract = spec.get("contract")
    return {
        "name": str(name),
        "type": spec.get("type"),
        "format": spec.get("format"),
        "path": spec.get("path"),
        "contract": dict(contract) if isinstance(contract, Mapping) else None,
    }


def _node_info(node_id: str, node: Mapping[str, Any]) -> dict[str, Any]:
    outputs = node.get("outputs")
    output_entries = [
        _output_info(name, spec)
        for name, spec in (outputs.items() if isinstance(outputs, Mapping) else [])
    ]
    params = node.get("params")
    inline_handler = params.get("_internal_handler") if isinstance(params, Mapping) else None
    return {
        "node_id": node_id,
        "tool_id": str(node.get("tool_id", node_id)),
        "category": str(node.get("category", "")),
        "scope": str(node.get("scope", "per_sample")),
        "optional": bool(node.get("optional", False)),
        "platforms": [str(p) for p in node.get("platforms", []) or []],
        "internal_handler": node.get("internal_handler")
        or (inline_handler.get("handler_id") if isinstance(inline_handler, Mapping) else None),
        "outputs": output_entries,
    }


def audit_plugin(dag_path: Path) -> dict[str, Any]:
    """Audit one plugin's ``pipeline_dag.yaml`` for output-contract coverage."""
    spec = yaml.safe_load(dag_path.read_text(encoding="utf-8")) or {}
    raw_nodes = spec.get("nodes")
    if not isinstance(raw_nodes, Mapping):
        raise ValueError(f"{dag_path}: pipeline_dag.yaml must contain a 'nodes' mapping")

    covered: list[dict[str, Any]] = []
    uncovered_internal: list[dict[str, Any]] = []
    uncovered_external: list[dict[str, Any]] = []
    exempt: list[dict[str, Any]] = []

    for node_id, node in raw_nodes.items():
        if not isinstance(node, Mapping):
            continue
        info = _node_info(str(node_id), node)
        contracted = [o for o in info["outputs"] if o["contract"]]
        is_exempt = any(o["contract"] and o["contract"].get("exempt") for o in info["outputs"])
        if is_exempt:
            exempt.append(info)
        elif contracted:
            info["outputs_without_contract"] = [
                o["name"] for o in info["outputs"] if not o["contract"]
            ]
            covered.append(info)
        elif _is_internal_node(node):
            uncovered_internal.append(info)
        else:
            uncovered_external.append(info)

    total = len(covered) + len(uncovered_internal) + len(uncovered_external) + len(exempt)
    return {
        "pipeline_dag": str(dag_path),
        "totals": {
            "nodes": total,
            "with_contract": len(covered),
            "exempt": len(exempt),
            "without_contract": len(uncovered_internal) + len(uncovered_external),
            "uncovered_internal_or_aggregation": len(uncovered_internal),
            "uncovered_external_tool": len(uncovered_external),
        },
        "covered_nodes": covered,
        "exempt_nodes": exempt,
        "uncovered_internal_or_aggregation": uncovered_internal,
        "uncovered_external_tool": uncovered_external,
    }


def _print_summary(report: Mapping[str, Any], stream: Any) -> None:
    print("Output-contract coverage audit (pipeline_dag.yaml)", file=stream)
    print("=" * 60, file=stream)
    for plugin_id, plugin in report["plugins"].items():
        t = plugin["totals"]
        print(
            f"{plugin_id:24s} nodes={t['nodes']:3d} covered={t['with_contract']:3d} "
            f"uncovered={t['without_contract']:3d} "
            f"(internal/exempt-candidates={t['uncovered_internal_or_aggregation']:3d}, "
            f"external-needs-contract={t['uncovered_external_tool']:3d})",
            file=stream,
        )
    t = report["totals"]
    print("-" * 60, file=stream)
    print(
        f"{'TOTAL':24s} nodes={t['nodes']:3d} covered={t['with_contract']:3d} "
        f"uncovered={t['without_contract']:3d} "
        f"(internal/exempt-candidates={t['uncovered_internal_or_aggregation']:3d}, "
        f"external-needs-contract={t['uncovered_external_tool']:3d})",
        file=stream,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugins-dir",
        type=Path,
        default=REPO_ROOT / "plugins",
        help="Directory containing built-in plugin folders (default: %(default)s)",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON report")
    args = parser.parse_args(argv)

    plugins: dict[str, Any] = {}
    for dag_path in sorted(args.plugins_dir.glob("*/pipeline_dag.yaml")):
        plugin_id = dag_path.parent.name
        plugins[plugin_id] = audit_plugin(dag_path)

    totals = {
        "nodes": sum(p["totals"]["nodes"] for p in plugins.values()),
        "with_contract": sum(p["totals"]["with_contract"] for p in plugins.values()),
        "exempt": sum(p["totals"]["exempt"] for p in plugins.values()),
        "without_contract": sum(p["totals"]["without_contract"] for p in plugins.values()),
        "uncovered_internal_or_aggregation": sum(
            p["totals"]["uncovered_internal_or_aggregation"] for p in plugins.values()
        ),
        "uncovered_external_tool": sum(
            p["totals"]["uncovered_external_tool"] for p in plugins.values()
        ),
    }
    report = {"plugins_dir": str(args.plugins_dir), "plugins": plugins, "totals": totals}

    indent = 2 if args.pretty else None
    print(json.dumps(report, indent=indent, sort_keys=False))
    _print_summary(report, sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
