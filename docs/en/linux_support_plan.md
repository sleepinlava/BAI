# Linux Support and Delivery Plan

## Support contract

ABI targets native Linux installation and agent operation without requiring
Docker. The core package supports Linux x86_64 and arm64; third-party
bioinformatics tools are certified per plugin and architecture.

| Surface | Linux support |
|---|---|
| Python package, CLI, MCP, SciPlot, planning, inspection, and reporting | Required on x86_64 and arm64 |
| Managed Conda/Mamba environments | Required where declared packages solve |
| External bioinformatics tools | Certified per plugin and architecture |
| Docker images | Optional, manual Linux deployment artifacts |

Non-Linux operating systems are outside the active development and
certification scope. “Supported” means that a clean Linux machine can install
the wheel, discover or create runtime environments, explain every selected
executable and interpreter, and complete the relevant smoke tests.

## Implemented foundation

The shared `abi.runtime_environment` resolver now owns Linux runtime discovery.
`abi.config`, the plasmid engine, local tool execution, runtime locks, and the
Nextflow exporter delegate environment-prefix selection to this shared layer.

Mamba root precedence is:

1. Explicit CLI/API `mamba_root`.
2. `ABI_MAMBA_ROOT`.
3. `MAMBA_ROOT_PREFIX`.
4. The legacy `AUTOPLASM_MAMBA_ROOT`.
5. Populated repository-compatible roots.
6. A populated `${XDG_DATA_HOME:-~/.local/share}/abi/mamba`.
7. A global `micromamba`, `mamba`, or `conda` installation reported by
   `<solver> info --json`.
8. An empty/default `${XDG_DATA_HOME:-~/.local/share}/abi/mamba`.

Explicit paths are authoritative and fail when missing. Named environments
prefer `<root>/envs/<name>`, retain `<root>/<name>` compatibility, and can use
prefixes reported by the selected solver. Executables resolve in this order:
explicit path, assigned environment, registry resource directories, then
global `PATH` when allowed. ABI-internal Python uses `sys.executable`; tool
Python uses its assigned environment first.

Operators can inspect this behavior without running an analysis:

```bash
abi env discover --output-json
abi env doctor --tool fastp --tool samtools --output-json
```

The report records Linux architecture, ABI Python, Mamba root and source,
environment prefixes, requested tool paths, Python paths, and health issues.

## Portable environment installation

ABI can now create or update packaged environments without a source checkout:

```bash
abi env install --type rnaseq_expression --dry-run --output-json
abi env install --type rnaseq_expression
abi env update --env rnaseq --output-json
```

The installer selects `micromamba`, `mamba`, then `conda`, or honors an explicit
`--solver`/`ABI_ENV_SOLVER`. It records the solver path and version, generated
specification SHA-256, exact argument-vector command, target prefix, and whether the
operation created, updated, or left an environment unchanged. Plugin selection is
deduplicated to its assigned environments.

The default writable root is `${XDG_DATA_HOME:-~/.local/share}/abi/mamba`; explicit
CLI and environment roots remain authoritative. Solver children retain Linux dynamic
library variables but receive no host `PYTHONPATH`. Installation is idempotent, update
uses pruning, failed solves do not publish an unapplied specification, and `--dry-run`
does not create the target root.

The wheel smoke test exercises this path with the packaged `environments.yaml`, proving
that it does not depend on repository-local `envs/*.yml`.

## Remaining delivery phases

### Phase 3 — plugin capability matrix

- Add Linux architecture constraints to tool/environment metadata.
- Solve every `envs/*.yml` on Linux x86_64 and Linux arm64.
- Classify every plugin/architecture cell as `certified`, `partial`, or
  `unsupported`, listing blockers and supported alternatives.
- Add representative real-tool smoke tests for every certified cell.
- Make `abi env doctor --type <plugin>` reject unsupported combinations before
  execution.

Exit criterion: every plugin publishes an honest, machine-readable Linux
capability status and certified cells pass real-tool validation.

### Phase 4 — Linux CI certification

The required CI matrix will cover:

- Python 3.10–3.13 editable and wheel installation;
- Linux x86_64 core tests on every supported Python;
- Linux arm64 wheel, CLI, MCP, and representative environment smoke tests;
- SciPlot font/rendering checks;
- repository-local, user-scoped, and global Mamba discovery;
- assigned-environment and global `PATH` tools;
- paths containing spaces and symlinks;
- runtime-lock reproducibility and provenance assertions.

Routine CI uses small representative environments. Large databases and long
real-tool workflows remain scheduled or manually approved acceptance jobs.
Docker image construction is not part of the required matrix.

Exit criterion: required Linux jobs pass for two consecutive releases and the
capability matrix is attached to release evidence.

### Phase 5 — release and operations

- Publish clean-machine Linux installation and troubleshooting guides.
- Cover solver selection, fonts, R/Bioconductor, Java, native libraries,
  architecture mismatches, and database locations.
- Verify the published wheel on fresh x86_64 and arm64 environments.
- Record wheel hashes, architecture, Python/solver versions, environment root,
  entry-point results, and representative plugin smoke results.

## Manual Docker policy

`.github/workflows/docker.yml` has only `workflow_dispatch`; pull requests,
pushes, tags, and releases never start image builds. A manual build is
recommended when container inputs change and is required before publishing a
container image. It is not a Python/plugin or PyPI gate.

```bash
gh workflow run docker.yml --ref master \
  -f plugin=rnaseq -f push=false -f push_to_dockerhub=false
```

For publication, select the verified `v<version>` tag as the workflow ref,
first record a successful `push=false` run, and then rerun the same tag with
`push=true`. The workflow repeats local build and `abi list-types` validation
before registry mutation.

## Definition of done

Linux support is complete when:

- clean wheel installation works without Docker or a source checkout;
- Mamba roots, prefixes, tools, and Python interpreters resolve
  deterministically and are reported by `abi env doctor`;
- x86_64 and arm64 core CI is green for two consecutive releases;
- each plugin publishes its Linux capability status;
- certified plugins pass representative real-tool smoke tests; and
- runtime locks, provenance, and bilingual documentation preserve the selected
  paths, versions, limitations, and verification evidence.
