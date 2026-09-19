from __future__ import annotations

import subprocess
from zipfile import ZipFile

import pytest

from scripts.verify_install_forms import (
    InstallFormError,
    _json_result,
    validate_distribution_metadata,
)


def _wheel(path, *, name: str, version: str, requires: tuple[str, ...] = ()) -> None:
    dist_info = f"{name.replace('-', '_')}-{version}.dist-info"
    metadata = ["Metadata-Version: 2.4", f"Name: {name}", f"Version: {version}"]
    metadata.extend(f"Requires-Dist: {requirement}" for requirement in requires)
    with ZipFile(path, "w") as archive:
        archive.writestr(f"{dist_info}/METADATA", "\n".join(metadata) + "\n")


def test_validate_distribution_metadata_accepts_one_versioned_core_and_plugins(tmp_path):
    core = tmp_path / "abi_agent-1.6.0-py3-none-any.whl"
    plugin = tmp_path / "abi_agent_plugin_demo-1.6.0-py3-none-any.whl"
    _wheel(core, name="abi-agent", version="1.6.0")
    _wheel(
        plugin,
        name="abi-agent-plugin-demo",
        version="1.6.0",
        requires=("abi-agent==1.6.0",),
    )

    assert validate_distribution_metadata(core, {"abi-agent-plugin-demo": plugin}) == "1.6.0"


def test_validate_distribution_metadata_rejects_mismatched_plugin_version(tmp_path):
    core = tmp_path / "abi_agent-1.6.0-py3-none-any.whl"
    plugin = tmp_path / "abi_agent_plugin_demo-1.5.0-py3-none-any.whl"
    _wheel(core, name="abi-agent", version="1.6.0")
    _wheel(
        plugin,
        name="abi-agent-plugin-demo",
        version="1.5.0",
        requires=("abi-agent==1.5.0",),
    )

    with pytest.raises(InstallFormError, match="version mismatch"):
        validate_distribution_metadata(core, {"abi-agent-plugin-demo": plugin})


def test_json_result_rejects_failed_subprocess_and_non_envelope():
    failed = subprocess.CompletedProcess(["abi"], 1, stdout="failure", stderr="details")
    with pytest.raises(InstallFormError, match="inspect failed"):
        _json_result(failed, command="inspect")

    malformed = subprocess.CompletedProcess(["abi"], 0, stdout='{"status":"error"}', stderr="")
    with pytest.raises(InstallFormError, match="unsuccessful envelope"):
        _json_result(malformed, command="inspect")


def test_plugin_cannot_make_exact_core_dependency_conditional(tmp_path):
    core = tmp_path / "core.whl"
    plugin = tmp_path / "plugin.whl"
    _wheel(core, name="abi-agent", version="1.7.0")
    _wheel(
        plugin,
        name="abi-agent-plugin-demo",
        version="1.7.0",
        requires=('abi-agent==1.7.0; python_version < "3.0"',),
    )
    with pytest.raises(InstallFormError, match="must require"):
        validate_distribution_metadata(core, {"abi-agent-plugin-demo": plugin})
