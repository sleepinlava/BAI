from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "config" / "worktree" / "core.sparse-checkout"


def _patterns() -> list[str]:
    return [
        line.strip()
        for line in PROFILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _is_hidden(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if not pattern.startswith("!/"):
            continue
        excluded = pattern[2:]
        if excluded.endswith("/"):
            excluded += "*"
        if fnmatch(path, excluded):
            return True
    return False


def test_core_worktree_profile_keeps_release_surface_visible() -> None:
    patterns = _patterns()

    assert patterns[0] == "/*"
    for path in (
        ".github/workflows/ci.yml",
        "docs/build_docs.sh",
        "docs/en/development.md",
        "docs/zh/development.md",
        "scripts/audit_contract_coverage.py",
        "scripts/check_release_identity.py",
        "scripts/cloud/prepare_release_lock.sh",
        "scripts/download_databases.sh",
    ):
        assert not _is_hidden(path, patterns), path


def test_core_worktree_profile_hides_archival_material() -> None:
    patterns = _patterns()

    for path in (
        "docs/_static/paper_examples/airway_validation.png",
        "docs/en/paper_evaluation.md",
        "docs/en/paper_outline.md",
        "docs/en/publication_evidence_package.md",
        "docs/paper_examples/manifests/airway.evidence-manifest.json",
        "docs/superpowers/specs/old-plan.md",
        "docs/zh/current_conclusions_next_steps.md",
        "docs/zh/figures/rendered/scapp_plsdb_technical_metrics.pdf",
        "docs/zh/paper_evaluation.md",
        "docs/zh/paper_outline.md",
        "scripts/build_paper_provenance.py",
        "scripts/cloud/continue_scapp_k127_and_validate.sh",
    ):
        assert _is_hidden(path, patterns), path


def test_core_worktree_profile_keeps_product_documentation_visible() -> None:
    patterns = _patterns()

    for path in (
        "docs/en/development.md",
        "docs/en/release.md",
        "docs/en/runtime_locks.md",
        "docs/en/usage_guide.md",
        "docs/zh/development.md",
        "docs/zh/release.md",
        "docs/zh/runtime_locks.md",
        "docs/zh/usage_guide.md",
    ):
        assert not _is_hidden(path, patterns), path


def test_worktree_view_documents_full_restore() -> None:
    readme = (PROFILE.parent / "README.md").read_text(encoding="utf-8")

    assert "git sparse-checkout disable" in readme
