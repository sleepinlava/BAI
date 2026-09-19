"""Compiled Execution Plan — backend-neutral compilation from ExecutionPlan.

Design doc ref: §4.4 Compiled Execution Plan, C08.

Converts a planner-resolved ``ExecutionPlan`` into an immutable ``CompiledPlan``
with resolved resources, environments, execution kinds, and validated invariants.

This runs on the live runtime plan path: ``ABIAgentInterface._plan`` compiles
every plan and persists the result as ``compiled_plan.json`` alongside
``execution_plan.json``.  Invariant violations raise and abort planning before
any artifact is written; the agent boundary surfaces them as a structured
error envelope.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Sequence, Set

from abi.errors import (
    PlanDriftError,
    PlanIntegrityError,
    ToolResolutionError,
    UnsupportedExecutionError,
)
from abi.execution_policy import ExecutionPolicy, apply_resource_policy
from abi.path_policy import InputPolicyError, resolve_within
from abi.schemas import plan_step_dependencies
from abi.tool_catalog import ToolCatalog
from abi.tools import ResourceSpec

__all__ = [
    "ExecutionKind",
    "CompiledStep",
    "CompiledPlan",
    "compile_plan",
    "CompilationWarning",
    "bind_confirmed_plan",
    "verify_confirmed_plan",
    "execution_confirmation_digest",
    "load_compiled_plan",
    "write_compiled_plan",
]


class ExecutionKind(str, Enum):
    """Backend-neutral execution kind for a compiled step."""

    EXTERNAL = "external"
    INTERNAL_WORKER = "internal_worker"
    INTERNAL_DRIVER = "internal_driver"


@dataclass
class CompilationWarning:
    """Non-fatal difference between compiled and current behavior."""

    step_id: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON round-tripping."""
        return {"step_id": self.step_id, "message": self.message}


@dataclass(frozen=True)
class CompiledStep:
    """A single step as resolved by the compiler.

    All fields that downstream adapters need are resolved here; adapters
    must not re-resolve resources, environments, or execution kinds.

    Immutability is deep, not shallow: ``__post_init__`` replaces nested
    lists/dicts with read-only views and freezes the resource spec, so a
    confirmed plan cannot be mutated after construction (WP4: nested lists,
    dicts, and resource objects must not bypass immutability constraints).
    """

    step_id: str
    tool_id: str
    category: str
    sample_id: str | None
    execution_kind: ExecutionKind

    # ── Dependencies ──
    dependencies: Sequence[str] = field(default_factory=list)

    # ── Resolved resources ──
    resources: ResourceSpec = field(default_factory=ResourceSpec)

    # ── Resolved environment ──
    env_name: str = ""
    container_image: str | None = None

    # ── I/O ──
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    params: Mapping[str, Any] = field(default_factory=dict)

    # ── Validation ──
    validated_paths: Sequence[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "validated_paths", tuple(self.validated_paths))
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        object.__setattr__(self, "outputs", MappingProxyType(dict(self.outputs)))
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        # ResourceSpec is a frozen value object; accept a raw mapping for
        # deserialization convenience, otherwise store it as-is.
        # ResourceSpec 是冻结值对象；为反序列化便利接受原始映射，否则原样存储。
        if isinstance(self.resources, Mapping) and not isinstance(self.resources, ResourceSpec):
            resource_kwargs = {
                name: self.resources[name] for name in _RESOURCE_FIELDS if name in self.resources
            }
            object.__setattr__(self, "resources", ResourceSpec(**resource_kwargs))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the compiled step for JSON persistence."""
        return {
            "step_id": self.step_id,
            "tool_id": self.tool_id,
            "category": self.category,
            "sample_id": self.sample_id,
            "execution_kind": self.execution_kind.value,
            "dependencies": list(self.dependencies),
            "resources": asdict(self.resources),
            "env_name": self.env_name,
            "container_image": self.container_image,
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "params": dict(self.params),
            "validated_paths": list(self.validated_paths),
        }

    _REQUIRED_FIELDS = (
        "step_id",
        "tool_id",
        "category",
        "execution_kind",
    )
    _KNOWN_FIELDS = frozenset(
        {
            "step_id",
            "tool_id",
            "category",
            "sample_id",
            "execution_kind",
            "dependencies",
            "resources",
            "env_name",
            "container_image",
            "inputs",
            "outputs",
            "params",
            "validated_paths",
        }
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompiledStep":
        """Deserialize and validate one compiled step (strict ``v1`` schema).

        Raises :class:`PlanIntegrityError` on unknown fields, missing required
        fields, or an unrecognized execution kind. Loaded nested containers
        are frozen exactly like compiler-produced steps.
        """
        _require_mapping(data, "compiled step")
        unknown = sorted(set(data) - cls._KNOWN_FIELDS)
        if unknown:
            raise PlanIntegrityError(
                f"Compiled step {data.get('step_id')!r} has unknown field(s): {', '.join(unknown)}"
            )
        missing = [name for name in cls._REQUIRED_FIELDS if not data.get(name)]
        if missing:
            raise PlanIntegrityError(
                f"Compiled step is missing required field(s): {', '.join(missing)}"
            )
        kind_value = str(data["execution_kind"])
        try:
            kind = ExecutionKind(kind_value)
        except ValueError as exc:
            raise PlanIntegrityError(
                f"Compiled step {data['step_id']!r} has unknown execution kind {kind_value!r}"
            ) from exc
        resources_data = data.get("resources") or {}
        _require_mapping(resources_data, f"compiled step {data['step_id']!r} resources")
        unknown_resources = sorted(set(resources_data) - set(_RESOURCE_FIELDS))
        if unknown_resources:
            raise PlanIntegrityError(
                f"Compiled step {data['step_id']!r} resources have unknown field(s): "
                + ", ".join(unknown_resources)
            )
        resources = ResourceSpec(
            **{name: resources_data[name] for name in _RESOURCE_FIELDS if name in resources_data}
        )
        sample_id_value = data.get("sample_id")
        return cls(
            step_id=str(data["step_id"]),
            tool_id=str(data["tool_id"]),
            category=str(data["category"]),
            sample_id=None if sample_id_value is None else str(sample_id_value),
            execution_kind=kind,
            dependencies=[str(dep) for dep in (data.get("dependencies") or [])],
            resources=resources,
            env_name=str(data.get("env_name") or ""),
            container_image=(
                None if data.get("container_image") is None else str(data["container_image"])
            ),
            inputs=_string_keyed_mapping(data.get("inputs"), "inputs"),
            outputs=_string_keyed_mapping(data.get("outputs"), "outputs"),
            params=_string_keyed_mapping(data.get("params"), "params"),
            validated_paths=[str(p) for p in (data.get("validated_paths") or [])],
        )


@dataclass(frozen=True)
class CompiledPlan:
    """Validated, backend-neutral compilation of an ``ExecutionPlan``.

    Every invariant tested by :func:`compile_plan` is guaranteed by
    construction after a successful compile.

    ``plan_id`` is the SHA-256 content digest of the compiled plan (excluding
    ``plan_id`` itself).  It is the identity that authorization, run records,
    and audit artifacts use to prove "this run executed the confirmed plan".
    """

    SCHEMA_VERSION = "abi.compiled_plan.v1"

    project_name: str
    mode: str
    threads: int
    outdir: Path

    steps: Sequence[CompiledStep]
    enabled_steps: Sequence[str] = field(default_factory=list)
    selected_tools: Sequence[str] = field(default_factory=list)
    analysis_type: str = ""
    # Canonical sample descriptors are part of the confirmed plan identity.
    # Older v1 artifacts may omit this optional field; new artifacts include
    # it whenever the source plan exposes ``samples``.
    samples: Any = None

    # ── Non-fatal compilation notes ──
    warnings: Sequence[CompilationWarning] = field(default_factory=list)

    # ── Content identity (set by compile_plan / from_dict) ──
    plan_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "enabled_steps", tuple(self.enabled_steps))
        object.__setattr__(self, "selected_tools", tuple(self.selected_tools))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def get(self, step_id: str) -> CompiledStep:
        """Return the compiled step for *step_id*."""
        for s in self.steps:
            if s.step_id == step_id:
                return s
        raise KeyError(step_id)

    @property
    def step_ids(self) -> List[str]:
        return [s.step_id for s in self.steps]

    @property
    def external_steps(self) -> List[CompiledStep]:
        return [s for s in self.steps if s.execution_kind == ExecutionKind.EXTERNAL]

    @property
    def internal_worker_steps(self) -> List[CompiledStep]:
        return [s for s in self.steps if s.execution_kind == ExecutionKind.INTERNAL_WORKER]

    @property
    def internal_driver_steps(self) -> List[CompiledStep]:
        return [s for s in self.steps if s.execution_kind == ExecutionKind.INTERNAL_DRIVER]

    @property
    def content_digest(self) -> str:
        """SHA-256 content identity of this compiled plan (excl. ``plan_id``)."""
        return plan_content_digest(self)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the compiled plan for persistence as ``compiled_plan.json``."""
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "plan_id": self.plan_id,
            "project_name": self.project_name,
            "analysis_type": self.analysis_type,
            "mode": self.mode,
            "threads": self.threads,
            "outdir": str(self.outdir),
            "steps": [step.to_dict() for step in self.steps],
            "enabled_steps": list(self.enabled_steps),
            "selected_tools": list(self.selected_tools),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
        if self.samples is not None:
            payload["samples"] = _canonical_value(self.samples)
        return payload

    _KNOWN_FIELDS = frozenset(
        {
            "schema_version",
            "plan_id",
            "project_name",
            "analysis_type",
            "mode",
            "threads",
            "outdir",
            "steps",
            "enabled_steps",
            "selected_tools",
            "warnings",
            "samples",
        }
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompiledPlan":
        """Deserialize and validate a compiled plan (strict ``v1`` schema).

        Re-validates structural invariants and — when ``plan_id`` is present —
        verifies that the stored identity matches the file's own content, so a
        persisted plan edited after signing is rejected instead of trusted.
        Legacy files written before identity binding have no ``plan_id``; they
        load without the self-check and are verified against the rebuilt plan
        by :func:`bind_confirmed_plan`.
        """
        _require_mapping(data, "compiled plan")
        if data.get("schema_version") != cls.SCHEMA_VERSION:
            raise PlanIntegrityError(
                f"Unsupported compiled plan schema_version {data.get('schema_version')!r}; "
                f"expected {cls.SCHEMA_VERSION!r}"
            )
        unknown = sorted(set(data) - cls._KNOWN_FIELDS)
        if unknown:
            raise PlanIntegrityError(f"Compiled plan has unknown field(s): {', '.join(unknown)}")
        steps_raw = data.get("steps")
        if not isinstance(steps_raw, list):
            raise PlanIntegrityError("Compiled plan 'steps' must be a list")
        steps = [CompiledStep.from_dict(step) for step in steps_raw]
        threads = data.get("threads")
        if not isinstance(threads, int) or isinstance(threads, bool):
            raise PlanIntegrityError("Compiled plan 'threads' must be an integer")
        outdir = data.get("outdir")
        if not isinstance(outdir, str) or not outdir:
            raise PlanIntegrityError("Compiled plan 'outdir' must be a non-empty path string")
        enabled_raw = data.get("enabled_steps") or []
        selected_raw = data.get("selected_tools") or []
        if not isinstance(enabled_raw, list) or not isinstance(selected_raw, list):
            raise PlanIntegrityError(
                "Compiled plan 'enabled_steps' and 'selected_tools' must be lists"
            )
        warnings_raw = data.get("warnings") or []
        if not isinstance(warnings_raw, list):
            raise PlanIntegrityError("Compiled plan 'warnings' must be a list")
        warnings = []
        for item in warnings_raw:
            _require_mapping(item, "compiled plan warning")
            warnings.append(
                CompilationWarning(
                    step_id=str(item.get("step_id", "")),
                    message=str(item.get("message", "")),
                )
            )
        plan = cls(
            project_name=str(data.get("project_name") or ""),
            mode=str(data.get("mode") or "auto"),
            threads=threads,
            outdir=Path(outdir),
            steps=steps,
            enabled_steps=[str(sid) for sid in enabled_raw],
            selected_tools=[str(tool) for tool in selected_raw],
            analysis_type=str(data.get("analysis_type") or ""),
            samples=_canonical_value(data["samples"]) if "samples" in data else None,
            warnings=warnings,
            plan_id=str(data.get("plan_id") or ""),
        )
        if set(plan.enabled_steps) != set(plan.step_ids):
            raise PlanIntegrityError(
                "Compiled plan 'enabled_steps' does not match its steps: "
                f"enabled={sorted(plan.enabled_steps)} steps={plan.step_ids}"
            )
        _validate_invariants(plan, set(plan.enabled_steps))
        if plan.plan_id and plan.plan_id != plan.content_digest:
            raise PlanIntegrityError(
                f"Compiled plan identity mismatch: stored plan_id {plan.plan_id!r} does not "
                f"match the file's content digest {plan.content_digest!r} "
                "(plan file modified after planning)"
            )
        return plan


# ── Compilation ──────────────────────────────────────────────────────────────


# Serializable field names of the frozen ResourceSpec value object.
# 冻结值对象 ResourceSpec 的可序列化字段名。
_RESOURCE_FIELDS = ("cpu", "memory", "walltime", "accelerator", "disk")


def compile_plan(
    plan: Any,  # ExecutionPlan — avoids hard import cycle
    *,
    catalog: ToolCatalog | None = None,
    policy: ExecutionPolicy | None = None,
    outdir: Path | None = None,
) -> CompiledPlan:
    """Compile an ``ExecutionPlan`` into a validated ``CompiledPlan``.

    Parameters
    ----------
    plan:
        Planner-resolved ``ExecutionPlan``.
    catalog:
        ``ToolCatalog`` for resolving tool environments and resources.
        If ``None``, builds one from the project root.
    policy:
        ``ExecutionPolicy`` with invocation and workflow overrides.
    outdir:
        Explicit output root.  Defaults to ``plan.outdir`` as a ``Path``.

    Returns
    -------
    CompiledPlan
        Validated, frozen compiled plan.  Raises on invariant violations.

    Raises
    ------
    PlanIntegrityError
        A compiled-plan invariant is violated (e.g., missing or duplicate
        steps, undefined dependencies, cycle).
    UnsupportedExecutionError
        A step has an execution kind the caller cannot handle.
    """
    if catalog is None:
        catalog = ToolCatalog.from_project_root()

    steps = plan.steps or []
    planned_dir = Path(outdir) if outdir else Path(plan.outdir)
    warnings: List[CompilationWarning] = []

    compiled_steps: List[CompiledStep] = []
    enabled_step_ids: Set[str] = set()

    for pstep in steps:
        if getattr(pstep, "skipped", False):
            continue

        sid = pstep.step_id
        enabled_step_ids.add(sid)

        kind = _resolve_execution_kind(pstep, warnings)
        if kind == ExecutionKind.EXTERNAL and not catalog.has(str(pstep.tool_id)):
            raise ToolResolutionError(
                f"Step {sid!r} references unknown external tool {pstep.tool_id!r}"
            )
        resources = _resolve_resources(pstep, catalog, policy, warnings)
        env_name = _resolve_environment(pstep, catalog, warnings)
        container = _resolve_container(pstep, catalog, warnings)
        deps = _resolve_dependencies(pstep)
        validated = _validate_paths(pstep, planned_dir)

        cstep = CompiledStep(
            step_id=sid,
            tool_id=pstep.tool_id,
            category=pstep.category,
            sample_id=pstep.sample_id,
            execution_kind=kind,
            dependencies=deps,
            resources=resources,
            env_name=env_name,
            container_image=container,
            inputs=dict(pstep.inputs or {}),
            outputs=dict(pstep.outputs or {}),
            params=dict(pstep.params or {}),
            validated_paths=validated,
        )
        compiled_steps.append(cstep)

    # ── Invariants ──
    compiled = CompiledPlan(
        project_name=plan.project_name or "",
        mode=plan.mode or "auto",
        threads=plan.threads or 1,
        outdir=planned_dir,
        steps=compiled_steps,
        enabled_steps=sorted(enabled_step_ids),
        selected_tools=list(plan.selected_tools or []),
        analysis_type=plan.analysis_type or "",
        samples=_canonical_value(getattr(plan, "samples", None)),
        warnings=warnings,
    )

    _validate_invariants(compiled, enabled_step_ids)
    # Bind the content identity: authorization, run records, and audit
    # artifacts reference this digest to prove which plan actually ran.
    # 绑定内容身份：授权、运行记录与审计产物引用该摘要证明实际执行的计划。
    object.__setattr__(compiled, "plan_id", plan_content_digest(compiled))
    return compiled


# ── Resolvers ────────────────────────────────────────────────────────────────


def _resolve_execution_kind(pstep: Any, warnings: List[CompilationWarning]) -> ExecutionKind:
    """Determine execution kind from step metadata."""
    tool_id = str(getattr(pstep, "tool_id", "") or "")
    # None-vs-empty matters here: an absent handler means EXTERNAL, so keep
    # the raw sentinel semantics instead of the normalizing helper.
    # 此处 None（缺席）与 {}（存在但空）语义不同，保留原始哨兵判定。
    handler = getattr(pstep, "internal_handler", None) or dict(getattr(pstep, "params", {})).get(
        "_internal_handler"
    )
    if handler is not None:
        scope = _get_execution_scope(handler)
        if scope == "worker":
            return ExecutionKind.INTERNAL_WORKER
        if scope == "driver":
            return ExecutionKind.INTERNAL_DRIVER
        warnings.append(
            CompilationWarning(
                step_id=pstep.step_id,
                message=f"Internal handler with unrecognized scope {scope!r}; treating as worker",
            )
        )
        return ExecutionKind.INTERNAL_WORKER

    # tool_id == "internal" without a handler is an error
    if tool_id == "internal":
        raise UnsupportedExecutionError(
            f"Step {pstep.step_id!r} has tool_id='internal' but no _internal_handler"
        )

    return ExecutionKind.EXTERNAL


def _get_execution_scope(handler: Any) -> str:
    """Extract execution_scope from a handler object or dict."""
    if hasattr(handler, "execution_scope"):
        return str(handler.execution_scope)
    if isinstance(handler, Mapping):
        return str(handler.get("execution_scope", "worker"))
    return "worker"


def _resolve_resources(
    pstep: Any,
    catalog: ToolCatalog,
    policy: ExecutionPolicy | None,
    warnings: List[CompilationWarning],
) -> ResourceSpec:
    """Resolve resources for *pstep* using catalog defaults and policy."""
    tool_id = str(getattr(pstep, "tool_id", "") or "")

    # Base from tool catalog
    try:
        if catalog.has(tool_id):
            catalog_spec = catalog.get(tool_id).resources
        else:
            catalog_spec = None
    except Exception:
        catalog_spec = None

    # Apply policy chain
    if policy:
        # catalog_spec holds recommended defaults; use as base.
        # Catalog-level overrides (ResourceOverride form) come later.
        resolved = apply_resource_policy(
            base=catalog_spec or ResourceSpec(),
            catalog=None,
            workflow=None,
            invocation=policy.invocation_overrides,
        )
    else:
        resolved = catalog_spec or ResourceSpec()

    return resolved


def _resolve_environment(
    pstep: Any,
    catalog: ToolCatalog,
    warnings: List[CompilationWarning],
) -> str:
    """Resolve environment name for a step."""
    tool_id = str(getattr(pstep, "tool_id", "") or "")

    try:
        if catalog.has(tool_id):
            return catalog.get(tool_id).env_name
    except Exception:
        pass

    warnings.append(
        CompilationWarning(
            step_id=pstep.step_id,
            message=f"Tool {tool_id!r} not in catalog; no environment resolved",
        )
    )
    return ""


def _resolve_container(
    pstep: Any,
    catalog: ToolCatalog,
    warnings: List[CompilationWarning],
) -> str | None:
    """Resolve container image for a step."""
    tool_id = str(getattr(pstep, "tool_id", "") or "")

    try:
        if catalog.has(tool_id):
            return catalog.get(tool_id).container_image
    except Exception:
        pass

    return None


def _resolve_dependencies(pstep: Any) -> List[str]:
    """Resolve step dependencies from explicit params."""
    return plan_step_dependencies(pstep)


def _validate_paths(pstep: Any, outdir: Path) -> List[str]:
    """Validate every declared output path within *outdir*."""
    validated: List[str] = []
    outputs = dict(getattr(pstep, "outputs", {}) or {})

    for name, value in outputs.items():
        if value is None or value == "":
            continue
        if not isinstance(value, (str, Path)):
            raise PlanIntegrityError(
                f"Step {pstep.step_id!r} output {name!r} must be a path, got {type(value).__name__}"
            )
        try:
            resolve_within(outdir, value, label=f"output {name!r}")
        except InputPolicyError as exc:
            raise PlanIntegrityError(f"Step {pstep.step_id!r}: {exc}") from exc
        validated.append(str(value))

    return validated


# ── Invariant checks ─────────────────────────────────────────────────────────


def _validate_invariants(
    compiled: CompiledPlan,
    enabled_step_ids: Set[str],
) -> None:
    """Validate compiled plan invariants.  Raises on violation."""
    compiled_ids = {s.step_id for s in compiled.steps}

    # Must have at least one step
    if not compiled_ids:
        return

    # Duplicate step IDs
    if len(compiled_ids) != len(compiled.steps):
        seen: Set[str] = set()
        for s in compiled.steps:
            if s.step_id in seen:
                raise PlanIntegrityError(f"Duplicate step_id {s.step_id!r} in compiled plan")
            seen.add(s.step_id)

    # Reference: enabled_steps == compiled_steps
    if enabled_step_ids != compiled_ids:
        extra = compiled_ids - enabled_step_ids
        missing = enabled_step_ids - compiled_ids
        msg_parts: List[str] = []
        if missing:
            msg_parts.append(f"missing={sorted(missing)}")
        if extra:
            msg_parts.append(f"extra={sorted(extra)}")
        raise PlanIntegrityError(
            "Compiled plan steps do not match enabled plan steps: " + "; ".join(msg_parts)
        )

    # All dependencies are defined
    for s in compiled.steps:
        for dep in s.dependencies:
            if dep not in compiled_ids:
                raise PlanIntegrityError(f"Step {s.step_id!r} depends on undefined step {dep!r}")

    # No self-dependency
    for s in compiled.steps:
        if s.step_id in s.dependencies:
            raise PlanIntegrityError(f"Step {s.step_id!r} depends on itself")

    # Cycle check via Kahn's algorithm
    _check_acyclic(compiled)


def _check_acyclic(compiled: CompiledPlan) -> None:
    """Kahn's algorithm: raise if the compiled plan has a cycle."""
    graph: Dict[str, List[str]] = {s.step_id: list(s.dependencies) for s in compiled.steps}
    in_degree: Dict[str, int] = {sid: 0 for sid in graph}

    for sid, deps in graph.items():
        for dep in deps:
            in_degree[sid] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    removed = 0

    while queue:
        node = queue.pop(0)
        removed += 1
        for sid, deps in graph.items():
            if node in deps:
                in_degree[sid] -= 1
                if in_degree[sid] == 0:
                    queue.append(sid)

    if removed != len(graph):
        remaining = [sid for sid, deg in in_degree.items() if deg > 0]
        raise PlanIntegrityError(f"Cycle detected in compiled plan: {sorted(remaining)}")


# ── Persistence & confirmed-plan binding ─────────────────────────────────


def _require_mapping(value: Any, label: str) -> None:
    if not isinstance(value, Mapping):
        raise PlanIntegrityError(f"{label} must be a JSON object, got {type(value).__name__}")


def _string_keyed_mapping(value: Any, label: str) -> Dict[str, Any]:
    """Validate a loaded I/O mapping: object with string keys."""
    _require_mapping(value, label)
    for key in value:
        if not isinstance(key, str):
            raise PlanIntegrityError(f"{label} has non-string key {key!r}")
    return dict(value)


def _canonical_value(value: Any) -> Any:
    """Convert planner/configuration values into deterministic JSON data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        items = [_canonical_value(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _canonical_value(to_dict())
        except Exception:  # pragma: no cover - third-party planner object
            pass
    if hasattr(value, "__dict__"):
        return _canonical_value(vars(value))
    return str(value)


def execution_confirmation_digest(plan: Any, config: Any, options: Any) -> str:
    """Digest every mutable execution input outside the compiled step view.

    ``CompiledPlan`` deliberately contains backend-neutral step information,
    while queueing layers also carry samples, resolved configuration, and
    runtime options.  Those values are mutable Python objects, so they need a
    separate confirmation fingerprint to prevent a queued run from starting
    with a different container, resource, timeout, or sample selection.
    ``confirmed_plan_id`` is derived after binding and is intentionally not
    included in its own fingerprint.
    """
    option_value = _canonical_value(options)
    if isinstance(option_value, dict):
        option_value.pop("confirmed_plan_id", None)
    payload = {
        "plan": _canonical_value(plan),
        "config": _canonical_value(config),
        "options": option_value,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def plan_content_digest(compiled: CompiledPlan) -> str:
    """Return the canonical SHA-256 content digest of a compiled plan.

    The digest covers every serialized field except ``plan_id`` itself, with
    sorted keys, so it is stable across processes and independent of dict
    insertion order. This is the identity that binds execution, run records,
    and audit artifacts to the confirmed plan.
    """
    content = compiled.to_dict()
    content.pop("plan_id", None)
    payload = json.dumps(content, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_compiled_plan(compiled: CompiledPlan, path: str | Path) -> Path:
    """Persist *compiled* as ``compiled_plan.json`` in the canonical format."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(compiled.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


def load_compiled_plan(path: str | Path) -> CompiledPlan:
    """Load, validate, and deep-freeze a persisted ``compiled_plan.json``.

    Raises :class:`PlanIntegrityError` on unreadable or malformed JSON, unknown
    schema versions, unknown/missing fields, violated invariants, or a stored
    ``plan_id`` that does not match the file's own content digest.
    """
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise PlanIntegrityError(f"Cannot read compiled plan {source}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanIntegrityError(f"Invalid JSON in compiled plan {source}: {exc}") from exc
    try:
        return CompiledPlan.from_dict(data)
    except PlanIntegrityError as exc:
        raise PlanIntegrityError(f"{source}: {exc}") from exc


def bind_confirmed_plan(prepared: Any) -> str:
    """Compile *prepared*'s plan and bind the run to the confirmed compiled plan.

    This is the seam that makes actual execution correspond to the plan the
    user approved (WP4): the plan is recompiled from the prepared workflow and
    its content identity is compared against the confirmed
    ``compiled_plan.json`` in the output directory.

    - Confirmed file matches → return the verified ``plan_id``.
    - Confirmed file missing (direct run without a prior ``abi plan``) →
      persist the verified plan first, then return its ``plan_id``.
    - Confirmed file differs → raise :class:`PlanDriftError`; the caller must
      re-plan and obtain fresh user approval.
    - Persisted file fails structural or self-identity validation → raise
      :class:`PlanIntegrityError`.
    """
    plan = getattr(prepared, "plan", None)
    config = getattr(prepared, "config", None)
    options = getattr(prepared, "options", None)
    # Preserve the planner-owned references across repeated binding calls so
    # mutations made by a queueing layer remain observable.  The backend gets
    # a defensive plan snapshot below; config/options are guarded by the
    # confirmation fingerprint immediately before backend selection.
    source_plan = getattr(prepared, "_confirmed_source_plan", plan)
    source_config = getattr(prepared, "_confirmed_source_config", config)
    source_options = getattr(prepared, "_confirmed_source_options", options)
    outdir_value = (config or {}).get("outdir") or getattr(plan, "outdir", None)
    if outdir_value is None:
        raise PlanIntegrityError(
            "Cannot bind the confirmed plan: the prepared workflow has no resolved output directory"
        )
    outdir = Path(outdir_value)
    compiled = compile_plan(plan, outdir=outdir)
    confirmed_path = outdir / "compiled_plan.json"
    if confirmed_path.exists():
        confirmed = load_compiled_plan(confirmed_path)
        if confirmed.content_digest != compiled.plan_id:
            raise PlanDriftError(
                f"Confirmed plan drift detected for output directory {outdir}: the persisted "
                f"compiled plan ({confirmed.content_digest}) does not match the plan rebuilt "
                f"from the current configuration ({compiled.plan_id}). Re-run `abi plan` for "
                "this output directory, review the regenerated plan, and re-run with "
                "confirm_execution=true after user approval."
            )
    else:
        # First bind: persist the verified identity so later runs (retry,
        # resume) verify against the same confirmed artifact.
        # 首次绑定：持久化已验证的身份，让后续运行（重试、恢复）对同一产物验证。
        write_compiled_plan(compiled, confirmed_path)
    confirmation_digest = getattr(prepared, "_confirmed_execution_digest", "")
    if not confirmation_digest:
        confirmation_digest = execution_confirmation_digest(
            source_plan, source_config, source_options
        )
    # Keep the exact object that was compiled as the execution snapshot.  The
    # planner object can still be held by a transport or plugin and may be
    # mutated while a queued job waits; handing that mutable object to a
    # backend would make the confirmation evidence weaker than the work that
    # actually starts.
    try:
        bound_plan = copy.deepcopy(plan)
    except Exception as exc:  # pragma: no cover - defensive for plugin objects
        raise PlanIntegrityError(
            f"Cannot freeze the confirmed execution plan before backend startup: {exc}"
        ) from exc
    try:
        object.__setattr__(prepared, "plan", bound_plan)
        object.__setattr__(prepared, "confirmed_plan_id", compiled.plan_id)
        # Keep the planner-owned object separately so a queueing layer that
        # mutates it after approval is detected rather than silently ignored.
        # The backend still receives the defensive snapshot above.
        object.__setattr__(prepared, "_confirmed_source_plan", source_plan)
        object.__setattr__(prepared, "_confirmed_source_config", source_config)
        object.__setattr__(prepared, "_confirmed_source_options", source_options)
        object.__setattr__(prepared, "_confirmed_execution_digest", confirmation_digest)
        # The agent boundary historically sets this field on its local
        # RuntimeOptions variable immediately after binding.  Set it here as
        # well so a defensive or frozen prepared object still carries the
        # identity that the selected backend must record.
        bound_options = getattr(prepared, "options", None)
        if bound_options is not None and hasattr(bound_options, "confirmed_plan_id"):
            setattr(bound_options, "confirmed_plan_id", compiled.plan_id)
    except (AttributeError, TypeError) as exc:
        raise PlanIntegrityError(
            "Cannot attach the confirmed execution snapshot to the prepared workflow"
        ) from exc
    return compiled.plan_id


def verify_confirmed_plan(prepared: Any) -> None:
    """Revalidate a bound snapshot immediately before selecting a backend."""
    expected = str(getattr(prepared, "confirmed_plan_id", "") or "")
    if not expected:
        return
    plan = getattr(prepared, "plan", None)
    config = getattr(prepared, "config", None)
    outdir_value = (config or {}).get("outdir") or getattr(plan, "outdir", None)
    if outdir_value is None:
        raise PlanIntegrityError(
            "Cannot verify the confirmed execution plan: no resolved output directory"
        )
    actual = compile_plan(plan, outdir=Path(outdir_value)).plan_id
    if actual != expected:
        raise PlanDriftError(
            "The confirmed execution snapshot changed after binding; "
            "re-plan and obtain fresh execution confirmation"
        )
    source_plan = getattr(prepared, "_confirmed_source_plan", None)
    if source_plan is not None:
        source_actual = compile_plan(source_plan, outdir=Path(outdir_value)).plan_id
        if source_actual != expected:
            raise PlanDriftError(
                "The planner-owned execution plan changed while waiting in the queue; "
                "re-plan and obtain fresh execution confirmation"
            )
    expected_context = str(getattr(prepared, "_confirmed_execution_digest", "") or "")
    if expected_context:
        bound_context = execution_confirmation_digest(
            plan,
            getattr(prepared, "config", None),
            getattr(prepared, "options", None),
        )
        if bound_context != expected_context:
            raise PlanDriftError(
                "The confirmed execution configuration or runtime options changed after "
                "binding; re-plan and obtain fresh execution confirmation"
            )
        source_context = execution_confirmation_digest(
            source_plan,
            getattr(prepared, "_confirmed_source_config", None),
            getattr(prepared, "_confirmed_source_options", None),
        )
        if source_context != expected_context:
            raise PlanDriftError(
                "The planner-owned execution configuration or runtime options changed while "
                "waiting in the queue; re-plan and obtain fresh execution confirmation"
            )
