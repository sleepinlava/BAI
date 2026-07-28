# Release Guide

This repository publishes one PyPI distribution, `abi-agent`. A release is built from a verified
`master` commit and keeps the Git tag, package version, GitHub Release, and PyPI artifacts tied to
the same identity.

## Pre-Release Checks

Start with the consolidated release check:

```bash
scripts/release_check.sh
```

Before pushing a candidate, confirm that `CHANGELOG.md` contains the exact `project.version` from
`pyproject.toml`. CI enforces this through `scripts/check_release_identity.py`, which also compares
the Claude Code and Codex plugin manifests with the package version.

Choose a version that is absent from both PyPI and remote Git tags. Tags and
PyPI versions are immutable identities: never move or reuse a tag after it has
been pushed. If a tag points to mismatched package metadata, abandon that
version and increment again. Historical example: `1.5.4` was abandoned because
its tag was created against `1.5.3` metadata. Later versions must still be
checked independently; never infer availability from that example.

The release policy requires the tag to point at the verified `master` commit.
This is a release-operator precondition: `release.yml` validates tag/package
identity and reuses CI, but it does not itself prove that the tagged commit is
the current `master` tip. Verify ancestry and remote tag absence before pushing.

The script creates a POSIX temporary directory under `/tmp` by default and
exports `TMPDIR`, `TMP`, and `TEMP` before running tests. This keeps
permission-sensitive checks off WSL/Windows-mounted temporary directories. Use
`ABI_RELEASE_TMPDIR` or `ABI_RELEASE_TMP_ROOT` to override the location.

The script runs the local Python/package subset below:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/abi/ --ignore-missing-imports
python -m pytest tests/ src/abi/sciplot/tests/ -v --tb=short \
  --strict-markers -m "not requires_tools" --capture=no \
  --cov=src/abi --cov-branch --cov-report=term-missing:skip-covered \
  --cov-report=xml --cov-report=json:coverage.json --cov-fail-under=75
python scripts/check_module_coverage.py --coverage coverage.json

python -m build
abi query --type metagenomic_plasmid --what stages
```

It does not replace every release-surface gate. Run `bash docs/build_docs.sh`,
`docker compose -f docker/docker-compose.yml config --quiet`, the Docker
configuration regression test, strict contract lint for all seven plugins, and
`python -m twine check dist/*` separately. Run applicable real-tool acceptance
checks, and run container acceptance only when container inputs changed or an
image will be published. The GitHub release workflow reruns the reusable CI
gate before creating a Release.

After building a wheel, install it with its `[mcp]` extra and smoke-test the
installed commands in a clean environment when possible:

```bash
abi list-types
abi query --type metagenomic_plasmid --what stages
abi query --type rnaseq_expression --what tools
autoplasm --help
abi dry-run --type metagenomic_plasmid --config examples/config_minimal.yaml --profile dry_run
abi doctor-agent --type metatranscriptomics
abi export-openai-tools --type metatranscriptomics --format json
abi install-skills --target /tmp/abi-smoke-skills
abi-mcp --help 2>/dev/null || python -m abi.mcp.server --help 2>/dev/null || true
for platform in claude-code opencode codex; do
  abi agent install "$platform" --scope project --project-dir "/tmp/abi-release-agent-$platform"
  abi agent doctor "$platform" --scope project --project-dir "/tmp/abi-release-agent-$platform"
done
```

Run this with the clean wheel environment's `bin` directory on `PATH`, because
the doctor verifies the installed `abi-mcp` entry point. `integrations/` is a
release input: it must be present in both distributions and every Docker `/app`
context. When it or another container input changes, a manual Docker workflow
run is recommended before a container release.

## GitHub Actions

- `ci.yml` runs lint, format check, mypy, tests, and a build check.
- `docker.yml` is manual-only. It builds and smoke-tests a selected plugin (or
  all plugins) and publishes only when the operator explicitly enables `push`.
  Registry pushes include provenance and SBOM; non-push validation loads a
  stable local image without attestations. Published images are multi-platform
  except RNA-seq, which remains `linux/amd64`-only until its R/DESeq2
  environment passes a native arm64 build and smoke test.
- `release.yml` builds distributions, creates a GitHub Release for `v*` tags,
  and emits the published event.
- `publish-pypi.yml` downloads those exact Release artifacts and publishes
  them through PyPI Trusted Publishing. PyPI binds the OIDC identity to this
  filename, so it remains required.

No optional bot or duplicate publishing workflow belongs in `.github/workflows/`.
The required workflow set is exactly `ci.yml`, `docker.yml`, `release.yml`, and
`publish-pypi.yml`.

The canonical automatic chain is:

```text
verified master commit → v<version> tag → reusable CI quality gate
→ build and smoke-test wheel/sdist → GitHub Release with exact artifacts
→ top-level release.published event starts publish-pypi.yml
→ download Release artifacts → PyPI Trusted Publishing
```

Do not call `publish-pypi.yml` as a reusable workflow: PyPI does not support the
parent workflow's OIDC Build Config URI. `release.published` is the single
automatic publication trigger. Recovery uses `workflow_dispatch` with the
existing GitHub Release tag and never rebuilds locally. Renaming the publisher
requires updating the trusted publisher configuration on PyPI first.

This chain combines policy and automation. The `v*` filter is enforced by
`release.yml`; the separate PyPI workflow reacts to a published GitHub Release
and manual recovery input. Release operators must therefore publish only the
verified `v<version>` Release and must not use the manual path to bypass the
identity checks.

Before merging packaging changes, require a successful default sdist-to-wheel
build. Docker is not a strict PR or PyPI release gate. When container inputs
change, a manual Docker workflow run is recommended; before publishing an image,
that run must cover build, local load, and `abi list-types`. A successful
BuildKit setup or Conda solve alone is not sufficient. Select the plasmid image
explicitly because of its size.

```bash
gh workflow run docker.yml --ref master \
  -f plugin=<plugin> -f push=false -f push_to_dockerhub=false
```

The Docker workflow is never started by a tag or GitHub Release. Container
publication is a separate, intentional operator action and is outside the
automatic GitHub Release → PyPI chain. To publish, select the exact verified
`v<version>` tag as the manual workflow ref, first record a successful
`push=false` run, and then rerun the same tag with `push=true`. The workflow
rejects branch and non-version-tag publication and repeats the local smoke test
before pushing registry tags.

## Post-Release Verification

After publication, verify the GitHub Release and PyPI version, confirm Trusted
Publishing provenance and file hashes, install the wheel in a clean environment,
and run `abi list-types`, `autoplasm --help`, and representative plugin dry-runs.
For container tags, verify the GHCR image can be pulled and runs
`abi list-types`. Record links to the Release, PyPI project, release workflow,
publish job, and container workflow in the release handoff.
