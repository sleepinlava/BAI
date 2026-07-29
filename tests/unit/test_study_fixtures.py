from __future__ import annotations

import json
from pathlib import Path

from abi.study.fixtures import build_fixtures, verify_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "experiments" / "abi_control_validation_v1"


def test_fixture_factory_builds_clean_fault_gold_and_archive(tmp_path: Path) -> None:
    summary = build_fixtures(
        repo_root=REPO_ROOT,
        study_root=STUDY_ROOT,
        output_root=tmp_path,
        task_ids={"rnaseq_t3_missing_mate"},
    )

    assert summary["task_count"] == 1
    clean = tmp_path / "rnaseq" / "t3_clean"
    fault = tmp_path / "rnaseq" / "t3_fault"
    assert (clean / "input" / "reads" / "D1_control_R2.fastq").is_file()
    assert not (fault / "input" / "reads" / "D1_control_R2.fastq").exists()
    assert not (fault / "input" / "shim_state.json").exists()
    assert (fault / "fixture_control.json").is_file()
    assert verify_fixture(clean)["valid"] is True
    assert verify_fixture(fault)["valid"] is False
    assert (tmp_path / "archives" / "rnaseq_t3_missing_mate.tar.gz").is_file()

    gold = json.loads(
        (tmp_path / "gold" / "rnaseq_t3_missing_mate" / "gold.json").read_text(encoding="utf-8")
    )
    assert gold["hidden_root_cause"] == "incomplete_pairs"
    assert gold["compiled_plan"]["analysis_type"] == "rnaseq_expression"
