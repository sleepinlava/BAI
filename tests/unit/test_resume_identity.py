from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from abi.resume import (
    build_resume_identity,
    compare_resume_identity,
    load_resume_identity,
    path_identity,
    validate_stored_resume_identity,
    write_resume_identity,
)


def test_resume_identity_ignores_generated_dag_outputs_but_keeps_raw_files(
    tmp_path: Path,
) -> None:
    outdir = tmp_path / "outputs"
    outdir.mkdir()
    raw = outdir / "raw.fastq"
    raw.write_text("@r1\nACGT\n+\n!!!!\n", encoding="utf-8")
    clean = outdir / "clean.fastq"
    plan = SimpleNamespace(
        selected_tools=[],
        steps=[
            SimpleNamespace(
                step_id="qc",
                inputs={"read1": str(raw)},
                outputs={"clean_read1": str(clean), "output_dir": str(outdir)},
            ),
            SimpleNamespace(
                step_id="assembly",
                inputs={"read1": str(clean)},
                outputs={"output_dir": str(outdir / "assembly")},
            ),
        ],
    )

    first = build_resume_identity(plan, plan_id="sha256:plan")
    clean.write_text("@r1\nTGCA\n+\n!!!!\n", encoding="utf-8")
    second = build_resume_identity(plan, plan_id="sha256:plan")

    assert "external input content changed" not in compare_resume_identity(second, first)
    assert any(row["path"] == str(raw.resolve()) for row in first["inputs"])


def test_resume_identity_rejects_raw_input_drift_inside_output_dir(tmp_path: Path) -> None:
    outdir = tmp_path / "outputs"
    outdir.mkdir()
    raw_target = tmp_path / "raw.fastq"
    raw_target.write_text("@r1\nACGT\n+\n!!!!\n", encoding="utf-8")
    raw_link = outdir / "raw.fastq"
    raw_link.symlink_to(raw_target)
    clean = outdir / "clean.fastq"
    plan = SimpleNamespace(
        selected_tools=[],
        steps=[
            SimpleNamespace(
                step_id="qc",
                inputs={"read1": str(raw_link)},
                outputs={"clean_read1": str(clean), "output_dir": str(outdir)},
            ),
            SimpleNamespace(
                step_id="assembly",
                inputs={"read1": str(clean)},
                outputs={"output_dir": str(outdir / "assembly")},
            ),
        ],
    )

    first = build_resume_identity(plan, plan_id="sha256:plan")
    clean.write_text("@r1\nTGCA\n+\n!!!!\n", encoding="utf-8")
    raw_target.write_text("@r1\nNNNN\n+\n!!!!\n", encoding="utf-8")
    second = build_resume_identity(plan, plan_id="sha256:plan")

    assert "external input content changed" in compare_resume_identity(second, first)


def test_resume_identity_expands_aggregate_dir_around_generated_files(tmp_path: Path) -> None:
    aggregate = tmp_path / "outputs"
    aggregate.mkdir()
    raw = aggregate / "provided.fastq"
    raw.write_text("raw-v1\n", encoding="utf-8")
    generated = aggregate / "clean.fastq"
    plan = SimpleNamespace(
        selected_tools=[],
        steps=[
            SimpleNamespace(
                step_id="qc",
                inputs={},
                outputs={"clean_read1": str(generated), "output_dir": str(aggregate)},
            ),
            SimpleNamespace(
                step_id="join",
                inputs={"reads": str(aggregate)},
                outputs={},
            ),
        ],
    )

    first = build_resume_identity(plan, plan_id="sha256:plan")
    generated.write_text("clean-v1\n", encoding="utf-8")
    second = build_resume_identity(plan, plan_id="sha256:plan")

    assert "external input content changed" not in compare_resume_identity(second, first)
    raw.write_text("raw-v2\n", encoding="utf-8")
    third = build_resume_identity(plan, plan_id="sha256:plan")
    assert "external input content changed" in compare_resume_identity(third, second)


def test_resume_identity_binds_external_input_content(tmp_path: Path) -> None:
    input_path = tmp_path / "reads.fastq"
    input_path.write_text("@r1\nACGT\n+\n!!!!\n", encoding="utf-8")
    plan = SimpleNamespace(
        selected_tools=["fastp"],
        steps=[SimpleNamespace(step_id="s1", inputs={"read1": str(input_path)})],
    )

    first = build_resume_identity(
        plan,
        plan_id="sha256:plan",
        tool_rows=[{"tool_id": "fastp", "version": "0.23.2", "status": "captured"}],
    )
    input_path.write_text("@r1\nTGCA\n+\n!!!!\n", encoding="utf-8")
    second = build_resume_identity(
        plan,
        plan_id="sha256:plan",
        tool_rows=[{"tool_id": "fastp", "version": "0.23.2", "status": "captured"}],
    )

    assert "external input content changed" in compare_resume_identity(second, first)


def test_resume_identity_binds_canonical_sample_inputs(tmp_path: Path) -> None:
    first_input = tmp_path / "first.fastq"
    second_input = tmp_path / "second.fastq"
    first_input.write_text("@r1\nACGT\n+\n!!!!\n", encoding="utf-8")
    second_input.write_text("@r1\nTGCA\n+\n!!!!\n", encoding="utf-8")
    plan = SimpleNamespace(
        selected_tools=[],
        steps=[],
        samples=[SimpleNamespace(sample_id="S1", read1=str(first_input))],
    )
    first = build_resume_identity(plan, plan_id="sha256:plan")
    plan.samples[0].read1 = str(second_input)
    second = build_resume_identity(plan, plan_id="sha256:plan")

    assert "external input content changed" in compare_resume_identity(second, first)


def test_resume_identity_binds_tools_and_resources(tmp_path: Path) -> None:
    resource = tmp_path / "index"
    resource.mkdir()
    (resource / "part.bin").write_bytes(b"v1")
    plan = SimpleNamespace(selected_tools=["tool"], steps=[])
    first = build_resume_identity(
        plan,
        plan_id="sha256:plan",
        tool_rows=[{"tool_id": "tool", "version": "1", "status": "captured"}],
        resources=[{"id": "index", "path": str(resource), "version": "1"}],
    )
    (resource / "part.bin").write_bytes(b"v2")
    second = build_resume_identity(
        plan,
        plan_id="sha256:plan",
        tool_rows=[{"tool_id": "tool", "version": "2", "status": "captured"}],
        resources=[{"id": "index", "path": str(resource), "version": "1"}],
    )

    reasons = compare_resume_identity(second, first)
    assert "tool identity changed" in reasons
    assert "resource identity changed" in reasons


def test_resume_identity_round_trip_is_schema_checked(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("data", encoding="utf-8")
    identity = {
        "schema_version": "abi.resume_identity.v1",
        "plan_id": "",
        "inputs": [path_identity(source)],
        "tools": [],
        "resources": [],
        "containers": [],
    }
    path = write_resume_identity(identity, tmp_path / "provenance")

    assert load_resume_identity(path) == identity
    path.write_text(json.dumps({**identity, "schema_version": "unknown"}), encoding="utf-8")
    assert load_resume_identity(path) is None


def test_resume_identity_binds_container_reference_and_digest() -> None:
    plan = SimpleNamespace(
        steps=[SimpleNamespace(step_id="s1", tool_id="fastp")],
        selected_tools=["fastp"],
    )
    first = build_resume_identity(
        plan,
        containers=[
            {
                "tool_id": "fastp",
                "image": "docker://example/fastp:latest",
                "runtime": "docker",
                "digest": "sha256:old",
            }
        ],
    )
    second = build_resume_identity(
        plan,
        containers=[
            {
                "tool_id": "fastp",
                "image": "docker://example/fastp:latest",
                "runtime": "docker",
                "digest": "sha256:new",
            }
        ],
    )

    assert "container image identity changed" in compare_resume_identity(second, first)


def test_resume_identity_rejects_equal_but_unverified_facts() -> None:
    plan = SimpleNamespace(steps=[], selected_tools=[])
    identity = build_resume_identity(
        plan,
        tool_rows=[{"tool_id": "tool", "version": "", "status": "not_captured"}],
        resources=[{"id": "db", "path": "/missing/db"}],
        containers=[
            {
                "tool_id": "tool",
                "image": "docker://example/tool:latest",
                "runtime": "docker",
                "digest": "",
            }
        ],
    )

    reasons = compare_resume_identity(identity, identity)
    assert "tool identity is unverified" in reasons
    assert "resource identity is unverified" in reasons
    assert "container image identity is unverified" in reasons


def test_resume_identity_rejects_unidentified_existing_cache(tmp_path: Path) -> None:
    cache = tmp_path / "nextflow-work"
    cache.mkdir()
    current = build_resume_identity(SimpleNamespace(steps=[], selected_tools=[]))

    reasons = validate_stored_resume_identity(tmp_path, current, cache_paths=(cache,))

    assert reasons == ["the prior run has no valid resume identity record"]
