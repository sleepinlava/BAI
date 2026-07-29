from __future__ import annotations

import json
from pathlib import Path

from abi.study.artifacts import build_contract_snapshot
from abi.study.tool_shim import run_tool_shim

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_tool_shim_clean_and_invalid_zero_exit_behaviors(tmp_path: Path) -> None:
    clean_output = tmp_path / "clean.tsv"
    clean = run_tool_shim(
        tool_id="build_count_matrix",
        arguments={"--counts": "input.tsv"},
        outputs={"count_table": clean_output},
        behavior="clean",
        state_root=tmp_path / "state",
        event_log=tmp_path / "events.jsonl",
    )
    invalid_output = tmp_path / "invalid.tsv"
    invalid = run_tool_shim(
        tool_id="build_count_matrix",
        arguments={"--counts": "input.tsv"},
        outputs={"count_table": invalid_output},
        behavior="exit_zero_with_empty_gene_counts",
        state_root=tmp_path / "state",
        event_log=tmp_path / "events.jsonl",
    )

    assert clean.exit_code == 0
    assert clean_output.read_text(encoding="utf-8").startswith("gene_id")
    assert invalid.exit_code == 0
    assert invalid_output.read_text(encoding="utf-8") == ""
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event"] for event in events] == [
        "external_tool_start",
        "external_tool_end",
        "external_tool_start",
        "external_tool_end",
    ]


def test_tool_shim_fails_once_then_resumes(tmp_path: Path) -> None:
    kwargs = {
        "tool_id": "prokka",
        "arguments": {"--outdir": "annotation"},
        "outputs": {"annotation": tmp_path / "annotation.tsv"},
        "behavior": "fail_once",
        "state_root": tmp_path / "state",
        "event_log": tmp_path / "events.jsonl",
    }

    assert run_tool_shim(**kwargs).exit_code == 42
    assert run_tool_shim(**kwargs).exit_code == 0


def test_selected_workflow_tools_accept_their_generated_golden_contracts(
    tmp_path: Path,
) -> None:
    for workflow in ["rnaseq_expression", "wgs_bacteria", "metagenomic_plasmid"]:
        snapshot = build_contract_snapshot(REPO_ROOT, workflow)
        for tool in snapshot["tools"]:
            arguments = {
                name: f"<{name}>"
                for name, specification in tool["parameters"].items()
                if specification.get("required", False)
            }
            outputs = {
                name: tmp_path / workflow / tool["id"] / f"{name}.tsv" for name in tool["outputs"]
            }
            result = run_tool_shim(
                tool_id=tool["id"],
                arguments=arguments,
                outputs=outputs,
                behavior="clean",
                state_root=tmp_path / "state" / workflow,
                event_log=tmp_path / "events.jsonl",
                contract_parameters=tool["parameters"],
                contract_outputs=tool["outputs"],
            )
            assert result.exit_code == 0
            assert set(result.output_digests) == set(outputs)
