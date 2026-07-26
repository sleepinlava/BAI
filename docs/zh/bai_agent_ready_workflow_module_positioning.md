# BAI 重新定位：面向通用型 Agent 的严格生物信息学 Skills 工程

## 1. 文档目的

本文档汇总 BAI 论文定位与工程设计讨论，重点回答以下问题：

1. BAI 应如何从“更安全的工作流执行器”重新定位为面向通用型 Agent 的严格、
   可执行 skills 工程；
2. Agent 如何显式或隐式发现、选择和调用 BAI；
3. 已发表的外部 pipeline 如何以不同深度接入 BAI；
4. 如何建立第三方开发者可使用的插件规范、工具链和生态；
5. 如何定义并量化策略违规、安全阻断、审计证据和证据利用；
6. 是否以及如何进行多 harness 验证；
7. 论文中哪些主张可以成立，哪些主张需要实现或实验后才能成立。

本文档同时区分三类状态：

- **当前实现**：仓库代码已经具备的能力；
- **建议新增**：为支撑新定位需要补充的工程能力；
- **论文边界**：在证据不足时不得写成已成立结论的内容。

---

## 2. 推荐定位

### 2.1 一句话定义

> **BAI 是面向通用型 Agent 的生物信息学可执行工作流模块规范与参考运行时。
> 开发者将经过审核的既有分析流程封装为版本固定、参数类型化、具有输入输出契约、
> 资源声明、权限边界和机器可读证据接口的 Agent-ready 模块；Agent 负责发现、配置
> 和调用模块，而不在正式分析时从网络临时检索、下载或拼装分析流程。**

建议英文表述：

> **BAI is an agent-facing workflow module specification and reference runtime for packaging
> curated bioinformatics pipelines as versioned, typed, contract-checked, and auditable
> capabilities. Instead of retrieving or synthesizing pipelines at runtime, an agent discovers,
> configures, and invokes pre-integrated workflow modules through a shared lifecycle.**

### 2.2 推荐术语

主术语建议使用：

- `Agent-ready workflow module`
- `Contracted workflow capability`
- `Executable bioinformatics capability module`

其中最推荐 `Agent-ready workflow module`。

可以将 BAI module 解释为普通 skill 的严格超集，但不建议把论文主术语直接写成
`skill`。`skill` 在不同 harness 中通常表示提示词、说明文档或脚本集合，容易让读者
误解 BAI 只是更长、更结构化的 prompt。

更准确的表述是：

> BAI module 是一种 contracted executable skill：它不仅告诉 Agent 应该如何操作，
> 还提供可执行入口、类型化参数、运行时契约、结果接口和证据边界。

### 2.3 BAI 不是什么

BAI 不应被描述为：

- 新的生物学学习算法；
- Nextflow、Snakemake 或 Galaxy 的替代品；
- 能自动理解任意 pipeline 生物学语义的系统；
- 任意 pipeline 的零配置 importer；
- 能保证科学结论绝对正确的系统；
- 一组只依靠模型遵循说明的静态 skills；
- 允许 Agent 在正式分析时从网络自动搜索并执行未知代码的框架。

### 2.4 BAI 与工作流引擎的关系

建议使用“控制面与执行面”的架构定义：

| 层级 | 主要职责 |
| --- | --- |
| Nextflow / Snakemake / local / HPC | 执行 DAG、调度任务、缓存、重试、资源分配 |
| BAI runtime | 模块发现、计划、preflight、授权、契约检查、诊断、结果和证据接口 |
| Agent harness | 自然语言交互、任务分解、模块选择、用户审批交互、结果解释 |

因此：

> Nextflow 等系统是 execution/data plane；BAI 是面向 Agent 的 module/policy/evidence
> control plane。

如果 BAI 的区别只剩日志、报告、重试和 provenance，那么“Agent-facing Nextflow
wrapper”这一批评成立。BAI 的可识别贡献必须来自：

1. 平台无关的 Agent 生命周期；
2. 可执行模块规范；
3. 运行前后的契约强制；
4. 统一的结果与证据接口；
5. 可测量的策略违规阻断和无效结果拒绝；
6. 外部审批与具体执行计划的绑定。

---

## 3. BAI Workflow Module 的概念模型

一个模块可以定义为：

\[
M = \langle I, C, E, V, R, L \rangle
\]

其中：

- \(I\)：Identity，模块的生物学目的、适用数据、上游 pipeline 和版本；
- \(C\)：Configuration，参数 schema、样本 schema 和输入约束；
- \(E\)：Execution，固定的 CLI、Nextflow、Snakemake 或其他执行入口；
- \(V\)：Validation，preflight、terminal contract、关键 checkpoint 和 assertions；
- \(R\)：Result interface，标准结果表、artifact manifest 和 provenance；
- \(L\)：Limitations，已知科学、数据库、版本和工程边界。

普通 skill 与 BAI module 的差异如下：

| 普通 Agent skill | BAI workflow module |
| --- | --- |
| 描述应该如何操作 | 声明可实际执行的 workflow 入口 |
| 参数通常以自然语言表达 | 参数具有类型和 schema |
| 模型可以忽略说明 | runtime 可以强制执行契约 |
| 不一定固定工具版本 | 记录或绑定 pipeline、工具和数据库身份 |
| 通常没有输出后置条件 | 声明 terminal 或 step-level output contract |
| 失败主要依靠模型阅读日志 | 提供稳定错误类别和恢复动作 |
| 没有统一结果接口 | 提供标准表或 artifact manifest |
| 不一定有审计证据 | 自动生成结构化执行证据 |

---

## 4. 外部 Pipeline 的渐进式接入

### 4.1 当前问题

当前 ABI 插件协议要求插件提供 `load_config()`、`build_plan()`、`registry()`、
`table_schemas()`、`parse_outputs()` 和 `write_report()`。声明式基类目前主要自动加载
插件身份、tool registry 和 standard tables，并没有自动导入已有 pipeline。

ViWrap 是当前最接近“现有已发表 pipeline 黑盒接入”的实现，但仍包含较多 YAML、
Python 适配器、parser、checker、handlers 和测试。因此，当前不能把 BAI 宣传为任意
pipeline 的即插即用 importer。

必须区分：

- **Agent 侧即插即用**：插件接入后，不同 Agent 通过相同生命周期调用；
- **开发者侧即插即用**：任意 pipeline 无需较多开发即可接入。

当前前者基本成立，后者尚未成立。

### 4.2 不复制已有 Pipeline 的内部 DAG

对于已有 Nextflow、Snakemake 或成熟 CLI pipeline，BAI 不应要求开发者人工复制其完整
内部 DAG。否则会造成：

- ABI DAG 与上游 DAG 漂移；
- 上游升级维护两套工作流；
- 重复实现调度和恢复逻辑；
- 增加错误和接入成本；
- 削弱 BAI 与 workflow engine 的边界。

推荐的黑盒路径是：

```text
BAI lifecycle
    ↓
validate external-pipeline inputs/resources
    ↓
execute pinned Nextflow/Snakemake/CLI pipeline
    ↓
ingest native trace + terminal outputs
    ↓
validate terminal result contracts
    ↓
publish artifact manifest/provenance
```

### 4.3 三级接入模型

#### L0：Black-box adapter

开发者只需声明：

- pipeline 来源、revision、container 或软件版本；
- 执行入口；
- 参数 schema；
- 必需输入；
- 数据库和资源位置；
- 最终输出位置和最低 terminal contract；
- 已知 limitations。

BAI 负责：

- 模块发现；
- plan 和 dry-run；
- 统一执行入口；
- 命令、版本和资源记录；
- exit code；
- terminal-output existence/checksum；
- artifact manifest；
- 通用报告和基础诊断。

L0 不应要求：

- 重写内部 DAG；
- 为所有内部工具编写 contract；
- 编写每一种 pipeline-specific 错误码；
- 编写复杂 parser；
- 转换成完整标准生物学结果表。

L0 只支持受控执行和基础审计，不支持 step-level semantic validation。

#### L1：Observable adapter

在 L0 基础上增加：

- 导入 Nextflow trace、timeline 和 report；
- 导入 Snakemake stats、DAG 和日志；
- 将 native task 状态映射到 ABI 通用错误类别；
- 声明少量关键 checkpoint；
- 提供结构化失败定位和基础恢复。

#### L2：Semantic adapter

在 L1 基础上增加：

- 关键步骤输入输出 contract；
- standard tables；
- parser；
- 生物学 assertions；
- claim-specific limitations；
- 结构化恢复策略；
- 结果级和证据级报告。

L2 需要领域专家参与，因为系统无法仅从 shell 或 DAG 自动推断生物学语义。

### 4.4 建议新增的开发工具

建议实现：

```bash
abi plugin wrap-cli <command>
abi plugin import-nextflow <repository>
abi plugin import-snakemake <directory>
abi plugin lint <plugin>
abi plugin test <plugin>
abi plugin certify <plugin> --profile black-box
```

Importer 应生成候选声明，而不是声称自动理解生物学：

- Nextflow：读取 `nextflow_schema.json`、固定 revision，生成黑盒执行节点；
- Snakemake：读取 config schema、固定 Snakefile/version；
- CLI：从 JSON Schema、OpenAPI 或人工最小模板生成；
- 自动创建 generic artifact manifest、terminal contract 和测试 skeleton；
- 开发者审查后冻结；
- 生物学 assertions 始终需要人工确认。

### 4.5 建议新增 BlackBoxPipelinePlugin

最低成本插件应允许近似如下的纯声明：

```yaml
plugin_id: published_rnaseq
adapter_level: black_box

upstream:
  engine: nextflow
  source: github.com/example/pipeline
  revision: v2.1.0
  schema: nextflow_schema.json

execution:
  command:
    - nextflow
    - run
    - "{source}"
    - -r
    - "{revision}"
    - -params-file
    - "{config}"

inputs:
  samplesheet: {type: file, format: csv}

outputs:
  result_dir:
    type: directory
    contract:
      contains: [multiqc_report.html, results.tsv]

resources:
  reference: {required: true}
```

BAI 自动生成或提供：

- 插件入口；
- 单节点 DAG；
- tool registry；
- generic parser；
- artifact manifest；
- default report；
- contract tests。

---

## 5. Agent 如何调用 BAI

### 5.1 当前显式调用

显式调用指用户或 Agent 明确指定 ABI，例如：

- “使用 ABI 分析这批 RNA-seq 数据”；
- 在 harness 中选择或提及 ABI skill；
- 直接调用 `abi_list_types`、`abi_plan` 等 MCP 工具；
- 直接运行 ABI CLI；
- 使用 ABI 导出的 provider-native function tools。

当前仓库支持为以下平台安装 integration：

```bash
abi agent install claude-code --scope project
abi agent install opencode --scope project
abi agent install codex --scope project
```

安装器写入：

- 一份共享 ABI operator skill；
- 一份平台对应的 safe MCP 配置。

当前共享生命周期为：

```text
abi_list_types
→ abi_export_agent_context
→ abi_query
→ abi_plan
→ abi_check
→ abi_dry_run
→ user review
→ abi_run
→ abi_inspect
→ abi_validate_result
→ abi_report
```

当前还支持导出：

- OpenAI-compatible function descriptors，可用于 OpenAI、Kimi、Qwen、DeepSeek 等；
- Anthropic tools；
- Gemini function declarations；
- MCP tools。

### 5.2 当前隐式调用

隐式调用指用户只表达生物学目标，harness 根据 skill description 或 tool description
自动加载 ABI。例如：

> 帮我分析这批细菌 WGS，检查 MLST 和耐药基因。

当前共享 skill 的 description 覆盖 sequencing、metagenomics、transcriptomics、
plasmid、bacterial WGS 和 amplicon 等请求。harness 选择该 skill 后，skill 指导 Agent
首先调用 `abi_list_types`。

必须明确：

> 当前 ABI 不拥有自然语言路由器。是否自动加载 ABI skill，由各 harness 的
> skill-selection/tool-selection 机制决定。

因此当前只能主张：

> ABI 提供兼容 harness discovery 的 skill metadata 和机器可读工具描述符。

不能主张：

> ABI 能保证自动识别所有组学请求并接管分析。

### 5.3 建议新增确定性模块匹配

建议新增只读工具：

```text
abi_match_analysis
```

输入示例：

```json
{
  "goal": "Compare treated and untreated paired airway RNA-seq samples",
  "input_files": ["samples.tsv", "*.fastq.gz"]
}
```

输出示例：

```json
{
  "candidates": [
    {
      "analysis_type": "rnaseq_expression",
      "confidence": "high",
      "matched_capabilities": [
        "paired RNA-seq",
        "differential expression"
      ],
      "missing_information": [
        "reference genome",
        "annotation GTF"
      ],
      "excluded": []
    }
  ]
}
```

该工具只能在已安装、已审核模块中匹配，不应：

- 联网搜索 pipeline；
- 自动下载未知代码；
- 自动执行；
- 根据模糊匹配替用户做高风险生物学选择。

### 5.4 Capability manifest

每个模块建议增加：

```yaml
capability:
  intents:
    - differential_expression
    - paired_rnaseq
  input_modalities:
    - paired_end_fastq
    - sample_sheet
  organisms:
    - human
  required_design_fields:
    - sample_id
    - condition
  supports:
    paired_design: true
  exclusions:
    - single_cell_rnaseq
    - spatial_transcriptomics
  example_requests:
    - Compare treated and untreated paired bulk RNA-seq samples.
```

隐式发现可以基于这些显式元数据，而不是让模型仅根据插件名称猜测。

### 5.5 隐式发现与显式执行的边界

核心原则：

> 模块发现和推荐可以隐式发生，真实执行不能隐式发生。

默认 safe MCP profile 不暴露执行工具。正式执行应由 harness 外部审批，并最终发展为
与具体 plan、config、input checksum、output directory 和资源预算绑定的 approval
receipt，而不是仅依赖 Agent 可以提交的 `confirm_execution=true` 布尔字段。

---

## 6. 第三方开发者生态

### 6.1 从开发指南升级为规范与工具链

仅提供长篇开发文档不足以建立生态。建议形成：

1. 版本化 module specification；
2. 模块 JSON Schema；
3. SDK 和基类；
4. importer/scaffolder；
5. lint；
6. conformance test suite；
7. certification profile；
8. reference modules；
9. 版本兼容和升级策略。

### 6.2 规范性语言

正式规范使用 MUST、SHOULD、MAY：

```text
A module MUST declare a stable module ID.
A module MUST pin or record the upstream workflow version.
A module MUST declare required inputs.
A module MUST not execute external tools during planning.
A module MUST declare terminal output contracts.
A semantic module MUST expose claim-relevant result tables.
A module SHOULD provide machine-readable limitations.
```

在缺少独立规范和 conformance suite 前，论文宜写：

> BAI proposes a workflow module specification and provides its reference implementation.

不宜直接声称 BAI 已经是行业标准。

### 6.3 Conformance certification

建议输出：

```text
Module identity                   PASS
No side effects during plan       PASS
Configuration schema              PASS
Upstream version pinned           PASS
Terminal output contracts         PASS
Result provenance                 PASS
Agent discovery                   PASS
Semantic result interface         NOT_IMPLEMENTED
Certified profile                 L0 BLACK-BOX
```

### 6.4 一份共享 operator skill

第三方插件开发者不应分别编写：

- Claude Code skill；
- Codex skill；
- OpenCode skill；
- OpenAI function schema；
- Kimi function schema；
- Gemini function schema。

推荐结构：

```text
Claude Code / Codex / OpenCode / other harness
                    ↓
          one shared BAI operator skill
                    ↓
          dynamic module discovery
                    ↓
          module-specific context
```

开发者只定义一次 module manifest，BAI 为不同平台生成描述符。harness adapter 应保持
轻量，不包含 workflow-specific 逻辑。

### 6.5 接入成本必须被量化

建议选择 3–5 个未参与 BAI 开发的已发表 pipeline，覆盖 Nextflow、Snakemake 和单体
CLI，由未参与核心开发的人分别完成 L0、L1、L2 适配。

记录：

| 指标 | 含义 |
| --- | --- |
| Time to first plan | 首次成功生成 BAI plan 的时间 |
| Time to first valid run | 首次真实运行通过的时间 |
| Handwritten LOC | 排除生成代码后的人工代码量 |
| Required annotations | 人工声明的字段和契约数量 |
| Upstream modifications | 是否修改原 pipeline |
| Adapter defects | 适配中发现的错误数 |
| Upgrade effort | 上游版本升级后的维护时间 |
| Feature coverage | 获得的 BAI 保证等级 |

目标不是证明“任何 pipeline 十分钟接入”，而是证明：

1. L0 可以不修改上游分析方法；
2. 一次接入后可被多个 Agent 和 transport 复用；
3. L2 的额外人工成本换来了可测量的验证能力；
4. 上游升级不需要维护第二套完整 DAG。

---

## 7. 安全、可靠与审计的可量化定义

### 7.1 不使用模糊的“安全总分”

建议将策略违规拆成三类：

1. **Unsafe attempt**：Agent 请求了预注册策略禁止的操作，但系统可能成功阻断；
2. **Unsafe execution**：系统实际放行了禁止行为并产生副作用；
3. **Unsafe acceptance**：无效输出被标记为成功、用于下游或发布为结论。

普通超时、崩溃或与论文结果不一致不自动等于“不安全”。只有错误放行、错误接受或越过
证据边界才属于安全问题。

### 7.2 可机器判定的违规事件

预先冻结策略 \(P\)。以下事件可以构成违规：

- 没有有效授权却启动真实计算；
- 授权后 plan、配置、输入或输出目录发生变化；
- preflight 失败后仍启动外部工具；
- 调用了未声明工具、参数或分支；
- 写入允许目录之外；
- checksum 不匹配后继续运行；
- 复用未经验证的历史输出；
- output contract 或 assertion 失败，却将步骤标记为成功；
- provenance 不完整，却声称运行可复现；
- 不满足证据条件，却发布生物学结论。

建议分别报告：

\[
\text{Unsafe execution rate}
=
\frac{\text{实际产生副作用的违规场景数}}
{\text{预注册违规挑战场景数}}
\]

\[
\text{Blocking rate}
=
\frac{\text{被正确阻断的违规尝试数}}
{\text{全部违规尝试数}}
\]

以及：

- invalid-output acceptance rate；
- diagnostic accuracy；
- recovery success rate；
- wasted compute before blocking。

### 7.3 审计证据的三个层级

#### Evidence generation

机械验证：

- commands、inputs、tool versions、resources、checksums、progress 是否存在；
- 每个实际步骤是否具有唯一记录；
- 失败和中断后记录是否可解析；
- 命令、状态、退出码、输入输出是否一致；
- provenance 与结果 hash 是否一致。

#### Evidence availability

验证 Agent 能通过稳定接口得到：

- run health；
- 失败步骤；
- contract violation；
- evidence paths；
- checksum；
- structured recovery action。

#### Evidence utilization

只有行为实验才能证明 Agent 实际使用了证据。隐藏任务可以设置：

- 旧报告显示成功，但本次 provenance 记录失败；
- exit code 为 0，但关键输出缺失；
- stdout 声称成功，但生物学 assertion 失败；
- 报告摘要与标准表冲突。

建议指标：

\[
\text{Evidence utilization rate}
=
\frac{\text{正确 inspect/validate 并据证据决策的任务数}}
{\text{必须检查证据的任务数}}
\]

并比较：

- 完整机器证据；
- provenance 被隐藏；
- 只有普通日志；
- 只有 Agent 自己生成的文字摘要。

在未完成该实验前，只能主张 BAI “生成并暴露机器可读证据”，不能主张 Agent 必然使用
这些证据改善决策。

---

## 8. 多 Harness 验证

### 8.1 是否需要

如果论文声称 BAI 是平台无关、面向通用型 Agent 的模块接口，则需要多 harness 验证。
但这不应称为“相关性验证”，而应称为：

- cross-harness portability validation；
- cross-harness replication；
- harness × interface interaction analysis。

多个 harness 得分相关并不能证明可移植性。需要回答：

> BAI 的调用和效果是否依赖某个 harness 特有的 skill loader、prompt、tool selection、
> approval UI 或 MCP 实现？

### 8.2 不做不可控的全矩阵

不建议直接执行：

```text
3 models × 3 harnesses × 4 interfaces × 20 tasks × 5 repeats
```

很多 harness 绑定特定模型，会使模型和 harness 混杂，而且真实组学运行成本过高。

建议拆成三层。

### 8.3 第一层：协议兼容性

在 Claude Code、OpenCode、Codex 等平台验证：

- skill 安装和发现；
- safe MCP 加载；
- tool schema；
- `list-types`、`plan`、`check`、`dry-run` 信封；
- execution tool 默认隐藏；
- error envelope；
- artifact path 和 result schema。

使用 mock/synthetic workflow，不需要真实生物学计算。

当前仓库已经有三套 integration 资产和配置测试，但主要属于安装、文件一致性和 MCP
注册级验证，不能替代真实 harness 端到端行为验证。

### 8.4 第二层：跨 Harness 行为复现

选择至少两个能够连接到同一模型 endpoint 的 harness，例如：

- OpenCode；
- 最小 reference MCP/function-calling harness；
- 另一个能连接相同 Qwen/Gemma endpoint 的 coding harness。

保持一致：

- model checkpoint；
- quantization；
- system prompt；
- shared BAI skill；
- MCP tools；
- token、时间和步骤预算；
- sandbox；
- fixture；
- retry policy。

对每个 harness 计算：

\[
\Delta_h = Score_{BAI,h} - Score_{control,h}
\]

检查：

- 效应方向是否一致；
- effect size；
- interface × harness interaction；
- tool selection；
- 生命周期遵循；
- 故障诊断和恢复；
- evidence utilization。

不要仅计算 Pearson 或 Spearman correlation。

### 8.5 第三层：真实生物学验证

Airway、WGS、plasmid 等昂贵运行可以只在一个冻结的 reference harness 中完成。

真实数据轨验证：

- workflow 是否完成；
- 是否恢复预注册生物学端点；
- provenance 是否完整；
- 结果边界是否被正确披露。

不需要为了证明 harness 兼容性，在所有 harness 中重复完整的大规模组学计算。

### 8.6 推荐最小矩阵

| 证据目标 | Harness | 模型 | 数据 |
| --- | ---: | ---: | --- |
| Tool/schema compatibility | 3 | mock/no model | synthetic |
| Skill discovery 与生命周期遵循 | 2 | 同一 Qwen/Gemma endpoint | synthetic + fault fixtures |
| BAI vs skill/Shell 效应 | 1 个主 harness + 1 个复现 harness | Qwen + Gemma | 小型可执行任务 |
| 生物学有效性 | 1 个冻结 reference harness | 冻结模型 | Airway/WGS/plasmid |

---

## 9. 推荐实验结构

### 9.1 Agent 接口效应

对于相同模型和相同 workflow，建议比较：

1. Native workflow CLI/Shell；
2. 信息量匹配的静态 skill/docs + Shell；
3. 标准化 BAI module metadata，但不启用 runtime contracts；
4. 完整 BAI module + contract runtime。

Shell 对照必须获得相同的底层 workflow 和近似等量信息，不能要求 Shell 组从零编写
pipeline，而 BAI 组直接获得专家预封装方法。否则比较的是专家知识，而不是模块协议或
控制层。

### 9.2 生物学有效性

真实数据评分直接读取运行产物：

- Airway：排序相关、效应方向、sentinel genes；
- WGS：MLST、AMR、SNP 距离等明确端点；
- plasmid：独立 truth 下的集合、precision、recall、F1 或其他预注册指标。

这条证据只能说明 BAI 没有破坏底层科学输出，不能单独证明 BAI 相对 Shell 的 Agent
效应。

### 9.3 开发者可用性

通过第三方 pipeline onboarding study 报告接入时间、人工 LOC、自动生成比例、错误数、
升级成本和 conformance profile。

---

## 10. 论文主张边界

### 10.1 当前较稳妥的主张

> BAI 提出了一种面向通用型 Agent 的生物信息学 workflow module framework。它将经过
> 审核的既有 pipeline 封装为具有固定身份、类型化配置、受控执行和机器可读证据接口的
> Agent-ready modules，并通过共享 operator skill 和 MCP/function descriptors 暴露给
> 不同 Agent harness。

### 10.2 完成实验后可以主张

- BAI modules 相比信息匹配的静态 skills 提高了配置或任务完成率；
- runtime contracts 降低了 policy violation execution 或 invalid-output acceptance；
- Agents 在隐藏诊断任务中实际利用机器证据改善了决策；
- 模块接口在多个 harness 上保持兼容；
- 黑盒 adapter 降低了外部 pipeline 的重复集成工作；
- 真实数据执行恢复了预注册的生物学端点。

### 10.3 当前不能直接主张

- 任意 pipeline 可以零配置接入；
- BAI 能自动理解外部 pipeline 的生物学语义；
- 所有 Agent 都会自动选择 BAI；
- 生成 provenance 等于 Agent 一定使用 provenance；
- `confirm_execution=true` 等于不可伪造的人类授权；
- BAI 比所有 workflow engines 更安全；
- BAI 保证生物学结论绝对正确；
- 在少数模型或 harness 上的结果可以推广到所有 Agent。

---

## 11. 建议工程优先级

### P0：明确规范边界

1. 固定 `BAI Workflow Module Specification v0.1`；
2. 明确 L0/L1/L2 conformance profile；
3. 定义 capability manifest；
4. 将“隐式发现”和“显式执行”写入规范；
5. 将安全主指标改为策略违规、阻断和无效结果接受。

### P1：降低接入成本

1. 实现 `BlackBoxPipelinePlugin`；
2. 实现 `wrap-cli`；
3. 实现基础 Nextflow/Snakemake importer；
4. 自动生成单节点 DAG、terminal contract、artifact manifest 和测试；
5. 建立 plugin lint/test/certify。

### P2：加强 Agent 调用

1. 实现 `abi_match_analysis`；
2. 扩展 capability metadata；
3. 将匹配理由、缺失输入和 exclusion 返回给 Agent；
4. 保持真实执行在 safe profile 中不可见；
5. 设计 plan-bound approval receipt。

### P3：验证与论文

1. 完成 3 harness 协议兼容性测试；
2. 完成 2 harness、同模型 endpoint 的行为复现；
3. 完成 BAI vs information-matched skill/Shell 配对实验；
4. 完成 evidence utilization hidden tasks；
5. 完成第三方 pipeline onboarding study；
6. 独立报告真实数据 biological validity。

---

## 12. 推荐标题与摘要用语

### 推荐标题

> **BAI: Contracted Workflow Modules for Agent-Mediated Bioinformatics**

或：

> **BAI: An Agent-Ready Workflow Module Framework for Auditable Bioinformatics**

### 推荐中文定位

> BAI 不是新的生物信息学工作流引擎，也不是一组仅依靠提示词约束模型的 skills。它是
> 一套将经过审核的既有生物信息学 pipeline 封装为版本固定、参数类型化、运行受控并
> 具有机器可读证据接口的 Agent-ready workflow module framework。

### 推荐英文定位

> BAI separates harness-specific capability discovery from platform-neutral workflow operation.
> Thin harness adapters install a shared operator skill and expose the same lifecycle tools, while
> workflow modules remain independent of provider-specific prompts and function schemas. Implicit
> discovery is advisory and harness-dependent; module execution remains explicit and
> permission-gated.

---

## 13. 最终结论

BAI 最有防御力的创新点不是“重新实现一个更安全的 Nextflow”，而是：

1. 将生物信息学 workflow 转换成统一的 Agent-ready executable modules；
2. 将普通 skills 中咨询性的说明升级为可执行、可检查的模块契约；
3. 将不同 harness 的 discovery adapter 与 workflow-specific implementation 解耦；
4. 允许已有 pipeline 从黑盒执行逐步升级到生物学语义验证；
5. 用机器可判定的 policy violation、contract rejection 和 evidence utilization 取代
   模糊的安全或审计声明；
6. 通过多 harness conformance 与行为复现证明接口不是某个 Agent 平台的特例。

这一路线承认领域开发者仍需提供必要的生物学知识，但把该成本限定为一次性、分级、
可测试的模块工程，并使其能够被多个 Agent、transport 和 runtime 后端复用。
