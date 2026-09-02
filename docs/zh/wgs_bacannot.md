# Bacannot 受管接入

`wgs_bacannot` 将 Bacannot 作为受管外部 Nextflow 工作流接入 ABI。它与较轻量、ABI 原生的
`wgs_bacteria` 并存；首版只支持 Illumina paired-end 细菌分离株。

当前支持基线为不可变身份：

- Bacannot `v3.4.4`
- commit `a78ddb0bffe75139adf1f443260d6d5b1987fe27`
- 契约集 `bacannot-3.4.4-v1`
- Nextflow `>=25.10.0,<26.0.0`、Java 17、Docker 或 Singularity

规划期只声明一个父级步骤及预期 process 类别；执行期保存每个 Nextflow task attempt，失败重试和
`CACHED` 均不会被折叠。ABI 强制生成 trace、report、timeline、DAG 和日志，并逐 attempt 归档
`.command.sh`、stdout、stderr 与退出码；证据 manifest 校验通过后，结果才可能被接受。

标准结果写入 `standard/`，并镜像到 ABI 兼容目录 `tables/`。`provenance/result_sources.tsv`
把标准表行关联到来源文件、摘要、task、process 和解析器版本。assembly、annotation、MLST、AMR
契约对缺 process 和缺关键产物均 fail closed。`validate-result` 会直接对照发布结果树重新校验关键
产物，删除或破坏任一关键产物都会使验证失败，并定位到样本、契约、task 和文件。

失败会被结构化诊断而不是笼统上报。每次运行都会写入 `provenance/diagnostics.json`，把失败 attempt
归入稳定错误码（`EXTERNAL_TASK_FAILED`、`RESOURCE_EXHAUSTED`、`DATABASE_MISSING`、
`TOOL_OR_CONTAINER_UNAVAILABLE`），并给出 process、样本、attempt、退出码、归档日志路径和可执行的
恢复建议。未映射的 Nextflow process 始终记录在 `task_attempts.tsv`；`audit.unmapped_policy`
（默认 `warn`）决定未映射 task 是否额外阻断结果验证（`fail`）。

resume 运行保留原运行的证据：前次快照、task-attempt 表、证据 manifest、验证与诊断文件会归档到
`provenance/previous_runs/<run-id>/`，新快照记录 `resumes_run_id` 和归档位置。每次运行摘要去报
告 CACHED 与重新执行的 task 数量对账，resume 结果保持可审计。

插件当前明确报告 `production_ready: false`。D2/D3 生物学验收、resume 认证、代表性 HPC 运行、
容器/数据库 manifest 和 strict release runtime lock 仍是发布门禁；完成前只能用于工程验证，不能宣称
生产认证或生物学验收已完成。

安全生命周期为：

```text
query -> plan -> check -> dry-run -> 审核后 run -> inspect -> validate-result -> report
```

真实执行必须经过 ABI 明确确认，并配置完整的 Bacannot 数据库 bundle。
