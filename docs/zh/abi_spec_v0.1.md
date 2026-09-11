# ABI 规范 v0.1

## 生命周期 API

`ABIAgentInterface` 是所有传输层的稳定边界：

- `list_types`
- `query`
- `plan`
- `check`
- `dry_run`
- `inspect`
- `report`
- `run`
- `export_nextflow`
- `export_snakemake`
- `export_agent_context`
- `check_resources`
- `doctor_agent`
- `install_skills`
- `abi_validate_result`
- `autoplasm_validate_result`（兼容别名）
- `dispatch`

每个公开方法返回一个带有统一信封格式的 JSON 字符串。

## JSON 信封

成功：

```json
{
  "status": "success",
  "command": "plan",
  "result": {}
}
```

确认门控：

```json
{
  "status": "confirmation_required",
  "command": "run",
  "result": {
    "message": "经用户批准后，以 confirm_execution=true 重新运行。"
  }
}
```

错误：

```json
{
  "status": "error",
  "command": "dry_run",
  "error_code": "missing_input",
  "error": "输入文件不存在。",
  "diagnostic_hints": []
}
```

## 权限

- `read_only`：`list_types`、`query`、`check`、`inspect`、
  `abi_validate_result`、`autoplasm_validate_result`、`check_resources`、
  `export_agent_context`、`doctor_agent`
- `planning_write`：`plan`、`dry_run`、`report`、`export_nextflow`、
  `export_snakemake`、`install_skills`
- `execution`：`run`

执行需要 `confirm_execution=true`。描述符默认不导出 `abi_run`。该值必须是
布尔值 `true`；此门控只检查请求值，不认证人类身份。

## 标准产物

规划和 dry-run 的输出应收敛到以下结构：

```text
outdir/
  execution_plan.json
  compiled_plan.json
  provenance/
    commands.tsv
    resolved_inputs.tsv
    tool_versions.tsv
    resources.json
    run_summary.json
    progress.jsonl
  tables/
    *.tsv
  report/
    report.md
    report.html
```

`provenance/commands.tsv` 记录 provenance schema 定义的生命周期字段。Nextflow
运行在 trace 暴露调度器/原生 ID 时（例如 Slurm 或云端批量执行器）也会填充
`remote_scheduler_job_id`。

`compiled_plan.json` 携带 `plan_id` —— 编译计划内容的 SHA-256 摘要。实际执行
绑定到该身份：`run` 在启动前重新编译准备好的计划，并与已确认的
`compiled_plan.json` 比对；若确认后配置、插件声明或工具目录发生变化，运行
以 `invalid_config`（计划漂移）拒绝启动，而不是执行未经批准的计划。没有先
执行 `plan` 的直接运行会先持久化已验证的计划，使后续运行对同一身份验证。
`run_summary.json` 记录 `plan_id`，把运行记录与已确认计划关联起来。

运行历史不会被覆盖：重试或恢复改写溯源视图之前，先前运行的证据先归档到
`provenance/previous_runs/<prior_run_id>/`。恢复运行在 `run_summary.json`
中记录 `resumes_run_id`（先前运行的 `run_id`）；全新重跑在
`previous_run_archive` 记录归档路径，不声称恢复关联。

四个后端（local、Nextflow、Snakemake、HPC）共享这些证据语义：其运行摘要
携带相同的运行身份、`plan_id` 与历史关联字段。

恢复时，被复用的步骤额外绑定到先前运行记录的校验和：步骤声明的产物或输
入与先前运行的 `checksums.json` 不再一致时不予复用——该步骤重新执行，且
命令记录写明原因（`resume reuse rejected: …`）。无校验和记录的旧产物回
退到存在性与契约检查。

取消区分“请求已记录”与“执行已确认终止”。取消请求以未确认证据记录；只有
实际终止的退出证据（信号死亡，或从未启动）才把作业标为 `cancelled`。在
取消请求已记录后仍完成的工作按真实结果报告（`succeeded`/`failed`），未
确认的请求保留在作业的 `termination` 字段中；终止调度 worker 绝不被声称
为已终止下游引擎或调度器进程。

## 错误码

ABI 使用来自 `abi.diagnostics` 的 19 个稳定错误码，枚举每一种已识别的失败模式：

| 代码 | 触发条件 |
| --- | --- |
| `unknown_analysis_type` | 插件 ID 未被识别 |
| `invalid_config` | YAML/JSON 配置未通过 schema 验证 |
| `invalid_sample_sheet` | 样本表缺失或格式错误 |
| `missing_input` | 必需的输入文件不存在 |
| `missing_resource` | 资源状态为 NOT_CONFIGURED 或缺失 |
| `missing_database` | 生物信息学数据库不可用 |
| `tool_not_found` | 外部工具可执行文件不在 PATH 中 |
| `permission_required` | 执行需要显式用户确认 |
| `runtime_not_supported` | 请求的引擎不是 local/nextflow/snakemake/hpc |
| `nonzero_exit` | 外部命令返回非零退出码 |
| `parse_failed` | 工具输出无法解析为表格 |
| `empty_result` | 管线未产生任何输出 |
| `artifact_missing` | 必需的结果产物缺失 |
| `internal_error` | ABI 边界处意外/未分类的错误 |
| `contract_violation` | 步骤合约断言或输出检查失败 |
| `duplicate_sample_id` | 样本表中存在重复样本 ID |
| `incomplete_pairs` | 双端测序的 R1/R2 文件不配对 |
| `invalid_platform` | 平台标识不被该插件支持 |
| `missing_sample_id` | 样本 ID 在预期集合中缺失 |

这组固定错误码定义在 `abi.diagnostics.ERROR_CODES` 中，每个错误响应携带稳定的 `error_code` + 可操作的 `diagnostic_hints`。每条 hint 还携带一个结构化的 `recovery` 块（`action`、`api_call`、`params`），由覆盖全部 19 个错误码的数据表驱动：`action` 取值为 `retry`、`resume`、`fix_input`、`install_resource`、`request_authorization` 或 `do_not_retry`；`do_not_retry` 类别（畸形样本表、契约违规、内部错误等）绝不可自动重试。

## 插件合约

每个插件必须提供：

- `abi-plugin.yaml`
- `tool_registry.yaml`
- `standard_tables.yaml`
- `tool_contracts/*.yaml`
- `limitations.yaml`（强制且非空；由 contract lint 检查）

`abi.testing.assert_plugin_contract()` 验证运行时 Python 接口和机器可读的插件资产。校验同时强制执行输出契约覆盖率：`pipeline_dag.yaml` 中每个调用外部工具的节点必须声明 `contract:` 块；无产出的聚合节点必须显式声明 `contract: {exempt: true, reason: ...}`。

## 插件发现与加载

`list_types`、Agent summary 和 `doctor` 使用 `list_plugin_metadata()` 读取插件声明，不实例化所有插件实现。`get_plugin()` 只加载选中的插件；旧 SDK 的 `list_plugins()` 仍作为显式全量加载兼容接口保留。ABI 尚未提供独立可选安装的插件包，仍假设全局资源根的 `query`/catalog 调用方迁移留待后续。

## 步骤合约与可复现性

运行时步骤合约由共享 DAG 规划器嵌入 `PlanStep.params["_contract"]`。全部 8 个
内置插件都从各自的 `pipeline_dag.yaml` 复制此块。

支持的输出检查包括：

- 声明的文件或目录是否存在
- `min_size`
- `extensions`
- 目录 `contains`
- `min_files`
- FASTA `min_contigs`
- JSON `required_keys`
- 点分 JSON `schema`
- 运行时 `assertions`
- 校验和记录以供下游验证

当规划路径为抽象路径但工具写入固定文件名时，执行器可在工具成功后解析实际文件。解析后的输出（而非抽象的规划器占位符）用于输出合约和断言。

科学可复现性需要的不仅仅是 ABI 信封。生产级工作流还应固定工具版本、记录数据库/模型清单和校验和，并验证已知的基准数据集。仓库级的目标追踪见
[工作流验证与科学证据计划](workflow_validation.md)。
