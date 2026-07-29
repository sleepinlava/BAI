from __future__ import annotations

import json
from pathlib import Path

import yaml

from abi import get_agent_guide
from abi.agent import ABIAgentInterface

EXPECTED_SAFE_SEQUENCE = [
    "list_types",
    "query",
    "plan",
    "check",
    "dry_run",
    "inspect",
    "run",
    "inspect",
    "abi_validate_result",
    "report",
]

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_agent_context_exports_canonical_control_lifecycle() -> None:
    payload = json.loads(
        ABIAgentInterface().export_agent_context(analysis_type="metatranscriptomics")
    )

    assert payload["status"] == "success"
    context = payload["result"]
    assert context["safe_sequence"] == EXPECTED_SAFE_SEQUENCE
    assert context["canonical_lifecycle"] == [
        {
            "phase": "discovery",
            "steps": ["list_types", "query"],
            "optional_steps": ["query"],
        },
        {
            "phase": "preparation",
            "steps": ["plan", "check", "dry_run", "inspect"],
            "optional_steps": [],
        },
        {
            "phase": "execution",
            "steps": ["request_authorization", "run"],
            "optional_steps": [],
        },
        {
            "phase": "validation",
            "steps": ["inspect", "abi_validate_result", "report"],
            "optional_steps": [],
        },
    ]


def test_agent_guide_describes_preflight_and_post_run_validation() -> None:
    guide = get_agent_guide()

    assert "query" in guide
    assert "check" in guide
    assert "request_authorization" in guide
    assert "validate_result" in guide
    assert guide.index("check") < guide.index("dry_run")
    assert guide.index("run") < guide.index("validate_result")


def test_study_and_agent_context_use_the_same_canonical_lifecycle() -> None:
    study = yaml.safe_load(
        (REPO_ROOT / "experiments" / "abi_control_validation_v1" / "study.yaml").read_text(
            encoding="utf-8"
        )
    )
    context = json.loads(
        ABIAgentInterface().export_agent_context(analysis_type="rnaseq_expression")
    )["result"]

    assert study["canonical_lifecycle_to_freeze"] == {
        phase["phase"]: phase["steps"] for phase in context["canonical_lifecycle"]
    }
