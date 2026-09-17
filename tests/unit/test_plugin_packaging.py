"""Official distributions own the dependencies and assets they execute."""

from pathlib import Path

import tomlkit

from scripts.build_plugin_wheels import PLASMID_SCRIPTS, stage_plugin, write_pyproject


def test_rnaseq_distribution_declares_its_statistics_dependencies(tmp_path):
    write_pyproject(tmp_path, "rnaseq_expression", "RNASeqExpressionPlugin", "1.7.0")
    project = tomlkit.parse((tmp_path / "pyproject.toml").read_text())["project"]
    assert set(project["dependencies"]) == {
        "abi-agent==1.7.0",
        "numpy>=1.21",
        "pandas>=1.5",
        "scipy>=1.9",
    }


def test_plasmid_distribution_stages_executable_normalization_assets(tmp_path):
    stage_plugin("metagenomic_plasmid", tmp_path)
    write_pyproject(tmp_path, "metagenomic_plasmid", "MetagenomicPlasmidPlugin", "1.7.0")
    config = tomlkit.parse((tmp_path / "pyproject.toml").read_text())
    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"] == {
        "scripts": "scripts"
    }
    root = Path(__file__).resolve().parents[2]
    for name in PLASMID_SCRIPTS:
        assert (tmp_path / "scripts" / name).read_bytes() == (root / "scripts" / name).read_bytes()
