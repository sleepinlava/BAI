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


def test_bundled_script_inputs_resolve_from_plugin_packages(tmp_path, monkeypatch):
    from abi.plugin_registry import get_plugin

    monkeypatch.chdir(tmp_path)
    samples = tmp_path / "samples.tsv"
    samples.write_text(
        "sample_id\tplatform\tread1\tread2\tgroup\tcondition\n"
        + "".join(
            f"S{i}\tillumina\t/data/S{i}_R1.fastq\t/data/S{i}_R2.fastq\t{group}\t{group}\n"
            for i, group in enumerate(["A", "A", "A", "B", "B", "B"])
        )
    )
    for plugin_id, expected in {
        "rnaseq_expression": {"build_count_matrix.py", "run_deseq2.R", "run_enrichment.py"},
        "metagenomic_plasmid": {"deseq2_plasmid.R"},
    }.items():
        plugin = get_plugin(plugin_id)
        config = plugin.load_config(
            None,
            overrides={
                "input": {"sample_sheet": str(samples)},
                "outdir": str(tmp_path / plugin_id),
                "enrichment": {"enabled": True},
                "resources": {
                    key: str(tmp_path / key)
                    for key in ("annotation_gtf", "go_obo", "go_gaf", "reactome_gmt")
                },
                "sample_analysis": {"run_differential_deseq2": True},
            },
        )
        plan = plugin.build_plan(config, check_files=False)
        paths = [
            Path(value)
            for step in plan.steps
            for key, value in step.inputs.items()
            if key.endswith("_script") and value
        ]
        bundled = [path for path in paths if path.name in expected]
        assert {path.name for path in bundled} == expected
        assert all(path.is_absolute() and path.is_file() for path in bundled)
        assert all(path.parent == plugin.root / "scripts" for path in bundled)
