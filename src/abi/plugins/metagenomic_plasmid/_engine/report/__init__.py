"""Report generation helpers."""

from __future__ import annotations

from typing import List

__all__ = ["load_plugin_limitations"]


def load_plugin_limitations() -> List[str]:
    """Load the declared limitations from the plugin's ``limitations.yaml``.

    Returns an empty list when the declaration is missing or unreadable;
    report writers render an explicit fallback sentence in that case so the
    limitations section is never silently omitted.
    """
    from abi.config import PLUGIN_ROOT
    from abi.report.limitations import load_limitations

    return load_limitations(PLUGIN_ROOT / "metagenomic_plasmid" / "limitations.yaml")
