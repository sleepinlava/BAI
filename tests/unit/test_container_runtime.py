"""Unit tests for container image resolution and command wrapping (Phase 2)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


from abi.tools import (
    _resolve_container_runtime,
    _wrap_container_command,
    container_image_identities,
    resolve_container_image,
    validate_container_images_ready,
)


class TestResolveContainerImage:
    """Layered container image resolution."""

    def test_returns_none_when_nothing_set(self):
        img = resolve_container_image("fastp", {})
        assert img is None

    def test_flat_metadata_container_image(self):
        img = resolve_container_image("fastp", {"container_image": "docker://test:v1"})
        assert img == "docker://test:v1"

    def test_execution_block_container_image(self):
        img = resolve_container_image(
            "fastp",
            {"execution": {"container_image": "docker://biocontainers/fastp:v0.23"}},
        )
        assert img == "docker://biocontainers/fastp:v0.23"

    def test_config_default_image_overrides_contract(self):
        img = resolve_container_image(
            "fastp",
            {"container_image": "docker://old:v1"},
            config={"execution": {"container": {"default_image": "docker://new:v2"}}},
        )
        assert img == "docker://new:v2"

    def test_config_per_tool_image_overrides_default(self):
        img = resolve_container_image(
            "spades",
            {"container_image": "docker://old:v1"},
            config={
                "execution": {
                    "container": {
                        "default_image": "docker://default:v2",
                        "tool_images": {"spades": "docker://spades:v4"},
                    }
                }
            },
        )
        assert img == "docker://spades:v4"

    def test_cli_image_highest_priority(self):
        img = resolve_container_image(
            "fastp",
            {"container_image": "docker://old:v1"},
            config={"execution": {"container": {"default_image": "docker://cfg:v2"}}},
            cli_image="docker://cli:v3",
        )
        assert img == "docker://cli:v3"

    def test_cli_none_uses_config(self):
        img = resolve_container_image(
            "fastp",
            {},
            config={"execution": {"container": {"default_image": "docker://cfg:v2"}}},
            cli_image=None,
        )
        assert img == "docker://cfg:v2"


class TestContainerCommandWrapping:
    """Container command wrapping for docker/singularity."""

    def test_docker_wrap_basic(self):
        cmd = _wrap_container_command(
            ["fastp", "-i", "input.fq"],
            image="docker://biocontainers/fastp:v1",
            runtime="docker",
        )
        assert "docker" == cmd[0]
        assert "run" in cmd
        assert "docker://biocontainers/fastp:v1" in cmd
        assert "fastp" in cmd

    def test_docker_includes_cpu_memory(self):
        cmd = _wrap_container_command(
            ["fastp"],
            image="img:v1",
            runtime="docker",
            cpu=4,
            memory="8GB",
        )
        assert "--cpus" in cmd
        assert "4" in cmd
        assert "--memory" in cmd
        assert "8GB" in cmd

    def test_singularity_wrap_basic(self):
        cmd = _wrap_container_command(
            ["fastp", "-i", "input.fq"],
            image="docker://biocontainers/fastp:v1",
            runtime="singularity",
        )
        assert "singularity" == cmd[0]
        assert "exec" in cmd
        assert "--bind" in cmd
        assert "docker://biocontainers/fastp:v1" in cmd

    def test_apptainer_is_same_as_singularity(self):
        cmd = _wrap_container_command(
            ["fastp"],
            image="img:v1",
            runtime="apptainer",
        )
        assert cmd[0] == "apptainer"
        assert "exec" in cmd

    def test_bind_mounts_work_dir(self):
        cmd = _wrap_container_command(
            ["fastp"],
            image="img:v1",
            work_dir="/data/results",
            runtime="singularity",
        )
        assert "/data/results:/data/results" in " ".join(cmd)

    def test_docker_volume_mount(self):
        cmd = _wrap_container_command(
            ["fastp"],
            image="img:v1",
            work_dir="/data/results",
            runtime="docker",
        )
        assert "-v" in cmd
        assert "/data/results:/data/results" in " ".join(cmd)


class TestResolveContainerRuntime:
    """Container runtime resolution from env/config/auto-detect."""

    def test_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv("ABI_CONTAINER_RUNTIME", "singularity")
        assert _resolve_container_runtime() == "singularity"

    def test_falls_back_to_docker(self, monkeypatch):
        monkeypatch.delenv("ABI_CONTAINER_RUNTIME", raising=False)
        runtime = _resolve_container_runtime({})
        assert runtime in ("docker", "podman", "singularity", "apptainer")


class TestContainerReadiness:
    def _plan(self):
        return SimpleNamespace(
            steps=[SimpleNamespace(step_id="s1", tool_id="fastp")],
            selected_tools=["fastp"],
        )

    class _Registry:
        def has(self, tool_id):
            return tool_id == "fastp"

        def get(self, tool_id):
            return {"container_image": "docker://example/fastp:1"}

    def test_missing_local_docker_image_fails_without_pull(self, monkeypatch):
        calls = []
        monkeypatch.setattr("abi.tools.shutil.which", lambda name: "/usr/bin/docker")

        def runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=1, stderr="No such image", stdout="")

        import pytest

        with pytest.raises(RuntimeError, match="will not pull"):
            validate_container_images_ready(
                self._plan(),
                self._Registry(),
                runtime="docker",
                runner=runner,
            )
        assert calls == [["docker", "image", "inspect", "example/fastp:1"]]
        assert all("pull" not in command for command in calls[0])

    def test_ready_image_is_inspected_before_backend(self, monkeypatch):
        calls = []
        monkeypatch.setattr("abi.tools.shutil.which", lambda name: "/usr/bin/docker")

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(
                returncode=0,
                stderr="",
                stdout='[{"Id": "sha256:local-image"}]',
            )

        validate_container_images_ready(
            self._plan(),
            self._Registry(),
            runtime="docker",
            runner=runner,
        )
        assert calls[0][0] == ["docker", "image", "inspect", "example/fastp:1"]
        assert calls[0][1]["check"] is False

    def test_image_identity_records_local_digest_without_pull(self, monkeypatch):
        monkeypatch.setattr("abi.tools.shutil.which", lambda name: "/usr/bin/docker")

        def runner(command, **kwargs):
            assert command == ["docker", "image", "inspect", "example/fastp:1"]
            return SimpleNamespace(
                returncode=0,
                stderr="",
                stdout='[{"Id": "sha256:local-image"}]',
            )

        rows = container_image_identities(
            self._plan(),
            self._Registry(),
            runtime="docker",
            runner=runner,
        )

        assert rows == [
            {
                "tool_id": "fastp",
                "image": "docker://example/fastp:1",
                "runtime": "docker",
                "digest": "sha256:local-image",
            }
        ]

    def test_singularity_requires_prepared_local_file(self, monkeypatch):
        monkeypatch.setattr("abi.tools.shutil.which", lambda name: "/usr/bin/apptainer")
        import pytest

        with pytest.raises(RuntimeError, match="local file"):
            validate_container_images_ready(
                self._plan(),
                self._Registry(),
                runtime="apptainer",
                runner=lambda *args, **kwargs: SimpleNamespace(returncode=0),
            )
