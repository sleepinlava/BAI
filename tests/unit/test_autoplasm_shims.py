from __future__ import annotations


def test_canonical_engine_objects_live_under_the_plugin_package():
    """WP2: the abi.autoplasm shim namespace is retired; imports resolve to
    the engine modules inside the plugin package."""
    from abi.plugins.metagenomic_plasmid import build_plan_from_dag as new_build_plan
    from abi.plugins.metagenomic_plasmid._engine.config import load_config
    from abi.plugins.metagenomic_plasmid._engine.parsers import parse_standard_outputs

    assert callable(load_config)
    assert callable(parse_standard_outputs)
    assert callable(new_build_plan)
