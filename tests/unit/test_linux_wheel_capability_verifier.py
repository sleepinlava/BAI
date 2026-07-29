from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "verify_linux_wheel_capabilities.py"


def _reports(tmp_path: Path) -> tuple[Path, Path]:
    support = yaml.safe_load((ROOT / "environments.yaml").read_text(encoding="utf-8"))[
        "platform_support"
    ]
    discover = tmp_path / "discover.json"
    discover.write_text(
        json.dumps(
            {
                "platform": {
                    "system": "Linux",
                    "normalized_architecture": "x86_64",
                },
                "support": support,
            }
        ),
        encoding="utf-8",
    )
    doctor = tmp_path / "doctor.json"
    doctor.write_text(
        json.dumps(
            {
                "plugin": {
                    "analysis_type": "viral_viwrap",
                    "architecture": "x86_64",
                    "status": "unsupported",
                },
                "issues": ["unsupported_plugin:viral_viwrap:x86_64"],
                "healthy": False,
            }
        ),
        encoding="utf-8",
    )
    return discover, doctor


def _fake_abi(tmp_path: Path) -> Path:
    executable = tmp_path / "bin" / "abi"
    executable.parent.mkdir()
    executable.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'if [ "${2:-}" = "discover" ]; then\n'
        '  /bin/cat "$ABI_TEST_DISCOVER_REPORT"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "${2:-}" = "doctor" ]; then\n'
        '  /bin/cat "$ABI_TEST_DOCTOR_REPORT"\n'
        "  exit 1\n"
        "fi\n"
        "exit 97\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _run_verifier(
    tmp_path: Path,
    discover: Path,
    doctor: Path,
) -> subprocess.CompletedProcess[str]:
    output = tmp_path / "capability.json"
    environ = {
        **os.environ,
        "ABI_TEST_DISCOVER_REPORT": str(discover),
        "ABI_TEST_DOCTOR_REPORT": str(doctor),
    }
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--abi",
            str(_fake_abi(tmp_path)),
            "--mamba-root",
            str(tmp_path / "mamba"),
            "--architecture",
            "x86_64",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environ,
    )


def test_verifier_accepts_complete_matrix_and_fail_closed_doctor_report(
    tmp_path: Path,
) -> None:
    discover, doctor = _reports(tmp_path)

    completed = _run_verifier(tmp_path, discover, doctor)

    assert completed.returncode == 0, completed.stderr
    assert "21 environments" in completed.stdout
    assert (
        json.loads((tmp_path / "capability.json").read_text(encoding="utf-8"))["support"][
            "active_os"
        ]
        == "linux"
    )


def test_verifier_rejects_malformed_architecture_cell(tmp_path: Path) -> None:
    discover, doctor = _reports(tmp_path)
    payload = json.loads(discover.read_text(encoding="utf-8"))
    del payload["support"]["environments"]["wgs"]["aarch64"]
    discover.write_text(json.dumps(payload), encoding="utf-8")

    completed = _run_verifier(tmp_path, discover, doctor)

    assert completed.returncode == 1
    assert "wgs architectures" in completed.stderr
