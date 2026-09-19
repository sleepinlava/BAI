"""Local ABI runtime backed by GenericABIExecutor."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Mapping

from abi.executor import GenericABIExecutor
from abi.internal import plugin_internal_handlers, run_plugin_preflight
from abi.provenance import RunLogger
from abi.runtimes.base import RuntimeOptions, RuntimeResult
from abi.schemas import ABIError
from abi.tables import StandardTableManager
from abi.tools import validate_container_images_ready

_LOGGER = logging.getLogger(__name__)


def _skip_preflight_requested() -> bool:
    """Honor an explicit opt-in bypass of the resource/runtime preflight.

    Some plugins (e.g. autoplasm) register resources for every supported tool
    regardless of which stages are enabled in the user config, which makes the
    default preflight over-report.  Setting ``ABI_SKIP_PREFLIGHT=1`` lets an
    operator who has manually verified the enabled tools bypass the gate while
    still running real tools.  Default behavior is unchanged.
    """
    return os.environ.get("ABI_SKIP_PREFLIGHT", "").strip().lower() in {"1", "true", "yes", "on"}


def _coerce_bool(value: Any) -> bool:
    """Coerce a config value to bool, handling string representations.

    ``bool("false") == True`` in Python, so we need explicit handling for
    common string falsy values from env vars and YAML string substitution.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "0", "no", "off", "none"}
    return bool(value)


class LocalRuntime:
    """Run ABI plans through the existing local GenericABIExecutor."""

    def __init__(self, plugin: Any, *, options: RuntimeOptions | None = None) -> None:
        self.plugin = plugin
        self.options = options or RuntimeOptions(engine="local")

    def check(self) -> None:
        return None

    def dry_run(self, plan: object, config: Mapping[str, object]) -> RuntimeResult:
        return self._run(plan, config, dry_run=True)

    def run(self, plan: object, config: Mapping[str, object]) -> RuntimeResult:
        return self._run(plan, config, dry_run=False)

    def _run(
        self,
        plan: object,
        config: Mapping[str, object],
        *,
        dry_run: bool,
    ) -> RuntimeResult:
        mock_tools = dry_run or _coerce_bool(config.get("mock_tools"))
        if not mock_tools:
            validate_container_images_ready(
                plan,
                self.plugin.registry(),
                config=config,
                cli_image=self.options.container_image,
                runtime=self.options.container_runtime,
            )
        if not mock_tools and not _skip_preflight_requested():
            report = run_plugin_preflight(
                self.plugin,
                config,
                engine="local",
                check_runtime=self.options.check_runtime,
            )
            if str(report.get("status", "pass")) == "fail":
                raise ABIError(
                    f"{self.plugin.plugin_id} preflight failed: "
                    + "; ".join(str(item) for item in report.get("recommendations", []))
                )
        table_manager = StandardTableManager(self.plugin.table_schemas())
        executor = GenericABIExecutor(
            self.plugin.registry(),
            RunLogger(str(config.get("log_dir", ""))),
            table_manager=table_manager,
            parse_outputs=self.plugin.parse_outputs,
            report_title=self.plugin.report_title,
            mock_tools=mock_tools,
            internal_handlers=plugin_internal_handlers(self.plugin),
            run_tables_hook=getattr(self.plugin, "write_run_tables", None),
        )
        try:
            if self.options.container_image or self.options.container_runtime:
                outputs = executor.run(
                    plan,
                    config,
                    dry_run=dry_run,
                    resume=self.options.resume,
                    confirmed_plan_id=str(getattr(self.options, "confirmed_plan_id", "") or ""),
                    container_image=self.options.container_image,
                    container_runtime=self.options.container_runtime,
                )
            else:
                outputs = executor.run(
                    plan,
                    config,
                    dry_run=dry_run,
                    resume=self.options.resume,
                    confirmed_plan_id=str(getattr(self.options, "confirmed_plan_id", "") or ""),
                )
        except BaseException as execution_error:
            # Preserve the execution failure as the primary error.  If the
            # output directory was created but the audit artifact itself also
            # cannot be written, attach that fact to the same exception rather
            # than masking the actionable execution error.
            try:
                _write_audit_snapshot(self.plugin, config)
            except Exception as snapshot_error:  # noqa: BLE001
                message = f"Audit snapshot write failed: {snapshot_error}"
                add_note = getattr(execution_error, "add_note", None)
                if callable(add_note):
                    add_note(message)
                else:
                    _LOGGER.error(message)
            raise
        # Write after the executor has archived the previous run.  This keeps
        # the prior snapshot byte-identical in history and also records a
        # snapshot when execution fails after the output directory exists.
        _write_audit_snapshot(self.plugin, config)
        return RuntimeResult(status="success", return_code=0, outputs=dict(outputs))


def _write_audit_snapshot(plugin: Any, config: Mapping[str, object]) -> None:
    """Persist the WP5 audit snapshot after the run resets provenance.

    The snapshot is plugin-owned declaration (schemas, limitations,
    references), not run history; the next run archives it before replacing it.
    写入 WP5 审计快照。快照是插件声明（schema、局限性、引用）而非运行历史；
    下一轮运行会在替换前先归档它。
    """
    from abi.audit import write_audit_snapshot

    outdir = str(config.get("outdir") or "")
    if not outdir:
        return
    write_audit_snapshot(plugin, Path(outdir) / "provenance", strict=True)
