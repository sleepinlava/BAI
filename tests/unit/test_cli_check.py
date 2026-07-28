"""Unit tests for abi.contracts.cli_check (opt-in --check-cli template check)."""

from __future__ import annotations

import subprocess

from abi.contracts import cli_check
from abi.contracts.cli_check import (
    check_cli_flags,
    extract_template_flags,
    parse_help_flags,
)
from abi.tools import ToolRegistry

SCAPP_HELP = """\
SCAPP: Sequence Contents-Aware Plasmid Peeling
Usage: scapp [options]

options:
  -g, --graph GRAPH       assembly graph file
  -o, --out OUTDIR        output directory
  -r1 READS1              paired-end reads file 1
  -r2 READS2              paired-end reads file 2
  -k INT                  k-mer size
"""

FEATURECOUNTS_HELP = """\
featureCounts: a universal read summarization program
Usage: featureCounts [options] -a <annotation_file> -o <output_file> input_file1 [input_file2] ...

  -a <string>         Name of an annotation file
  -o <string>         Name of the output file
  -T <int>            Number of threads
  -p                  Check validity of paired-end distance
  --countReadPairs    Count read pairs
"""


def _registry(tools: list[dict]) -> ToolRegistry:
    return ToolRegistry(tools, environments_path=None, plugin_name="_default")


def _tool(tool_id: str, template: str, executable: str | None = None) -> dict:
    meta = {"id": tool_id, "command_template": template}
    if executable:
        meta["executable"] = executable
    return meta


class _FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_run(monkeypatch, behavior) -> list[list[str]]:
    """Patch subprocess.run inside cli_check; behavior(cmd) -> _FakeProc or raises."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return behavior(cmd)

    monkeypatch.setattr(cli_check.subprocess, "run", fake_run)
    return calls


def _patch_resolve(monkeypatch, mapping: dict[str, str | None]) -> None:
    monkeypatch.setattr(cli_check, "resolve_executable", lambda skill: mapping.get(skill.name))


# ── extract_template_flags ────────────────────────────────────────────────


def test_extract_simple_template_flags():
    template = "scapp -g {graph} -o {output_dir} -r1 {read1} -r2 {read2} -k {kmer}"
    assert extract_template_flags(template) == {"-g", "-o", "-r1", "-r2", "-k"}


def test_extract_long_flags_and_equals_suffix():
    template = "tool --threads={threads} --output {out} --verbose"
    assert extract_template_flags(template) == {"--threads", "--output", "--verbose"}


def test_extract_skips_fields_and_positionals():
    template = "tool -x {value} $1 plain {field} -1"
    assert extract_template_flags(template) == {"-x"}


def test_extract_sh_c_wrapper_uses_inner_script_only():
    template = (
        'sh -c \'tmp="$3.stderr.tmp"; if featureCounts -T "$1" -p --countReadPairs '
        '-a "$2" -o "$3" "$4" 2>"$tmp"; then cat "$tmp" >&2; fi\' '
        "featurecounts {threads} {annotation_gtf} {counts} {bam}"
    )
    flags = extract_template_flags(template)
    # Inner script flags are extracted …
    assert {"-T", "-p", "--countReadPairs", "-a", "-o"} <= flags
    # … while the wrapper's own -c (belongs to sh) and $1-style params are not.
    assert "-c" not in flags
    assert "$1" not in flags


# ── parse_help_flags ──────────────────────────────────────────────────────


def test_parse_help_flags():
    flags = parse_help_flags(SCAPP_HELP)
    assert {"-g", "--graph", "-o", "--out", "-r1", "-r2", "-k"} <= flags


# ── check_cli_flags ───────────────────────────────────────────────────────


def test_flags_present_in_help_pass(monkeypatch):
    registry = _registry([_tool("scapp", "scapp -g {graph} -o {out} -r1 {r1} -r2 {r2}")])
    _patch_resolve(monkeypatch, {"scapp": "/fake/env/bin/scapp"})
    _patch_run(monkeypatch, lambda cmd: _FakeProc(stdout=SCAPP_HELP))

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert skipped == []


def test_missing_flag_yields_cli_flag_mismatch(monkeypatch):
    registry = _registry([_tool("scapp", "scapp --contigs {graph} -o {out}")])
    _patch_resolve(monkeypatch, {"scapp": "/fake/env/bin/scapp"})
    _patch_run(monkeypatch, lambda cmd: _FakeProc(stdout=SCAPP_HELP))

    findings, skipped = check_cli_flags(registry)
    assert skipped == []
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "error"
    assert finding.check == "cli_flag_mismatch"
    assert "--contigs" in finding.detail
    assert "scapp" in finding.detail


def test_unresolvable_executable_is_skipped_without_finding(monkeypatch):
    registry = _registry([_tool("scapp", "scapp -g {graph}")])
    _patch_resolve(monkeypatch, {"scapp": None})

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert len(skipped) == 1
    assert skipped[0].tool_id == "scapp"
    assert "not found" in skipped[0].reason


def test_sh_c_wrapper_flags_checked_against_tool_help(monkeypatch):
    template = (
        'sh -c \'if featureCounts -T "$1" -p --countReadPairs -a "$2" -o "$3" '
        '"$4"; then exit 0; fi\' featurecounts {threads} {annotation_gtf} {counts} {bam}'
    )
    registry = _registry([_tool("featurecounts", template, executable="featureCounts")])
    _patch_resolve(monkeypatch, {"featurecounts": "/fake/env/bin/featureCounts"})
    _patch_run(monkeypatch, lambda cmd: _FakeProc(stdout=FEATURECOUNTS_HELP))

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert skipped == []


def test_sh_c_wrapper_inner_missing_flag_errors(monkeypatch):
    template = (
        'sh -c \'featureCounts -T "$1" --bogus-inner-flag -a "$2" -o "$3" "$4"\' '
        "featurecounts {threads} {annotation_gtf} {counts} {bam}"
    )
    registry = _registry([_tool("featurecounts", template, executable="featureCounts")])
    _patch_resolve(monkeypatch, {"featurecounts": "/fake/env/bin/featureCounts"})
    _patch_run(monkeypatch, lambda cmd: _FakeProc(stdout=FEATURECOUNTS_HELP))

    findings, _ = check_cli_flags(registry)
    assert len(findings) == 1
    assert findings[0].check == "cli_flag_mismatch"
    assert "--bogus-inner-flag" in findings[0].detail


def test_timeout_on_help_falls_back_to_short_h(monkeypatch):
    registry = _registry([_tool("scapp", "scapp -g {graph} -o {out}")])
    _patch_resolve(monkeypatch, {"scapp": "/fake/env/bin/scapp"})

    def behavior(cmd):
        if cmd[-1] == "--help":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)
        return _FakeProc(stdout=SCAPP_HELP)

    calls = _patch_run(monkeypatch, behavior)

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert skipped == []
    # --help was attempted first, then -h.
    assert calls[0][-1] == "--help"
    assert calls[1][-1] == "-h"


def test_timeout_on_both_help_flags_is_skipped(monkeypatch):
    registry = _registry([_tool("scapp", "scapp -g {graph}")])
    _patch_resolve(monkeypatch, {"scapp": "/fake/env/bin/scapp"})

    def behavior(cmd):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    _patch_run(monkeypatch, behavior)

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert len(skipped) == 1
    assert "--help" in skipped[0].reason


def test_help_output_cached_per_executable(monkeypatch):
    tools = [
        _tool("tool_a", "tool -g {graph}", executable="shared"),
        _tool("tool_b", "tool -o {out}", executable="shared"),
    ]
    registry = _registry(tools)
    monkeypatch.setattr(cli_check, "resolve_executable", lambda skill: "/fake/bin/shared")
    calls = _patch_run(monkeypatch, lambda cmd: _FakeProc(stdout=SCAPP_HELP))

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert skipped == []
    assert len(calls) == 1  # second tool reuses the cached help output


def test_tool_without_command_template_is_skipped(monkeypatch):
    registry = _registry([{"id": "notmpl"}])
    monkeypatch.setattr(cli_check, "resolve_executable", lambda skill: "/fake/bin/notmpl")

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert len(skipped) == 1
    assert "command_template" in skipped[0].reason


SCRIPT_HELP = """\
usage: script.py [-h] --input INPUT --output OUTPUT

options:
  -h, --help        show this help message and exit
  --input INPUT     input file
  --output OUTPUT   output file
"""


def test_python_script_wrapper_checks_script_help(monkeypatch):
    template = "python /fake/scripts/tool.py --input {infile} --output {outfile}"
    registry = _registry([_tool("pytool", template, executable="python")])
    monkeypatch.setattr(cli_check, "resolve_executable", lambda skill: "/usr/bin/python")
    calls = _patch_run(monkeypatch, lambda cmd: _FakeProc(stdout=SCRIPT_HELP))

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert skipped == []
    assert calls == [["/usr/bin/python", "/fake/scripts/tool.py", "--help"]]


def test_python_script_wrapper_missing_flag_errors(monkeypatch):
    template = "python /fake/scripts/tool.py --input {infile} --bogus {x}"
    registry = _registry([_tool("pytool", template, executable="python")])
    monkeypatch.setattr(cli_check, "resolve_executable", lambda skill: "/usr/bin/python")
    _patch_run(monkeypatch, lambda cmd: _FakeProc(stdout=SCRIPT_HELP))

    findings, skipped = check_cli_flags(registry)
    assert skipped == []
    assert len(findings) == 1
    assert findings[0].check == "cli_flag_mismatch"
    assert "--bogus" in findings[0].detail
    assert "tool.py --help" in findings[0].detail


def test_script_wrapper_with_nonliteral_path_is_skipped(monkeypatch):
    template = "python {script} --input {infile} --output {outfile}"
    registry = _registry([_tool("pytool", template, executable="python")])
    monkeypatch.setattr(cli_check, "resolve_executable", lambda skill: "/usr/bin/python")

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert len(skipped) == 1
    assert skipped[0].reason == "script wrapper with non-literal script path"


def test_abi_subcommand_wrapper_checks_subcommand_help(monkeypatch):
    template = "abi report --result-dir {result_dir} --type {type}"
    abi_help = (
        "usage: abi report [-h] --result-dir DIR --type TYPE\n\n  --result-dir DIR\n  --type TYPE\n"
    )
    registry = _registry([_tool("report_markdown", template, executable="abi")])
    monkeypatch.setattr(cli_check, "resolve_executable", lambda skill: "/fake/bin/abi")
    calls = _patch_run(monkeypatch, lambda cmd: _FakeProc(stdout=abi_help))

    findings, skipped = check_cli_flags(registry)
    assert findings == []
    assert skipped == []
    assert ["/fake/bin/abi", "report", "--help"] in calls


def test_help_cache_key_includes_script_path(monkeypatch):
    template_a = "python /fake/scripts/a.py --input {infile}"
    template_b = "python /fake/scripts/b.py --input {infile}"
    registry = _registry(
        [
            _tool("tool_a", template_a, executable="python"),
            _tool("tool_b", template_b, executable="python"),
        ]
    )
    monkeypatch.setattr(cli_check, "resolve_executable", lambda skill: "/usr/bin/python")
    calls = _patch_run(
        monkeypatch,
        lambda cmd: _FakeProc(stdout="" if any("b.py" in str(x) for x in cmd) else SCRIPT_HELP),
    )

    findings, skipped = check_cli_flags(registry)
    # tool_a passes; tool_b fails because the mocked b.py help is empty,
    # proving the cache key is not just the executable.
    assert len(findings) == 0
    assert len(skipped) == 1
    assert skipped[0].tool_id == "tool_b"
    assert len(calls) == 3  # a.py --help, b.py --help, b.py -h fallback
