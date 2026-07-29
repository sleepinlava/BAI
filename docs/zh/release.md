# 发布指南

本仓库只发布一个 PyPI 分发包：`abi-agent`。发布从已验证的 `master` 提交产生，Git tag、
包版本、GitHub Release 和 PyPI 制品必须指向同一个发布身份。

## 发布前检查

先运行统一的发布检查：

```bash
scripts/release_check.sh
```

推送候选版本前，确认 `CHANGELOG.md` 中有与 `pyproject.toml` 的 `project.version`
完全一致的小节。CI 通过 `scripts/check_release_identity.py` 检查这一点，同时核对
Claude Code、Codex plugin manifest 与包版本。

版本必须同时不存在于 PyPI 和远端 Git tag。tag 与 PyPI 版本都是不可变发布身份，
推送后不能移动或复用。如果 tag 指向与包元数据不一致的提交，应放弃该版本并继续
递增。历史示例：`1.5.4` 因 tag 对应 `1.5.3` 元数据而被放弃；后续版本仍必须
独立检查，不能从该示例推断某个版本可用。

发布政策要求 tag 指向已验证的 `master` 提交。这是发布操作员的前置条件：
`release.yml` 会验证 tag/包身份并复用 CI，但不会自动证明被标记提交就是当前
`master` 顶端。推送前必须检查祖先关系和远端 tag 是否存在。

脚本默认会在 `/tmp` 下创建 POSIX 临时目录，并在测试前导出
`TMPDIR`、`TMP` 和 `TEMP`。这样可以避免 WSL/Windows 挂载的临时目录破坏
权限敏感测试的 `chmod` 语义。可通过 `ABI_RELEASE_TMPDIR` 或
`ABI_RELEASE_TMP_ROOT` 覆盖位置。

该脚本运行以下本地 Python/包子集：

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

它不能替代全部发布表面门禁。还需分别运行 `bash docs/build_docs.sh`、
`docker compose -f docker/docker-compose.yml config --quiet`、Docker 配置回归测试、
全部 7 个插件的严格 contract lint 和 `python -m twine check dist/*`。适用时运行
真实工具验收；只有容器输入变化或准备发布镜像时才运行容器验收。GitHub release
workflow 会在创建 Release 前重新运行可复用 CI 门禁。

构建 wheel 后，使用 `[mcp]` extra 安装，并在可行的情况下于干净环境中对
已安装命令进行冒烟测试：

```bash
abi list-types
abi query --type metagenomic_plasmid --what stages
abi query --type rnaseq_expression --what tools
autoplasm --help
abi dry-run --type metagenomic_plasmid --config examples/config_minimal.yaml --profile dry_run
abi doctor-agent --type metatranscriptomics
abi export-tools --type metatranscriptomics --format json
abi install-skills --target /tmp/abi-smoke-skills
abi query --type amplicon_16s --what stages
abi query --type wgs_bacteria --what tools
abi query --type easymetagenome --what stages
abi dry-run --type viral_viwrap --config examples/config_minimal.yaml --profile dry_run 2>/dev/null || echo "ViWrap smoke skipped (requires external CLI)"
abi-mcp --help 2>/dev/null || python -m abi.mcp.server --help 2>/dev/null || true
for platform in claude-code opencode codex; do
  abi agent install "$platform" --scope project --project-dir "/tmp/abi-release-agent-$platform"
  abi agent doctor "$platform" --scope project --project-dir "/tmp/abi-release-agent-$platform"
done
```

执行时应将干净 wheel 环境的 `bin` 目录加入 `PATH`，因为 doctor 会校验已安装的
`abi-mcp` 入口。`integrations/` 属于发布输入，必须同时进入两种分发包和每个
Docker `/app` 上下文。该目录或其他容器输入变化时，建议在容器发布前手动运行
Docker workflow。

## GitHub Actions

- `ci.yml` 运行 lint、格式检查、mypy、测试、Python 3.10–3.13 默认构建与 wheel
  安装检查、原生 arm64 验证，以及共享的已安装 wheel 能力验证器。
- `docker.yml` 仅允许手动触发。它构建并冒烟测试所选插件（或全部插件），只有操作员显式启用 `push` 才发布。registry push 包含 provenance 与 SBOM；非 push 验证以稳定本地 tag load，并关闭 attestation。发布镜像默认多架构，但 RNA-seq 在其 R/DESeq2 环境通过原生 arm64 构建与冒烟测试前仅发布 `linux/amd64`。
- `release.yml` 构建分发包，在源码 checkout 外执行 wheel smoke，附加由该已安装
  wheel 生成的 `abi-linux-capability-v<version>.json`，为 `v*` tag 创建 GitHub
  Release，并发出 published event。
- `publish-pypi.yml` 只下载并发布 Release 中的 `*.whl` 和 `*.tar.gz`。能力 JSON
  保留为 GitHub Release 证据，不上传 PyPI。PyPI OIDC 身份绑定该文件名，因此它是
  必需 workflow。

`.github/workflows/` 不保留可选 bot 或重复发布 workflow；必需集合严格为 `ci.yml`、`docker.yml`、`release.yml` 和 `publish-pypi.yml`。

唯一正常的自动发布链为：

```text
已验证 master 提交 → v<version> tag → 可复用 CI 质量门
→ 构建并冒烟测试 wheel/sdist → 携带原始分发包与 Linux 能力证据的 GitHub Release
→ 顶层 release.published event 启动 publish-pypi.yml
→ 下载 Release 产物 → PyPI Trusted Publishing
```

不能把 `publish-pypi.yml` 作为 reusable workflow 调用：PyPI 不支持父 workflow 的 OIDC Build Config URI。`release.published` 是唯一自动发布触发器。恢复操作使用 `workflow_dispatch` 并输入已有 GitHub Release tag，不能本地重新构建。重命名 publisher 前必须先更新 PyPI Trusted Publisher 配置。

上述链条同时包含政策和自动化。`release.yml` 强制 `v*` 过滤；独立 PyPI workflow
响应已发布 GitHub Release 和手动恢复输入。因此发布操作员只能发布已验证的
`v<version>` Release，不能用手动路径绕过身份检查。

合并 packaging 变更前必须通过默认 sdist→wheel 构建。Docker 不再是 PR 或 PyPI
发布的严格门禁。容器输入变化时建议手动运行 Docker workflow；发布镜像前，该次
运行必须覆盖构建、本地 load 和容器内 `abi list-types`，仅 BuildKit 初始化或
Conda 求解成功不算完成。质粒镜像体积较大，需要显式选择。

```bash
gh workflow run docker.yml --ref master \
  -f plugin=<plugin> -f push=false -f push_to_dockerhub=false
```

tag 和 GitHub Release 均不会启动 Docker workflow。容器发布是独立且有意的
操作员动作，不属于自动 GitHub Release → PyPI 链。发布时必须把手动 workflow
ref 设为准确且已验证的 `v<version>` tag，先记录一次成功的 `push=false` 运行，
再在同一 tag 上以 `push=true` 重跑。workflow 会拒绝从分支或非版本 tag 发布，
并在推送 registry tag 前重新执行本地冒烟测试。

## 发布后验证

发布完成后，核对 GitHub Release 与 PyPI 版本、Trusted Publishing provenance 和
文件哈希；确认 GitHub Release 含 `abi-linux-capability-v<version>.json`，其中恰有
21 个环境及声明的 x86_64/aarch64 单元格，且 unsupported 单元格保持明确。PyPI
应仅包含 wheel 与 sdist。在干净环境安装 wheel，并运行 `abi list-types`、
`autoplasm --help` 和代表性插件 dry-run。容器 tag 需要从 GHCR 拉取并执行
`abi list-types`。发布交接中记录 Release、PyPI、release workflow、publish job 和
container workflow 链接。
