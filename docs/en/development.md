# Development Guide

ABI ships as a core distribution, `abi-agent`, plus one distribution per
official analysis plugin, `abi-agent-plugin-<id>` (WP11B: the core wheel is
plugin-free). This page is a map of the codebase and the main extension
points. For the order in which changes should be made and checked, see
`development_workflow.md`.

## Source Tree

```
src/abi/
  agent/              ABIAgentInterface, JSON envelopes, agent context export
  agent_integrations.py  Claude Code, OpenCode, and Codex integration installer/doctor
  report/             write_full_report, write_plugin_report, write_methods,
                      citations, limitations, html — generic report system
  workflow/           ResourceManifest, workflow validation, figure_specs loading
  plugin_registry.py  Core-owned plugin discovery/selection (WP11B step 1) —
                      metadata-only discovery, selected loading, data roots
  plugin_validation.py  Structural plugin validation (plugin-implementation-free)
  plugins/            Built-in analysis plugins — each a self-contained package
                      with co-located data (abi-plugin.yaml, DAG, tool registry,
                      limitations); excluded from the core wheel and shipped as
                      abi-agent-plugin-<id> distributions
    metagenomic_plasmid/   Self-contained plugin package (support lib in lib/, 64 tools, 90-node DAG)
    easymetagenome/        Shotgun metagenomics adapter (10 tools, 25-node DAG)
    viral_viwrap/          Managed external CLI adapter (1 tool, 7-node DAG)
    rnaseq_expression/     Bulk RNA-seq (5 tools, 5-node DAG)
    wgs_bacteria/           Bacterial WGS (5 tools)
    amplicon_16s/          16S microbiome (10 tools)
    metatranscriptomics/   Metatranscriptomics (3 tools)
    wgs_bacannot/          Managed external Bacannot workflow (WP8/11A)
  dag_planner.py      UniversalDAG — declarative plan generation from pipeline_dag.yaml
  tsv_mapping.py      Declarative TSV column mapper — YAML-driven output parsing, 3 source types
  _shared.py          Shared utilities: _read_tsv, _display_command, _plan_dict, _common_overrides
  provenance.py       RunLogger, PipelineProgressRecorder, TSV provenance writers
  tools.py            ToolRegistry, ToolSkill, GenericCommandSkill, SafeFormatDict, RunResult
  schemas.py          Canonical types: SampleInput, ExecutionPlan, PlanStep, SampleContext
  executor.py         GenericABIExecutor — step iteration, tool invocation, contract enforcement.
                      Supports sample-level parallel execution via ThreadPoolExecutor
                      (config.execution.parallel + config.execution.workers).
  dag.py              DAG inference engine — L1 (literature) / L2 (path) / L3 (validation)
  contracts/          WorkflowSpec, step contract enforcement, checksum chaining, assertion eval
  permissions.py      read_only / planning_write / execution levels
  diagnostics.py      Error taxonomy + DiagnosticHint + classify_exception
  interfaces.py       ABIPlugin, ABIDryRunPlugin, ABIInitializablePlugin protocols
  json_utils.py       JSON file/payload loading with ABIJSONError wrapping
  timeouts.py         Timeout parsing: parse_timeout_seconds, timeout_from_env_or_value
  resources.py        Read-only resource checks and readiness reporting:
                      check_resources, setup_resources (report/plan/mock only —
                      downloads and installs belong to an external system)
  tables.py           StandardTableManager
  tool_descriptors.py Unified tool descriptor SSOT (3 format families, 7+ LLM providers)
  jobs/               HTTP Job Service (service, client, force-kill support)
  runtimes/           local, Nextflow, Snakemake, HPC runtimes
  exporters/          Nextflow DSL2 and Snakemake exporters
  mcp/                Optional MCP stdio server (exposed via ``abi-mcp``)
  skills/             Agent skill files → installed via ``abi install-skills``
  cli.py              Typer CLI (abi, abi-mcp entry points)
```

The plasmid engine lives inside the plugin package
(`abi.plugins.metagenomic_plasmid.lib`); the retired `abi.autoplasm`
compatibility shim namespace was removed in WP2 and must not be
reintroduced. Internal code imports the engine from the plugin package and
shared infrastructure from the ABI core modules.

## Public SDK

| Module | Purpose |
| --- | --- |
| `abi.interfaces` | `ABIPlugin`, `ABIDryRunPlugin`, `ABIInitializablePlugin` protocol classes |
| `abi.schemas` | `SampleInput`, `SampleContext`, `PlanStep`, `ExecutionPlan` |
| `abi.tools` | `ToolRegistry`, `ToolSkill`, `GenericCommandSkill`, `RunResult` |
| `abi.provenance` | `RunLogger`, `PipelineProgressRecorder`, TSV provenance writers |
| `abi.contracts.step_contract` | `ContractViolationError`, `validate_output_contract`, `evaluate_assertions`, checksum chaining |
| `abi.contracts` | `WorkflowSpec`, `WorkflowStepSpec`, `load_workflow_spec` — L1/L2/L3 workflow validation |
| `abi.dag` | `infer_dag`, `ABIDAG`, `StepBinding` — DAG inference with literature + path + validation layers |
| `abi.dag_planner` | `UniversalDAG`, `build_plan_from_dag`, `PathTemplateContext` — declarative plan generation, shared by all 7 plugins |
| `abi.tsv_mapping` | `TSVMapper`, `generate_rows` — YAML-driven TSV/JSON/log parsing with 3 source types |
| `abi.errors` | `ABIError`, `ConfigError`, `SampleSheetError`, `ToolError` |
| `abi.diagnostics` | Error taxonomy + `DiagnosticHint` + `classify_exception` |
| `abi.json_utils` | JSON file/payload loading with `ABIJSONError` |
| `abi.timeouts` | `parse_timeout_seconds`, `timeout_from_env_or_value` |
| `abi.tool_descriptors` | `ABI_AGENT_TOOLS`, `TOOL_ALIASES`, `export_openai_compatible`, `export_anthropic`, `export_gemini`, `PROVIDER_PROFILES` |
| `abi.testing` | `assert_plugin_contract` |

## Local Setup

```bash
pip install -e ".[dev]"
```

Useful checks:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/abi/ --ignore-missing-imports
pytest tests/ -v --tb=short
```

`mypy` is intentionally scoped to `src/abi/`; the bundled pipeline is covered by
runtime tests and ruff first, with stricter typing left for later hardening.

## Agent Integration Development

Treat `integrations/<platform>/abi/` as the source of truth for platform-native
assets. `abi agent install` copies those assets into the target project or user
configuration, while `abi agent doctor` validates the installed skill, MCP
configuration, command availability, and safe-server initialization without
changing files.

When changing an integration:

1. Keep Claude Code, OpenCode, and Codex behavior aligned unless a platform has a
   documented constraint.
2. Run `abi agent install <platform> --scope project --project-dir <tmp-dir>` and
   the matching `abi agent doctor` command for all three platforms.
3. Run the native validator when the installed client exposes one: currently
   `claude plugin validate` for Claude Code. Codex releases without a local
   `plugin validate` subcommand rely on the manifest and asset regression tests.
4. Run `python -m build`, install the wheel with its `[mcp]` extra, and repeat
   install/doctor with the command from the clean wheel environment. Source-tree
   success alone does not prove the assets or MCP runtime were packaged correctly.
5. Keep `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` versions equal
   to `project.version`; `scripts/check_release_identity.py` enforces this.

`integrations/` is a package and Docker build input. It must remain in the sdist,
wheel, and every Docker `/app` context. Changes under it should receive a
recommended manual Docker workflow validation before a container release; they
do not trigger an automatic image build.

## Runtime Contract Enforcement

The generic executor enforces the step-level contract embedded in each
`PlanStep.params["_contract"]`. The DAG-driven planner copies this block from
`pipeline_dag.yaml`, so the DAG remains the source of truth for outputs and
runtime assertions.

Execution-time contract handling follows this order:

1. Verify upstream input checksums against `provenance/checksums.json`.
2. Run the external tool.
3. Resolve actual output files from `output_dir` when planned paths are abstract.
4. Validate output contracts and record output checksums.
5. Evaluate assertions against the resolved outputs.

Output validation supports file/directory existence, `min_size`, `extensions`,
directory `contains`, directory/file `min_files`, FASTA `min_contigs`, JSON
`required_keys`, and dotted JSON `schema` constraints.

Two executor details are intentional and should be preserved:

- `output_dir` itself is not pre-created. Some assemblers and workflow tools
  fail if their output directory already exists. The executor only creates its
  parent directory and any unrelated file-output parents.
- Actual-output resolution is deterministic and read-pair aware. If a tool
  writes `S1_R1.clean.fastq.gz` and `S1_R2.clean.fastq.gz` while the plan holds
  abstract paths such as `S1.fastp.clean_read1`, contract checks use the real
  R1/R2 files.

Regression coverage lives in `tests/unit/test_executor.py` and
`tests/unit/test_step_contract.py`.

## Runtime Assets

Small source assets are tracked:

- `config/`
- `envs/` — generated from `environments.yaml` via `scripts/emit_env_yamls.py`
- `skills/` (inside ``src/abi/skills/`` — bundled with the package, installed via ``abi install-skills``)
- `src/abi/plugins/<id>/` — co-located plugin data (DAG, tool registry, limitations); ships in the `abi-agent-plugin-<id>` distributions
- `integrations/` — platform-native Claude Code, OpenCode, and Codex bundles
- `examples/`
- `scripts/`

Large or generated runtime state is ignored:

- `.mamba/`
- `resources/`
- `results/`
- `logs/`
- Nextflow and Snakemake work directories

Tool execution resolves environments via ``abi.config.resolved_mamba_root()``
with this priority:

1. Explicit CLI/API root
2. ``ABI_MAMBA_ROOT`` and ``MAMBA_ROOT_PREFIX``
3. ``AUTOPLASM_MAMBA_ROOT`` (legacy compatibility)
4. Populated repository-compatible roots
5. Global Micromamba/Mamba/Conda metadata
6. Linux user data root

The ``env_name`` for each tool is resolved at runtime from ``environments.yaml``.
The current manifest declares 21 Conda environments and 99 tool-to-environment
assignments; code and documentation should derive these inventories from the
manifest rather than duplicating them.

### Parallel Execution

``GenericABIExecutor`` supports sample-level parallel execution via
``ThreadPoolExecutor`` when ``config.execution.parallel`` is set to ``true``:

```yaml
execution:
  parallel: true
  workers: 8
  batch_size: 8  # optional strict sample-batch barrier
```

With the ``local`` engine, samples run concurrently; steps within each sample
remain serial respecting DAG topological order. When ``batch_size`` is set, the
local executor waits for every sample
in the batch to finish its analysis phase, runs steps marked as batch cleanup,
and only then starts the next batch. Omitting it preserves unbounded sample
queueing up to ``workers``. Other engines do not currently implement this batch
barrier. Thread safety is maintained via ``threading.Lock``
for ``StandardTableManager``, ``PipelineProgressRecorder``, and ``RunLogger``.

## Agent Interfaces

`ABIAgentInterface` is the transport-neutral boundary. Keep CLI JSON (``--output-json``),
MCP (``abi-mcp``), OpenAI descriptors (``abi export-openai-tools``), Skills
(``abi install-skills``), ``abi dispatch``, and Job Service behavior aligned with it.

Plugins join this interface through discovery and the shared `analysis_type` argument; they do not add transport-specific lifecycle tools.

See the [Plugin Development Guide](plugin_development_guide.md) for the required Agent context, safety, result, and test contracts.

Execution must remain gated: `abi run`, `abi_run`, and Job Service execution
submissions should return `confirmation_required` unless explicit confirmation
is passed.

### Agent-Facing Commands

| Command | Purpose |
|---------|---------|
| `abi list-types --output-json` | Discover installed plugins |
| `abi query --type <plugin> --what stages` | Lightweight pipeline metadata (~50ms) |
| `abi export-agent-context --type <plugin>` | Machine-readable operating context |
| `abi doctor-agent --type <plugin>` | Human-readable operating guide |
| `abi check-resources --type <plugin>` | Check resource/database availability |
| `abi setup-resources --type <plugin> --confirm` | Auto-install/setup resources |
| `abi install-skills` | Install SKILL.md files to `~/.claude/skills/abi/` |
| `abi agent install <platform>` | Install a Claude Code, OpenCode, or Codex integration |
| `abi agent doctor <platform>` | Read-only validation of an installed integration |
| `abi export-openai-tools --type <plugin>` | OpenAI function-calling descriptors |
| `abi-mcp` | Start MCP stdio server |

### Python Agent API

```python
import abi
abi.get_agent_guide()          # returns compact operating guide (str)
abi.list_plugins_summary()     # returns list[dict] of (analysis_type, name, description)
```

### MCP Compatibility

- ABI targets MCP protocol `2026-07-28` through MCP Python SDK 2.x. The adapter
  uses `MCPServer`, returns structured JSON envelopes, supplies standard tool
  behavior annotations, and supports stdio plus opt-in stateless Streamable HTTP.
