# ABI 精简重构计划

状态：阶段 A、B1 已落地；B2 已实施工作包 3 的恢复身份绑定与取消终止确认、工作包 4 的四后端证据语义、11A 的资源根参数化；工作包 2（旧 AutoPlasm 收敛）完成依赖梳理，退役留待专门批次。当前版本：v0.10。

代码基线：`17bdc5b043cec0ffb8fac182e0982c08e29a1875`，ABI `1.5.12`。
本文依据对话中已确认的决定恢复，替代此前临时目录内的计划副本。
临时副本在当前环境中不可用；其中的测试数字不作为本轮验证结果。

## 1. 目标与取舍

ABI 只承担两项主线职责：

1. 让智能体按照经过检查、得到授权且可验证的流程执行生物信息学分析。
2. 让人事后能够复查数据经历了哪些分析，包括实际工具调用、参数、输入、数据库、结果、失败和重试历史。

保留 Python，采用逐步替换现有实现的方式。没有证据证明换语言能够消除当前的职责重叠、证据缺口与打包耦合，因此不启动跨语言重写。
不以文件数、行数或测试数作为成功指标；以维护入口减少、职责集中和上述两项能力可验证作为指标。

| 范围 | 最终职责 |
| --- | --- |
| ABI 核心 | 计划、校验、授权、执行协调、状态、证据记录、历史读取、基础审计报告 |
| 分析插件 | 特定分析的 DAG、工具及输出契约、解析、必要的科学计算、结构化结果、局限性 |
| CLI、MCP、HTTP jobs | 调用同一核心行为的薄适配器 |
| local、Nextflow、Snakemake、HPC | 保留四种后端，各自负责真实执行机制，对齐核心证据和状态语义 |
| 外部系统 | 原始数据、工具、环境、数据库、工作流源码及镜像的获取与部署；科学绘图；独立研究项目管理 |

保留现有八种分析能力：`metagenomic_plasmid`、`metatranscriptomics`、`rnaseq_expression`、`amplicon_16s`、`wgs_bacteria`、`wgs_bacannot`、`easymetagenome`、`viral_viwrap`。
“保留能力”不表示八种插件必须随核心安装，也不表示其全部真实运行环境已得到认证。

分析插件可选；核心安全检查和审计记录不可由插件绕过。只装核心时，可以读取已有分析记录；执行某种分析需要对应插件以及外部预先准备好的运行条件。
不为重构新增账户系统、通用安装平台、全新工作流引擎或独立数据库服务。

## 2. 必须保持的行为

- 执行前检查输入、工具、资源、输出契约及插件局限性；实际执行必须对应被确认的计划。
- 原始输入不因分析、恢复、清理而被覆盖或删除，包含位于输出目录中的输入和符号链接指向的输入。
- 记录实际执行事实，区分“计划调用”“已启动”“失败”“成功”“复用历史产物”；未知的旧信息标为未知。
- 历史记录不可被恢复、重试、重置覆盖；保留可读的旧结果目录及已冻结证据。
- 基础审计读取不要求安装当时的分析插件、工具、数据库或绘图库，也不重新运行分析。
- 正常运行检查所选工作流的必需条件；正式运行锁继续检查明确声明的认证范围，不能因插件缺失而静默缩小范围。
- 保留严格契约检查、非空局限性、发布身份与已有不可变锁规则；支持能力与已认证能力分别说明。

## 3. 执行原则

优先复用 `WorkflowCoordinator`、`GenericABIExecutor`、现有插件接口及结果文件，不在旧实现外再叠一层同等复杂的调度框架。
统一的是计划、状态和证据语义，后端的任务提交、进程管理和工作目录机制仍由后端负责。
公共接口集中提供有用行为，内部不为了“解耦”制造只转发参数的抽象。

每个提交对应一个可说明的行为或退役动作，先建立验收依据，再替换调用方，最后删除旧实现。
不能因测试复用了旧实现，就直接删除测试所保护的核心行为。
保留兼容的读取方式与必要的短期入口，不无限期维护两套执行主干。

## 4. 工作包与验收

### 0 — 范围与依赖基线

记录入口、导入、配置、插件资源、构建、测试、文档和发布依赖，明确“保留、迁移、退役、待核实”。
选择简单分析 `metatranscriptomics`、复杂分析 `metagenomic_plasmid`、外部工作流 `wgs_bacannot` 作为迁移代表；最终仍覆盖全部保留插件。
记录四后端的当前支持差异，不能把本地假工具测试当成 HPC 或真实分析认证。

验收：每个删除候选都能说明调用者及替代行为；每个保留能力都有最低验收路径。

### 1 — 低风险清理

优先核实同名遮蔽文件 `src/abi/testing.py` 与 `src/abi/testing/`、完全重复的测试、失效标记、过期注释及无意义转发。
目前普通导入解析到 `src/abi/testing/__init__.py`，但删除同名文件前仍需检查直接路径加载、构建和引用。
测试体相同只生成候选清单；只有被测对象、参数化、fixture、类上下文与断言价值都重复时才删。
历史文档存在性测试按仍需维护的契约调整，不继续固定过期文件名。
Black 仍被 `CMakeLists.txt` 调用，不能因为 Ruff 已存在就直接删依赖。

验收：没有有效行为或独立覆盖消失；按受影响入口验证。低影响清理不新增仅证明“文件被删了”的测试。

### 2 — 收敛旧 AutoPlasm 执行实现

逐项梳理真正的运行路径与 dry-run 路径，将重复调度、状态、证据写入和执行入口迁入现有共享机制。
生物学处理、解析及必要统计保留在分析插件；其他模块仍引用的旧 helper 先迁出，再退役旧执行目录。
区分分析工具注册表与智能体接口工具描述，二者服务不同调用方，不能仅因都叫工具就合并。

验收：代表样本的新旧结构化结果、执行顺序、失败及恢复行为符合既定容差；旧入口没有隐藏调用者后退役。
结果一致性只能证明迁移保持既有行为，不能替代科学方法有效性验证。

### 3 — 统一运行历史、恢复与取消语义

复用已有运行 ID、任务尝试和外部工作流的历史关联。恢复启动产生独立运行记录，通过 `resumes_run_id` 关联先前运行；单次运行内保留步骤尝试。
已有外部工作流作为 ABI 父级运行/步骤记录，保留它自己的 process/task attempt、trace 和工作流提交身份，不把每个外部 process 伪装成 ABI 原生步骤。
如果实现发现现有字段不足，先说明具体缺失，不预设再增加全局“分析项目”身份体系。
恢复判断绑定计划、输入、工具和资源身份，以及产物契约；无法证明匹配时不直接复用。
取消分为请求已记录与执行已确认终止；不能在下游进程仍运行时声明成功取消。
先复用现有状态并补足终止证据，再决定是否需要新状态名；本地 worker 终止不能替代远端调度任务的终止确认。

验收：成功、失败、部分恢复、重试及取消都留下可关联的事实；重启和清理不抹去旧证据。

### 4 — 让实际执行绑定被确认的计划

先独立修复布尔授权判断：不允许通过一般真值转换把字符串 `"false"` 等误判为批准。
核心授权要求实际布尔值 `True`。现有 local `_coerce_bool()` 接受未知非空字符串，不能直接复用为授权验证；普通配置开关按各自明确的兼容契约另行处理。
对编译计划做完整序列化和加载验证，嵌套列表、字典和资源对象不能绕过不可变约束。
CLI、MCP、HTTP jobs 和各后端消费同一份已确认计划身份；排队后实际开始时再次检查关键运行条件。
避免确认后根据原始配置重新生成一份可能漂移的计划。记录配置、插件、工具及资源身份，明确变更如何触发重新确认。
计划摘要用于匹配完整性，不自行提供授权；复用宿主授权，不建设额外身份服务。

验收：非布尔批准、确认后修改、队列等待期间漂移、恢复条件不匹配均不能启动未经确认的工作；合法执行保持可用。

### 5 — 独立的人类审计接口

以实际记录形成基础人类报告与机器可读结果：数据身份、工具及版本、命令参数、资源身份、步骤状态、产物、局限性和历史关联。
明确记录失败调用和步骤复用，避免只展示计划表。
基础读取和报告只使用保存的事实；当前文件是否还在是另一个状态，不改变历史成功事实。
旧目录缺字段时明确缺失，不伪造完整性。
插件专有解析、重新计算与扩展报告独立于基础审计；需要它们时才加载相应插件。
生成新结果时一并保存审计必需的 schema、方法、引用和局限性快照。基础结构检查读取该快照；插件专有科学校验仍需插件，并单独报告是否执行。
旧记录没有这些快照时，只展示已保存的事实及缺失项，不能把基础读取包装成完整结果认证。

验收：卸下原插件、绘图库及真实工具后，仍能查看旧目录中的成功与失败分析记录，并解释缺失信息。

### 6 — Study 退出核心

退役默认安装、命令入口、默认测试和发布中的研究项目管理职责。
保留独有的科学计算与核心审计测试，改用直接覆盖主线的最小 fixture。
已冻结研究记录按其用途保留；普通旧方案使用 Git 历史追溯。
本轮不另建一个没有维护者的 Study 项目。

验收：核心执行与历史审计不导入 Study；退役不会删除需要保留的真实研究证据。

### 7 — 科学绘图退出核心

同时梳理 SciPlot、旧 `abi.figures`、报告渲染、工作流导入、绘图节点、注册表、默认产物和安装依赖。
将真正的分析计算与展示计算区分，例如有科学用途的排序坐标和检验结果应保存为结构化数据；颜色、布局等不迁入核心。
普通审计报告保留表格和事实，移除对科学图件的必需约束以及“没有绘图就是失败”的默认行为。

验收：核心导入和基础报告不需要绘图库；保留插件的必要结构化结果与局限性仍完整；删除节点后 DAG 依赖和输出契约有效。

### 8 — 所有获取与安装交给外部系统

退出 ABI 的职责包含原始数据下载、环境创建、工具安装、数据库下载，以及运行时隐式获取工作流和镜像。
保留已有输入清单、来源信息、文件完整性校验、只读环境发现和诊断；缺少预备条件时给出明确报告。
拆开 `ABIResourcePlugin` 中检查与 setup 的耦合，以及混合只读检查和下载的实现，避免删安装函数后让专有资源检查失效。

EasyMeta 的 ENA 下载节点必须连同后继输入映射、`streaming_inputs` 校验绕行及清理逻辑一起迁移。
外部准备的 reads 直接作为已存在输入，accession、URL、校验和等可作为来源记录；不保留可调用的隐藏下载入口。
清理只删除 ABI 拥有的中间产物，不能把外部原始 reads 接入旧下载文件的删除规则。

Nextflow、Snakemake、容器和外部工作流只能使用已准备好的依赖；部署阶段如何准备属于外部系统。
这不等于 ABI 提供网络隔离沙箱，也不增加通用防火墙或安装平台。

验收：运行接口不下载、不安装；缺少原始数据或依赖时在分析启动前失败；所有正常与失败清理路径保持原始输入。

### 9 — 收敛分发、依赖和质量门槛

与工作包 6、7、8、11、12 同步删除失效入口、默认依赖、强制打包资产、测试收集路径及覆盖配置。
不把“有 extra 名称”当作真正可选安装；使用干净环境安装构建产物验证依赖和文件实际归属。
默认 sdist 到 wheel 构建路径、Docker 构建上下文与必要的声明文件保持一致。
保留四个工作流、发布身份、不可变产物规则和当前有效覆盖门槛；不靠降低门槛掩盖未迁移行为。

验收：按改变后的职责验证核心分发、官方插件集成及安装文档；不再因已退役功能失败。

### 10 — 退役旧兼容路径并完成第一轮

在替代路径和历史读取通过后移除重复入口与执行主干。
逐项关闭残余导入、文档、命令、打包与测试引用，保留有真实读者的历史格式支持。
旧环境变量和资源根目录语义先核实再迁移，不能批量同名替换。

验收：第一轮包含工作包 11A 与 12；执行可靠性、原始输入保护和事后审计已落地，保留能力没有依靠旧主干继续运行。

### 11 — 分析插件可选化

**11A，第一轮：按需加载与失败隔离。**

发现插件时只读取可获得的元数据，执行时才加载被选插件；一个无关插件的损坏不能阻止其他插件及历史审计。
Entry point 本身不提供完整显示信息。优先复用已有 `abi-plugin.yaml`，建立不导入实现即可定位声明文件的最小约定；不新增重复维护的第二套插件目录。
处理插件自己的资源位置，以及全局 `PLUGIN_ROOT`、运行锁和工具清单等目录扫描调用者。
记录选用插件的身份和版本；重复标识与不兼容版本给出确定错误，不能由遍历顺序决定运行哪个实现。
发现/加载失败返回可检查的状态和原因；与某次运行相关的失败进入该次证据。普通列表查询无需额外创建一套持久日志系统。
普通运行检查所选插件；官方全部插件的 CI 与正式锁仍按声明范围验证，不能随本机安装内容静默收缩。
当前默认运行锁列表为七项且不含 `wgs_bacannot`，云端正式 helper 又有独立认证范围；工作包 0 应明确这些差异，不为了凑齐八项静默扩大认证承诺。

验收：单个坏插件的发现/执行错误被限定；所选工作流可运行；核心可独立读历史；元数据发现不执行所有插件构造函数。

**11B，第二轮：真正可选安装。**

在同一仓库中将核心与分析插件的代码、数据及依赖整理成可选分发；不用八个新仓库和八条独立版本流程制造维护负担。
接口版本、包身份和资源定位采用满足现有需要的最小约定，不新增插件市场或自动安装器。
保留正式发行版全套插件的集成验证，核心自身测试使用最小假插件。

验收：仅装核心、装单插件、装官方完整组合分别检查；缺插件时给出可解释错误；已存在的基础审计记录始终可读。

### 12 — 文档退役与维护入口收敛

按内容、读者和实际引用分类，不按日期、文件名版本号或长度判断价值。
每个候选列明去向：保留为权威文档、提取有效部分后退役、随功能退役、仅为本地未跟踪文件。

| 候选 | 处理原则 |
| --- | --- |
| 双语 `devlog.md` | 独有的当前约束先提取；历史过程以 Git 和必要发布记录追溯，避免复制到庞大公开归档 |
| 双语 `abi_spec_v0.1.md` | 含接口、生命周期和契约，先合并到当前规范并替换引用，不能直接当成垃圾删除 |
| `abi_sciplot_design.md`、`plugin_report_figure_spec.md` | 随绘图职责退出处理；保留有关结构化结果、方法、局限性和引用的有效要求 |
| 双语 `linux_support_plan.md` | 将现行支持约定与旧实施计划分开，保留仍有效的平台行为 |
| `docs/download_databases.md` | 随获取职责退出，必要的外部预备条件转入运行说明，不再维护 ABI 安装指南 |
| `docs/zh/bacannot_integration_development_plan.md` | 对照已实现插件核对，保留独有验收或未决限制，退役过时实施过程 |
| `docs/zh/mcp_protocol_20260728_update_research.md` | 只核实它与当前代码和维护说明的关系；外部协议事实另需官方来源核查 |

检查 Git 跟踪状态、导航、README、源文件链接、Sphinx 排除项、测试硬编码路径、发布资产以及技能源文件与必需同步副本。
本轮核对上述 13 份候选：双语 ABI 规范、双语 SciPlot 设计及下载指南共 5 份受 Git 跟踪；其余 8 份为当前工作区被忽略的本地文件。
因此，“本地仍存在”不等于“仍在发布树”。尤其 Bacannot 本地规划稿未发现 Git 历史，先提取其独有有效信息，不能假设删除后可由 Git 恢复。
共享 Sphinx 排除配置对双语都生效；`plugin_report_figure_spec.md` 已被排除，其它被忽略的文档仍可能进入本地构建。
不要为了减少重复而删除宿主安装实际需要的生成副本；先明确谁是源文件以及生成方法。
双语文档保持相同职责与约束，不要求机械逐行复制。
文档描述当前已实现行为；未来行为只出现在明确标记的计划中。

验收：从新输出目录构建双语文档，并检查本地链接和退役页面没有出现在输出中。
现有 `docs/build_docs.sh` 的 `-E` 重建不能保证旧 HTML 被清除，普通构建通过不能代替这一项。
低风险文档可在 A 阶段处理；功能文档与对应 C 阶段变更同步；第一轮结束前完成导航和发布引用清理。

## 5. 顺序与阶段出口

| 阶段 | 工作包 | 必须达到的出口 |
| --- | --- | --- |
| A | 0、1；11/12 依赖调查及可独立文档清理 | 删除候选与支持矩阵明确，低风险变更不会抹去有效行为 |
| B1 | 4 的严格布尔检查；3/4 的计划身份与本地历史骨架 | 授权与实际执行有可验证关联，历史不被覆盖 |
| B2 | 2、3、4 的四后端及 jobs 迁移；11A | 共用执行与证据语义，选定插件加载独立；按职责拆提交 |
| B3 | 5；与 2–4、11A 联合验收；12 同步 | 脱离原插件仍能读取成功、失败和恢复记录 |
| C | 6、7、8；9/12 配套 | Study、绘图及所有获取职责退出，输入保护和必要科学结果不退化 |
| D | 9 第一轮收口、10、11A、12 | 第一轮主线与文档完成，无隐藏旧入口或失效门槛 |
| E | 11B、9 分发验收、12 安装文档 | 核心与分析插件实际可选安装，完整官方组合仍受集成验证 |

严格布尔修复、计划消费、历史保存、插件加载和包拆分分别提交，避免一个提交同时改变所有控制逻辑。
若某项退役依赖尚未落实，保留该项并说明缺口，不提前删除其唯一有效实现。

## 6. 测试保留与精简规则

必须保留或补齐：授权拒绝、实际计划一致、输入与资源变化、契约失败、原始输入保护、失败证据、恢复历史、真实取消、插件失败隔离、缺插件历史读取、真实安装布局。
核心测试使用最小假工具及插件，插件测试验证其科学产物契约，后端集成测试验证实际后端差异。
受影响的真实分析冒烟用于证明真实工具接线；假工具测试不能代替它。

可删或改写：上下文也完全相同的重复用例、仅固定旧实现内部结构的断言、退役功能专属测试、固定旧文档标题/文件名的检查。
参数化测试体相同、文件名带 `ext` 或一个测试很短，都不是删除理由。
没有行为变化的文档精简不新增 Python 行为测试；保留能捕获安全或审计退化的少量直接测试。

按仓库现行要求执行检查：

- Python 变更：Ruff、mypy、定向 pytest 和受影响集成测试。
- 插件变更：严格 contract-lint、dry-run 与相关真实工具 smoke；缺少环境时记录尚未验证的范围。
- 文档变更：`bash docs/build_docs.sh`；退役另检查新构建目录、链接及旧页面残留。
- 发布面变更：Docker 配置回归、Compose 配置检查、默认 `python -m build`；正式发布另执行完整发布门槛。

## 7. GPT-Luna 独立核验（实施前基线）

上一轮使用三位 `gpt-5.6-luna` 子智能体分别检查核心流程、可选插件和文档退役。
主代理交叉核对关键源码、执行只读探针，并修正子智能体的范围偏移。该轮仅新增本文，未修改产品代码、退役文件或发布。
本节事实与验证数字描述实施前基线；实施后状态以第 8 节为准。

### 核实结果与对应修订

| 核实结果 | 当次证据 | 计划中的处理 |
| --- | --- | --- |
| 单个插件选择仍触发全量加载 | `src/abi/plugins/__init__.py:22–94`；Luna 的导入阻断探针中，无关 Amplicon 导入失败导致目标插件失败 | 11A 采用不加载实现的发现；11B 再验证真实分发隔离 |
| Entry point 不含完整展示信息，资源读取仍假设全局目录 | 现有 `abi-plugin.yaml` 已有展示信息；`agent/interface.py:1442`、`workflow/catalog.py:51` 仍使用全局根 | 复用声明文件；同时迁移 query/catalog/lock 等调用者，不仅修改 `plugin.root` |
| 已保存的编译计划未成为运行唯一输入；冻结只是浅层 | `agent/interface.py:910–950` 与 `1246–1257`；`workflow/compiled_plan.py:58–166`；主代理成功修改 frozen plan 内部列表 | 工作包 4 增加实际消费、加载验证、身份绑定与嵌套不可变性 |
| 授权一般真值转换不可靠 | `agent/interface.py:776`、`jobs/service.py:335`；主代理证实 `bool("false")` 及 local `_coerce_bool("unrecognized")` 都为真 | 独立严格授权修复；不直接提升宽松配置解析函数为安全验证 |
| 恢复检查产物但缺少身份约束，启动会重置证据 | `executor.py:256–278`、`1018–1070` | 先保存历史及身份，再迁移恢复路径；复用外部 task attempt 证据 |
| 取消记录不证明底层任务停止 | `jobs/service.py:480–535` | 增加后端停止确认，保留请求与实际终止的区别，不预先强制五种新状态 |
| inspect 可直接读事实；report 和 validate-result 仍加载插件 | `agent/interface.py:1064–1131`、`results.py:250–290`；Luna 在阻断分析实现时成功 inspect | 工作包 5 保存报告所需快照；区分基础读取、结构校验与插件专有校验 |
| 核心导入仍带入绘图代码 | `workflow/__init__.py:29–30` → `figure_specs` → `abi.figures`；绘图库本身仍为延迟导入 | 7 清理完整导入与报告路径，不能只删 SciPlot 目录 |
| ENA 获取退役会影响后继输入与清理 | `plugins/easymetagenome/pipeline_dag.yaml:42–89,202–218`、插件 `handlers.py:726–760` | 8 同步改输入、校验绕行与清理所有权，防止删除外部原始 reads |
| 旧文件名不代表内容无效，部分本地页面已退出 Git | `git ls-files`、`git check-ignore`；规范的导航与测试引用 | 12 按内容与跟踪状态退役；ABI 规范保留有效契约并修正过期数量 |
| MCP 研究稿的本地实现快照已过期 | 研究稿写 FastMCP/SDK 1.x；当前 `src/abi/mcp/server.py:19` 与 `pyproject.toml:45` 已不同 | 退役失效快照；本轮不据此判断外部 MCP 规范事实 |
| 文档构建既扫描本地孤立源，又保留旧输出 | `docs/build_docs.sh:19–68`；本轮双语构建及 HTML 文件检查 | 12 加入干净来源/输出、链接与旧页面检查 |

### 不采纳或收窄的建议

- 不把数据获取留在可选分析包，不另建无人维护的 acquisition 项目；最终均由外部系统承担。
- SciPlot 文档和下载脚本测试仅在相应代码尚未退役时保持一致；不据此长期保留 ABI 绘图 extra 或下载工具。
- 不为本轮引入 zip 资源支持、插件别名市场、替换授权系统、每次发现都持久化的日志库或所有配置布尔值的统一重写。
- 不因保留八种能力而声称八种已认证；不把现有测试通过当作未来设计已经实现。
- 对重复测试只建立候选。本轮 AST 扫描亦找到测试体相同但参数化上下文不同的例子，不能自动批量删除。

### 本轮实际验证

子智能体运行的现有测试：

| 命令 | 结果 |
| --- | --- |
| `pytest -q tests/unit/test_compiled_plan.py tests/unit/test_compiled_plan_runtime.py tests/unit/test_external_workflows.py tests/unit/test_job_service.py --disable-warnings --tb=short` | 51 passed，5 skipped |
| `pytest -q tests/unit/test_easymetagenome_plugin.py tests/integration/test_easymetagenome_handlers.py tests/unit/test_study_tool_shim.py tests/unit/test_study_grading.py --disable-warnings --tb=short` | 46 passed |
| `pytest -q tests/unit/test_abi_plugins.py tests/unit/test_declarative_plugin.py tests/unit/test_runtime_lock.py` | 26 passed |
| `pytest -q tests/integration/test_abi_cli.py -k 'inspect or report or validate_result' --tb=short` | 4 passed，28 deselected |
| `pytest -q tests/test_report.py tests/unit/test_report_generic.py tests/unit/test_report_limitations.py` | 30 passed |

合计 157 passed、5 skipped，另有 28 项未被本次筛选选中。它们验证现有行为；ENA 下载与 Study 用例的通过尤其不等于职责退出已验收。
一次最初误写测试路径的命令没有收集到测试，之后按正确路径重跑，未把该次计入通过数。

主代理验证：

- 只读导入与对象探针确认 `abi.testing` 解析到包目录、计划嵌套可变以及布尔转换问题；未启动分析工具。
- `bash docs/build_docs.sh`：退出 1，英文 5 条警告后停止。1 条是 Python 文档 inventory 的 DNS 获取失败，3 条是本地孤立页面，1 条是 Linux 证据链接无法解析。
- `bash docs/build_docs.sh zh`：退出 1，中文 8 条警告。1 条相同 DNS 问题，6 条本地孤立页面，1 条相同证据链接问题。
- 双语均生成了 HTML，但未达到仓库零诊断门槛；不能报告“文档检查通过”。未修改源码文档或降低门槛。
- 构建后仍能看到被排除的 `plugin_report_figure_spec.html` 等历史输出。部分其它页面是被本地残留源重新生成，应分别解决来源扫描与旧产物残留。

上述文档结果针对当前含本地被忽略文件的工作区，不能直接推断干净 CI checkout 也存在相同孤立源问题。
本文位于 Sphinx 文档树外；已有文档构建不是对本文内容正确性的证明，本文另经人工及文件检查。
未运行完整 CI、真实生物信息学工具、集群终止验证或包拆分安装验证。这些仍是实施阶段必须完成的验收，当前不得声称已经满足。

## 8. GPT-Terra 实施记录

本批由三位 `gpt-5.6-terra` 子智能体实现低风险代码/测试精简、严格授权修复和低风险文档退役；主代理检查差异并执行整体检查。
先前的额度中断后已从原工作树恢复，无重置或覆盖用户修改。没有提交或发布。

### 范围与调用基线

| 范围 | 当前调用与资产归属 | 后续迁移条件 |
| --- | --- | --- |
| 公共入口 | CLI、`ABIAgentInterface`、MCP、HTTP jobs；`abi list-types` 实测列出八种能力 | 保持接口与错误语义，实际执行共用核心约束 |
| AutoPlasm | `src/abi/autoplasm/` 是兼容转发；实际旧实现位于 `src/abi/plugins/metagenomic_plasmid/_engine/`。普通 local 运行进入共享执行器，但插件 dry-run、旧 CLI 及部分 helper 仍依赖旧实现 | 不能只删兼容目录就宣称执行迁移完成；先迁移运行、dry-run、helper 和证据路径 |
| Study | `src/abi/study/`、`abi-study` 入口及专属 tests；实验材料位于 `experiments/abi_control_validation_v1/` | 分开研究专属测试与主线保障，保留冻结证据，实际退出打包 |
| 绘图 | `src/abi/sciplot/`、`src/abi/figures/`、`abi-sciplot`、report extra；报告渲染与 workflow 导入仍有关联 | 保留必要科学计算，先完成无绘图库基础审计 |
| 获取/安装 | `resources.py`、`resource_downloader.py`、`runtime_environment.manage_environments`、插件资源 setup、EasyMeta ENA handler/DAG 与脚本 | 外部系统准备数据与依赖；迁移只读检查、输入映射和清理所有权后退出实现 |
| 分发 | `pyproject.toml` 的 scripts/entry points/force-include、`environments.yaml`、`envs/`、Docker 上下文、四个工作流 | 本批不改变发布身份或环境声明；后续职责退出必须同步这些入口 |
| 结果 | `execution_plan.json`、`provenance/`、`tables/`、`report/`；四后端保持当前真实支持状态 | 本批不改变结果格式，不将 mock/fixture 验证升级为生物学认证 |

后续代表流程仍为 metatranscriptomics、metagenomic_plasmid、wgs_bacannot。
本批使用现有假工具/fixture 测试与打包检查；未执行真实生物信息学工具、调度器取消或正式运行锁认证。

### 已实施变化

- 删除被同名包遮蔽的 `src/abi/testing.py`，保留现行 `src/abi/testing/__init__.py` 及其契约检查。
- 删除 7 项上下文也重复的行为测试：5 项路径解析、1 项工具版本异常处理、1 项异常继承检查。对应原始用例保留。
- 删除已由四工作流精确集合覆盖的 `opencode.yml` 缺失检查，以及架构图固定标题、历史 xfail 文本两个无行为价值的检查。实际 dry-run 和发布门槛保留。
- CLI 从 `abi.tool_descriptors` 直接导入规范导出函数；外部兼容模块 `abi.openai_contracts` 保留。
- 修正旧绘图模块不实的 Plotly fallback 说明，仅改变说明。
- 在直接 run、通用 dispatch、HTTP jobs 准入三个入口要求实际布尔 `True`。保持原后端解析和确认错误结构，没有新增第二套后端映射。
- 删除过期的 `docs/download_databases.md`；有效的资源根与正式运行锁规则由现有双语 runtime-lock/cloud 文档继续承载。
- 修正双语 ABI 规范中的内置数量 7→8；不提前声称可选安装已实现。
- 共享文档配置排除本地被忽略的退役候选；构建只清除当前语言的生成目录，防止旧页面继续发布。独有本地草稿未删除或改写。

严格授权验证增加了必要的回归用例；本批并非单纯追求测试数量下降。布尔门控只表示满足 ABI 的调用条件，不提供独立的人类身份认证。

### 验证结果

- 精简相关定向测试：291 passed；授权相关定向测试：39 passed、5 skipped；文档相关测试：15 passed。各组存在重复执行，不将它们相加作为唯一测试总数。
- 全仓 Ruff 与 mypy 通过；受影响文件格式检查通过；差异空白检查通过。
- `python -m build --no-isolation --outdir /tmp/abi-terra-dist-20260911` 通过，实际执行 sdist → wheel 路径。使用已安装且满足声明的构建工具，未改构建依赖。
- 在新虚拟环境仅安装该 wheel，以隔离模式从仓库外检查：`abi.testing` 定位到该环境的 `site-packages/abi/testing/__init__.py`，wheel 不含旧 `abi/testing.py`。这是安装布局验证，不是全部运行依赖或真实分析认证。
- 初始隔离网络构建仅剩 Python 官方 inventory 的 DNS 警告；允许读取该索引后，`bash docs/build_docs.sh` 双语均达到 `0/0` 诊断预算。没有压低门槛或屏蔽网络警告。
- 当时的整体测试结果为 2975 passed、6 failed、7 skipped、11 deselected。三处失败来自已退役模板接口的旧测试；另外三处涉及当前工作区缺失的论文示例数据和冻结 Linux 证据文件。后续 Luna 批次分别处理并记录，不能将此结果写成完整门槛通过。

### 尚未完成

编译计划成为实际执行唯一输入、不可变运行历史、后端取消确认、无原插件基础报告、旧 AutoPlasm 执行退役，以及 Study/绘图/所有获取实现退出、插件可选化与真实拆包，均仍需按第 5 节顺序实施。
本批的授权小修复不代表工作包 4 或阶段 B 已完成；文档删除也不代表下载功能已从产品移除。

## 9. GPT-Luna 接续实施记录

用户随后指定由 `gpt-5.6-luna` 专用子智能体接续实施。本批保留并复核第 8 节的现有修改，完成低风险清理、严格授权验证，以及工作包 11A 的发现/选定加载子项。
以下记录区分已实现的小项与尚未完成的整个工作包，不将局部功能当作全部重构完成。

### 范围

- 工作包 1：保留当前 `abi.testing` 包、规范工具导出和真实行为测试，退役上下文也重复的测试及明确失效的历史断言。
- 工作包 4 小项：直接 run、dispatch、jobs 准入只接受实际布尔 `True`；回归测试额外证明被拒绝调用没有触发准备、排队或执行。
- 工作包 11A 小项：通过现有 manifest/entry point 发现元数据，只加载选定分析实现；旧 SDK `list_plugins()` 保留显式全量加载兼容行为。真正可选分发、外部插件资源路径和无原插件基础报告继续按计划迁移。
- 工作包 12 小项：退役过期下载指南；排除不属于发布树的本地草稿并清除旧生成页面，保留独有本地稿和现行有效规范。

### 验收记录

主代理接续批次对继承工作树执行了联合验收，并在此基础上实施 B1（见第 10 节）：

- 全量测试（不含 smoke）：2830 passed、3 skipped；仅剩的 3 个失败均为第 8 节已记录的预存环境问题（冻结 Linux 证据文件与论文示例数据缺失），与本轮改动无关。
- smoke：8 passed、10 skipped（真实工具用例按标记跳过）。
- 修复 Luna 批次引入的一个 mypy 错误（`src/abi/plugins/__init__.py:94` 的 plugin_id 收窄），修复后全仓 mypy 通过。
- Luna 批次的 11A 发现/选定加载行为由 `tests/unit/test_abi_plugins.py` 等既有测试覆盖并通过；未重复运行第 9 节列出的旧命令。

未修改版本、发布流程、环境声明或冻结证据；没有提交或发布。

## 10. B1 实施记录：计划身份绑定与本地历史骨架

本批由主代理实施工作包 3/4 的 B1 出口项：授权与实际执行可验证关联、历史不被覆盖。严格布尔检查（B1 另一项）此前已落地。没有提交或发布。

### 已实施变化

**计划消费与身份绑定（工作包 4）。**

- `CompiledPlan`/`CompiledStep` 增加 `plan_id`（内容 SHA-256，排序键规范化，不含 `plan_id` 本身）；`compile_plan` 在不变量验证后写入。
- 新增 `CompiledPlan.from_dict` / `CompiledStep.from_dict` 严格加载：校验 schema 版本、未知/缺失字段、执行种类、资源字段与结构不变量；已签名文件内容被修改时拒绝（身份不匹配）。旧的无 `plan_id` 文件按遗留产物加载，由绑定函数与重建计划比对内容。
- 嵌套不可变加固：`dependencies`/`validated_paths`/`steps` 等冻结为 tuple，`inputs`/`outputs`/`params` 冻结为 `MappingProxyType`；`ResourceSpec` 本身改为冻结值对象（全仓确认无原地修改，policy 层本就构造新实例），嵌套资源不再绕过不可变约束。`to_dict` 输出保持 JSON 安全。
- 新增 `bind_confirmed_plan(prepared)`：运行前重新编译准备好的计划，与输出目录中已确认的 `compiled_plan.json` 比对内容身份；漂移抛 `PlanDriftError`（新错误类型，继承 `PlanIntegrityError`），首次无确认文件时持久化已验证计划再返回身份。接缝位于 `ABIAgentInterface._run`（prepare 之后、coordinator.run 之前），CLI、MCP、HTTP jobs（含排队作业在实际开始时）与四后端共用；dry-run 不绑定，保留探索自由；easymetagenome 内部 ENA 节点与 viwrap 兼容 runner 等插件内部调用路径留待其所属工作包迁移。
- 身份经 `RuntimeOptions.confirmed_plan_id` 传入本地运行时，`run_summary.json` 记录 `plan_id`，与已确认产物形成可验证链条；`plan` 响应新增 `plan_id`。
- `diagnostics.classify_exception` 为 `PlanDriftError` 增加规则（`invalid_config` + 重新规划提示）；措辞避开确认闸门关键词，不误导为权限问题。

**本地历史骨架（工作包 3）。**

- `reset_run_provenance` 改为先归档后重置：先前运行的可变溯源产物（含 step_logs）复制到 `provenance/previous_runs/<prior_run_id>/`，无 `run_summary` 的崩溃残留以 `unidentified-<时间戳>` 归档；返回血缘字典。重试与恢复都不再覆盖旧证据；旧引擎调用点同样受益。
- 执行器将血缘写入运行身份：恢复运行记录 `resumes_run_id`（先前 run_id），重跑记录 `previous_run_archive`；与外部工作流运行时的既有字段命名一致。运行仍产生独立 `run_id`，单次运行内步骤尝试由 `commands.tsv` 记录（现状保留）。

**文档。** 双语 ABI 规范与使用指南同步 `plan_id` 绑定、漂移拒绝、`previous_runs/` 归档与 `resumes_run_id` 语义；`tests/test_dag_planner.py` 补一处格式。

### 验证结果

- 全量测试（不含 smoke）：2830 passed、3 skipped、3 failed；3 个失败为预存环境问题（`docs/evidence/linux_x86_64_capability_20260729.json` 与 `docs/paper_examples/airway_metrics.tsv` 缺失），第 8 节已记录，与本批无关。smoke：8 passed、10 skipped。
- 本批新增/更新的测试：CompiledPlan 身份确定性、序列化回载、防篡改、严格 schema、嵌套不可变、绑定幂等与漂移拒绝；接口级计划→运行绑定、直接运行绑定、漂移拒绝（无执行产物、确认文件字节不变）、恢复链接与重跑归档；`reset_run_provenance` 三种归档语义；`PlanDriftError` 分类规则。既有测试按新契约更新：嵌套相等断言、local runtime 执行器桩签名、公共错误导出面、agent interface 授权桩。
- Ruff（lint + format）与 mypy 全部通过；`ResourceSpec` 冻结未发现原地修改调用方。
- `python -m build` 未重跑：本批未触及 pyproject、打包资产或 Docker 输入（发布面无变化）。

### 尚未完成与边界

- 编译计划尚不是执行器直接消费的唯一输入：本地执行器仍消费插件 `ExecutionPlan`，绑定以内容身份比对实现；计划对象级消费（后端任务提交、工作目录机制）按第 5 节在 B2 迁移。
- 恢复仍只校验产物存在性与计划身份；输入/工具/资源身份的完整恢复约束属 B2 的恢复路径迁移。
- 取消终止确认（后端停止证据）未实施，属 B2。
- 插件内部旧执行路径（`easymetagenome` ENA 节点、viwrap 兼容 runner、metagenomic_plasmid 旧引擎）未纳入绑定，随工作包 2/8 退役或迁移；本批不扩大改动面。
- 未运行完整 CI、真实生物信息学工具、集群终止验证或包拆分安装验证；这些仍是后续阶段的验收项。

## 11. B2 实施记录：恢复身份绑定、后端证据语义与取消终止确认

本批由主代理实施 B2 的可验证子集：工作包 3 的恢复身份绑定与取消语义、工作包 4 的四后端证据共享、11A 的资源根参数化；工作包 2 完成依赖梳理。没有提交或发布。

### 已实施变化

**恢复身份绑定（工作包 3）。**

- 恢复运行从归档的先前运行加载 `checksums.json` 链条：`self._checksums` 以先前映射为初值，使被复用产物继续参与下游输入验证，重执行步骤照常失效并刷新链条（修复 B1 归档后链条中断的隐患）。
- `_step_is_resumable` 增加身份校验并返回 `(resumable, rejection_reason)`：声明的产物必须与先前记录的校验和一致；步骤消费、且先前记录过校验和的输入必须未变化。任一不匹配则不复用，步骤重执行，`commands.tsv` 的 reason 写明 `resume reuse rejected: …`（含首个不匹配路径）。旧目录无校验和记录时回退到既有存在性/契约检查，不伪造完整性。
- 分发顺序保持原语义（skipped > 验证恢复 > dry-run/internal > 未注册 > 真实执行）：恢复检查提升到 elif 链之前，被拒绝的恢复落入正常执行。

**取消终止确认（工作包 3）。**

- `JobRecord` 新增 `termination` 字段（随 to_dict 持久化），区分“请求已记录”（confirmed=False）与“执行已确认终止”（confirmed=True）。
- 排队即取消：confirmed=True（从未启动，无需终止）。运行中取消：仅记录请求（sigterm/cooperative），明确不构成对下游引擎/调度器进程终止的确认。
- 子进程路径依据退出证据分类：信号死亡（rc<0）→ `cancelled` + confirmed=True（含信号号）；rc=0 → 工作已完成，按真实信封结果归类（succeeded），不得声称取消成功；rc>0 → failed，请求保留为未确认证据。
- 进程内路径：取消请求后仍成功完成的调度按 succeeded 报告（旧行为伪造 `cancelled`，已退役）；失败按 failed。
- 修复竞态：请求记录先于 kill 写入，调度路径的确认证据是最后写入者；重复 cancel 不再覆盖已有证据（elif 收紧为 running）。

**四后端证据语义（工作包 4）。**

- `ABIResultWriter.write` 接入与本地执行器相同的共享语义：先归档后重置（`reset_run_provenance`）、`capture_run_identity`（run_id/git/abi_version/lock 身份）、`plan_id` 与 `resumes_run_id`/`previous_run_archive` 血缘字段。nextflow、snakemake、hpc 及托管外部工作流的 ABI 结果侧全部生效；外部工作流自身的 snapshot/lineage 体系不变。
- 各后端从 `RuntimeOptions.confirmed_plan_id` 传入身份；`abi run` 与 `run-nextflow` 别名的等价性测试更新为归一化每次运行必然不同的身份字段（run_id、plan_id——后者按设计绑定 outdir）。

**11A 资源根参数化。**

- `ABIPlugin` 协议新增 `root` 属性（捆绑插件仍指向全局 PLUGIN_ROOT 下的目录，行为不变）；`_query` 从 `plugin.root` 解析 `pipeline_dag.yaml` 并以 `plugin_root=plugin.root` 调用 `WorkflowCatalog.for_plugin`；easymetagenome/viral_viwrap 内部调用同样传入自身根。外部安装的插件布局就绪，全局根不再是核心调用者的假设。

**工作包 2 梳理（未退役）。**

- `_engine`（9,529 行）的引用面：真实运行路径使用其 parsers/standard_tables/report/资源检查（生物学处理按计划保留在插件）；`execute_dry_run` 覆写仍走 `PipelineExecutor` mock（重复执行入口）；`abi.autoplasm.*` 约 20 个转发模块与旧 CLI 仍被 SDK/CLI 测试引用。退役需要按路径迁移 dry-run、helper 与证据写入后删除旧目录，属独立批次；本批不提前删除其唯一有效实现。

### 验证结果

- 全量测试（不含 smoke）：2836 passed、3 skipped、3 failed；3 个失败仍为预存环境问题（冻结 Linux 证据文件与论文示例数据缺失）。
- 本批新增/更新测试：恢复身份绑定四例（产物校验和不匹配重跑、输入校验和不匹配重跑、匹配则复用、整跑链条继承+篡改重跑+证据行）；取消语义三态（迟到请求不声称终止、信号死亡确认终止、排队取消 confirmed）；`ABIResultWriter` 共享身份与历史语义；query 从插件根解析 DAG。
- Ruff（lint + format）与 mypy 全部通过；双语文档构建 0/0 诊断。
- 未运行完整 CI、真实生物信息学工具或集群取消验证；HPC 远端调度任务的终止确认仍是缺口，属后续批次。

## 12. v1.6.0 发布记录与 B3 开工

### 发布记录（2026-09-11）

- 版本 1.6.0：版本提升（pyproject、CHANGELOG、双插件清单 manifest）→ `check_release_identity` 通过 → 本地与远端完整 CI 门槛通过 → `python -m build`（sdist→wheel）+ `twine check` 通过 → 干净 venv 从官方 PyPI 安装 wheel 冒烟（`abi list-types` 八种能力、入口点、wheel 布局）→ 远端核查（PyPI 无 1.6.0、无同名标签）→ 推送 master 与 `v1.6.0` 标签 → Release 工作流（质量门 + 构建 + GitHub Release）→ publish-pypi 手动 dispatch → PyPI 上线并验证哈希与干净安装。
- 发布前修复了阻塞 CI 的既有红灯：arm64 的过期 `PathTemplateContext` 断言（Phase A 已修剪，断言的是 f7dbd7e 退役的点号变量能力）；strict contract-lint 的四条 `unused_registry_input` 告警（metabat2/threads、plasmidfinder/assembly→plasmid_contigs、scapp 死 max_k、wgs_bacteria mlst 死 scheme）——渲染命令零变化；scapp `-k 77` 与声明 `max_k` 的不一致记录待科学复核。
- 已知缺口：`release.yml` 以默认 GITHUB_TOKEN 创建 Release，GitHub 为防递归不触发 `release.published`，publish-pypi 需按其 `workflow_dispatch` 入口手动启动（1.5.12 亦如此）。后续可改为 PAT 创建 Release 或 workflow_call 链接以闭环。
- 本地 3 个测试失败均为本地专属：两个属于未跟踪的 `test_create_real_data_case_study_figures.py`（依赖 gitignored 的论文材料），一个依赖 sparse-checkout 隐藏的 Linux 证据文件（CI 有该文件并通过）。

### B3 开工：工作包 5 审计快照（已实施部分）

- 新增 `src/abi/audit.py`：`audit_snapshot.json`（schema_version、analysis_type、report_title、standard_table_schemas、limitations、references、abi_version、captured_at）由 `ABIResultWriter`（四后端）与 `LocalRuntime`（本地执行器）在每次运行时写入 `provenance/`。
- `validate_abi_result_dir` 的表 schema 解析回退到审计快照并报告 `schema_source`（plugin/audit_snapshot/unavailable）；无插件且无快照时如实报错，不伪造 schema 检查。
- `report` 在插件不可用时回退到基于保存事实与快照的基础报告，信封明确 `plugin_report_generated: false` 与 `audit_snapshot_found`；旧目录无快照时渲染缺失说明。
- 兼容别名路径 `autoplasm_validate_result` 同样携带 `plugin_validation_executed` 诚实标志。
- 尚未完成（WP5 余项）：inspect 的历史关联字段展示、失败调用与步骤复用的报告呈现增强、限制性章节与引用快照在旧记录中的缺失项渲染细节、与 WP2 退役后的基础报告收口。

### B3 续：WP5 余项完成（执行事实与历史关联）

- `write_generic_report` 新增 `build_run_facts` 与"Execution Facts"章节：步骤状态计数、失败调用及原因、复用（验证恢复）步骤、历史关联（resumes_run_id/previous_run_archive/plan_id）；JSON 摘要同载。无命令事实的报告如实声明，不暗示。
- 本地执行器、`ABIResultWriter`（四后端）与无插件基础报告均灌入真实命令行。
- `inspect` 暴露 `run_id`/`plan_id`/`resumes_run_id`/`previous_run_archive`、复用步骤列表、状态计数与审计快照存在性；旧摘要缺失字段保持 None。
- 双语规范同步；全量测试通过（仅本地专属 3 项失败）；CI 绿（4c54cd9）。

### WP2 专门批次：dry-run 迁移验收依据（已勘察，未实施）

旧 `PipelineExecutor` 重复共享执行器的全流程，差异点即迁移验收清单：

1. `analysis_status` 标准表：`*_not_run` 跳过步骤的 not_run 行（module/status/reason/sample_count/eligible_sample_count/group_counts/threshold 列），重复 dry-run 必须替换而非追加（append=False 语义）。该表属插件报告职责，需在插件侧实现（候选：共享执行器调用的可选插件钩子，如 `write_plugin_tables(tables_dir, plan, command_rows)`），共享路径不硬编码。
2. `commands.tsv` 渲染命令（如 genomad）与 `run_summary.json` 产物标签名（outputs["commands"]/["summary"]）需与共享路径对齐或映射。
3. `write_resolved_config` 与 `_plan_payload` 为旧引擎自有序列化；共享路径已有等价产物，迁移后以共享产物为准。
4. `tests/integration/test_dry_run.py`（14 项）直接从 `abi.autoplasm.*` 导入并直接构造 `PipelineExecutor`——迁移时同步改为经 `WorkflowCoordinator`/共享入口验收。
5. 退役顺序：插件钩子落地 → 删除 `execute_dry_run` 覆写（LocalRuntime 回退共享 dry-run）→ test_dry_run 换入口 → `abi.autoplasm` 转发与 `_engine.pipeline/cli` 退役。每步一个提交。

### B3 续：WP2 dry-run 迁移实施（步骤 1-2 完成）

- 新增可选协议 `ABIPluginRunTablesPlugin.write_run_tables(tables_dir, plan)`：共享执行器与 `ABIResultWriter`（四后端）在标准表头建立后调用，插件自有运行级表不再需要私有执行入口。
- metagenomic_plasmid 实现 `write_run_tables`（`analysis_status` 的 `*_not_run` 行，替换语义，与旧覆写逐列一致）；**删除 `execute_dry_run` 覆写**——插件 dry-run 正式走共享执行器路径（含计划绑定、审计快照、执行事实、归档语义）。
- 对等验证：含 `diversity_not_run` 跳过步骤的共享 dry-run 产出行与旧引擎逐列一致，重复 dry-run 替换语义一致（`tests/integration/test_dry_run_shared.py` 三项经共享入口验收）。
- 版本表语义按共享统一：覆盖 `selected_tools`（旧引擎为全 registry），`test_abi_cli` 相应更新；旧引擎直连测试（`test_dry_run.py`）在旧引擎上保持不变，待引擎退役时同步。
- 剩余（WP2 后续提交）：`abi.autoplasm` 转发模块与 `_engine.pipeline/cli` 退役、`_engine` 内 parsers/report helper 迁出目录。

### B3 续：旧引擎执行核心退役（步骤 3 完成）

- `_engine/pipeline.py`（1088 行：PipelineExecutor、私有调度、状态/证据写入、共识刷新）删除；所有执行路径经共享执行器，插件自有表经 write_run_tables 钩子。
- `_engine/cli.py`（1159 行）与 `_engine/dashboard.py` 随之退役：console 入口此前已移除，应用仅测试可达；其被取代命令由 abi CLI 承载，setup-resources/check-resources 经 abi setup-resources 保留且 --confirm 门测试现保护 abi 面。
- FASTA 生物 helper 迁至插件包 `metagenomic_plasmid/sequences.py`（记录键 id/header/sequence 与退役实现精确一致）；handlers 与 policy 测试改从插件导入。
- 引擎直连测试换成共享路径等价（marker 保留、resolved-plan 步骤对齐、outdir 为文件的拒绝）；引用已退役引擎的本地 ignored 修复/整合脚本（repair_plasmid_standard_tables、integrate_plasmid_supplement）一并清理。
- `_engine` 剩余 6,840 行：生物/数据 helper（parsers、statistics、normalize、report、schemas、resources setup 等）待归位；`_engine/cli.py` 的 setup-resources 职责由 WP8 承接。

### B3 续：`_engine` 目录归位（步骤 4 完成）

- `src/abi/plugins/metagenomic_plasmid/_engine/` 整体更名为 `lib/`：旧执行目录名退役，剩余的生物/数据支持库（parsers、normalize、report、statistics、schemas、resources setup、skills 等）以插件支持库身份归位。55 个文件导入 swept；wheel 打包验证 lib 在、_engine 无；Migration Gate 同步（PLUGIN_DIR → lib）并保持 5/5 通过。
- 入口无隐藏调用者确认：dry-run 已走共享路径（WP2 步骤 1-3），执行核心已删除，剩余模块为声明与生物处理，符合"生物学处理保留在插件"的边界。
- WP2 至此完成：插件私有执行入口、兼容命名空间、旧执行核心与旧目录名全部退役；剩余 WP8 承接 setup-resources 的下载职责。

### 阶段 C 开工：WP8 步骤 1（运行/运维接口停止下载）

- `ABIResourcePlugin` 拆分：仅保留只读发现/诊断；setup 移至新 `ABIResourceSetupPlugin` 协议（契约禁止下载）。
- metagenomic_plasmid 的真实下载执行器删除（约 400 行：资源命令执行、kraken2 aria2c 管线、plasmidfinder 安装、tool_git/pip/download 安装器、ENA 示例数据抓取）。真实运行 setup 逐资源报告就绪状态：就绪=ok，其余=manual_required 外部准备指引；绝不触碰资源路径。
- `abi setup-resources` 移除 `--confirm` 下载门：正常=报告就绪与指引，--dry-run=计划，--mock=夹具；通用分发路径同样输出 manual_required。
- 受保护行为（ready/incomplete 分类、ready_check 字段）移至检查路径测试；13 项下载专属测试随特性退役。
- 剩余 WP8：其余三插件的 ResourceDownloader 真实路径、EasyMeta ENA 节点迁移、环境创建（manage_environments）、运行时隐式工作流/镜像获取。

### 阶段 C 续：WP8 步骤 2（ResourceDownloader 退役）

- `src/abi/resource_downloader.py`（552 行：原子下载引擎、URL 抓取、完整性/清理、锁机制）删除。行构建移至 `abi.resources`（DownloadResult + download_result_to_row），mock 夹具生成变为 `write_mock_resource`（目录 + 就绪哨兵）。
- amplicon_16s：真实运行报告 manual_required 并点名 RDP 下载脚本为外部准备工具；**静默合成 taxonomy 回退退役**——真实分析绝不能对伪造数据运行。
- rnaseq_expression：真实运行报告就绪状态（DESeq2 标记）或 manual_required 外部指引；不再执行准备脚本。
- wgs_bacteria：已存在目录的 ready/incomplete 分类保留（诊断）；缺失目标报告 manual_required（amrfinder_update 提示）。
- Migration Gate 同步（DownloadSpec 检查 → resources.py）；test_resource_paths/resource_boundaries 转换为新语义；ruff 0.16 的死变量门修正。
- 剩余 WP8：EasyMeta ENA 节点迁移、manage_environments 环境创建、运行时隐式工作流/镜像获取。
