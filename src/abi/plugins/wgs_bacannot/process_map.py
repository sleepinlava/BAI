"""Process inventory and contracts for Bacannot v3.4.4."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from abi.external_workflows.models import ExternalProcessContract


def map_process_class(process_name: str, contracts: list[ExternalProcessContract]) -> str:
    for contract in contracts:
        if any(
            re.search(pattern, process_name, flags=re.IGNORECASE)
            for pattern in contract.process_patterns
        ):
            return contract.process_class
    return "unmapped"


def load_process_contracts(root: str | Path) -> list[ExternalProcessContract]:
    contracts: list[ExternalProcessContract] = []
    for path in sorted(Path(root).glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cardinality = raw.get("cardinality", {}).get("per_sample", {})
        contracts.append(
            ExternalProcessContract(
                contract_id=str(raw["contract_id"]),
                contract_version=str(raw["contract_version"]),
                process_class=str(raw["process_class"]),
                enabled_when=str(raw["enabled_when"]),
                process_patterns=tuple(str(value) for value in raw["process_patterns"]),
                min_successful_per_sample=int(cardinality.get("min_successful", 1)),
                max_successful_final_per_sample=cardinality.get("max_successful_final"),
                accepted_statuses=tuple(raw.get("accepted_statuses", ["COMPLETED", "CACHED"])),
                required_outputs=tuple(raw.get("required_outputs", [])),
                publish=bool(raw.get("publish", True)),
            )
        )
    return contracts
