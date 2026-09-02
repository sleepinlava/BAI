"""Permission model for ABI agent-facing operations -- who can do what.

This module defines a three-tier permission system that gates every ABI
agent tool. The permission level determines whether the tool can run
automatically or requires explicit user confirmation.

**Security model / 安全模型**

The permission model follows the **principle of least privilege**: every
tool defaults to the most restrictive level that allows it to function.
Agents are assumed to be semi-autonomous -- they can read and plan freely,
but destructive or expensive operations require a human in the loop.

**Three permission levels / 三种权限级别**

===============  ======================================================  ========
Level              Description / 描述                                      Confirm?
===============  ======================================================  ========
``READ_ONLY``     Inspect state, read files, validate results.             No
                  Safe to run at any time without side effects.
                  检查状态、读取文件、验证结果。无副作用，安全随时运行。
``PLANNING_WRITE`` Generate plans, reports, exports. Writes to disk         No
                  but does NOT execute pipelines. Idempotent.
                  生成计划、报告、导出。写磁盘但不执行流水线。幂等。
``EXECUTION``     Run actual pipelines -- consumes resources, produces      **Yes**
                  outputs, may be expensive or irreversible.
                  运行实际流水线 -- 消耗资源、产生输出，可能昂贵或不可逆。
===============  ======================================================  ========

**Why ``run`` requires confirmation / 为何 run 需要确认**

``abi_run`` is the only tool at the ``EXECUTION`` level. This is
deliberate: running a pipeline can consume hours of CPU, produce gigabytes
of output, and potentially overwrite previous results. We want a human to
explicitly approve execution so that:
1. The user has reviewed the plan (``abi_plan`` output).
2. Resource costs are understood.
3. Accidental execution by an agent is impossible.

**Why planning tools do NOT require confirmation / 为何计划工具不需要确认**

``abi_plan``, ``abi_dry_run``, ``abi_report``, ``abi_export_nextflow``, and
``abi_export_snakemake`` are all ``PLANNING_WRITE``. They write files to disk
but do not launch
subprocesses or consume significant resources. They are also idempotent:
running them twice produces the same output. Requiring confirmation for
every plan iteration would slow down agent workflows without adding safety.

**Adding a new tool / 添加新工具**

Add the tool name → ``PermissionLevel`` mapping to ``TOOL_PERMISSIONS``.
If you are unsure which level to use, classify it explicitly before exposing
the tool. Unregistered names fall back to ``READ_ONLY``. Only use ``EXECUTION`` for tools
that launch subprocesses or mutate external state.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict

from abi.tool_descriptors import ABI_AGENT_TOOLS

__all__ = [
    "PermissionLevel",
    "TOOL_PERMISSIONS",
    "permission_for_tool",
    "requires_confirmation",
]


class PermissionLevel(str, Enum):
    """Agent permission level for an ABI tool.

    Levels are ordered by increasing power: READ_ONLY < PLANNING_WRITE < EXECUTION.
    A tool at a higher level can do everything a lower-level tool can do.

    **Why ``str, Enum``? / 为何继承 str 和 Enum？**
    Inheriting from ``str`` makes the enum values directly JSON-serializable
    (for agent context messages) and comparable to plain strings (for
    configuration file lookups) without calling ``.value``.
    同时继承 str 和 Enum 使枚举值可直接 JSON 序列化（用于智能体上下文消息）
    并可与普通字符串比较（用于配置文件查找），而无需调用 .value。
    """

    READ_ONLY = "read_only"
    # Read-only operations: list tools, inspect config, validate results.
    # Safe to run at any time. No side effects, no resource consumption.
    # 只读操作：列出工具、检查配置、验证结果。随时安全运行，无副作用。

    PLANNING_WRITE = "planning_write"
    # Planning operations: generate plans, reports, exports. May write files
    # to disk but does NOT execute pipelines. Idempotent -- running twice
    # produces the same output.
    # 计划操作：生成计划、报告、导出。可写磁盘但不执行流水线。幂等。

    EXECUTION = "execution"
    # Pipeline execution: runs tools, consumes CPU/memory/disk, may be
    # expensive or irreversible. REQUIRES user confirmation.
    # 流水线执行：运行工具、消耗 CPU/内存/磁盘，可能昂贵或不可逆。需要用户确认。


# ── Tool permission map / 工具权限映射 ──
# Permissions are **derived** from the tool descriptor SSOT
# (``abi.tool_descriptors.ABI_AGENT_TOOLS``) so the set advertised to agents
# and the set enforced at the dispatch gate can never drift apart. The only
# hand-written additions are legacy dispatch aliases, which inherit the
# permission of their canonical ``abi_*`` tool.
# 权限从工具描述符 SSOT 派生, 使广告给 agent 的集合与 dispatch 闸门强制执行的
# 集合永远不会漂移。唯一手工维护的是遗留别名, 它们继承规范 abi_* 工具的权限。

# Legacy (non-``abi_``-prefixed) dispatch aliases → canonical descriptor name.
_PERMISSION_ALIAS_TO_CANONICAL: Dict[str, str] = {
    "autoplasm_validate_result": "abi_autoplasm_validate_result",
}

TOOL_PERMISSIONS: Dict[str, PermissionLevel] = {
    tool_name: PermissionLevel(metadata["permission"])
    for tool_name, metadata in ABI_AGENT_TOOLS.items()
}
for _alias, _canonical in _PERMISSION_ALIAS_TO_CANONICAL.items():
    TOOL_PERMISSIONS[_alias] = TOOL_PERMISSIONS[_canonical]


def permission_for_tool(tool_name: str) -> PermissionLevel:
    """Return the agent permission level for an ABI tool name.

    **Fallback behavior / 回退行为:**
    If ``tool_name`` is not in ``TOOL_PERMISSIONS``, returns
    ``PermissionLevel.READ_ONLY`` (S11: unregistered tools default to
    the most restrictive permission level for safety).
    如果 tool_name 不在 TOOL_PERMISSIONS 中，返回 READ_ONLY --
    未注册工具默认使用最严格的权限级别以确保安全（S11）。
    """
    # S11: default to READ_ONLY for unknown tools — unregistered tools
    # should not be allowed to write files or execute by default.
    return TOOL_PERMISSIONS.get(tool_name, PermissionLevel.READ_ONLY)


def requires_confirmation(tool_name: str) -> bool:
    """Return whether an ABI tool is execution-gated.

    **Semantics / 语义:**
    Returns ``True`` ONLY when ``permission_for_tool(tool_name) == EXECUTION``.
    The agent runtime uses this to decide whether to prompt the user before
    dispatching a tool call.

    **Why a separate function? / 为何是单独的函数？**
    Abstraction: callers don't need to know the ``PermissionLevel`` enum;
    they only need a boolean answer to "should I ask the user?". If we later
    add more confirmation-gated levels, only this function changes.
    抽象：调用者无需了解 PermissionLevel 枚举，只需一个布尔答案"我该问用户吗？"。
    如果将来添加更多需要确认的级别，只有此函数需要修改。
    """
    return permission_for_tool(tool_name) == PermissionLevel.EXECUTION
