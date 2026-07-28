# Linux 与 macOS 支持计划

## 目标与支持契约

ABI 将支持在 Linux 和 macOS 上直接安装和运行核心 Agent，不要求使用 Docker。
容器镜像保留为可选部署产物，而不是安装前提。

目标支持层级如下：

| 范围 | Linux | macOS |
|---|---|---|
| ABI Python 包、CLI、MCP、SciPlot、规划、检查与报告 | 必须支持 x86_64 和 arm64 | 必须支持 Intel 与 Apple silicon |
| 托管 Conda/Mamba 环境 | 声明包可用时必须支持 | 按插件/工具逐项认证 |
| 外部生物信息工具 | 按插件和架构认证 | 按插件和架构认证；仅支持 Linux 的工具必须明确报告限制或替代方案 |
| Docker 镜像 | 可选、手动构建的 Linux 容器 | 可通过 Linux 容器运行时选用，不属于 macOS 原生执行 |

“支持”是指一台干净机器可以安装 wheel、发现或创建运行环境、解释每个已解析的
可执行文件与 Python 解释器，并通过对应冒烟测试；不表示所有第三方生信工具都在
所有架构上可用。

## 当前基线

ABI 已将 `environments.yaml` 打包，支持
`<mamba-root>/<env-name>` 与 `<mamba-root>/envs/<env-name>` 两种布局，
会把托管环境的 `bin` 前置到 `PATH`，并在运行时锁与溯源中记录环境信息。
`ABI_MAMBA_ROOT` 是显式覆盖入口，`AUTOPLASM_MAMBA_ROOT` 保留为兼容别名。

当前缺口主要是可移植性认证：根目录发现仍偏向仓库相邻目录，平台/工具兼容性
尚未形成机器可读矩阵，干净 Linux/macOS 安装也尚未由完整 CI 矩阵认证。

## 确定性的运行环境发现

实现一个与传输层无关的统一解析器，并由 CLI、执行器、运行时锁、导出器、资源
检查和插件适配器共同使用。解析结果必须确定且可由用户检查。

Mamba 根目录优先级：

1. CLI 或 API 显式传入的 `mamba_root`。
2. `ABI_MAMBA_ROOT`。
3. `MAMBA_ROOT_PREFIX`。
4. `micromamba info --json`、`mamba info --json` 或
   `conda info --json` 报告的活动安装。
5. ABI 用户级托管目录：Linux 使用
   `${XDG_DATA_HOME:-~/.local/share}/abi/mamba`，macOS 使用
   `~/Library/Application Support/abi/mamba`。
6. 现有仓库本地兼容候选目录。

环境前缀优先级：

1. 为环境显式记录的前缀。
2. `<mamba-root>/envs/<env-name>`。
3. `<mamba-root>/<env-name>`。
4. 所选 Conda/Mamba 安装返回的环境前缀。

可执行文件优先级：

1. 配置中的显式绝对路径。
2. 工具被分配到的 ABI 环境。
3. registry 声明的资源目录。
4. 仅当工具策略允许系统安装时，才回退到全局 `PATH`。

Python 工具步骤默认使用其分配环境中的 Python；ABI 内部步骤使用
`sys.executable`。每次运行记录所选根目录、环境前缀、工具路径、解释器路径、
版本、系统、架构和发现来源。

用户通过 `--mamba-root` 或 `ABI_MAMBA_ROOT` 提供的显式配置无效时必须给出可操作
错误，不得静默切换到另一个根目录。

## 交付阶段

### 阶段 1——平台契约与统一解析器

- 为平台、架构、环境根目录、前缀和工具解析添加类型化模型。
- 将重复的根目录/前缀逻辑统一迁移到 `runtime_environment.py`。
- 添加 `abi env discover --output-json` 与 `abi env doctor`。
- 在运行时锁和溯源中保存解析轨迹。
- 测试含空格路径、符号链接、缺失前缀、过期环境以及 Intel/Apple silicon 差异。

退出标准：local、Nextflow、Snakemake、HPC、CLI、MCP 和插件执行使用相同解析规则。

### 阶段 2——可移植安装

- 定义与系统无关的用户级安装位置。
- 使用发现到的 Micromamba、Mamba 或 Conda，提供幂等的环境创建/更新命令。
- 防止宿主 `PYTHONPATH` 泄漏，同时保留 Linux/macOS 所需动态库路径。
- 从干净虚拟环境验证 wheel 内容与所有 CLI 入口。

退出标准：只有 Python 3.10+ 和受支持的 Conda 系求解器时，也可在无源码仓库、
无 Docker 的机器上安装 ABI。

### 阶段 3——插件能力矩阵

- 在工具/环境元数据中加入操作系统和架构约束。
- 在 runner 可用时，分别求解 Linux x86_64、Linux arm64、macOS Intel 与
  macOS Apple silicon 的全部 `envs/*.yml`。
- 每个插件在各目标上标记为 `certified`、`partial` 或 `unsupported`，并列出
  阻塞工具与替代方案。
- 为每个已认证单元添加代表性真实工具冒烟测试。

退出标准：`abi doctor` 在执行前拒绝不支持的组合，并将限制定位到具体工具或插件。

### 阶段 4——CI 认证

在 Linux 与 macOS 上运行 Python 包和 Agent 测试矩阵，包括：

- editable 与 wheel 安装；
- CLI 和 MCP 入口冒烟测试；
- SciPlot 字体与渲染验证；
- 仓库本地及全局 Mamba 布局的环境发现；
- 全局 `PATH` 工具与指定环境工具；
- 含空格路径；
- 运行时锁可复现性与溯源断言。

常规 CI 只使用小型代表环境；大型数据库和长时间真实工具流程放入定时或人工批准
的验收任务。Docker 镜像构建不属于必需矩阵。

退出标准：所有必需 Linux/macOS job 连续两个版本通过，并随版本发布支持矩阵。

### 阶段 5——发布与运维

- 增加 Linux 与 macOS 干净机器安装步骤。
- 发布求解器选择、Apple silicon、Rosetta、字体、R/Bioconductor、Java、
  原生库与数据库路径的故障排查。
- 将支持矩阵及未解决限制纳入发布审查。
- 发布后在全新机器验证包安装。

退出标准：发布证据包含 wheel 哈希、系统/架构、Python 与求解器版本、解析到的
环境根目录、入口测试结果和代表性插件冒烟结果。

## Docker 手动策略

`.github/workflows/docker.yml` 只保留 `workflow_dispatch`。PR、分支 push、tag 和
GitHub Release 都不会自动启动镜像构建。

当 Dockerfile、`.dockerignore`、`environments.yaml`、`envs/*.yml`、打包的插件
定义或容器运行脚本变化，以及准备发布容器镜像时，建议手动构建。普通 Python/
插件开发和 PyPI 发布不以 Docker 构建作为强制门禁。

在 GitHub Actions 中选择 **Docker → Run workflow**，选择单个插件或 `all`；
仅验证时保持发布选项关闭。等价 CLI 命令为：

```bash
gh workflow run docker.yml --ref master \
  -f plugin=rnaseq -f push=false -f push_to_dockerhub=false

gh workflow run docker.yml --ref master \
  -f plugin=all -f push=false -f push_to_dockerhub=false
```

发布容器时，workflow ref 必须选择已验证的准确 `v<version>` tag，并先完成一次
`push=false` 验证。随后在同一 tag 上以 `push=true` 重跑；workflow 会在发布
`latest` 和不可变 semver tag 前，再次完成本地构建与 `abi list-types` 冒烟测试。
从分支或非版本 tag 发布会被拒绝。只有确认仓库 secret 与目标命名空间后才启用
`push_to_dockerhub`。

## 完成定义

Linux/macOS 支持达到完成状态需要：

- 核心 CI 矩阵在两个系统及受支持架构上通过；
- 干净 wheel 无需 Docker 或源码仓库即可安装；
- Mamba 根目录、环境前缀、全局工具和 Python 解释器均可确定解析，并由
  `abi env doctor` 报告；
- 每个插件发布真实的平台能力状态；
- 已认证插件通过代表性真实工具冒烟测试；
- 运行时锁和溯源保留所选路径与版本；以及
- 中英文安装、故障排查和发布文档保持同步。
