# ABI Skills

`skills/` 收录随 ABI 安装的 Agent skills。维护者可以在这里核对工具用途、输入输出、
资源要求和排错方法；Agent 则通过这些说明使用 `abi` CLI 和统一的生命周期接口。

## 先分清几个名字

项目和产品统一写作 **ABI**，Python 包、CLI、manifest 和环境变量使用小写 `abi`。
AutoPlasm 是内置 `metagenomic_plasmid` 插件的历史名称，不代表整个项目。

新建项目级文件、skill、类或配置时不要再用 `autoplasm`。已有的 `autoplasm_agent`、
`autoplasm-*` 环境和 `autoplasm` 命令仅为该插件保留。

## 安装 ABI Skills 到 Claude Code

```bash
# 通过 abi CLI 安装 ABI skills
abi install-skills

# 自定义目标目录
abi install-skills --target /path/to/skills

# 覆盖已有文件
abi install-skills --force
```

安装后，Claude Code 会自动加载 skills 目录中的所有 SKILL.md 文件。

## 现有 Agent skills

| 文件 | 用途 |
| --- | --- |
| `abi_agent/SKILL.md` | ABI operator skill，说明如何使用生命周期命令和 Agent 传输接口。 |
| `autoplasm_agent/SKILL.md` | 内置 `metagenomic_plasmid` 插件的历史兼容 skill，只用于该插件，不是 ABI 仓库级 operator。 |
| `abi-plugin-development/SKILL.md` | ABI 插件开发门禁：开发者冻结流程图与版本，Agent 补充契约和实现建议，开发者逐项审查资源，最后由 Agent 实现、验证并进行代码审查。 |

ABI 模块的权威入口是 `plugins/<analysis_type>/` 中的 manifest、DAG、registry、contracts、
schemas 和 limitations，以及 `src/abi/` 中的共享运行时契约校验。Markdown skill 文件
只负责解释这些契约，不应另写一套实现事实。

## 文件分工

| 文件 | 用途 |
| --- | --- |
| `abi-plugin-development/SKILL.md` | ABI workflow module 的开发、资源审查、验证和最终代码审查流程。 |
| `abi_agent/SKILL.md` | 使用 `abi` CLI 操作所有已注册 ABI 模块。 |
| `autoplasm_agent/SKILL.md` | 操作内置 `metagenomic_plasmid` 插件的历史兼容说明。 |
| `{tool}/SKILL.md` | 当前主要服务于 `metagenomic_plasmid` 的外部工具 skill。 |
| `README.md` | 当前文件，作为 skills 目录的维护说明、详细索引和同步清单。 |

## Agent 如何使用这些 skills

Agent 处理 ABI workflow module 时必须保留这个控制路径：

```text
validate-sample-sheet
check-tools
check-resources
plan
dry-run
inspect provenance
run
report
```

除非正在调试单个失败步骤，否则不要直接运行已注册的底层工具。直接运行会绕过
`commands.tsv`、stdout/stderr、资源状态和标准表记录。

dry-run 只说明 planner、命令模板和 provenance 能正常生成。生物学结论必须来自真实
运行得到的工具输出、标准表和报告。单个工具有论文支持，也不等于整条工作流已经完成
科学验证；相关要求见 `docs/workflow_validation.md`。

## `metagenomic_plasmid` 工具 skill 的写法

每个 `{tool}/SKILL.md` 应包含以下小节：

| 小节 | 必须说明的内容 |
| --- | --- |
| `Purpose` | 工具在 `metagenomic_plasmid` ABI 模块中解决什么问题。 |
| `When to Use` | 哪些平台、步骤或配置会选择该工具。 |
| `Inputs` | registry 输入、命令模板参数和上游步骤提供的字段。 |
| `Outputs` | 工具原始输出、标准化输出和 provenance 日志位置。 |
| `Environment` | 对应 `envs/*.yml`、runtime env_name、executable 和本地 `.mamba` 解析规则。 |
| `Command Template` | 与 `plugins/metagenomic_plasmid/tool_registry.yaml` 完全一致的 command template。 |
| `Auto-selection Rules` | default/optional、required/recommended、平台路由和限制。 |
| `Interactive Parameters` | 用户需要选择或确认的阈值、数据库、模型、策略或跳过逻辑。 |
| `Failure Handling` | 真实运行前检查项，以及失败后查看 `commands.tsv` 和 step logs 的顺序。 |
| `Normalization` | 原始输出如何归一化到 `tables/*.tsv` 或稳定下游路径。 |
| `Agent Usage Notes` | agent 不应绕过 CLI、不能夸大 dry-run、需要先更新配置再执行计划。 |
| `Example` | 推荐 dry-run、run 或 report 示例。 |

如果工具依赖大型数据库、模型、参考图、索引或特殊输入，应在 `Inputs`、
`Interactive Parameters` 和 `Failure Handling` 中写清楚，不要只放在示例里。

## 4. `metagenomic_plasmid` 工具 skill 索引

以下索引来自 `plugins/metagenomic_plasmid/tool_registry.yaml`。表中的 `autoplasm-*`
环境名和 `autoplasm list-tools` 命令是该内置插件保留的技术兼容标识，不是项目名称。

| 工具 | 类别 | 默认状态 | 必需性 | 运行环境 | Skill |
| --- | --- | --- | --- | --- | --- |
| `fastp` | `qc` | default | required | `autoplasm-qc` | [fastp](fastp/SKILL.md) |
| `fastqc` | `qc` | default | recommended | `autoplasm-qc` | [fastqc](fastqc/SKILL.md) |
| `multiqc` | `qc` | default | recommended | `autoplasm-qc` | [multiqc](multiqc/SKILL.md) |
| `nanoplot` | `qc` | default | recommended | `autoplasm-qc` | [nanoplot](nanoplot/SKILL.md) |
| `filtlong` | `qc` | default | recommended | `autoplasm-qc` | [filtlong](filtlong/SKILL.md) |
| `hifiadapterfilt` | `qc` | default | recommended | `autoplasm-qc` | [hifiadapterfilt](hifiadapterfilt/SKILL.md) |
| `megahit` | `assembly` | default | required | `autoplasm-assembly` | [megahit](megahit/SKILL.md) |
| `metaspades` | `assembly` | optional | required | `autoplasm-assembly` | [metaspades](metaspades/SKILL.md) |
| `metaflye` | `assembly` | default | required | `autoplasm-assembly` | [metaflye](metaflye/SKILL.md) |
| `hifiasm_meta` | `assembly` | default | recommended | `autoplasm-assembly` | [hifiasm_meta](hifiasm_meta/SKILL.md) |
| `opera_ms` | `assembly` | default | required | `autoplasm-assembly` | [opera_ms](opera_ms/SKILL.md) |
| `quast` | `assembly_qc` | default | recommended | `autoplasm-assembly` | [quast](quast/SKILL.md) |
| `genomad` | `plasmid_detection` | default | required | `autoplasm-plasmid-detect` | [genomad](genomad/SKILL.md) |
| `plasme` | `plasmid_detection` | optional | recommended | `autoplasm-plasmid-detect` | [plasme](plasme/SKILL.md) |
| `plasx` | `plasmid_detection` | optional | recommended | `autoplasm-plasmid-detect` | [plasx](plasx/SKILL.md) |
| `plasmaag` | `plasmid_binning` | optional | recommended | `autoplasm-plasmid-binning` | [plasmaag](plasmaag/SKILL.md) |
| `gplas2` | `plasmid_binning` | optional | recommended | `autoplasm-plasmid-binning` | [gplas2](gplas2/SKILL.md) |
| `plasmidfinder` | `typing` | optional | recommended | `autoplasm-annotation` | [plasmidfinder](plasmidfinder/SKILL.md) |
| `mob_typer` | `typing` | optional | recommended | `autoplasm-annotation` | [mob_suite](mob_suite/SKILL.md) |
| `copla` | `typing` | optional | recommended | `autoplasm-annotation` | [copla](copla/SKILL.md) |
| `plasmidhostfinder` | `host_prediction` | optional | recommended | `autoplasm-annotation` | [plasmidhostfinder](plasmidhostfinder/SKILL.md) |
| `kraken2` | `host_prediction` | optional | recommended | `stats` | [kraken2](kraken2/SKILL.md) |
| `metaphlan` | `host_prediction` | reads default | recommended | `stats` | [metaphlan](metaphlan/SKILL.md) |
| `bakta` | `annotation` | default | recommended | `autoplasm-annotation` | [bakta](bakta/SKILL.md) |
| `abricate` | `annotation` | default | recommended | `autoplasm-annotation` | [abricate](abricate/SKILL.md) |
| `amrfinderplus` | `annotation` | default | recommended | `autoplasm-annotation` | [amrfinderplus](amrfinderplus/SKILL.md) |
| `mob_suite` | `annotation` | optional | recommended | `autoplasm-annotation` | [mob_suite](mob_suite/SKILL.md) |
| `isescan` | `annotation` | default | recommended | `autoplasm-annotation` | [isescan](isescan/SKILL.md) |
| `integronfinder` | `annotation` | default | recommended | `autoplasm-integronfinder` | [integronfinder](integronfinder/SKILL.md) |
| `bowtie2` | `abundance` | default | required | `autoplasm-abundance` | [bowtie2](bowtie2/SKILL.md) |
| `minimap2` | `abundance` | default | required | `autoplasm-abundance` | [minimap2](minimap2/SKILL.md) |
| `samtools` | `abundance` | default | required | `autoplasm-abundance` | [samtools](samtools/SKILL.md) |
| `coverm` | `abundance` | default | recommended | `autoplasm-abundance` | [coverm](coverm/SKILL.md) |
| `blast` | `comparative_genomics` | optional | recommended | `autoplasm-annotation` | [blast](blast/SKILL.md) |
| `mmseqs2` | `comparative_genomics` | optional | recommended | `autoplasm-annotation` | [mmseqs2](mmseqs2/SKILL.md) |
| `mummer` | `comparative_genomics` | optional | recommended | `autoplasm-annotation` | [mummer](mummer/SKILL.md) |
| `clinker` | `comparative_genomics` | optional | recommended | `autoplasm-visualization` | [clinker](clinker/SKILL.md) |
| `fastspar` | `network` | default | recommended | `stats` | [fastspar](fastspar/SKILL.md) |
| `report_markdown` | `report` | default | recommended | `autoplasm-base` | [report_markdown](report_markdown/SKILL.md) |

## 5. `metagenomic_plasmid` 平台到工具的默认路线

| 平台 | QC | Assembly | Plasmid detection | Host evidence | Annotation/typing | Abundance |
| --- | --- | --- | --- | --- | --- | --- |
| `illumina` | `fastp`, `fastqc`, `multiqc` | `megahit` by default, `metaspades` optional | `genomad` | `metaphlan` | `bakta`, `amrfinderplus`, `abricate`, `isescan`, `integronfinder` | `bowtie2`, `samtools`, `coverm` |
| `ont` | `nanoplot`, `filtlong`, `multiqc` | `metaflye` | `genomad` | `metaphlan --long_reads` | same annotation defaults | `minimap2`, `samtools`, `coverm` |
| `pacbio_hifi` | `hifiadapterfilt`, `multiqc` | `hifiasm_meta` | `genomad` | `metaphlan --long_reads` | same annotation defaults | `minimap2` with `map-hifi`, `samtools`, `coverm` |
| `hybrid` | short-read QC plus long-read QC | `opera_ms` | `genomad` | `metaphlan` on short reads | same annotation defaults | short and long tracks are recorded separately |
| `assembly` | skipped | skipped | `genomad` | explicit config only | configured typing/annotation tools | skipped unless reads and abundance module are configured |

## 6. `metagenomic_plasmid` 常见真实运行资源

能找到可执行程序不代表工具已经可以运行。下面这些工具还需要数据库、模型或参考文件：

| 工具 | 常见必填资源或参数 |
| --- | --- |
| `genomad` | `resources.genomad.database` |
| `plasme` | PLASMe database |
| `plasx` | annotations, gene calls, model |
| `plasmidfinder` | PlasmidFinder database |
| `plasmidhostfinder` | host prediction database/model |
| `mob_suite` | MOB-suite database directory |
| `bakta` | Bakta database, light database is enough for smoke testing |
| `copla` | `refgraph`, `reflist` |
| `blast` | BLAST database |
| `mmseqs2` | MMseqs2 database |
| `kraken2` | Kraken2 database |
| `mummer` | reference plasmid FASTA |
| `clinker` | annotated GenBank files |

缺少资源时应修改项目配置，不要通过编辑 provenance 来掩盖缺失输入。

## 7. `metagenomic_plasmid` 工具 skill 更新规则

修改 registry 条目时：

1. 更新 `plugins/metagenomic_plasmid/tool_registry.yaml`。
2. 更新对应的 `plugins/metagenomic_plasmid/tool_contracts/{tool}.yaml`。
3. 更新对应的 `{tool}/SKILL.md`。
4. 可执行程序发生变化时，同步 `envs/*.yml`。
5. 运行 `autoplasm list-tools`，确认输出仍与本页表格一致。

修改旧 AutoPlasm CLI 行为时：

1. 更新 [../../../README.md](../../../README.md)。
2. 更新 [../../../docs/agent_usage.md](../../../docs/agent_usage.md)。
3. 更新 [autoplasm_agent/SKILL.md](autoplasm_agent/SKILL.md)。
4. 输入输出、命令模板、资源或归一化逻辑变化时，同步相关工具 skill。

新增工具 skill 时：

1. 在 `plugins/metagenomic_plasmid/tool_registry.yaml` 中注册工具。
2. 添加或更新对应的环境 YAML。
3. 按上面的结构创建 `{tool}/SKILL.md`。
4. 工具写入 `tables/*.tsv` 时，补充 parser 和归一化说明。
5. 实现输出解析时，同步测试和 fixture。

## 8. `metagenomic_plasmid` 工具 skill 验证命令

修改文档或 skill 后运行：

```bash
PYTHONPATH=src python -m abi.autoplasm.cli --help
PYTHONPATH=src python -m abi.autoplasm.cli list-tools --config examples/config_minimal.yaml
PYTHONPATH=src python -m abi.autoplasm.cli dry-run --config examples/config_minimal.yaml
git diff --check
```
