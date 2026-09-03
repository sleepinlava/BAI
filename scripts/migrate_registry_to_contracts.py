#!/usr/bin/env python3
"""One-time migration (P1-1): strip execution metadata from tool_registry.yaml.

``tool_contracts/<tool_id>.yaml`` is the authoritative execution declaration.
``ToolCatalog`` already overlays contract execution fields onto registry
entries, so any ``executable``/``command_template``/``inputs`` copy in the
registry is a second hand-maintained source that must be kept in sync
manually. This script removes the redundant copies:

- ``command_template`` / ``executable``: removed when byte-identical
  (whitespace-normalized) to the contract's ``execution.*`` value; conflicts
  are reported and kept for manual adjudication.
- ``inputs``: removed when the contract declares its own typed ``inputs``
  mapping (the merged runtime view always uses the contract's); the removed
  names are printed so any divergence stays visible in the diff.

Run with ``--apply`` to write changes; the default is a dry-run report.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXECUTION_FIELDS = ("command_template", "executable")


def _normalize(value: object) -> str:
    return " ".join(str(value or "").split())


def _contract_execution(contract: dict, field: str) -> str | None:
    execution = contract.get("execution")
    if not isinstance(execution, dict):
        return None
    value = execution.get(field)
    return None if value is None else str(value)


def migrate_plugin(plugin_dir: Path, *, apply: bool) -> int:
    registry_path = plugin_dir / "tool_registry.yaml"
    contracts_dir = plugin_dir / "tool_contracts"
    if not registry_path.is_file() or not contracts_dir.is_dir():
        return 0
    plugin = plugin_dir.name
    contracts: dict[str, dict] = {}
    for contract_path in sorted(contracts_dir.glob("*.yaml")):
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
        if isinstance(contract, dict) and contract.get("tool_id"):
            contracts[str(contract["tool_id"])] = contract

    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    tools = data.get("tools")
    if not isinstance(tools, list):
        print(f"{plugin}: registry has no tools list; skipped")
        return 0

    changed = 0
    for entry in tools:
        if not isinstance(entry, dict):
            continue
        tool_id = str(entry.get("id", "") or entry.get("tool_id", ""))
        contract = contracts.get(tool_id)
        if contract is None:
            print(f"{plugin}/{tool_id}: no contract; registry entry kept as-is")
            continue
        for field in EXECUTION_FIELDS:
            if field not in entry:
                continue
            contract_value = _contract_execution(contract, field)
            if contract_value is None:
                print(f"{plugin}/{tool_id}: contract lacks execution.{field}; kept")
                continue
            if _normalize(entry[field]) == _normalize(contract_value):
                del entry[field]
                changed += 1
            else:
                print(
                    f"{plugin}/{tool_id}: CONFLICT on {field} — "
                    f"registry={entry[field]!r} contract={contract_value!r}; kept for review"
                )
        if "inputs" in entry:
            contract_inputs = contract.get("inputs")
            if isinstance(contract_inputs, dict):
                registry_names = [str(name) for name in entry["inputs"]]
                missing = sorted(set(registry_names) - set(contract_inputs))
                del entry["inputs"]
                changed += 1
                if missing:
                    print(
                        f"{plugin}/{tool_id}: registry inputs not in contract "
                        f"(now dropped with the list): {missing}"
                    )
            else:
                print(f"{plugin}/{tool_id}: contract lacks typed inputs; registry list kept")

    if apply and changed:
        registry_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    print(f"{plugin}: {changed} field(s) {'removed' if apply else 'to remove'}")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default: dry-run report only; exits 1 when a "
        "dry-run finds pending changes).",
    )
    parser.add_argument(
        "--plugin",
        action="append",
        help="Limit to one plugin directory name; repeatable.",
    )
    args = parser.parse_args(argv)

    plugins_root = PROJECT_ROOT / "plugins"
    total = 0
    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if args.plugin and plugin_dir.name not in args.plugin:
            continue
        total += migrate_plugin(plugin_dir, apply=args.apply)
    print(f"total: {total} field(s) {'removed' if args.apply else 'to remove'}")
    return 0 if total == 0 or args.apply else 1


if __name__ == "__main__":
    sys.exit(main())
