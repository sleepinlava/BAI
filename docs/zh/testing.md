# ABI 测试指南

测试数量和覆盖率会随代码变化，当前数字以最新 CI 为准。本文说明测试应该放在哪里、
本地常用哪些命令，以及 CI 会检查什么。

## 测试结构

| 层级 | 位置 | 用途 | 外部工具 |
| --- | --- | --- | --- |
| 单元 | `tests/unit/` | 核心逻辑、schema、解析器、契约和运行时 | 否 |
| 集成 | `tests/integration/` | CLI/核心边界、dry-run、golden trace | 通常不需要 |
| 冒烟 | `tests/smoke/` | 真实工具与数值级工作流检查 | 通常需要 |
| SciPlot | `src/abi/sciplot/tests/` | schema、渲染器、lint、CLI/API、Unicode 排版 | report 依赖 |

文件名使用 `test_<feature>.py`，函数名使用 `test_<behavior>`。行为发生变化时应补上
回归测试。调用外部工具的测试使用 `@pytest.mark.smoke`、
`@pytest.mark.requires_tools`，或同时使用两者。

## 本地命令

```bash
# 主测试集
pytest tests/ -v --tb=short

# 接近 CI、排除外部工具
pytest tests/ src/abi/sciplot/tests/ -v --tb=short \
  --strict-markers -m "not requires_tools"

# 聚焦模块
pytest tests/unit/test_dag_planner.py -q

# 仅真实工具测试
pytest tests/ -v -m requires_tools

# 分支感知的全局门禁
pytest tests/ src/abi/sciplot/tests/ \
  --strict-markers -m "not requires_tools" \
  --cov=src/abi --cov-branch --cov-report=term \
  --cov-report=json:coverage.json --cov-fail-under=75
python scripts/check_module_coverage.py --coverage coverage.json
```

CI 强制全局 75% 底线，并对高风险模块设置行/分支门禁。持续维护的指南中不要写死
某次测得的百分比或测试数量。

## 共享 fixtures

`tests/conftest.py` 当前提供：

- `mock_sample`；
- `mock_sample_context`；
- `mock_contract_dict`；
- `tmp_project`；
- 隔离 mamba/resource-root 环境变量的 autouse fixture。

复用 fixture 放在这里。文件系统写入使用 `tmp_path`，环境变量和全局状态通过
pytest fixture 恢复。

## 插件契约门禁

每个内置插件必须：

1. 通过 `assert_plugin_contract` 检查的 Python 插件协议；
2. 能加载工具注册表和标准表 schema；
3. 提供声明式 `pipeline_dag.yaml`；
4. 为每个外部工具输出声明 contract，或给出带理由的显式豁免；
5. 提供非空 `limitations.yaml`。

对全部内置插件运行严格 lint：

```bash
for plugin in \
  amplicon_16s easymetagenome metagenomic_plasmid metatranscriptomics \
  rnaseq_expression viral_viwrap wgs_bacteria
do
  abi contract-lint --type "$plugin" --strict
done

python scripts/audit_contract_coverage.py
```

严格模式把 warning 也视为失败，并强制检查缺失/无效/空 limitations 和输出
contract 覆盖。

## Golden traces

Golden traces 位于仓库根目录：

```text
golden_traces/
├── amplicon_16s.jsonl
├── metagenomic_plasmid.jsonl
├── metatranscriptomics.jsonl
├── rnaseq_expression.jsonl
└── wgs_bacteria.jsonl
```

当前覆盖 5 个工作流家族，不是全部 7 个内置插件。运行：

```bash
pytest tests/integration/test_golden_traces.py -q
```

有意修改计划后，应先审查语义 diff，再更新 trace；不能只为让测试通过而重新生成。

## 冒烟与 benchmark

`tests/smoke/test_*_benchmark.py` 包含原始 5 个工作流家族的真实工具检查，
`abi.testing.benchmark` 提供通用 `expected_assertions.yaml` 评估器。当前仓库
checkout 不包含完整的 `data/benchmarks/` fixture 树。运行这些测试前，应先确认
数据集、期望断言、工具、数据库和环境变量均已配置。默认 CI 会排除
`requires_tools` 测试。

EasyMetagenome 与 ViWrap 有契约、dry-run、集成和发布 wheel 冒烟覆盖，但当前
没有与原始 5 个工作流相同形态的仓内数值级 benchmark fixture。

## CI 与发布表面

仓库有且仅有 4 个 workflow：

- `ci.yml`：Python 3.10–3.13 lint/format/mypy、测试、3.12 覆盖率、严格
  contract lint、文档、Compose、包构建、wheel 冒烟和 migration gate；
- `docker.yml`：自动 amd64 构建 amplicon、RNA-seq、WGS 和宏转录组；
  plasmid 仅手动；registry push 启用 provenance/SBOM，RNA-seq 之外为多架构；
- `release.yml`：复用 CI 门禁、构建、Twine 检查、干净 wheel 冒烟并创建
  GitHub Release；
- `publish-pypi.yml`：下载 GitHub Release 的原始产物，通过 PyPI Trusted
  Publishing 发布。

修改 CI/Docker/构建输入时运行：

```bash
pytest tests/unit/test_docker_configuration.py -q
docker compose -f docker/docker-compose.yml config --quiet
python -m build
```

修改文档时运行：

```bash
bash docs/build_docs.sh
```

## 提交评审前

Python 变更需要 Ruff、格式、mypy、聚焦 pytest 和受影响集成测试。插件变更还需
严格 contract lint、dry-run 和相关 smoke。Release 与 Docker 变更的额外门禁
见[开发流程](development_workflow.md)和[发布指南](release.md)。

在 PR 中记录所有命令和结果。无法运行真实工具、容器或集群检查时，必须明确说明
未验证内容和残余风险。
