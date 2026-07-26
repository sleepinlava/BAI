---
name: abi-plugin-development
description: Develop or revise ABI bioinformatics workflow modules and plugins. Use when adding an ABI analysis type, integrating a published pipeline or CLI, changing a plugin DAG or tool set, or adding databases, models, references, containers, and other runtime resources. The developer chooses the workflow and versions, the agent fills in engineering details, every resource requires developer review, and the finished change receives an agent code review.
---

# ABI 插件开发

这个 skill 用来把已经选定的生物信息学流程接入 ABI。流程和版本由开发者决定，Agent
负责补齐契约、配置、解析器和测试。外部资源必须由开发者逐项核对，代码完成后再做一次
独立的 diff 审查。

## 名称约定

项目和产品统一写作 `ABI`。Python 包、命令行、manifest 和环境变量使用小写 `abi`，
例如 `abi-plugin.yaml` 和 `abi contract-lint`。

AutoPlasm 只指内置的 `metagenomic_plasmid` 插件。新建项目级文件、类、skill 或配置时，
不要继续使用 `autoplasm`。`autoplasm_agent/SKILL.md` 也不是通用插件模板。

## 开始前先看现有实现

先阅读仓库说明和当前工作区状态，再找一个接入方式最接近的插件作为参考。重点查看：

- `docs/zh/plugin_development_guide.md`
- `docs/zh/development_workflow.md`
- `plugins/<analysis_type>/`
- `src/abi/plugin.py`、`src/abi/interfaces.py` 和 `src/abi/testing/`
- `environments.yaml` 与 `envs/`

比较插件时，先判断它是原生声明式 DAG，还是对 Nextflow、Snakemake 或成熟 CLI 的适配。
不要因为 `metagenomic_plasmid` 文件最多，就默认照搬它的结构。保留工作区中与本次任务
无关的修改。

## 第一步：由开发者确定流程和版本

开发者需要先给出一张可以直接讨论的流程图。Mermaid、Graphviz 或节点/边表都可以，
但不能只有一段笼统描述。

流程图和配套说明至少要写清：

- 插件 ID、生物学目的、支持的输入和预期结果；
- 执行引擎，以及采用原生 DAG 还是外部 pipeline 适配；
- 每个节点的 ID、工具或 pipeline、准确版本和依赖关系；
- 各节点的输入、输出、可选分支和启用条件；
- 数据库、模型、参考序列、索引、容器等外部资源；
- 会影响生物学解释的阈值；
- 标准结果表、发布产物、已知限制和不支持的用法。

Agent 可以整理图、统一节点名称并指出缺项，但不能替开发者选择流程、版本或科学阈值。
整理后，用一张简短的表格列出流程图、工具版本、资源版本、科学阈值和接入层级的状态。

只有开发者明确确认“流程和版本已经定稿”后，才进入下一步。仍有待定项时，列出待定项
即可，不要提前生成插件骨架。

## 第二步：由 Agent 补齐工程细节

流程定稿后，Agent 根据当前仓库和上游官方文档提出实现方案，包括：

- 稳定的节点和工具 ID；
- 参数类型、样本表字段和默认配置；
- 输入输出路径、输出契约、断言和合理的豁免；
- 资源预检和必要的 sentinel 文件；
- parser 映射、标准表字段、单位、缺失值和 provenance；
- 结构化诊断、恢复建议、测试、golden trace 和文档更新；
- Conda 环境分配以及对 runtime lock 的影响。

建议中要区分“工程实现”和“会改变科学行为的选择”。后一类必须再次交给开发者确认。

接入成熟外部 pipeline 时，通常保留它自己的 DAG。ABI 负责固定入口和版本、检查输入、
采集 trace、验证最终产物并发布 provenance。除非开发者明确选择原生 ABI DAG，否则
不要在 `pipeline_dag.yaml` 中重写一遍上游内部流程。

## 第三步：逐项审查外部资源

在 `plugins/<analysis_type>/resource_review.yaml` 中记录资源审查结果。工具发行包、pipeline
revision、容器、数据库、模型、参考基因组、注释、索引和远程辅助文件都要单独列出。

```yaml
schema_version: "1"
plugin_id: "<analysis_type>"
workflow_review:
  graph_fingerprint: "<normalized graph sha256>"
  approved_by: "<reviewer>"
  approved_on: "<YYYY-MM-DD>"
resources:
  - id: "<resource_id>"
    role: "<why it is needed>"
    kind: "<tool|pipeline|container|database|model|reference|index|other>"
    version: "<exact version, release, revision, or digest>"
    authoritative_source: "<official URL>"
    retrieved_on: "<YYYY-MM-DD>"
    license_or_terms: "<license or access terms>"
    integrity:
      algorithm: "sha256"
      value: "<checksum>"
    expected_layout: ["<required path or sentinel>"]
    acquisition: "<install, download, or build method>"
    configuration: "<config key or environment mapping>"
    validation: "<safe identity and usability check>"
    citation: "<DOI, accession, or canonical citation>"
    limitations: ["<known constraint>"]
    review:
      status: "<approved|rejected|unverified>"
      reviewer: "<reviewer>"
      reviewed_on: "<YYYY-MM-DD>"
      notes: "<what was checked>"
```

资料优先取自项目官网、正式 release、官方镜像仓库、数据库发布方、论文 DOI 页面和长期
存档。搜索结果摘要、第三方教程和镜像站只能帮助定位，不能作为唯一依据。

开发者需要逐项确认以下内容：

1. 资源适合流程图中的用途；
2. 链接来自权威来源；
3. 版本、revision、数据库 release 或镜像 digest 准确；
4. 许可和访问条件允许预期用法；
5. checksum 或其他不可变身份可以核对；
6. 获取与配置方法在目标环境可用；
7. 文件布局、sentinel 和验证方法与实际安装一致；
8. 引用和限制说明准确。

Agent 初次填写的记录一律标成 `unverified`。开发者需要填写 reviewer、日期和审查说明，
再将状态改为 `approved`。只要必需资源中还有未批准项，就不要编写下载脚本、生产配置
或依赖这些资源的契约。

不要接受 `latest`、未固定的分支、没有 digest 的容器标签、未注明 release 的数据库或
空 checksum。如果上游确实没有不可变制品，开发者应在 notes 中写明替代校验方法和残余
风险。

## 第四步：实现插件

按当前声明式接口完成最小、完整的一组修改：

1. 注册 entry point，并保持注册键、`plugin_id` 和插件类身份一致。
2. 添加 `abi-plugin.yaml`、默认配置、样本表模板、`pipeline_dag.yaml`、
   `tool_registry.yaml`、`standard_tables.yaml` 和非空 `limitations.yaml`。
3. 每个外部工具只保留一份权威 contract；registry 只记录运行策略。
4. 外部工具节点必须有有效输出契约。无输出聚合节点使用带理由的显式豁免。
5. 工具到环境的映射放在 `environments.yaml`，并同步受影响的 `envs/*.yml`。
6. 资源预检只引用已经批准的审查记录，并在 provenance 中记录版本、路径和身份。
7. 简单 TSV、JSON 和日志优先使用声明式 parser；确有语义转换时再写 Python。
8. 核心保持传输无关，不为单个插件新增专用 MCP 或模型 schema。
9. 根据接入层级添加单元、集成、golden trace 和 smoke 测试。
10. 公共行为发生变化时，同步英文和中文文档。

如果实现过程中需要更换资源、版本、checksum 或获取方式，先回到资源审查，不要直接
修改已经批准的记录。

## 第五步：验证

先跑插件相关的快速检查，再按修改范围补齐仓库质量门禁。基础检查包括：

```bash
abi contract-lint --type <analysis_type> --strict
abi query --type <analysis_type> --what stages
abi query --type <analysis_type> --what tools
abi export-agent-context --type <analysis_type>
abi doctor-agent --type <analysis_type>
pytest <focused plugin tests> -q
ruff check <changed Python and tests>
ruff format --check <changed Python and tests>
mypy src/abi/ --ignore-missing-imports
git diff --check
```

需要时再运行 plugin validation、dry-run、集成测试、contract coverage audit 和真实工具
smoke 测试。Docker、发布面或双语文档发生变化时，按仓库指南补跑相应检查。

交付说明要记录实际运行的命令和结果。没有运行的检查也要写清原因和风险。dry-run 只能
证明计划与命令能够生成，不能当作生物学验证结果。

## 最后做一次代码审查

实现和测试完成后，从头查看完整 diff，按审查别人提交的代码来处理。重点检查：

- 实现是否偏离开发者批准的流程、版本、阈值或资源；
- 是否出现重复或冲突的事实来源；
- DAG 的依赖、scope、分支、路径和计划是否稳定；
- 输出契约是否过弱，豁免是否合理，是否存在隐藏执行路径；
- 资源是否固定版本，获取方式是否安全，provenance 是否完整；
- parser、schema、标准表、单位和科学表述是否一致；
- entry point、环境、打包、Docker、发布和文档是否遗漏；
- 正常、失败、权限和恢复路径是否有回归测试。

先按严重程度列出问题，并给出文件和行号。修复确认的问题后，重跑相关检查，再看一次
diff。没有待处理问题时，交付结果应包含：

- 已批准流程的 fingerprint；
- `resource_review.yaml` 的位置和审查状态；
- 修改文件；
- 验证命令及结果；
- 最终代码审查结论；
- 未运行的检查、残余风险和仍需开发者决定的事项。

流程或资源尚未批准、检查失败或代码审查仍有未解决问题时，插件还不能算完成。
