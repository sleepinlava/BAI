# ABI developer guide for Claude Code

Read `AGENTS.md` for repository, release, Docker, runtime-lock, and cloud-secret rules.
`ABI_REFACTOR_PLAN.md` section 15 is the current refactor status; older sections are history.
Use actual source and current CI results for test counts and supported capabilities.

## Development commands

```bash
pip install -e ".[dev,docs]"
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/abi/ --ignore-missing-imports
pytest tests/ -v --tb=short --strict-markers -m "not requires_tools" \
  --cov=src/abi --cov-branch --cov-report=json:coverage.json --cov-fail-under=75
python scripts/check_module_coverage.py --coverage coverage.json
python scripts/migration_gate.py
bash docs/build_docs.sh
python -m build
python scripts/build_plugin_wheels.py --outdir dist-plugins --build
python scripts/verify_install_forms.py --dist-dir dist --plugin-dist-dir dist-plugins
python -m twine check dist/* dist-plugins/*.whl
abi list-types
abi query --type metagenomic_plasmid --what stages
abi contract-lint --type metagenomic_plasmid --strict
```

The product suite excludes the git-ignored local paper figure reproduction task. See
`docs/en/testing.md` for explicitly running that research task with external dependencies.
Frozen platform evidence tests remain mandatory. Dry-runs and synthetic fixtures do not
certify scientific results or real scheduler termination.

## Architecture and ownership

Keep transport-neutral behavior in `src/abi/`. CLI, MCP, HTTP jobs, and provider adapters
call the shared core. Core modules include `workflow/`, `executor.py`, `dag_planner.py`,
`tools.py`, `contracts/`, `provenance.py`, `resume.py`, `audit.py`, `results.py`, and `report/`.
The four runtimes are `local`, `nextflow`, `snakemake`, and `hpc`; containers are an execution
option, not a fifth runtime. Runtimes must check locally provisioned tools and images.
ABI does not install environments, download databases, or pull missing images.

Eight optional plugin distributions contain their implementation and co-located YAML,
contracts, scripts, schemas, and limitations in `src/abi/plugins/<analysis_type>/`:
`metagenomic_plasmid`, `easymetagenome`, `rnaseq_expression`, `wgs_bacteria`,
`wgs_bacannot`, `amplicon_16s`, `metatranscriptomics`, and `viral_viwrap`.
The core wheel has no analysis plugins or scientific-computing dependencies.
Each plugin requires the exact matching core version. Plugin builds and entry points are
maintained in `scripts/build_plugin_wheels.py`.

Study, SciPlot, the old `autoplasm` CLI/import tree, and the old execution engine are retired.
Plasmid-specific helpers live under `src/abi/plugins/metagenomic_plasmid/lib/`.
Do not restore parallel execution paths or make core safety/audit optional. Scientific
figures are an external consumer of structured results; comparison and network calculations
remain analysis operations. Historical result tables remain readable.

## Behavior contracts

`ABIAgentInterface` returns JSON envelopes with `success`, `confirmation_required`, or
`error`; failures include diagnostic guidance. Preserve these permission boundaries:

- Read-only discovery, inspect, query and result validation do not execute tools.
- Planning and dry-run write plans/provenance; reports write audit artifacts.
- Real execution requires explicit confirmation and is bound to the confirmed plan.

`tool_descriptors.py` is the common provider/MCP tool metadata definition. Update it when
changing the agent surface. Use `abi._shared` utilities rather than copying their logic.

The planner reads `pipeline_dag.yaml`; external tool nodes require output contracts or
explicit justified exemptions. Plugins must have non-empty `limitations.yaml` and reports
must disclose limitations. Use internal handlers for Python computation and TSVMapper for
simple normalization. Keep `wgs_bacannot`'s external Nextflow adapter distinct from the
shared generic execution path.

Tool execution checks installation, inputs, output contracts, checksums, and assertions.
Preserve input protection, archived run evidence, and independent historical audit even
when the analysis plugin is unavailable. Resume binds external inputs and runtime identity;
upstream-generated intermediates must not be mistaken for external inputs. A cancel request
is not proof of termination: record observed process/scheduler evidence separately.

Jobs run either in worker threads or `abi dispatch` subprocesses. In-process cancellation
is cooperative; subprocess cancellation uses SIGTERM/SIGKILL. Tests should synchronize worker
state and assert observed outcomes, including successful completion racing with cancellation.

## Adding or changing a plugin

1. Implement the ABIPlugin protocol in its co-located package.
2. Add its manifest, DAG, registry, result schemas, limitations, and contracts.
3. Use shared DAG planning, handlers, result writers and thin adapters.
4. Declare scientific dependencies and any runtime assets in its distribution.
5. Validate plugin contracts, strict lint, dry-run, focused integration tests and installation.

Keep `environments.yaml` and generated `envs/*.yml` synchronized. Conda specifications,
examples and deployment scripts remain in the sdist and Docker context for external use;
they are not core wheel assets. Resource checks report readiness and external preparation
requirements without promising nonexistent setup scripts.

## Maintained documentation

- `docs/en/development_workflow.md` and `docs/zh/development_workflow.md`: development gates.
- `docs/en/testing.md` and `docs/zh/testing.md`: product and real-tool tests.
- `docs/en/plugin_development_guide.md`: plugin SDK and contracts.
- `docs/en/workflow_validation.md`: scientific evidence requirements.
- `docs/en/runtime_locks.md` and `docs/zh/runtime_locks.md`: release-scope runtime certification.
- `docs/en/release.md` and `docs/zh/release.md`: immutable release identities and publishing.

Keep both language builds at zero diagnostics. Release checks must cover the complete core
sdist/wheel and eight plugin wheels, clean installation forms, version/dependency identity,
and the SHA-256 manifest both before attaching assets and after downloading them for PyPI.
The four GitHub workflows and Trusted Publishing identity are governed by `AGENTS.md`.
