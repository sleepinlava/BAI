from __future__ import annotations

import io
import tarfile
from zipfile import ZipFile

import pytest

from scripts.verify_install_forms import InstallFormError
from scripts.verify_release_artifacts import verify_release


@pytest.fixture
def distributions(tmp_path):
    for name in ["abi-agent"]:
        stem = f"{name.replace('-', '_')}-1.7.0"
        with ZipFile(tmp_path / f"{stem}-py3-none-any.whl", "w") as archive:
            archive.writestr(
                f"{stem}.dist-info/METADATA",
                f"Name: {name}\nVersion: 1.7.0\n",
            )
    with tarfile.open(tmp_path / "abi_agent-1.7.0.tar.gz", "w:gz") as archive:
        data = b"Name: abi-agent\nVersion: 1.7.0\n"
        info = tarfile.TarInfo("abi_agent-1.7.0/PKG-INFO")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    return tmp_path


def test_release_round_trip_and_manifest_is_immutable(distributions):
    verify_release(distributions, "1.7.0", write_manifest=True)
    verify_release(distributions, "1.7.0")
    with pytest.raises(FileExistsError):
        verify_release(distributions, "1.7.0", write_manifest=True)


@pytest.mark.parametrize("mutation", ["missing", "extra", "version", "bytes", "plugin"])
def test_release_rejects_changed_artifact_set(distributions, mutation):
    verify_release(distributions, "1.7.0", write_manifest=True)
    wheel = distributions / "abi_agent-1.7.0-py3-none-any.whl"
    if mutation == "missing":
        wheel.unlink()
    elif mutation == "extra":
        (distributions / "unexpected.whl").write_bytes(wheel.read_bytes())
    elif mutation == "version":
        with ZipFile(wheel, "w") as archive:
            archive.writestr(
                "demo.dist-info/METADATA",
                "Name: abi-agent\nVersion: 1.6.0\n",
            )
    elif mutation == "plugin":
        (distributions / "abi_agent_plugin_amplicon_16s-1.7.0-py3-none-any.whl").write_bytes(
            wheel.read_bytes()
        )
    else:
        with ZipFile(wheel, "a") as archive:
            archive.writestr("changed.py", "unexpected bytes")
    with pytest.raises(InstallFormError):
        verify_release(distributions, "1.7.0")
