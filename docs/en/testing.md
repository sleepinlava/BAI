# ABI Testing Guide

Test counts and coverage move with the code, so use the latest CI run for current numbers. This page
explains where tests belong, which commands are useful locally, and what CI requires.

## Test layout

| Layer | Location | Purpose | External tools |
| --- | --- | --- | --- |
| Unit | `tests/unit/` | Core logic, schemas, parsers, contracts, runtimes | No |
| Integration | `tests/integration/` | CLI/core boundaries, dry-runs, golden traces | Normally no |
| Smoke | `tests/smoke/` | Real tools and value-level workflow checks | Usually yes |
| SciPlot | `src/abi/sciplot/tests/` | Schema, renderer, lint, CLI/API, Unicode layout | Report dependencies |

Name files `test_<feature>.py` and functions `test_<behavior>`. Every behavior change should come
with a regression test. Tests that run external tools use `@pytest.mark.smoke`,
`@pytest.mark.requires_tools`, or both.

## Local commands

```bash
# Main suite
pytest tests/ -v --tb=short

# CI-like suite without external tools
pytest tests/ src/abi/sciplot/tests/ -v --tb=short \
  --strict-markers -m "not requires_tools"

# Focused module
pytest tests/unit/test_dag_planner.py -q

# Real-tool tests only
pytest tests/ -v -m requires_tools

# Branch-aware global gate
pytest tests/ src/abi/sciplot/tests/ \
  --strict-markers -m "not requires_tools" \
  --cov=src/abi --cov-branch --cov-report=term \
  --cov-report=json:coverage.json --cov-fail-under=75
python scripts/check_module_coverage.py --coverage coverage.json
```

The CI floor is 75% plus risk-based per-module line/branch gates. Do not put a
fixed measured percentage or test count in maintained guidance.

## Shared fixtures

`tests/conftest.py` currently provides:

- `mock_sample`;
- `mock_sample_context`;
- `mock_contract_dict`;
- `tmp_project`;
- an autouse fixture that isolates mamba/resource-root environment variables.

Keep reusable fixtures there. Use `tmp_path` for filesystem writes and restore
environment/global state through pytest fixtures.

## Plugin contract gates

Every built-in plugin must:

1. satisfy the Python plugin protocol checked by `assert_plugin_contract`;
2. load its registry and standard-table schemas;
3. have a declarative `pipeline_dag.yaml`;
4. provide a contract for every external-tool output, or a justified explicit
   exemption;
5. ship a non-empty `limitations.yaml`.

Run strict lint for all built-ins:

```bash
for plugin in \
  amplicon_16s easymetagenome metagenomic_plasmid metatranscriptomics \
  rnaseq_expression viral_viwrap wgs_bacteria
do
  abi contract-lint --type "$plugin" --strict
done

python scripts/audit_contract_coverage.py
```

Strict lint turns warnings into failures and also enforces missing/invalid/empty
limitations declarations and output-contract coverage.

## Golden traces

Golden traces are stored at the repository root:

```text
golden_traces/
├── amplicon_16s.jsonl
├── metagenomic_plasmid.jsonl
├── metatranscriptomics.jsonl
├── rnaseq_expression.jsonl
└── wgs_bacteria.jsonl
```

They currently cover five workflow families, not all seven built-ins. Replay
them with:

```bash
pytest tests/integration/test_golden_traces.py -q
```

When a deliberate plan change modifies a trace, review the semantic diff before
updating the fixture. Do not regenerate traces merely to make a test pass.

## Smoke and benchmark tests

`tests/smoke/test_*_benchmark.py` contains real-tool checks for the original five
workflow families, and `abi.testing.benchmark` provides a generic
`expected_assertions.yaml` evaluator. The current repository checkout does not
ship a complete `data/benchmarks/` fixture tree. Before running those tests,
verify that the required dataset, expected assertions, tools, databases, and
environment variables are provisioned. CI excludes `requires_tools` tests from
the default quality gate.

EasyMetagenome and ViWrap are covered by contract, dry-run, integration, and
release wheel smoke paths, but do not currently have the same checked-in
value-level benchmark fixture shape as the original five.

## CI and release surface

The repository intentionally keeps four workflows:

- `ci.yml`: Python 3.10–3.13 lint/format/mypy, tests, 3.12 coverage, strict
  contract lint, docs, Compose validation, package build, wheel smoke, and a
  migration gate;
- `docker.yml`: automatic amd64 builds for amplicon, RNA-seq, WGS, and
  metatranscriptomics; plasmid is manual-only; registry pushes enable
  provenance/SBOM and are multi-platform except RNA-seq;
- `release.yml`: reusable CI gate, build, Twine check, clean-wheel smoke, and
  GitHub Release creation;
- `publish-pypi.yml`: download the exact GitHub Release artifacts and publish
  with PyPI Trusted Publishing.

For CI/Docker/build-input changes run:

```bash
pytest tests/unit/test_docker_configuration.py -q
docker compose -f docker/docker-compose.yml config --quiet
python -m build
```

For documentation changes run:

```bash
bash docs/build_docs.sh
```

## Before review

Python changes require Ruff, formatting, mypy, focused pytest, and affected
integration tests. Plugin changes additionally require strict contract lint,
dry-run validation, and relevant smoke tests. Release and Docker changes have
the additional gates described in the
[development workflow](development_workflow.md) and [release guide](release.md).

Record commands and results in the pull request. If a real-tool, container, or
cluster check cannot run, state that explicitly and describe the remaining
risk.
