# Linux 支持与交付计划

## 支持契约

ABI 以无需 Docker 的 Linux 原生安装和 Agent 运行为目标。核心包支持 Linux
x86_64 与 arm64；第三方生物信息工具按插件和架构逐项认证。

| 范围 | Linux 支持 |
|---|---|
| Python 包、CLI、MCP、SciPlot、规划、检查与报告 | 必须支持 x86_64 和 arm64 |
| 托管 Conda/Mamba 环境 | 声明包可求解时必须支持 |
| 外部生物信息工具 | 按插件和架构认证 |
| Docker 镜像 | 可选、手动构建的 Linux 部署产物 |

非 Linux 操作系统不属于当前开发和认证范围。“支持”是指一台干净 Linux
机器可以安装 wheel、发现或创建运行环境、解释每个已选择的工具与解释器，并完成
相应冒烟测试。

## 已实现基础

统一的 `abi.runtime_environment` 解析器现在负责 Linux 运行环境发现。
`abi.config`、质粒引擎、本地工具执行、运行时锁和 Nextflow 导出器均委托该层选择
环境前缀。

Mamba 根目录优先级为：

1. CLI/API 显式 `mamba_root`。
2. `ABI_MAMBA_ROOT`。
3. `MAMBA_ROOT_PREFIX`。
4. 兼容变量 `AUTOPLASM_MAMBA_ROOT`。
5. 已填充的仓库兼容根目录。
6. 已填充的 `${XDG_DATA_HOME:-~/.local/share}/abi/mamba`。
7. 全局 `micromamba`、`mamba` 或 `conda` 的 `<solver> info --json` 结果。
8. 空的或默认 `${XDG_DATA_HOME:-~/.local/share}/abi/mamba`。

显式路径具有权威性，缺失时直接失败。命名环境优先
`<root>/envs/<name>`，兼容 `<root>/<name>`，也可使用求解器报告的前缀。
可执行文件依次从显式路径、分配环境、registry 资源目录以及策略允许的全局
`PATH` 解析。ABI 内部 Python 使用 `sys.executable`，工具 Python 优先使用其
分配环境。

无需运行分析即可检查解析结果：

```bash
abi env discover --output-json
abi env doctor --tool fastp --tool samtools --output-json
```

报告包含 Linux 架构、ABI Python、Mamba 根目录及来源、环境前缀、请求的工具路径、
Python 路径和健康问题。

## 可移植环境安装

ABI 现在无需源码 checkout 即可创建或更新 wheel 内置的环境：

```bash
abi env install --type rnaseq_expression --dry-run --output-json
abi env install --type rnaseq_expression
abi env update --env rnaseq --output-json
```

安装器依次选择 `micromamba`、`mamba`、`conda`，也接受明确的
`--solver`/`ABI_ENV_SOLVER`。报告记录求解器路径和版本、生成规范的 SHA-256、
实际参数向量、目标前缀，以及环境是新建、更新还是保持不变。按插件选择时会对其
分配环境去重。

默认可写根目录为 `${XDG_DATA_HOME:-~/.local/share}/abi/mamba`；CLI 和环境变量
指定的根目录仍具有权威性。求解器子进程保留 Linux 动态库变量，但不会继承宿主
`PYTHONPATH`。安装具有幂等性，更新执行 prune；求解失败不会发布未应用的规范，
缺失目标环境时 `update` 会先执行创建，不含 `conda-meta/` 的残缺前缀不会被视为
有效环境，且 `--dry-run` 不会创建目标根目录。

x86_64 与 arm64 wheel 冒烟测试都会先切换到隔离的临时目录，再通过严格测试求解器
实际执行环境创建并读取打包的 `environments.yaml`，从而证明该路径不会回退到源码
checkout 或仓库本地 `envs/*.yml`。

## 后续交付阶段

### 阶段 3——插件能力矩阵

- 在工具/环境元数据中加入 Linux 架构约束。
- 在 Linux x86_64 与 Linux arm64 上求解全部 `envs/*.yml`。
- 每个插件/架构单元标记为 `certified`、`partial` 或 `unsupported`，并列出
  阻塞项与支持的替代方案。
- 为每个已认证单元增加代表性真实工具冒烟测试。
- 让 `abi env doctor --type <plugin>` 在执行前拒绝不支持的组合。

退出标准：每个插件发布真实、机器可读的 Linux 能力状态，已认证单元通过真实工具
验证。

### 阶段 4——Linux CI 认证

必需 CI 矩阵覆盖：

- Python 3.10–3.13 editable 与 wheel 安装；
- 所有支持 Python 上的 Linux x86_64 核心测试；
- Linux arm64 wheel、CLI、MCP 与代表性环境冒烟；
- SciPlot 字体/渲染；
- 仓库本地、用户级与全局 Mamba 发现；
- 分配环境工具与全局 `PATH` 工具；
- 含空格路径和符号链接；
- 运行时锁可复现性与溯源断言。

常规 CI 使用小型代表环境；大型数据库和长时间真实工具流程放入定时或人工批准
验收。Docker 镜像构建不属于必需矩阵。

退出标准：必需 Linux job 连续两个版本通过，并把能力矩阵附加到发布证据。

### 阶段 5——发布与运维

- 发布干净机器 Linux 安装与故障排查指南。
- 覆盖求解器选择、字体、R/Bioconductor、Java、原生库、架构不匹配和数据库路径。
- 在全新 x86_64 与 arm64 环境验证已发布 wheel。
- 记录 wheel 哈希、架构、Python/求解器版本、环境根目录、入口测试和代表性插件
  冒烟结果。

## Docker 手动策略

`.github/workflows/docker.yml` 仅保留 `workflow_dispatch`；PR、push、tag 和
release 均不会启动镜像构建。容器输入变化时建议手动构建，发布容器镜像前必须
手动验证；它不是 Python/插件或 PyPI 门禁。

```bash
gh workflow run docker.yml --ref master \
  -f plugin=rnaseq -f push=false -f push_to_dockerhub=false
```

发布时把已验证的 `v<version>` tag 设为 workflow ref，先记录成功的
`push=false` 运行，再在同一 tag 上以 `push=true` 重跑。workflow 会在修改
registry 前再次完成本地构建和 `abi list-types` 验证。

## 完成定义

Linux 支持完成需要：

- 干净 wheel 无需 Docker 或源码 checkout 即可安装；
- Mamba 根目录、前缀、工具和 Python 解释器可确定解析，并由
  `abi env doctor` 报告；
- x86_64 与 arm64 核心 CI 连续两个版本通过；
- 每个插件发布 Linux 能力状态；
- 已认证插件通过代表性真实工具冒烟；以及
- 运行时锁、溯源和双语文档保留所选路径、版本、限制与验证证据。
