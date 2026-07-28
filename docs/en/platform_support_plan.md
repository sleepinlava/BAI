# Linux and macOS Support Plan

## Goal and support contract

ABI will support installation and core agent operation on Linux and macOS without
requiring Docker. Container images remain an optional deployment artifact, not an
installation prerequisite.

The target support tiers are:

| Surface | Linux | macOS |
|---|---|---|
| ABI Python package, CLI, MCP server, SciPlot, planning, inspection, and reporting | Required on x86_64 and arm64 | Required on Intel and Apple silicon |
| Managed Conda/Mamba environments | Required where declared packages are available | Required per certified plugin/tool |
| External bioinformatics tools | Certified per plugin and architecture | Certified per plugin and architecture; Linux-only tools must report a clear limitation or supported alternative |
| Docker images | Optional, manually built Linux containers | Optional through a Linux container runtime; not native macOS execution |

“Supported” means a clean machine can install the wheel, discover or create its
runtime environments, explain every resolved executable and Python interpreter,
and complete the appropriate smoke tests. It does not mean that every third-party
bioinformatics binary is available on every architecture.

## Current baseline

ABI already packages `environments.yaml`, supports both
`<mamba-root>/<env-name>` and `<mamba-root>/envs/<env-name>`, prepends a managed
environment's `bin` directory to `PATH`, and records runtime information in
locks and provenance. `ABI_MAMBA_ROOT` is the explicit override, while
`AUTOPLASM_MAMBA_ROOT` remains a compatibility alias.

The remaining gap is portability assurance: root discovery is currently biased
toward repository-adjacent directories, platform/tool compatibility is not yet
expressed as a machine-readable matrix, and clean Linux/macOS installation is
not yet certified by a complete CI matrix.

## Deterministic runtime discovery

Implement one transport-neutral resolver and use it from the CLI, executor,
runtime lock, exporters, resource checks, and plugin adapters. Resolution must
be deterministic and visible to the user.

Mamba root precedence:

1. An explicit CLI or API `mamba_root`.
2. `ABI_MAMBA_ROOT`.
3. `MAMBA_ROOT_PREFIX`.
4. The active Conda/Mamba installation reported by `micromamba info --json`,
   `mamba info --json`, or `conda info --json`.
5. ABI-managed user data locations:
   `${XDG_DATA_HOME:-~/.local/share}/abi/mamba` on Linux and
   `~/Library/Application Support/abi/mamba` on macOS.
6. Existing repository-local compatibility candidates.

Environment prefix precedence:

1. An explicit prefix recorded for the environment.
2. `<mamba-root>/envs/<env-name>`.
3. `<mamba-root>/<env-name>`.
4. Prefixes returned by the selected Conda/Mamba installation.

Executable precedence:

1. An explicit absolute executable in configuration.
2. The assigned ABI environment.
3. Registry-declared resource directories.
4. The system `PATH`, only when the tool policy permits a system installation.

Python steps must default to the Python interpreter belonging to their assigned
environment; ABI-internal steps must use `sys.executable`. Every run must record
the selected root, environment prefix, executable path, interpreter path,
version, platform, architecture, and discovery source.

Invalid explicit configuration must fail with an actionable message. ABI must
not silently choose another root when the user supplied `--mamba-root` or
`ABI_MAMBA_ROOT`.

## Delivery phases

### Phase 1 — platform contract and resolver

- Add typed models for platform, architecture, environment root, prefix, and
  executable resolution.
- Move all duplicate root/prefix logic into `runtime_environment.py`.
- Add `abi env discover --output-json` and `abi env doctor`.
- Include the resolution trace in runtime locks and provenance.
- Test paths containing spaces, symlinks, missing prefixes, stale environments,
  and Intel/Apple-silicon architecture differences.

Exit criterion: identical resolution rules are used by local, Nextflow,
Snakemake, HPC, CLI, MCP, and plugin execution paths.

### Phase 2 — portable installation

- Define user-scoped, system-independent install locations.
- Add idempotent environment creation/update commands using a discovered
  Micromamba, Mamba, or Conda executable.
- Prevent host `PYTHONPATH` leakage while preserving required dynamic-library
  paths on Linux and macOS.
- Verify wheel contents and all CLI entry points from a clean virtual
  environment.

Exit criterion: a machine with Python 3.10+ and a supported Conda-family solver
can install ABI without a repository checkout or Docker.

### Phase 3 — plugin capability matrix

- Add OS and architecture constraints to tool/environment metadata.
- Solve every `envs/*.yml` on Linux x86_64, Linux arm64, macOS Intel, and macOS
  Apple silicon where a runner is available.
- Classify each plugin as `certified`, `partial`, or `unsupported` for each
  target, with the blocking tools and alternatives listed.
- Add representative real-tool smoke tests for every certified cell.

Exit criterion: `abi doctor` rejects unsupported combinations before execution
and links the limitation to the affected tool or plugin.

### Phase 4 — CI certification

Run the Python package and agent test matrix on Linux and macOS, including:

- editable and wheel installation;
- CLI and MCP entry-point smoke tests;
- SciPlot rendering with bundled or documented fonts;
- environment discovery with repository-local and global Mamba layouts;
- global `PATH` tools and assigned-environment tools;
- paths containing spaces;
- runtime-lock reproducibility and provenance assertions.

Use small representative environments in routine CI. Keep large databases and
long real-tool workflows in scheduled or manually approved acceptance jobs.
Docker image construction is not part of this required matrix.

Exit criterion: all required Linux/macOS jobs pass for two consecutive releases,
and the support matrix is published with the release.

### Phase 5 — release and operations

- Add Linux and macOS clean-machine installation recipes.
- Publish troubleshooting for solver selection, Apple silicon, Rosetta, fonts,
  R/Bioconductor, Java, native libraries, and database locations.
- Make the support matrix and unresolved limitations part of release review.
- Verify package installation on fresh machines after publication.

Exit criterion: release evidence contains the wheel hash, OS/architecture,
Python and solver versions, resolved environment root, entry-point results, and
representative plugin smoke results.

## Manual Docker policy

`.github/workflows/docker.yml` has only `workflow_dispatch`; pull requests,
branch pushes, tags, and GitHub Releases do not start image builds.

A manual build is recommended when Dockerfiles, `.dockerignore`,
`environments.yaml`, `envs/*.yml`, packaged plugin definitions, or container
runtime scripts change, and before publishing container images. It is not a
required gate for ordinary Python/plugin development or PyPI publication.

From GitHub Actions, select **Docker → Run workflow**, choose a plugin (or
`all`), and leave publishing disabled for validation. The equivalent CLI
commands are:

```bash
gh workflow run docker.yml --ref master \
  -f plugin=rnaseq -f push=false -f push_to_dockerhub=false

gh workflow run docker.yml --ref master \
  -f plugin=all -f push=false -f push_to_dockerhub=false
```

For a container release, select the exact verified `v<version>` tag as the
workflow ref and first complete a `push=false` validation run. Then rerun the
same tag with `push=true`; the workflow repeats the local build and
`abi list-types` smoke test before it publishes `latest` and immutable semver
tags. Publishing from a branch or a non-version tag is rejected. Enable
`push_to_dockerhub` only when the repository secrets and target namespace have
been verified.

## Definition of done

Linux/macOS support is complete when:

- the core CI matrix passes on both operating systems and supported
  architectures;
- a clean wheel install works without Docker or a source checkout;
- Mamba roots, environment prefixes, global tools, and Python interpreters are
  resolved deterministically and reported by `abi env doctor`;
- each plugin publishes an honest platform capability status;
- certified plugins pass representative real-tool smoke tests;
- runtime locks and provenance preserve the selected paths and versions; and
- the bilingual installation, troubleshooting, and release documentation stays
  synchronized.
