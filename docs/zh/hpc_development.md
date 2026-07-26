# 运行时与 HPC 开发指南

ABI 支持四种执行引擎。它们读取同一份编译计划，区别在于步骤在哪里、以什么方式运行。

| 引擎 | 实现 | 典型用途 |
| --- | --- | --- |
| `local` | `src/abi/runtimes/local.py` | 单机直接启动子进程 |
| `nextflow` | `src/abi/runtimes/nextflow.py` | 在工作站、集群或云端运行 Nextflow DSL2 |
| `snakemake` | `src/abi/runtimes/snakemake.py` | Snakemake、完成标记文件与可选 Conda |
| `hpc` | `src/abi/runtimes/hpc.py` | ABI 原生 Slurm/PBS 提交与轮询 |

`abi plan` 先生成与后端无关的 `execution_plan.json` 和 `compiled_plan.json`，
运行时再通过 `abi run --engine` 选择。

## 预检

提交前应针对目标引擎进行无副作用检查：

```bash
abi check \
  --type rnaseq_expression \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --engine hpc
```

该命令检查插件输入与资源，并在未设置 `--no-check-runtime` 时检查运行时可执行程序。
预检成功不等于计算节点能看到相同路径；共享存储、module/Conda 环境和调度器账户
策略仍需单独验证。

## Nextflow

导出独立 DSL2 文件：

```bash
abi export-nextflow \
  --type rnaseq_expression \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --output workflow.nf

nextflow run workflow.nf -resume
```

也可以由 ABI 导出并启动：

```bash
abi run \
  --type rnaseq_expression \
  --engine nextflow \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --workflow workflow.nf \
  --work-dir work/nextflow \
  --nextflow-profile slurm \
  --resume \
  --confirm-execution
```

相关参数包括 `--nextflow-bin`、`--nextflow-profile`、`--executor`、
`--nxf-home` 和 `--work-dir`。

## Snakemake

导出独立 Snakefile：

```bash
abi export-snakemake \
  --type rnaseq_expression \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --output Snakefile

snakemake --snakefile Snakefile --cores 8 --use-conda
```

也可以通过 ABI 执行：

```bash
abi run \
  --type rnaseq_expression \
  --engine snakemake \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --workflow Snakefile \
  --confirm-execution
```

ABI 使用 `--rerun-incomplete` 调用 Snakemake，并在成功和失败时写入溯源。
完成标记文件代表已完成 rule；不能仅凭工作目录存在就判定成功。通用 CLI 虽接受
`--resume`，但当前 Snakemake 后端不会因此增加另一个 Snakemake 恢复参数。

## 原生 Slurm/PBS

```bash
abi run \
  --type rnaseq_expression \
  --engine hpc \
  --scheduler slurm \
  --partition production \
  --account project_abi \
  --qos normal \
  --config config.yaml \
  --sample-sheet samples.tsv \
  --resource-profile hpc_standard \
  --hpc-timeout 86400 \
  --poll-interval 30 \
  --resume \
  --confirm-execution
```

原生运行时为 worker 范围步骤创建 payload 和调度脚本，提交带依赖关系的作业，
轮询调度器，记录 job ID 与原子步骤结果，并取消超时任务。Slurm 是主要生产验证
对象；PBS 支持兼容指令和依赖提交，但生产使用前必须在目标集群完成验收。

资源可来自步骤契约、资源 profile（`dev_small`、`hpc_standard`、`hpc_large`）
或命令行覆盖：

```bash
--cpu 16 --memory 64GB --walltime 08:00:00 --accelerator gpu:v100:1
```

也可覆盖容器：

```bash
--container-image ghcr.io/example/abi-rnaseq:1.5.7.1 \
--container-runtime apptainer
```

支持的运行时名称为 `docker`、`podman`、`singularity` 和 `apptainer`。容器仍须能
访问输入、输出与资源路径。

## Conda 与资源

`environments.yaml` 是工具→环境映射的单一事实源。当前插件分配为：

| 插件 | 声明环境 |
| --- | --- |
| `rnaseq_expression` | `rnaseq` |
| `wgs_bacteria` | `wgs` |
| `amplicon_16s` | `amplicon` |
| `metatranscriptomics` | `abi-qc`、`abi-stats` |
| `easymetagenome` | `easymeta-p0`、`easymeta-humann` |
| `viral_viwrap` | `autoplasm-base`（ViWrap 本身由外部环境管理） |
| `metagenomic_plasmid` | 11 个 `autoplasm-*`/`stats` 环境 |

通过 `ABI_MAMBA_ROOT` 或 `--mamba-root` 选择共享环境根。使用
`abi check-resources` 做只读诊断；任何确认安装前先运行
`abi setup-resources --dry-run`。

托管云端发布布局与严格认证流程见[可发布运行时锁](runtime_locks.md)。不要混淆
运行时锁使用的顶层 `ABI_RUNTIME_RESOURCE_ROOT`，与旧版质粒数据库语义下的
`ABI_RESOURCE_ROOT`。

## 验收清单

在宣称集群部署达到生产标准前：

1. 对受影响插件运行严格 contract lint。
2. 从计算节点验证输入和资源可见性，而不只在登录节点检查。
3. 导出并审查选定的工作流表示。
4. 使用相同调度器/profile/容器路径执行小型 `--smoke` 作业。
5. 测试失败、超时、取消和 `--resume`。
6. 验证标准表、溯源、校验和、报告限制与调度器 ID。
7. 为发布范围生成严格运行时锁。

完整本地与 HPC 门禁见[生产环境手动验收检查清单](production_manual_acceptance_checklist.md)。
