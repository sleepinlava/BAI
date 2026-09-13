"""Generic ABI report writer.

# Purpose / 目的
Produces three output files in a report/ subdirectory:
    report.md          — Markdown (human-readable, portable) / 人类可读的 Markdown
    report.html        — HTML (browser-friendly, styled) / 浏览器友好的 HTML
    report_summary.json — JSON (machine-readable, API-friendly) / 机器可读的 JSON

# Plugin usage / 插件用法
Plugins call write_generic_report() at the end of a pipeline run, passing the
plan object (for metadata like project name, analysis type, tool list) and the
table_summary from StandardTableManager.summarize() (for row counts per table).

# Design decisions / 设计决策
- **Three formats, one function**: Generating all three from a single call
  ensures consistency — the Markdown, HTML, and JSON all reflect the same data.
  / 一个调用生成三种格式确保一致性
- **Minimal dependencies**: No template engine is used. The HTML is built with
  string concatenation so there are zero dependencies beyond the stdlib.
  / 无模板引擎，零额外依赖
- **Escape early**: html.escape() is applied at generation time so plugins that
  later embed the HTML don't need to remember to escape. / 生成时转义 HTML
"""

from __future__ import annotations

import json
import logging
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from abi.report.limitations import FALLBACK_LIMITATION

__all__ = ["write_generic_report", "write_full_report", "write_plugin_report", "build_run_facts"]

_LOGGER = logging.getLogger(__name__)


def build_run_facts(
    command_rows: Any,
    run_summary: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Distill actual execution facts from command rows and the run summary.

    WP5 requires reports to record failed calls and reused steps explicitly —
    not just the plan tables. The returned mapping drives the report's
    "Execution Facts" section and stays honest when facts are missing.
    WP5 要求报告明确记录失败调用与步骤复用，而非只展示计划表。
    """
    rows = list(command_rows or [])
    counts: Dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    failed_steps = [
        {
            "step_id": str(row.get("step_id", "")),
            "tool_id": str(row.get("tool_id", "")),
            "reason": str(row.get("reason", "")),
        }
        for row in rows
        if row.get("status") == "failed"
    ]
    resumed_steps = [str(row.get("step_id", "")) for row in rows if row.get("status") == "resumed"]
    summary = dict(run_summary or {})
    facts: Dict[str, Any] = {
        "status": str(summary.get("status", "")),
        "run_id": summary.get("run_id"),
        "plan_id": summary.get("plan_id"),
        "resumes_run_id": summary.get("resumes_run_id"),
        "previous_run_archive": summary.get("previous_run_archive"),
        "step_status_counts": counts,
        "failed_steps": failed_steps,
        "resumed_steps": resumed_steps,
    }
    return facts


def write_generic_report(
    plan: Any,
    result_dir: str | Path,
    *,
    table_summary: Mapping[str, Mapping[str, Any]],
    title: str = "ABI Report",
    limitations: Optional[List[str]] = None,
    run_facts: Mapping[str, Any] | None = None,
) -> Dict[str, Path]:
    """Write a human-readable + machine-readable pipeline report.

    # What plugins need to provide / 插件需要提供
    - plan: The pipeline plan object (duck-typed: needs .to_dict() or be dict) / 管道计划
    - result_dir: Where to create the report/ subdirectory / 报告输出目录
    - table_summary: Dict from StandardTableManager.summarize() / 表格汇总
    - limitations: Optional list of declared limitation strings; when empty or
      omitted an explicit fallback sentence is rendered instead of omitting
      the section. / 局限性声明列表，缺省时渲染兜底句而非省略章节

    # What is produced / 生成内容
    - report/report.md: Markdown with project metadata and a table summary. / Markdown 格式
    - report/report.html: HTML with the same content, escaped for safety. / HTML 格式
    - report/report_summary.json: Machine-readable summary (same data as Markdown).
      / 机器可读的 JSON

    # Duck-typing the plan / plan 的鸭子类型
    The `plan` parameter is typed as `Any` intentionally: it can be a dataclass
    with .to_dict(), a plain dict, or any object with dict-like access. This
    decouples the report writer from the plan schema so plugins can evolve their
    plan structures independently. / 接受任何有 to_dict() 或 dict 访问的对象。
    """
    root = Path(result_dir)
    report_dir = root / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    # Normalize plan to a dict for uniform access / 将 plan 统一转为 dict
    plan_data = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
    project_name = str(plan_data.get("project_name", root.name))
    analysis_type = str(plan_data.get("analysis_type", "unknown"))
    selected_tools = plan_data.get("selected_tools", [])
    markdown = report_dir / "report.md"
    html = report_dir / "report.html"

    limitations_list = [str(item) for item in (limitations or [])]
    limitations_md = [f"{i}. {lim}" for i, lim in enumerate(limitations_list, 1)] or [
        FALLBACK_LIMITATION
    ]
    limitations_html = (
        "<ol>" + "".join(f"<li>{escape(lim)}</li>" for lim in limitations_list) + "</ol>"
        if limitations_list
        else f"<p>{escape(FALLBACK_LIMITATION)}</p>"
    )

    # ── Execution facts / 实际执行事实 ──
    # WP5: failed calls and reused steps must be explicit; a report that only
    # restates the plan table hides what actually happened.
    # WP5：失败调用与复用步骤必须显式呈现；只复述计划表的报告会掩盖实际
    # 发生的事。
    facts = dict(run_facts) if run_facts else None
    facts_md_lines: List[str] = []
    facts_html_rows: List[str] = []
    if facts is None:
        facts_md_lines = ["_Execution facts were not provided for this report._"]
    else:
        counts = facts.get("step_status_counts") or {}
        if counts:
            facts_md_lines.append("| Status | Steps |")
            facts_md_lines.append("| --- | ---: |")
            for status in sorted(counts):
                facts_md_lines.append(f"| {status} | {counts[status]} |")
            facts_md_lines.append("")
            facts_html_rows = [
                (f"<tr><td>{escape(status)}</td><td>{escape(str(counts[status]))}</td></tr>")
                for status in sorted(counts)
            ]
        else:
            facts_md_lines.append("_No step-level command records available._")
            facts_md_lines.append("")
        failed_steps = facts.get("failed_steps") or []
        if failed_steps:
            facts_md_lines.append("**Failed calls:**")
            facts_md_lines.extend(
                f"- `{item['step_id']}` ({item['tool_id']}): {item['reason']}"
                for item in failed_steps
            )
        else:
            facts_md_lines.append("Failed calls: none recorded.")
        resumed_steps = facts.get("resumed_steps") or []
        if resumed_steps:
            facts_md_lines.append(
                "**Reused steps (validated resume):** " + ", ".join(f"`{s}`" for s in resumed_steps)
            )
        else:
            facts_md_lines.append("Reused steps: none recorded.")
        linkage = []
        if facts.get("resumes_run_id"):
            linkage.append(f"resumes run `{facts['resumes_run_id']}`")
        if facts.get("previous_run_archive"):
            linkage.append(f"prior evidence archived at `{facts['previous_run_archive']}`")
        if facts.get("plan_id"):
            linkage.append(f"plan identity `{facts['plan_id']}`")
        if linkage:
            facts_md_lines.append("")
            facts_md_lines.append("History: " + "; ".join(linkage) + ".")

    # ── Markdown report / Markdown 格式 ──
    # Build line by line via join() for clarity (f-strings would be unwieldy
    # with this many lines). / 逐行构建，比 f-string 更清晰。
    markdown.write_text(
        "\n".join(
            [
                f"# {title}: {project_name}",
                "",
                f"- Analysis type: `{analysis_type}`",
                f"- Planned steps: {len(plan_data.get('steps', []))}",
                f"- Selected tools: {', '.join(str(tool) for tool in selected_tools) or 'none'}",
                "",
                "## Standard Tables",
                "",
                # Right-aligned "Rows" column for numeric data / 行数列右对齐
                "| Table | Rows | Path |",
                "| --- | ---: | --- |",
                *[
                    f"| `{table}.tsv` | {meta.get('rows', 0)} | `{meta.get('path', '')}` |"
                    for table, meta in sorted(table_summary.items())
                ],
                "",
                "## Execution Facts",
                "",
                *facts_md_lines,
                "",
                "## Known Limitations",
                "",
                # Mandatory disclosure: fallback sentence when nothing declared
                *limitations_md,
                "",
                # Disclaimer: dry-run = structural validation only / 免责声明
                "Dry-run artifacts prove planning, command rendering, provenance, and table "
                "contracts only; biological conclusions require real tool outputs.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # ── HTML report / HTML 格式 ──
    # Build table rows first then interpolate into the HTML template. / 先构建行再插入模板。
    # Every dynamic value is escaped via html.escape() to prevent XSS. / 所有动态值都转义防 XSS。
    html_rows = [
        (
            f"<tr><td>{escape(table)}.tsv</td>"
            f"<td>{escape(str(meta.get('rows', 0)))}</td>"
            f"<td><code>{escape(str(meta.get('path', '')))}</code></td></tr>"
        )
        for table, meta in sorted(table_summary.items())
    ]
    html.write_text(
        "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                f'<head><meta charset="utf-8"><title>{escape(title)}</title></head>',
                "<body>",
                f"<h1>{escape(title)}: {escape(project_name)}</h1>",
                f"<p>Analysis type: <code>{escape(analysis_type)}</code></p>",
                f"<p>Planned steps: {len(plan_data.get('steps', []))}</p>",
                "<h2>Selected Tools</h2>",
                "<ul>",
                *[f"<li>{escape(str(tool))}</li>" for tool in selected_tools],
                "</ul>",
                "<h2>Standard Tables</h2>",
                "<table><thead><tr><th>Table</th><th>Rows</th><th>Path</th></tr></thead>",
                "<tbody>",
                *html_rows,
                "</tbody></table>",
                "<h2>Execution Facts</h2>",
                *(
                    [
                        "<table><thead><tr><th>Status</th><th>Steps</th></tr></thead><tbody>",
                        *facts_html_rows,
                        "</tbody></table>",
                    ]
                    if facts_html_rows
                    else ["<p><em>No step-level command records available.</em></p>"]
                ),
                "<h2>Known Limitations</h2>",
                limitations_html,
                "<p>Dry-run artifacts prove planning, command rendering, provenance, and "
                "table contracts only.</p>",
                "</body>",
                "</html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # ── JSON summary / JSON 格式 ──
    # Machine-readable version: suitable for API responses, CI checks, and
    # dashboard ingestion. / 适合 API 响应、CI 检查和仪表盘摄取。
    (report_dir / "report_summary.json").write_text(
        json.dumps(
            {
                "project_name": project_name,
                "analysis_type": analysis_type,
                "selected_tools": selected_tools,
                "standard_tables": dict(table_summary),
                "limitations": limitations_list,
                "execution_facts": facts,
            },
            indent=2,
            ensure_ascii=False,  # Allow Unicode in project names / 允许中文项目名
        )
        + "\n",
        encoding="utf-8",
    )
    return {"report": markdown, "report_html": html}


def write_full_report(
    plan: Any,
    result_dir: str | Path,
    *,
    table_summary: Mapping[str, Mapping[str, Any]],
    title: str = "ABI Report",
    citations: Optional[List[Dict[str, str]]] = None,
    limitations: Optional[List[str]] = None,
    config: Optional[Mapping[str, Any]] = None,
    methods: bool = True,
    resource_manifest: bool = True,
) -> Dict[str, Path]:
    """Write a complete ABI report with all sections.

    This is the **recommended** function for plugins to call.  It produces
    a full report suite in ``report/``:
    - ``report.md`` — Executive summary with table overview.
    - ``report.html`` — Full styled HTML report with figures, methods,
      limitations, and citations embedded.
    - ``methods.md`` — Standalone methods section for publication.
    - ``report_summary.json`` — Machine-readable summary.
    - ``resource_manifest.json`` (in ``provenance/``) — Resource inventory.

    # Parameters / 参数
    - **plan**: Execution plan (duck-typed: needs ``.to_dict()`` or be dict-like).
    - **result_dir**: Pipeline output directory (must contain ``tables/`` and
      ``provenance/`` subdirectories).
    - **table_summary**: Dict from ``StandardTableManager.summarize()``.
    - **title**: Report title (defaults to plugin's ``report_title``).
    - **citations**: List of citation dicts with ``tool``, ``stage``, ``citation`` keys.
    - **limitations**: List of limitation strings.
    - **config**: Plugin config dict (used for resource manifest generation).
    - **methods**: If True, generate ``methods.md``.
    - **resource_manifest**: If True, generate ``resource_manifest.json``.

    # Returns / 返回
    Dict mapping section name → Path to generated file.
    """
    from abi.report.html import write_html_report
    from abi.report.methods import write_methods

    root = Path(result_dir)
    paths: Dict[str, Path] = {}

    # ── Generic report (Markdown + HTML + JSON) ──
    generic = write_generic_report(
        plan,
        result_dir,
        table_summary=table_summary,
        title=title,
        limitations=limitations,
    )
    paths.update(generic)

    # Generate or load the database manifest before methods so report regeneration
    # preserves the resources recorded by the original run.
    resource_manifest_data: Optional[Mapping[str, Any]] = None
    if resource_manifest:
        manifest_path = root / "provenance" / "resource_manifest.json"
        if config:
            from abi.workflow.manifest import write_resource_manifest

            plan_data = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
            analysis_type = str(plan_data.get("analysis_type", "unknown"))
            manifest_path = write_resource_manifest(
                root / "provenance",
                analysis_type=analysis_type,
                config=config,
                checksum=True,
            )
        if manifest_path.exists():
            try:
                loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                _LOGGER.warning("Could not load resource manifest %s: %s", manifest_path, exc)
            else:
                if isinstance(loaded_manifest, Mapping):
                    resource_manifest_data = loaded_manifest
                    paths["resource_manifest"] = manifest_path

    # ── Full HTML report (overwrites the simpler one) ──
    methods_md = None
    if methods:
        methods_path = write_methods(
            result_dir,
            plan=plan,
            citations=citations,
            limitations=limitations,
            resource_manifest=resource_manifest_data,
            title=f"{title} — Methods",
        )
        paths["methods"] = methods_path
        methods_md = methods_path.read_text(encoding="utf-8")

    html_path = write_html_report(
        result_dir,
        plan=plan,
        table_summary=table_summary,
        methods_md=methods_md,
        limitations_yaml=limitations,
        citations=citations,
        title=title,
    )
    paths["report_html"] = html_path

    return paths


def write_plugin_report(
    plugin: Any,
    plan: Any,
    result_dir: str | Path,
) -> Dict[str, Path]:
    """Convenience wrapper implementing the standard plugin ``write_report()``.

        Every inline plugin (rnaseq_expression, wgs_bacteria, amplicon_16s,
        metatranscriptomics) follows the same pattern.  This function
        centralises it so plugins only need a one-liner::

                from pathlib import Path

        from abi.report.citations import load_citations
        from abi.report.limitations import load_limitations
        from abi.tables import StandardTableManager

        # ── Table summary ──
        tm = StandardTableManager(plugin.table_schemas())
        summary = tm.summarize(Path(result_dir) / "tables")

        # ── Citations & limitations ──
        root = plugin.root
        cit_path = root / "citation_registry.yaml"
        lim_path = root / "limitations.yaml"
        citations = load_citations(cit_path) if cit_path.exists() else []
        limitations = load_limitations(lim_path) if lim_path.exists() else []

        # ── Stashed config (for resource manifest) ──
        config = getattr(plugin, "_last_config", None)

        return write_full_report(
            plan,
            result_dir,
            table_summary=summary,
            title=plugin.report_title,
            citations=citations,
            limitations=limitations,
            config=config,
            methods=True,
            resource_manifest=True,
        )


    def write_report(self, plan, result_dir):
                return write_plugin_report(self, plan, result_dir)

        # What it does / 做了什么
        1. Summarises standard tables via ``StandardTableManager``.
        2. Loads ``citation_registry.yaml`` and ``limitations.yaml`` from
           the plugin root (if they exist).
        3. Renders figures via ``abi_sciplot`` (if *use_sciplot*) or legacy
           ``FigureEngine`` (if *render_figures* and a ``figure_specs.yaml`` exists).
        4. Calls ``write_full_report()`` with methods, resource manifest,
           and the stashed config (``plugin._last_config``).

        .. versionchanged:: 1.3.3
           Added *use_sciplot* flag (default True). When True, renders figures
           through ``abi.sciplot`` with PDF+SVG+PNG export, provenance, and lint.
    """
    from pathlib import Path

    from abi.report.citations import load_citations
    from abi.report.limitations import load_limitations
    from abi.tables import StandardTableManager

    # ── Table summary ──
    tm = StandardTableManager(plugin.table_schemas())
    summary = tm.summarize(Path(result_dir) / "tables")

    # ── Citations & limitations ──
    root = plugin.root
    cit_path = root / "citation_registry.yaml"
    lim_path = root / "limitations.yaml"
    citations = load_citations(cit_path) if cit_path.exists() else []
    limitations = load_limitations(lim_path) if lim_path.exists() else []

    # ── Stashed config (for resource manifest) ──
    config = getattr(plugin, "_last_config", None)

    return write_full_report(
        plan,
        result_dir,
        table_summary=summary,
        title=plugin.report_title,
        citations=citations,
        limitations=limitations,
        config=config,
        methods=True,
        resource_manifest=True,
    )
