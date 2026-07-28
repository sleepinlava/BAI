"""Opt-in CLI-level template check for ``abi contract-lint --check-cli``.

Unlike :mod:`abi.contracts.lint` — which is purely static and execution-free
by design — this module *does* invoke tool executables (``<exe> --help``) to
verify that every literal flag used by a tool's ``command_template`` is
actually advertised by the tool's own CLI.  It exists because a wrong
template (e.g. ``scapp --contigs ...`` instead of the real ``-g/-o/-r1/-r2``)
passes every static gate and only fails at execution time.

Design / 设计
--------------
- Invoked only via ``abi contract-lint --check-cli``; never imported by the
  static lint path.
- Executable resolution reuses the runtime machinery: ``ToolRegistry`` fills
  ``env_name`` from ``environments.yaml`` and ``ToolSkill``/``GenericCommandSkill``
  expose ``env_bin``/``extra_path_dirs()`` — the same search order as
  ``ToolSkill.check_installation()`` (env bin → extra path dirs → system PATH).
- Tools whose executable cannot be resolved (env not installed on this
  machine) are *not* findings; they are collected into a "skipped" list so
  ``--strict`` runs on machines without conda envs still pass.
- ``--help`` output is cached per resolved executable so tools sharing a
  binary are only probed once.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from abi.contracts.lint import LintFinding

__all__ = [
    "HELP_TIMEOUT_SECONDS",
    "SkippedTool",
    "check_cli_flags",
    "extract_template_flags",
    "parse_help_flags",
    "resolve_executable",
]

HELP_TIMEOUT_SECONDS = 10
"""Per-invocation timeout for ``<exe> --help`` / ``<exe> -h`` probes."""

# A literal CLI flag: ``-x`` or ``--long-flag`` (letter-leading; numeric short
# flags such as ``-1`` are intentionally excluded on both the template and the
# help side so they can never produce a false mismatch).
_FLAG_PATTERN = r"-{1,2}[A-Za-z][\w-]*"
_FLAG_FULL_RE = re.compile(rf"^(?:{_FLAG_PATTERN})$")
# In help text a flag token must start at a word boundary (start or whitespace)
# so hyphenated prose words like "short-read" are not mistaken for flags.
_HELP_FLAG_RE = re.compile(rf"(?<!\S)({_FLAG_PATTERN})")

# Shells whose ``-c`` wrapper scripts are parsed for inner flags.
_SH_WRAPPERS = {"sh", "bash", "/bin/sh", "/bin/bash"}

# Interpreters that pass flags through to a script/subcommand; for these we
# must probe ``<exe> <script> --help`` rather than ``<exe> --help``.
_SCRIPT_WRAPPERS = {"python", "python3", "Rscript", "abi"}


@dataclass
class SkippedTool:
    """A tool that could not be CLI-checked (informational, not a finding)."""

    tool_id: str
    executable: str
    env_name: str
    reason: str


def resolve_executable(skill: Any) -> Optional[str]:
    """Return the resolved path of *skill*'s executable, or None if not found.

    Mirrors the search order of ``ToolSkill.check_installation()``:
    absolute/directory-qualified paths are checked directly, then the conda
    env ``bin/``, then registry-declared ``extra_path_dirs``, then PATH.
    """
    executable = str(skill.executable)
    exe_path = Path(executable)
    if exe_path.is_absolute() or exe_path.parent != Path("."):
        return str(exe_path) if exe_path.exists() else None
    env_bin = Path(skill.env_bin)
    if env_bin.exists():
        found = shutil.which(executable, path=str(env_bin))
        if found:
            return found
    for directory in skill.extra_path_dirs():
        found = shutil.which(executable, path=str(directory))
        if found:
            return found
    return shutil.which(executable)


def parse_help_flags(help_text: str) -> Set[str]:
    """Extract the set of CLI flags advertised in ``--help`` output."""
    return set(_HELP_FLAG_RE.findall(help_text))


def _token_to_flag(token: str) -> Optional[str]:
    """Normalize a template token to a literal flag, or None if not a flag.

    Drops ``=value`` suffixes (``--opt=val`` → ``--opt``) and rejects tokens
    containing ``{fields}`` (non-literal) and non-flag shapes (``-``, ``-1``,
    ``$1``-style positionals never start with ``-`` so they pass through).
    """
    flag = token.split("=", 1)[0]
    if "{" in flag or "}" in flag:
        return None
    if _FLAG_FULL_RE.match(flag):
        return flag
    return None


def _inner_shell_scripts(tokens: List[str]) -> Optional[List[str]]:
    """Return the script bodies of ``sh -c '<script>'`` wrappers, if any.

    When a template wraps its real command in ``sh -c '...'`` (see the
    featureCounts entry in the RNA-seq registry), the wrapper's own tokens —
    including ``-c``, which belongs to ``sh``, not to the tool — are ignored
    and only the inner script's flags are checked against the tool's help.
    """
    scripts: List[str] = []
    for index, token in enumerate(tokens[:-2]):
        if token in _SH_WRAPPERS and tokens[index + 1] == "-c":
            scripts.append(tokens[index + 2])
    return scripts or None


def extract_template_flags(template: str) -> Set[str]:
    """Extract the literal flags used by a ``command_template``.

    Rules / 提取规则:
    1. The template is ``shlex``-split; tokens starting with ``-`` that are
       not ``{fields}`` and match ``-x``/``--long-flag`` are kept (``=value``
       suffixes are stripped first).
    2. Inside ``sh -c '<script>'`` wrappers only the *inner* script is parsed
       (the outer ``-c`` belongs to the shell; ``$1``-style positional
       parameters are not flags).
    """
    try:
        tokens = shlex.split(template)
    except ValueError:
        tokens = template.split()
    scripts = _inner_shell_scripts(tokens)
    if scripts is not None:
        tokens = []
        for script in scripts:
            try:
                tokens.extend(shlex.split(script))
            except ValueError:
                tokens.extend(script.split())
    flags: Set[str] = set()
    for token in tokens:
        flag = _token_to_flag(token)
        if flag is not None:
            flags.add(flag)
    return flags


def _resolve_help_target(executable_path: str, template: str) -> Optional[List[str]]:
    """Return the command to run for help output for *template*.

    For most tools this is ``[executable_path, --help]``.  For script wrappers
    such as ``python script.py --flags ...`` or ``abi subcommand --flags ...``,
    the flags belong to the script/subcommand, so we probe
    ``[executable_path, script, --help]`` instead.

    Returns None when the template is a wrapper but the script/subcommand
    cannot be determined statically (e.g. it contains a ``{field}``).
    """
    exe_name = Path(executable_path).name
    if exe_name not in _SCRIPT_WRAPPERS:
        return [executable_path, "--help"]
    try:
        tokens = shlex.split(template)
    except ValueError:
        tokens = template.split()
    # Skip the executable token itself.
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        if "{" in token or "}" in token:
            return None
        # The first literal positional is the script/subcommand.
        return [executable_path, token, "--help"]
    return None


def _probe_help(cmd: List[str]) -> Optional[str]:
    """Run *cmd* with ``--help`` (falling back to ``-h``) and return its output.

    Returns None when the tool cannot produce help text (non-zero exit on
    both flags, timeout, or OS error) — the caller treats that as "skipped".
    """
    base = cmd[:-1]
    for help_flag in ("--help", "-h"):
        try:
            proc = subprocess.run(
                base + [help_flag],
                capture_output=True,
                text=True,
                timeout=HELP_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if proc.returncode == 0 and output:
            return output
    return None


def check_cli_flags(registry: Any) -> Tuple[List[LintFinding], List[SkippedTool]]:
    """Check every registry tool's template flags against its ``--help`` output.

    Args:
        registry: A ``ToolRegistry`` (or compatible object offering
            ``list_tools()`` and ``create(tool_id)``).

    Returns:
        ``(findings, skipped)`` — findings are ``cli_flag_mismatch`` errors;
        skipped lists tools whose executable or help text was unavailable.
    """
    findings: List[LintFinding] = []
    skipped: List[SkippedTool] = []
    help_cache: Dict[Tuple[str, ...], Optional[str]] = {}

    for metadata in registry.list_tools():
        tool_id = str(metadata.get("id", ""))
        skill = registry.create(tool_id)
        executable = str(skill.executable)
        env_name = str(getattr(skill, "env_name", "") or metadata.get("env_name", ""))

        if not metadata.get("command_template"):
            skipped.append(
                SkippedTool(tool_id, executable, env_name, "no command_template declared")
            )
            continue

        exe_path = resolve_executable(skill)
        if exe_path is None:
            skipped.append(SkippedTool(tool_id, executable, env_name, "executable not found"))
            continue

        help_cmd = _resolve_help_target(exe_path, str(metadata["command_template"]))
        if help_cmd is None:
            skipped.append(
                SkippedTool(
                    tool_id,
                    executable,
                    env_name,
                    "script wrapper with non-literal script path",
                )
            )
            continue
        cache_key = tuple(help_cmd)
        if cache_key not in help_cache:
            help_cache[cache_key] = _probe_help(help_cmd)
        help_text = help_cache[cache_key]
        if help_text is None:
            skipped.append(SkippedTool(tool_id, executable, env_name, "no usable --help output"))
            continue

        available = parse_help_flags(help_text)
        for flag in sorted(extract_template_flags(str(metadata["command_template"]))):
            if flag not in available:
                findings.append(
                    LintFinding(
                        severity="error",
                        check="cli_flag_mismatch",
                        detail=(
                            f"Tool '{tool_id}' command_template uses flag '{flag}' "
                            f"which is not advertised by '{' '.join(help_cmd)}'. "
                            f"Fix the template to match the tool's real CLI."
                        ),
                        location=tool_id,
                    )
                )
    return findings, skipped
