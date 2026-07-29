from __future__ import annotations

from pathlib import Path

import pytest

try:
    from docs.diagrams.generate_abi_architecture_drawio import render
except ImportError:
    render = None  # type: ignore[assignment]

DIAGRAM_PATH = Path(__file__).parents[2] / "docs/diagrams/abi-architecture.drawio"


@pytest.mark.skipif(render is None, reason="Diagram generator not available")
def test_architecture_diagram_generation_is_deterministic():
    assert render() == render()


@pytest.mark.skipif(render is None, reason="Diagram generator not available")
def test_checked_in_architecture_diagram_matches_generator():
    assert DIAGRAM_PATH.read_text(encoding="utf-8") == render()


@pytest.mark.skipif(render is None, reason="Diagram generator not available")
def test_architecture_diagram_documents_workflow_deepening():
    assert 'name="05-工作流深模块"' in render()
