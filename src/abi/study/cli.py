"""Command-line entry point for the ABI control-layer validation harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
import yaml

from abi.study.build import build_study_artifacts, record_semantic_review
from abi.study.grading import grade_trial
from abi.study.harness import invoke_workspace_operation, prepare_trial

app = typer.Typer(no_args_is_help=True, help="Build and execute ABI validation study trials.")


def _mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise typer.BadParameter(f"Expected a YAML mapping: {path}")
    return payload


@app.command("build-artifacts")
def build_artifacts_command(
    study_root: Path = typer.Option(..., exists=True, file_okay=False),
    repo_root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False),
    out: Path = typer.Option(..., file_okay=False),
    generate_fixtures: bool = typer.Option(True, "--fixtures/--skip-fixtures"),
) -> None:
    """Generate snapshots, matched cards, fixtures, gold, shims, and audit records."""
    summary = build_study_artifacts(
        repo_root=repo_root.resolve(),
        study_root=study_root.resolve(),
        output_root=out.resolve(),
        generate_fixtures=generate_fixtures,
    )
    typer.echo(json.dumps(summary, sort_keys=True))


@app.command("run")
def run_command(
    study: Path = typer.Option(..., exists=True, dir_okay=False),
    task: str = typer.Option(...),
    condition: str = typer.Option(...),
    model: str = typer.Option(...),
    seed: int = typer.Option(...),
    artifact_root: Path = typer.Option(..., file_okay=False),
    tasks: Path | None = typer.Option(None, exists=True, dir_okay=False),
    fixtures: Path | None = typer.Option(None, exists=True, file_okay=False),
    interface_root: Path | None = typer.Option(None, exists=True, file_okay=False),
) -> None:
    """Prepare an isolated trial request for a frozen external model runner."""
    study_data = _mapping(study)
    study_root = study.parent
    tasks_path = tasks or study_root / "tasks.yaml"
    fixture_root = fixtures or study_root / "fixtures"
    interface = interface_root or study_root
    try:
        result = prepare_trial(
            study=study_data,
            tasks=_mapping(tasks_path),
            study_root=study_root,
            fixture_root=fixture_root,
            interface_root=interface,
            task_id=task,
            condition=condition,
            model_id=model,
            seed=seed,
            artifact_root=artifact_root,
        )
    except (ValueError, FileNotFoundError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(json.dumps(result, sort_keys=True))


@app.command("record-coverage-review")
def record_coverage_review_command(
    coverage: Path = typer.Option(..., exists=True, dir_okay=False),
    reviewer: str = typer.Option(...),
    attest_all_pass: bool = typer.Option(False, "--attest-all-pass"),
) -> None:
    """Record an independent semantic-equivalence attestation."""
    if not attest_all_pass:
        raise typer.BadParameter("Explicit --attest-all-pass is required")
    count = record_semantic_review(coverage, reviewer)
    typer.echo(json.dumps({"status": "recorded", "rows": count, "reviewer": reviewer}))


@app.command("grade")
def grade_command(
    study: Path = typer.Option(..., exists=True, dir_okay=False),
    tasks: Path = typer.Option(..., exists=True, dir_okay=False),
    trial_root: Path = typer.Option(..., exists=True, file_okay=False),
    out: Path = typer.Option(..., dir_okay=False),
) -> None:
    """Grade a completed trial from its final workspace and event trace."""
    record = grade_trial(
        study=_mapping(study),
        tasks=_mapping(tasks),
        trial_root=trial_root,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    typer.echo(json.dumps({"status": "graded", "cvc": record["scores"]["cvc"]}))


@app.command("invoke")
def invoke_command(
    trial_root: Path = typer.Option(..., exists=True, file_okay=False),
    operation: str = typer.Option(...),
    arguments: str = typer.Option("{}"),
) -> None:
    """Invoke one allow-listed advisory workspace operation."""
    try:
        parsed = json.loads(arguments)
        if not isinstance(parsed, dict):
            raise ValueError("arguments must decode to a JSON object")
        result = invoke_workspace_operation(
            trial_root=trial_root,
            operation=operation,
            arguments=parsed,
        )
    except (ValueError, PermissionError, FileNotFoundError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(json.dumps({"status": "success", "result": result}, sort_keys=True))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
