"""Unit tests for structured recovery actions on DiagnosticHint (Phase 5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))


from abi.agent.envelopes import error_envelope, json_dumps
from abi.contracts.step_contract import ContractViolation, ContractViolationError
from abi.diagnostics import (
    _RECOVERY_BY_CODE,
    ERROR_CODES,
    RECOVERY_ACTIONS,
    DiagnosticHint,
    RecoveryAction,
    classify_exception,
)

# The intended recovery mapping, asserted in full so any accidental drift
# from the data-driven table in diagnostics.py fails loudly.
# 预期映射表, 与 diagnostics.py 中的 _RECOVERY_BY_CODE 全量比对。
EXPECTED_RECOVERY = {
    "unknown_analysis_type": ("fix_input", "abi_list_types"),
    "runtime_not_supported": ("fix_input", "abi_run"),
    "missing_input": ("fix_input", "abi_plan"),
    "artifact_missing": ("fix_input", "abi_plan"),
    "missing_resource": ("install_resource", "abi_check"),
    "missing_database": ("install_resource", "abi_check"),
    "tool_not_found": ("install_resource", "abi_check"),
    "permission_required": ("request_authorization", "abi_run"),
    "nonzero_exit": ("resume", "abi_run"),
    "invalid_config": ("do_not_retry", "abi_plan"),
    "invalid_sample_sheet": ("do_not_retry", "abi_plan"),
    "missing_sample_id": ("do_not_retry", "abi_plan"),
    "duplicate_sample_id": ("do_not_retry", "abi_plan"),
    "incomplete_pairs": ("do_not_retry", "abi_plan"),
    "invalid_platform": ("do_not_retry", "abi_plan"),
    "parse_failed": ("do_not_retry", "abi_inspect"),
    "empty_result": ("do_not_retry", "abi_inspect"),
    "contract_violation": ("do_not_retry", "abi_inspect"),
    "internal_error": ("do_not_retry", "abi_inspect"),
}


class TestRecoveryMapping:
    def test_every_error_code_has_a_recovery_mapping(self):
        assert set(_RECOVERY_BY_CODE) == ERROR_CODES

    def test_mapping_actions_are_valid_recovery_actions(self):
        for code, (action, api_call, params) in _RECOVERY_BY_CODE.items():
            assert action in RECOVERY_ACTIONS, code
            assert isinstance(api_call, str) and api_call.startswith("abi_"), code
            assert isinstance(params, dict), code

    def test_mapping_matches_expected_table(self):
        actual = {
            code: (action, api_call) for code, (action, api_call, _) in _RECOVERY_BY_CODE.items()
        }
        assert actual == EXPECTED_RECOVERY

    def test_do_not_retry_codes_never_carry_retry_or_resume(self):
        retryable = {"retry", "resume"}
        for code, (action, _, _) in _RECOVERY_BY_CODE.items():
            if code in EXPECTED_RECOVERY and EXPECTED_RECOVERY[code][0] == "do_not_retry":
                assert action not in retryable, code


class TestClassifiedRecovery:
    def _recovery(self, exc: Exception, command: str = "run"):
        code, hints = classify_exception(exc, command=command)
        assert len(hints) == 1
        return code, hints[0]

    def test_missing_input_maps_to_fix_input(self):
        code, hint = self._recovery(ValueError("Input file does not exist: /data/R1.fq"))
        assert code == "missing_input"
        assert hint["recovery"] == {"action": "fix_input", "api_call": "abi_plan", "params": {}}

    def test_missing_resource_maps_to_install_resource(self):
        code, hint = self._recovery(ValueError("Resource NOT_CONFIGURED: genome_index"))
        assert code == "missing_resource"
        assert hint["recovery"]["action"] == "install_resource"

    def test_tool_not_found_maps_to_install_resource(self):
        exc = RuntimeError("executable 'fastp' was not found in /path/bin or PATH")
        code, hint = self._recovery(exc)
        assert code == "tool_not_found"
        assert hint["recovery"]["action"] == "install_resource"

    def test_nonzero_exit_maps_to_resume(self):
        code, hint = self._recovery(RuntimeError("command failed with nonzero return code 1"))
        assert code == "nonzero_exit"
        assert hint["recovery"] == {"action": "resume", "api_call": "abi_run", "params": {}}

    def test_permission_required_maps_to_request_authorization(self):
        code, hint = self._recovery(RuntimeError("Execution requires explicit confirmation"))
        assert code == "permission_required"
        assert hint["recovery"] == {
            "action": "request_authorization",
            "api_call": "abi_run",
            "params": {"confirm_execution": True},
        }

    def test_contract_violation_maps_to_do_not_retry(self):
        exc = ContractViolationError(
            "step_1",
            [ContractViolation(check="file_exists", detail="missing output", path="out.bam")],
        )
        code, hint = self._recovery(exc)
        assert code == "contract_violation"
        assert hint["recovery"]["action"] == "do_not_retry"

    def test_sample_sheet_classes_are_do_not_retry(self):
        cases = {
            "Row 2: missing sample_id": "missing_sample_id",
            "Row 3: duplicate sample_id 'S1'": "duplicate_sample_id",
            "Row 2: incomplete FASTQ pair": "incomplete_pairs",
            "Row 2: invalid platform 'bad'": "invalid_platform",
            "The sample sheet has wrong columns": "invalid_sample_sheet",
        }
        for message, expected_code in cases.items():
            code, hint = self._recovery(ValueError(message), command="plan")
            assert code == expected_code
            assert hint["recovery"]["action"] == "do_not_retry"
            assert hint["recovery"]["action"] not in {"retry", "resume"}

    def test_internal_error_maps_to_do_not_retry(self):
        code, hint = self._recovery(RuntimeError("Something completely unexpected happened!"))
        assert code == "internal_error"
        assert hint["recovery"]["action"] == "do_not_retry"

    def test_suggested_next_action_is_preserved(self):
        _, hint = self._recovery(ValueError("Input file does not exist: /data/R1.fq"))
        assert "rerun plan or dry-run" in hint["suggested_next_action"]


class TestRecoverySerialization:
    def test_envelope_json_includes_structured_recovery(self):
        exc = ValueError("Input file does not exist: /data/R1.fq")
        error_code, hints = classify_exception(exc, command="plan")
        payload = json.loads(
            json_dumps(
                error_envelope(
                    "plan",
                    error=str(exc),
                    error_type="ValueError",
                    error_code=error_code,
                    diagnostic_hints=hints,
                )
            )
        )
        recovery = payload["diagnostic_hints"][0]["recovery"]
        assert recovery["action"] == "fix_input"
        assert recovery["api_call"] == "abi_plan"
        assert recovery["params"] == {}

    def test_recovery_action_to_dict_shape(self):
        action = RecoveryAction(action="retry", api_call="abi_run", params={"attempt": 2})
        assert action.to_dict() == {
            "action": "retry",
            "api_call": "abi_run",
            "params": {"attempt": 2},
        }

    def test_hint_without_recovery_omits_the_field(self):
        # Backward compatibility: consumers that never set recovery must not
        # see a new key in the serialized hint.
        hint = DiagnosticHint(
            severity="error",
            code="missing_input",
            message="Missing input",
            suggested_next_action="Check paths",
        )
        d = hint.to_dict()
        assert hint.recovery is None
        assert "recovery" not in d

    def test_hint_with_recovery_serializes_nested_block(self):
        hint = DiagnosticHint(
            severity="error",
            code="permission_required",
            message="Needs confirmation",
            suggested_next_action="Ask the user",
            recovery=RecoveryAction(
                action="request_authorization",
                api_call="abi_run",
                params={"confirm_execution": True},
            ),
        )
        d = hint.to_dict()
        assert d["recovery"] == {
            "action": "request_authorization",
            "api_call": "abi_run",
            "params": {"confirm_execution": True},
        }
        # Must survive a JSON round-trip unchanged.
        assert json.loads(json.dumps(d)) == d
