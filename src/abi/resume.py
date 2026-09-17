"""Identity evidence used to decide whether a run may be resumed.

Resume is an execution decision, not merely an output-existence check.  This
module keeps the small, backend-neutral identity record shared by the local,
Nextflow, Snakemake, and HPC runtimes.  The record deliberately contains
content digests for files and directory trees; paths, mtimes, and tool names
alone are not sufficient to prove that reusing an old result is safe.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from abi.filesystem import checksum_path
from abi.tools import container_image_identities

RESUME_IDENTITY_SCHEMA = "abi.resume_identity.v1"
RESUME_IDENTITY_FILENAME = "resume_identity.json"

_PATH_KEY_PARTS = (
    "assembly",
    "bam",
    "count",
    "database",
    "db",
    "file",
    "genome",
    "gtf",
    "index",
    "input",
    "model",
    "read",
    "reference",
    "resource",
    "sample",
)


def path_identity(value: str | Path) -> dict[str, Any]:
    """Return a stable content identity for one input or resource path."""
    raw = Path(str(value)).expanduser()
    try:
        resolved = raw.resolve(strict=False)
    except OSError:
        resolved = raw.absolute()
    exists = resolved.exists()
    return {
        "path": str(resolved),
        "exists": exists,
        "checksum_sha256": checksum_path(resolved) if exists else "",
    }


def collect_plan_input_identities(plan: Any) -> list[dict[str, Any]]:
    """Collect content identities for path-like values consumed by a plan.

    The planner has a deliberately flexible input schema.  We therefore use
    both semantic key hints and existing filesystem paths, including values
    nested in lists and mappings.  Output declarations are excluded: output
    reuse is validated by the executor's checksum chain separately.
    """
    identities: dict[tuple[str, str, str], dict[str, Any]] = {}
    steps = [step for step in getattr(plan, "steps", ()) if not getattr(step, "skipped", False)]
    produced_paths = _plan_produced_paths(steps)
    sample_input_paths: set[str] = set()
    for sample in getattr(plan, "samples", ()) or ():
        for field in (
            "read1",
            "read2",
            "long_reads",
            "pod5",
            "bam",
            "assembly",
            "host_reference",
        ):
            value = getattr(sample, field, None)
            if value:
                for _label, candidate in _path_values(field, value):
                    sample_input_paths.add(_normalized_path(candidate))
    # Index directory ancestry once. Scanning every output for every input
    # makes large multi-sample plans quadratic even when no input is a directory.
    generated_directories: dict[str, int] = {}
    for output_path, producer_index in produced_paths.items():
        if output_path in sample_input_paths:
            continue
        for parent in Path(output_path).parents:
            key = str(parent)
            generated_directories[key] = min(
                producer_index, generated_directories.get(key, producer_index)
            )
    for step_index, step in enumerate(steps):  # pragma: no branch - tiny iterator
        step_id = str(getattr(step, "step_id", ""))
        inputs = getattr(step, "inputs", {})
        if isinstance(inputs, Mapping):
            for key, value in inputs.items():
                for label, candidate in _path_values(str(key), value):
                    if _is_prior_plan_output(
                        candidate,
                        step_index=step_index,
                        produced_paths=produced_paths,
                        protected_paths=sample_input_paths,
                    ):
                        continue
                    expanded = _expand_directory_input(
                        candidate,
                        label=label,
                        step_index=step_index,
                        produced_paths=produced_paths,
                        protected_paths=sample_input_paths,
                        generated_directories=generated_directories,
                    )
                    for expanded_label, expanded_candidate in expanded:
                        identity = path_identity(expanded_candidate)
                        identity.update(
                            {
                                "step_id": step_id,
                                "input_name": expanded_label,
                            }
                        )
                        key_value = (step_id, expanded_label, identity["path"])
                        identities[key_value] = identity
    # Sample descriptors are canonical execution inputs even when a plugin
    # does not repeat them in every step's ``inputs`` mapping.  Include these
    # paths explicitly so changing only the sample sheet cannot leave a stale
    # resume identity looking equivalent.
    sample_fields = (
        "read1",
        "read2",
        "long_reads",
        "pod5",
        "bam",
        "assembly",
        "host_reference",
    )
    for sample in getattr(plan, "samples", ()) or ():
        sample_id = str(getattr(sample, "sample_id", ""))
        for field in sample_fields:
            value = getattr(sample, field, None)
            if not value:
                continue
            for label, candidate in _path_values(field, value):
                identity = path_identity(candidate)
                identity.update(
                    {
                        "step_id": f"__sample__:{sample_id}",
                        "input_name": label,
                    }
                )
                key_value = (f"__sample__:{sample_id}", label, identity["path"])
                identities[key_value] = identity
    return [
        identities[key] for key in sorted(identities, key=lambda item: (item[0], item[1], item[2]))
    ]


def _plan_produced_paths(steps: Iterable[Any]) -> dict[str, int]:
    """Index declared output paths by their producer's plan position.

    ``output_dir`` is deliberately not indexed as a produced path.  A work
    directory can contain user-provided reads or symlinks to those reads.
    """
    produced: dict[str, int] = {}
    for index, step in enumerate(steps):
        outputs = getattr(step, "outputs", {})
        if not isinstance(outputs, Mapping):
            continue
        for key, value in outputs.items():
            if str(key) == "output_dir":
                continue
            values = value if isinstance(value, (list, tuple, set)) else (value,)
            for value in values:
                if not isinstance(value, (str, Path)):
                    continue
                normalized = _normalized_path(value)
                if normalized:
                    produced.setdefault(normalized, index)
    return produced


def _normalized_path(value: str | Path) -> str:
    raw = Path(str(value)).expanduser()
    try:
        return str(raw.resolve(strict=False))
    except OSError:
        return str(raw.absolute())


def _is_prior_plan_output(
    candidate: str | Path,
    *,
    step_index: int,
    produced_paths: Mapping[str, int],
    protected_paths: set[str],
) -> bool:
    normalized = _normalized_path(candidate)
    producer_index = produced_paths.get(normalized)
    return (
        bool(normalized)
        and normalized not in protected_paths
        and producer_index is not None
        and producer_index < step_index
    )


def _expand_directory_input(
    candidate: str | Path,
    *,
    label: str,
    step_index: int,
    produced_paths: Mapping[str, int],
    protected_paths: set[str],
    generated_directories: Mapping[str, int],
) -> Iterable[tuple[str, str | Path]]:
    """Expand aggregate directories when known outputs live below them.

    This removes generated files from the directory-level identity while
    retaining every other present file, including files and symlinks in an
    ABI output directory that were supplied by the user.
    """
    path = Path(str(candidate)).expanduser()
    try:
        root = path.resolve(strict=False)
    except OSError:
        root = path.absolute()
    earliest_producer = generated_directories.get(str(root))
    if earliest_producer is None or earliest_producer >= step_index:
        yield label, candidate
        return
    if not path.is_dir():
        # The aggregate directory is itself a generated input whose declared
        # children do not exist yet.  Do not bind its absence to resume.
        return
    for child in sorted(path.rglob("*"), key=lambda item: str(item)):
        if not child.is_file() and not child.is_symlink():
            continue
        if _is_prior_plan_output(
            child,
            step_index=step_index,
            produced_paths=produced_paths,
            protected_paths=protected_paths,
        ):
            continue
        try:
            relative = child.relative_to(path)
        except ValueError:  # pragma: no cover - path was walked below root
            relative = Path(child.name)
        yield f"{label}[{relative}]", child


def normalize_tool_identities(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Keep only deterministic tool identity fields, in stable order."""
    normalized = []
    for row in rows:
        normalized.append(
            {
                "tool_id": str(row.get("tool_id", "")),
                "executable": str(row.get("executable", "")),
                "env_name": str(row.get("env_name", "")),
                "version": str(row.get("version", "")),
                "status": str(row.get("status", "")),
                "executable_checksum": _executable_checksum(str(row.get("executable", ""))),
            }
        )
    return sorted(normalized, key=lambda row: row["tool_id"])


def normalize_resource_identities(resources: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Normalize resource manifest entries and bind their current contents."""
    normalized = []
    for resource in resources:
        resource_id = str(resource.get("id", ""))
        if resource_id in {
            "auto_download",
            "database_sha256",
            "database_snapshot_id",
            "max_cpus",
            "max_memory",
            "max_time",
        }:
            # These configuration values live under ``resources`` for plugin
            # convenience but are not filesystem identities.
            continue
        path = str(resource.get("path", ""))
        if _is_placeholder_resource(path):
            # Optional plugin resources use stable sentinels such as
            # ``BACANNOT_DB_NOT_CONFIGURED``.  They are not execution inputs;
            # omitting them keeps smoke/offline plans resumable while real
            # missing resources remain explicitly unverified below.
            continue
        identity = path_identity(path) if path else {"exists": False, "checksum_sha256": ""}
        normalized.append(
            {
                "id": resource_id,
                "path": str(identity.get("path", path)),
                "exists": str(bool(identity.get("exists", False))).lower(),
                "checksum_sha256": str(identity.get("checksum_sha256", "")),
                "version": str(resource.get("version", "")),
                "source_url": str(resource.get("source_url", "")),
            }
        )
    return sorted(normalized, key=lambda row: (row["id"], row["path"]))


def normalize_container_identities(
    containers: Iterable[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Keep resolved image references and immutable local digests."""
    normalized = []
    for container in containers:
        normalized.append(
            {
                "tool_id": str(container.get("tool_id", "")),
                "image": str(container.get("image", "")),
                "runtime": str(container.get("runtime", "")),
                "digest": str(container.get("digest", "")),
            }
        )
    return sorted(normalized, key=lambda row: (row["tool_id"], row["image"]))


def build_resume_identity(
    plan: Any,
    *,
    plan_id: str = "",
    tool_rows: Iterable[Mapping[str, Any]] = (),
    resources: Iterable[Mapping[str, Any]] = (),
    containers: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build the canonical identity record for a planned execution."""
    return {
        "schema_version": RESUME_IDENTITY_SCHEMA,
        "plan_id": str(plan_id or ""),
        "inputs": collect_plan_input_identities(plan),
        "tools": normalize_tool_identities(tool_rows),
        "resources": normalize_resource_identities(resources),
        "containers": normalize_container_identities(containers),
    }


def write_resume_identity(identity: Mapping[str, Any], provenance_dir: str | Path) -> Path:
    """Write one canonical, atomically replaceable resume identity artifact."""
    path = Path(provenance_dir) / RESUME_IDENTITY_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(identity), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_resume_identity(path: str | Path) -> dict[str, Any] | None:
    """Load a valid identity record, returning ``None`` for legacy/bad records."""
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, Mapping) or data.get("schema_version") != RESUME_IDENTITY_SCHEMA:
        return None
    if not all(
        isinstance(data.get(key), list) for key in ("inputs", "tools", "resources", "containers")
    ):
        return None
    return dict(data)


def compare_resume_identity(
    current: Mapping[str, Any], previous: Mapping[str, Any] | None
) -> list[str]:
    """Return human-readable reasons why a previous run cannot be reused."""
    if previous is None:
        return ["the prior run has no valid resume identity record"]
    reasons = []
    if str(current.get("plan_id", "")) != str(previous.get("plan_id", "")):
        reasons.append("confirmed plan identity changed")
    for field, label in (
        ("inputs", "external input content changed"),
        ("tools", "tool identity changed"),
        ("resources", "resource identity changed"),
        ("containers", "container image identity changed"),
    ):
        if current.get(field) != previous.get(field):
            reasons.append(label)
    unverified = (
        _unverified_tool_identity(current),
        _unverified_tool_identity(previous),
        _unverified_resource_identity(current),
        _unverified_resource_identity(previous),
        _unverified_container_identity(current),
        _unverified_container_identity(previous),
    )
    for reason in unverified:
        if reason and reason not in reasons:
            reasons.append(reason)
    return reasons


def runtime_resume_identity(
    plan: Any,
    config: Mapping[str, Any],
    registry: Any,
    *,
    smoke: bool = False,
    plan_id: str = "",
    cli_image: str | None = None,
    container_runtime: str | None = None,
    extra_containers: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Capture the identity used by non-local runtime resume preflight."""
    tool_rows: list[dict[str, Any]] = []
    selected = {str(tool_id) for tool_id in getattr(plan, "selected_tools", ())}
    selected.update(
        str(getattr(step, "tool_id", ""))
        for step in getattr(plan, "steps", ())
        if str(getattr(step, "tool_id", "")) not in {"", "internal"}
    )
    try:
        registered = list(registry.list_tools())
    except Exception:  # pragma: no cover - defensive for third-party registries
        registered = []
    from abi.provenance import capture_tool_version

    for tool in registered:
        tool_id = str(tool.get("id", ""))
        if selected and tool_id not in selected:
            continue
        try:
            skill = registry.create(tool_id, mock_tools=smoke)
            version, status = capture_tool_version(skill, mock_tools=smoke)
        except Exception:  # pragma: no cover - an identity failure is fail-closed below
            version, status = "", "not_captured"
        tool_rows.append(
            {
                "tool_id": tool_id,
                "executable": tool.get("executable", ""),
                "env_name": tool.get("env_name", ""),
                "version": version,
                "status": status,
            }
        )

    from abi.workflow.manifest import generate_resource_manifest

    manifest = generate_resource_manifest(
        analysis_type=str(getattr(plan, "analysis_type", "")),
        config=config,
    )
    container_rows = container_image_identities(
        plan,
        registry,
        config=config,
        cli_image=cli_image,
        runtime=container_runtime,
    )
    container_rows.extend(dict(row) for row in extra_containers)
    return build_resume_identity(
        plan,
        plan_id=plan_id,
        tool_rows=tool_rows,
        resources=manifest.resources,
        containers=container_rows,
    )


def validate_stored_resume_identity(
    result_dir: str | Path,
    current: Mapping[str, Any],
    *,
    cache_paths: Iterable[str | Path] = (),
) -> list[str]:
    """Compare a current identity with the last completed runtime identity."""
    root = Path(result_dir)
    identity_path = root / "provenance" / RESUME_IDENTITY_FILENAME
    if not identity_path.exists():
        # ``--resume`` on a brand-new output directory is harmless: there is
        # no cache to reuse yet.  An existing result without this artifact is
        # different; fail closed instead of guessing from output existence.
        evidence = any(
            (root / relative).exists()
            for relative in (
                "execution_plan.json",
                "compiled_plan.json",
                "provenance/run_summary.json",
                "provenance/checksums.json",
                "provenance/resource_manifest.json",
                "provenance/hpc_jobs.json",
                "provenance/nextflow_trace.tsv",
                "snakemake",
                "nextflow",
                "work",
            )
        )
        evidence = evidence or any(Path(path).exists() for path in cache_paths)
        if not evidence:
            return []
    previous = load_resume_identity(identity_path)
    return compare_resume_identity(current, previous)


def _path_values(key: str, value: Any) -> Iterable[tuple[str, str | Path]]:
    """Yield path-like leaves while retaining a useful input label."""
    key_lower = key.lower()
    hinted = any(part in key_lower for part in _PATH_KEY_PARTS)
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            yield from _path_values(f"{key}.{child_key}", child_value)
        return
    if isinstance(value, (list, tuple, set)):
        for index, child in enumerate(value):
            yield from _path_values(f"{key}[{index}]", child)
        return
    if isinstance(value, (str, Path)) and (hinted or Path(str(value)).expanduser().exists()):
        yield key, value


def _executable_checksum(executable: str) -> str:
    """Return a binary digest when the registry resolves an executable locally."""
    if not executable:
        return ""
    candidate = Path(executable).expanduser()
    if not candidate.is_file():
        resolved = shutil.which(executable)
        candidate = Path(resolved) if resolved else candidate
    return checksum_path(candidate) if candidate.is_file() else ""


def _unverified_tool_identity(identity: Mapping[str, Any]) -> str:
    """Reject equal-but-unknown tool captures during resume comparison."""
    rows = identity.get("tools", [])
    if not isinstance(rows, list):
        return "tool identity is unverified"
    for row in rows:
        if not isinstance(row, Mapping):
            return "tool identity is unverified"
        status = str(row.get("status", ""))
        if status != "captured" or not str(row.get("version", "")):
            return "tool identity is unverified"
    return ""


def _is_placeholder_resource(path: str) -> bool:
    normalized = str(path or "").strip().upper()
    return not normalized or any(
        marker in normalized for marker in ("NOT_CONFIGURED", "PLACEHOLDER", "TODO")
    )


def _unverified_resource_identity(identity: Mapping[str, Any]) -> str:
    """Reject missing or checksum-less resources during resume comparison."""
    rows = identity.get("resources", [])
    if not isinstance(rows, list):
        return "resource identity is unverified"
    for row in rows:
        if not isinstance(row, Mapping):
            return "resource identity is unverified"
        if str(row.get("exists", "false")) != "true" or not str(row.get("checksum_sha256", "")):
            return "resource identity is unverified"
    return ""


def _unverified_container_identity(identity: Mapping[str, Any]) -> str:
    """Reject container references whose local immutable digest is unknown."""
    rows = identity.get("containers", [])
    if not isinstance(rows, list):
        return "container image identity is unverified"
    for row in rows:
        if not isinstance(row, Mapping):
            return "container image identity is unverified"
        if str(row.get("image", "")) and not str(row.get("digest", "")):
            return "container image identity is unverified"
    return ""
