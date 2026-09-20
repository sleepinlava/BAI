# ABI 精简重构计划

状态：N1–N5 重构及审查修复已合并，主干 CI 全通过。用户随后调整分发方案：`abi-agent` 继续发布 PyPI，八个插件迁至独立 `abi-plugin` 仓库，仅从 GitHub 按需下载（第 15.10 节）。该迁移正在验收，尚未打正式版本标签或发布。当前计划版本：v0.30；本节后续决定取代旧的插件 PyPI 发布安排。

历史代码基线：`17bdc5b043cec0ffb8fac182e0982c08e29a1875`，ABI `1.5.12`。
本轮复核基线：`127a377`，ABI `1.6.0`；开始复核时工作树干净。
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

### 阶段 C 续：WP8 步骤 3（EasyMeta ENA 节点退役）

- `download_ena_reads` 节点、三个验证传输后端（urllib/aria2c/script）、`streaming_inputs` 校验绕行与 download-only 工作流阶段全部退役。外部准备的 reads 经 ABISample read1/read2 字段成为既有输入；manifest 中的 ENA URL/MD5/字节保留为来源记录；manifest 校验始终检查本地文件存在性。
- `cleanup_taxonomy_intermediates` 不再消费外部原始 reads——清理仅覆盖 ABI 拥有的中间产物（fastp/dehost/kraken2 输出），外部 reads 不进入删除规则。
- preflight 保留 ibd_core53 manifest 校验、kraken2 策略与资源检查，移除 ENA 后端/脚本检查；download-only 工作流预设与其 cohort 配置退役。
- 验证：easymetagenome strict contract-lint 通过；冻结队列计划 31 节点无下载步骤；dry-run 端到端工作；全量测试通过（仅 3 个已知本地专属失败）；CI 绿。
- 剩余 WP8：manage_environments 环境创建职责、nextflow/容器隐式获取核查；剩余阶段 C：Study 退出核心（6）、绘图退出核心（7）。

### 阶段 C 续：WP8 步骤 3 续（环境创建退役）

- `abi env install/update` 命令与 `manage_environments`（及其求解器调用、spec 渲染、写根 helper）退役；`abi env discover/doctor`（只读发现与诊断）保留，求解器发现链路完整。
- Snakemake 运行移除 `--use-conda`：运行时不再隐式创建环境；导出的 `conda:` 指令仅作声明性记录。
- CI 能力检查直接伪造受管环境结构（不再驱动已退役命令）；docker-configuration 断言更新；双语 linux_support_plan 指向外部准备脚本（scripts/cloud/01_envs.sh）。
- 容器镜像核查：无工具契约声明 container_image，container 指令默认不渲染——隐式镜像获取当前无活跃面（记录为核查结论）。
- 工具链同步：本地 ruff 升级至 0.16.7 与 CI 一致（消除版本漂移导致的格式门差异）。
- 剩余 WP8 项：无（获取/安装退役完成，等待阶段 C 其余工作包）。下一批：WP6 Study 退出核心、WP7 绘图退出核心。

### 阶段 C 续：WP6 Study 退出核心（完成）

- `src/abi/study/`（3,050 行）与 `abi-study` 入口从默认安装退役：artifacts/grading/fixtures/harness/workspace/tool_shim/CLI 均为研究项目管理职责，主线无任何导入（导入清扫验证）。不另建无人维护的 Study 项目；旧方案经 Git 历史追溯。
- 七个研究专属测试文件随模块退役；核心执行与历史审计不导入 Study（WP6 验收 ✓）。
- 冻结研究证据 `experiments/abi_control_validation_v1/` 原样保留（跟踪数据/文档，不打包）。
- 剩余阶段 C：WP7 绘图退出核心（SciPlot、abi.figures、报告渲染关联、绘图节点、注册表、默认产物与安装依赖）。

### 阶段 C 续：WP6/WP7 状态核实与 WP7 残余清扫

**重要状态更正**：WP6（Study 退出，6943eca/00553f1）与 WP7 主体（绘图退出，82ba882——sciplot 8k 行、figures 模块、abi-sciplot 入口、report extra 绘图依赖）已由并行工作会话完成并推送；本节此前"尚未完成"清单在该点过时。并行会话在同一目录工作，其提交与本会话的 WP5/WP2/WP8 提交错行于同一主线（reflog 可溯）。

**WP7 残余清扫（da1a646 + 758e01e）**——82ba882 遗漏的三处：

1. ci.yml 仍收集已删除的 `src/abi/sciplot/tests/`——master 的测试门实际是坏的；已修正并断言不再引用。
2. `workflow/validation.py` 的 `check_figures`/`expected_figures`（无调用者）与 plasmid html 报告的死参数 `rendered_figures`/`_figures_html` 移除；`write_plugin_report` 文档字符串不再描述已退役渲染。
3. scipy 归位为主依赖：富集分析脚本（GO/Reactome ORA + GSEA，保留的生物统计）依赖 `scipy.stats.hypergeom`，82ba882 将其误当绘图依赖移除导致 CI 收集失败。

**figure_specs.yaml 保留**（82ba882 的设计决策）：作为外部绘图系统的惰性输入声明。

**WP7 验收确认**：阻断 matplotlib/plotly 导入后核心模块（report/executor/agent）导入正常；报告为表格+事实；插件结构化结果与局限性完整。

**剩余阶段 C**：WP8 已全部完成；Study（WP6）与绘图（WP7）已退出。阶段 C 的剩余核查项为运行时隐式获取的持续监督（nextflow/容器）。下一阶段 D：第一轮收口（WP9/10/12）。

### 阶段 D：WP12/WP10 收口切片（9581692）

- **WP12**：双语 `abi_sciplot_design.md` 退役（绘图职责已退出），目录行与 Sphinx toctree/api 引用同步清除；构建保持 0/0 诊断。devlog/linux_support_plan/plugin_report_figure_spec 为本地忽略文件（不属发布树），按第 4 节处置原则保留本地、不进入输出。
- **WP10**：`resolve_resources` 兼容桥（C06，2026-07——一个发布周期已满）自 `abi.tools` 退役；分层优先级行为由 `resolve_resources_v2` 桥接测试保护。`abi.openai_contracts`、`autoplasm_validate_result` 别名按既有决定保留（有真实外部读者）。
- 验证：Ruff/mypy、全量测试、双语构建 0/0、CI 绿。
- 剩余阶段 D：P0Workflow.run() 弃用入口与其集成测试的 canonical 路径转换；WP9 分发面收口核查（report extra 空置、examples/examples 数据归属）。

### 阶段 D 续：WP10 P0Workflow.run() 退役（f320ef5）

- 弃用执行入口 `P0Workflow.run()` 及其专属 legacy 层删除（整体结果复用匹配、legacy 命令/版本行重塑、根级别名写出；净删 ~280 行）。P0Workflow 的规划/解析面（documented_workflow）保留。
- 集成测试转为 canonical 协调器路径，保留受保护行为：清理回执、host-removal 临时删除、workers 传播、进度事件、溯源持久化。resume 断言切换为 canonical 步骤级恢复关联（resumes_run_id + previous_runs 归档）；report-manifest 篡改块随旧整体门退役（新信任模型为校验和 + 计划绑定）。
- CI 绿；全量测试通过（仅 3 个已知本地专属失败）。

### 阶段 E 开工：WP11B 步骤 1（分发层与实现分离，35b2ffb + c39dc6b）

- `abi/plugin_registry.py` 成为核心所有的发现/选择/加载层（入口点 + manifest、可解释错误、确定性冲突处理）；核心的 agent/resources/executor/results/doctor 模块全部改从其导入。
- **导入探针验证**：仅核心路径（dispatch/diagnose/audit）加载零个插件实现模块；缺失插件错误保持可解释（含可用类型清单）。
- `abi/plugins/__init__.py` 变为实现包根（兼容 re-export）；校验器迁至核心 `abi/plugin_validation.py`（校验插件结构而非实现）；Migration Gate 路径同步，5/5 通过。
- 剩余 WP11B：插件数据打包进分发（root 经 importlib.resources 解析）、双发行结构（core / plugins）、三种安装形态验收（仅核心/单插件/完整组合）。

## 13. 阶段 E 续：WP11B 步骤 2（插件数据同址打包与三种安装形态验收）

本批由主代理接续完成（继承此前会话在工作树中已开始的同址化改动并修正其中断点）。没有发布。

### 已实施变化

**插件数据同址与双发行结构。**

- 8 个官方插件的声明数据（abi-plugin.yaml、pipeline_dag.yaml、tool_registry.yaml、tool_contracts/、limitations.yaml、schemas/、skills/ 等）从仓库根 `plugins/<id>/` 整体迁移至实现包内 `src/abi/plugins/<id>/`，实现代码与声明数据同址；根级 `plugins/` 目录退役。wgs_bacannot 数据此前已在 `src/abi/plugins/wgs_bacannot/`。
- 核心 wheel（abi-agent）通过 hatchling `exclude` 不再包含任何插件实现与数据（wheel 内容探针验证为 0 个插件文件，`abi/plugins/__init__.py` 兼容垫片保留）；官方插件以 `abi-agent-plugin-<id>` 独立发行版发布：实现包 + 同址数据 + 各自的 `abi.plugins` 入口点，依赖锁定 `abi-agent==<同版本>`。
- `pyproject.toml` 新增 `plugins` extra（完整官方组合 = 8 个插件发行版）；`[tool.hatch.build.targets.wheel.force-include]` 中的 `"plugins" = "plugins"` 移除。
- `scripts/build_plugin_wheels.py`（新增）：按同址布局 staging 每个插件发行版并生成其 pyproject（含 `--build` 直接产出 wheel、`--no-build-isolation` 离线构建、3.10 兼容的版本读取回退）。staging 拒绝代码/数据冲突并剔除 `__pycache__`。
- `scripts/verify_install_forms.py`（新增）：三种安装形态验收——仅装核心（list-types 为空、未知类型以 unknown_analysis_type + 空可用清单可解释失败）、核心+单插件（仅该插件可发现、无配置 dry-run 成功、其他类型可解释失败）、核心+完整组合（8 种类型全部解析）。CI 使用干净 venv 全依赖解析；`--reuse-system-deps` 为离线环境的降级路径。

**发现与数据根（核心扫描调用者迁移）。**

- `plugin_registry` 新增 `plugin_data_roots(project_root)` / `plugin_data_root(id)`：合并同址捆绑包与 `PLUGIN_ROOT` 散装插件目录，散装目录不得遮蔽捆绑 id（警告并忽略），不加载任何实现；manifest 发现复用同一同址扫描。
- `ToolCatalog.from_project_root`：按 plugin_id 确定性排序遍历插件数据根（捆绑 + 项目根散装），不再假设全局 `plugins/`；显式 project_root（测试/备用 checkout）语义保留。
- `runtime_lock`：工具锁遍历插件数据根；`_release_required_tools`/`_resource_consuming_tools` 经 `plugin_data_root` 解析，找不到插件数据时显式报错（不因插件缺失静默缩小认证范围）。
- `workflow/catalog.py::for_plugin` 兜底经 `plugin_data_root` 解析（`PLUGIN_ROOT` 散装路径仅作最后兜底）。
- `config._resolve_project_root` 的项目根标记从 `plugins/` 改为 `config/`（源码树根与安装后 site-packages 根均存在）。
- `contracts/lint_template.py::_plugin_root` 兜底经 `plugin_data_root` 解析。
- 修正继承工作树中的三处 off-by-one：`lib/pipeline_dag.py`（parents[1]）、`lib/report/__init__.py`（parents[2]）、`lib/skills/registry.py`（parents[2]）；`plugin_registry` 中重复的 `raise` 死代码删除。
- 插件 `root` 属性全部改为解析自身包目录（`Path(__file__).resolve().parent`）；`interfaces.py` 协议注释同步（满足同址需要，未引入 importlib.resources 包装层——常规 wheel/editable 布局下两者等价，`abi.data` 的 importlib.resources 读取保持不变）。

**Docker 与 CI（发布面）。**

- 5 个 Dockerfile 移除 `COPY plugins/`；安装序列改为：核心 wheel → `build_plugin_wheels.py --build` 构建插件 wheel → `pip install --no-index --find-links` 安装 8 个插件发行版（完整官方组合），清理列表同步。镜像内 `abi list-types` 仍应列出 8 种类型。
- `tests/unit/test_docker_configuration.py`：工具合约路径改指 `src/abi/plugins/`；`test_every_dockerfile_copy_source_exists` 移除 `plugins` 项；新增 `test_dockerfiles_install_the_official_plugin_combo` 锁定插件发行版安装与 COPY 退役。
- `ci.yml`：matrix 与 arm64 的构建步骤追加插件 wheel 构建；两个 wheel 冒烟步骤先装完整组合再验证能力矩阵；新增 "Acceptance — WP11B installation forms" 步骤（3.12）运行三形态验收。
- README（双语）：安装章节改为核心 + `abi-agent[plugins]`/单插件发行版；退役的 `abi env install/update` 与 `setup-resources --confirm` 表述替换为只读诊断与就绪报告；`[report]` extra（绘图退役后为空）不再宣传；插件布局段落改为同址 + 独立发行版。插件开发指南（双语）：目录布局、发行版（WP11B）小节、资源管理章节（移除"自动安装/下载"表述，改为就绪报告 + manual_required）。development 指南（双语）：源码树/运行时资产/SDK 表同步（移除 sciplot/figures 残留，标注双发行结构）。

### 验证结果

- 全量测试（不含 smoke）：2536 passed、13 skipped、3 failed；3 个失败为第 12 节已记录的预存环境问题（未跟踪的论文示例数据测试 ×2、sparse-checkout 隐藏的 Linux 证据文件 ×1），与本批无关。
- Ruff（lint + format）与 mypy 全部通过；双语 Sphinx 构建 0/0 诊断（且输出无退役页面残留）。
- `python -m build`：默认 sdist→wheel 路径通过；`twine check` 对核心 wheel/sdist 与 8 个插件 wheel 全部 PASSED（插件 wheel 缺 long_description 的非阻断警告，属生成产物的已知简化）。
- 三种安装形态验收本机通过（`--reuse-system-deps` 离线降级路径；CI 将以干净 venv 复验）。同址 wheel 内容验证：插件 wheel 含实现 + 全部 YAML 数据 + 入口点；核心 wheel 无插件文件。
- `abi contract-lint --strict` 七项通过；`abi list-types` 8 种；`docker compose config --quiet` 通过；`test_docker_configuration` 23 项通过。

### 尚未完成与边界

- Docker 镜像的实际构建与 `abi list-types` 冒烟需在发布前手工执行（AGENTS.md 规定非 PR 门槛）；本批仅通过配置回归测试与 Dockerfile 断言锁定。
- `release.yml` 默认 GITHUB_TOKEN 不触发 `release.published` 的已知缺口（第 12 节）仍未处理。
- 插件发行版当前不含 `py.typed`/独立版本策略：与核心同版本同流程是 WP11B 的明确取舍；后续若引入独立插件版本需先修订发布身份规则。
- 11A 时期记录的 "root 经 importlib.resources 解析" 以同址 `__file__` 解析实现满足现有需要（zipapp/zip 安装不受支持）；若未来需要只读 zip 布局再引入 `importlib.resources` 包装。
- 真实生物信息学工具、HPC 终止确认、正式运行锁认证仍为后续阶段的验收项。

## 14. 当前目标复核与下一步计划（2026-09-14，v0.24）

复核代码：`3615dcf94a64b1343ff96a1001880f7ccea9637c`；开始时工作树干净。本轮由三个 GPT-5.6-Luna 子代理分别复核核心、分发和职责退役，主代理交叉检查关键源码与测试；只更新计划，不实施产品修复或发布。

### 14.1 完成程度更正

**结论：方向和主要拆除工作成立，但两个产品目标均为部分达成。** 当前不适合继续以删行数作为主要进度，也不能将已存在的审计字段等同于完整、独立、可靠的历史审计。

| 目标/范围 | 已有实质成果 | 尚未通过的验收 |
| --- | --- | --- |
| 安全可靠地执行分析 | 严格布尔授权、编译计划校验及运行前身份比较、共享协调器、契约检查 | 原始输入保护仍有旧删除分支；恢复未完整绑定外部输入/工具/资源身份；后端执行对象仍是可变插件计划；超时与远端取消证据不完整 |
| 人工事后复查 | 命令 TSV、运行身份及历史关联、审计快照、缺插件时基础报告与表结构校验 | 旧运行归档不完整；成功调用详情未进入基础报告；缺插件严格校验可崩溃；快照错误和缺失状态不足 |
| 旧主干、Study 与绘图退役 | AutoPlasm 旧执行核心、Study、SciPlot、abi.figures 和对应入口已移除 | 七个插件仍有专用 dry-run 路径；plasmid DAG 仍有可选绘图节点及工具实现，WP7 不能整体结项 |
| 所有获取交给外部系统 | ENA 节点、ResourceDownloader、环境安装命令已移除 | 核心 wheel 仍强制包含下载脚本；Nextflow 容器声明及 HPC 容器启动路径尚无充分的预备镜像校验，隐式获取边界未验收 |
| 分析插件可选 | 按需发现/加载、八个同址插件 wheel、核心 wheel 不含插件实现 | 独装核心尚无历史读取的安装产物验收；发布流程没有接入插件构建和发布；科学计算依赖仍在核心 |
| 文档及质量门槛 | 双语部分旧文档退役、构建清除旧页面、有效核心测试保留 | AGENTS.md 仍含旧目录和命令；全套测试历史记录仍有三个失败，不能称为全绿 |

同一 Git 统计口径下，非测试 Python 源文件从基线的 236 个降至 158 个；受跟踪的双语 Markdown/RST 从 42 个降至 40 个。这只证明规模变化，不证明安全性或科学有效性。

### 14.2 必须优先处理的具体缺口

1. **原始数据保护（工作包 8/3）。** `easymetagenome/handlers.py::cleanup_taxonomy_intermediates_handler` 仍把 `raw_read1/raw_read2` 纳入删除列表，只检查路径位于输出目录内。当前生成计划已不传这两个字段，但处理器与旧集成测试仍允许删除它们。应在清理边界明确输入保护与 ABI 中间产物归属，不能只依赖调用方省略字段。
2. **完整历史（工作包 3/5）。** `provenance.py::reset_run_provenance` 只归档部分 provenance 文件及日志，遗漏执行计划、结果表、报告和 `audit_snapshot.json`；重跑会改写这些文件。先保存旧运行可独立解释的证据，再允许重写当前视图。无需复制全部巨大生物数据，但被覆盖的审计证据必须保存；产物后续消失应标为不可用，不能篡改历史成功事实。
3. **独立审计（工作包 5/11B）。** `results.py::validate_abi_result_dir(..., allow_empty_tables=False)` 在插件加载失败后使用未绑定的 `plugin`；`audit.py` 忽略写入错误且读取不校验快照版本；基础报告只有状态计数、失败调用和复用信息，成功命令与参数仍需人工查 TSV。修复异常和缺失状态，展示或明确链接全部实际调用，确保报告使用最终运行身份。
4. **执行与恢复身份（工作包 3/4）。** `bind_confirmed_plan` 已提供运行前比较，不能称为没有计划保护；但四后端仍消费 `prepared.plan`。恢复只核对已记录的文件校验和，外部原始输入通常不在该映射中，旧记录无校验和时仍回退到存在性检查。应使执行内容与确认内容保持一致，并对输入、工具和资源变更拒绝未经验证的复用。历史可读与历史产物可安全复用是两项不同保证。
5. **终止与超时事实（工作包 3）。** jobs 已明确确认范围只是 dispatch worker；HPC 发出取消命令后缺少终态确认，Nextflow/Snakemake 超时可能在写结果前抛异常。必须保留请求、已确认终止、下游状态未知的区别，失败和超时也写入持久记录。
6. **正式分发（工作包 9/11B）。** `release.yml` 只构建核心、仍执行已退役的 `autoplasm`、未安装插件就运行插件 dry-run，也未构建/附加八个插件 wheel。CI 中构建插件不等于 Release 包含插件。先修复这一明确阻断，再核验完整发行物集合、同版本关系及从 Release 原样下载至 PyPI 的流程。保持现有四工作流及可信发布身份，不复用已发布版本。
7. **隐式获取（工作包 8）。** `exporters/nextflow.py` 仍输出容器声明，`tools.py` 仍生成 Docker/Singularity 启动命令；这些路径没有证明缺镜像时一定先失败。补齐只读就绪检查及拒绝隐式获取的后端约束，以“缺镜像不启动、不下载”行为验收。当前正常 setup-resources 只读/模拟行为应保留，不能把外部准备命令的说明误判为已经执行下载。

Release 事件链还须按官方行为核验：默认 `GITHUB_TOKEN` 创建的事件通常不会触发后续工作流（例外包括 workflow_dispatch/repository_dispatch）。现有手工发布入口可用于明确的人工步骤，但不能将未验证的自动链称为闭环；本计划不授权新增自动发布入口、改可信发布身份或配置密钥。依据：[GitHub 官方工作流触发说明](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。

### 14.3 下一步分批执行及出口

| 批次 | 具体改动范围 | 必须得到的验收证据 |
| --- | --- | --- |
| 1：保护输入与历史 | 清理处理器退役原始 reads 删除分支；以现有运行目录机制补完整归档；每项独立提交 | 原始输入位于 outdir、符号链接、失败清理均不误删；连续两次运行后，旧计划、表、报告和快照字节不变且可独立读取 |
| 2：完成基础审计 | 修复缺插件严格校验；快照版本/结构与写入失败显式处理；成功/失败/复用调用可查；报告身份写入顺序收口 | 干净环境只安装核心 wheel，读取成功、失败、恢复、缺快照旧结果；inspect/report/validate-result 均给出准确结果；不用安装原插件或执行工具 |
| 3：收口执行保证 | 保持确认内容到后端执行的一致性；恢复身份覆盖外部输入/工具/资源；持久化超时及取消证据；补预备镜像与禁止隐式获取约束 | 更换输入内容、工具或资源后不能错误复用；队列等待期间漂移不能启动；缺镜像在后端启动前失败；四后端控制测试区分请求与终止确认，保留真实集群验证的限制 |
| 4：完成安装与发行 | 核心和八插件同版本构建/安装/Release 资产检查；删除失效发布命令；核验事件链；复用批次 2 的独装审计验收 | 默认 sdist→wheel、三种干净安装、完整组合集成、发行物集合与哈希检查通过；实际发布另按已有身份规则执行，不在本轮审查中发布 |
| 5：继续职责精简 | 清除残留活动绘图节点/脚本及失效依赖；退出产品包中的获取脚本；将科学计算依赖归到使用它的插件；逐个迁移仍必要的专用 dry-run 行为 | 八种分析的必要计算和结构化输出保持；DAG/契约与所需工具清单一致；核心独装不要求绘图或无关科学依赖；不新增安装平台或第二套执行主干 |
| 6：文档与开发入口收口 | 同步 AGENTS.md、开发/安装指南与权威规范；处理空 report extra、重复格式化入口和无主资产候选；精简过程记录 | 每项删除有调用者/读者核查；双语构建 0/0；没有仍可执行的旧命令或已删除目录指引；当前状态只由本节维护 |

批次 1、2 优先于继续大规模删除；批次 4 的独立发布修复可并行准备，但整体验收须等待批次 1–3。批次 5 按职责分别落地，不把依赖搬迁、行为改动和文档删除混成一次大提交。保留工具→环境映射与必要的 Docker/外部部署构建输入，先移出核心 wheel 再判断仓库文件去留。批次 6 同时修复失效的 `setup-resources --confirm` 调用及指向不存在脚本的准备提示。每批完成相应质量门槛后再进入下一批。

### 14.4 测试取舍与本轮证据

- 保留并补强原始输入保护、授权/漂移、恢复身份、历史不可改写、失败/取消持久化、缺插件审计、契约和安装产物测试；这些直接对应两条主线。
- 将只搜索发布 YAML 中插件名字的断言改为检查实际构建、安装和发行资产链；现有字符串检查未捕获过期 `autoplasm` 与插件缺包问题。优先复用安装验收脚本，避免复制多套发布冒烟逻辑。
- 仅随退役职责删除专属测试，或在证明 fixture、参数与行为覆盖完全重复后合并；不新增仅断言文件不存在、代码行数或文档标题的测试。
- 历史非 smoke 全量记录为 2536 passed、13 skipped、3 failed；本轮 Luna 重新执行 `pytest -q --disable-warnings --tb=short` 得到 **2531 passed、18 skipped、3 failed**，两者选择口径不同，不报告为全绿。两个失败来自被忽略的本地论文测试及其缺失数据；另一个来自本地隐藏的受跟踪 Linux 冻结证据文件。论文专属测试应明确移出产品默认收集，或将仍有产品价值的行为改用自包含 fixture；冻结证据应恢复真实受跟踪文件并保留验证。本轮不采纳“缺证据就自动跳过”的建议，不能伪造证据、弱化原有门槛或删测试换绿色。
- 本轮主代理：编译计划、运行适配与通用报告测试 **52 passed**；缺插件基础审计测试 **4 passed**。Luna：计划/溯源/取消/接口等定向测试 **98 passed**；协调器/共享 dry-run/结果等 **32 passed**。这些集合有重叠，不能相加为独立测试总数，也不能替代全套 CI 或真实工具验收。
- 本轮源码探针复现了缺插件严格校验异常、错误快照版本被接受及历史归档遗漏。已有本地 wheel 内容支持“核心与八插件分包成立”；不证明它们对应远端已发布发行物，也不把复用系统依赖的安装测试算作完全隔离验收。
- `bash docs/build_docs.sh` 初次因受限环境无法解析 Python 官方文档索引地址，出现 1 个网络警告而按零警告门槛失败；联网重跑后双语均 **0/0 诊断，通过**，未放宽门槛。未运行真实分析、远端集群取消、Docker 实际镜像构建或发布。

## 15. 当前目标验收与下一步精简计划（2026-09-17，v0.28）

本节是当前唯一的进度与执行顺序入口，后续复核直接更新本节，不逐轮追加重复计划。v0.24 之后的修复提交应计入进展，不再照抄第 14 节的旧问题。v0.26 由两个 GPT-5.6-Luna 子代理与主代理完成只读复核；用户随后授权继续实施 N1，实施与验收记录见 15.6。

### 15.1 已落地实现与对应提交

| 批次 | 当前本地实现 | 主要提交与出口 |
| --- | --- | --- |
| 1：保护输入与历史 | EasyMetagenome 清理处理器保护原始文件、原始符号链接和符号链接目标；运行重写前归档计划、表、报告与快照 | `7cb19b5`；输入位于 outdir、符号链接、失败清理和两次运行历史测试已覆盖 |
| 2：完成基础审计 | 快照写入失败显式报错，快照版本/结构/身份校验，插件缺失时使用保存的 schema，基础报告写入执行事实与历史关联 | `c5d9aaf`；缺插件、缺快照、坏快照、严格空表、inspect/report/validate-result 定向测试已覆盖 |
| 3：收口执行保证 | 恢复身份覆盖计划、输入、工具、资源、容器与缓存；四后端补充超时、取消请求、终止确认和下游未知证据 | `d1abbfe`、`14222ce`；运行前漂移拒绝、超时/取消持久化和容器只读就绪检查已覆盖。v0.26 发现的中间输入误拒绝由 N1 修复，见 15.6；真实 HPC 调度器终止仍未认证 |
| 4：完成安装与发行（本地验收） | Release 工作流构建核心 sdist/wheel 和八个插件 wheel，校验同版本与精确核心依赖，发布资产合并到 `dist/`，执行核心独装、单插件和全插件验收；移除退役 `autoplasm` 冒烟 | `9da3314`；核心与八插件 `1.6.0` 本地构建、Twine 检查和三种安装形态验收通过。未创建 GitHub Release，未发布 PyPI |
| 5：职责精简（首个切片） | 下载数据库脚本仍保留在源码/sdist 供外部部署，但不再被核心 wheel 强制打包；核心 wheel 内容与 sdist 内容均有实际检查 | `2b8d7fa`；下载脚本不在核心 wheel、仍在 sdist 的打包验收通过 |
| 6：文档与开发入口（首个切片） | 移除云端脚本、双语开发/使用文档、CLAUDE 指引和默认配置中失效的 `setup-resources --confirm`；统一为只读报告/外部准备说明，并修正云端脚本残留的“自动获取”阶段标签 | `7a552dd`、`8d6a0db`；回归测试禁止这些受跟踪入口重新出现，双语文档构建为 0/0，云端脚本通过语法检查 |

### 15.2 v0.25 实施时的验证记录（历史证据）

- 本轮相关定向集合为 **38 passed**：发行/文档、安装形态和 Docker 配置回归，以及失效资源确认参数回归；新增切片没有引入测试失败。
- `ruff check src/ tests/ scripts/verify_install_forms.py`、`ruff format --check src/ tests/ scripts/verify_install_forms.py`、`mypy src/abi/ --ignore-missing-imports`、`bash -n scripts/cloud/02_databases.sh scripts/cloud/deploy_rebuild.sh` 和 `git diff --check` 通过。
- 核心 `1.6.0` 的默认构建在依赖镜像可用时已通过；本轮配置切片在受限网络下使用已安装构建后端分别重建 sdist/wheel，实际确认下载脚本仅存在于 sdist、不存在于 wheel。八个插件 wheel 和三种安装形态的完整证据来自 `9da3314`。
- 完整 `pytest tests/ -q --tb=short` 曾启动但本地长时间没有最终汇总，随后中止；不能据此报告全套测试全绿。第 14.4 记录的三个历史失败和真实工具、远端集群、实际发布限制继续有效。

### 15.3 当前验收结论

两条主线的基础实现已明显完善，但“本地实现存在”“安装产物可用”“真实环境认证”必须分别记录。不能继续把已经修复的原始 reads 删除、缺插件严格校验异常、旧发布命令当成当前阻断，也不能由相关单元测试通过推出整体完成。

| 目标 | 当前证据与判断 | 尚需补齐 |
| --- | --- | --- |
| 安全、可靠地执行分析 | 输入保护、完整结果证据归档、防御性计划副本及再次校验、恢复身份和终止记录已有实现；N1 补齐中间产物分类及两步恢复回归 | 形成四后端明确支持矩阵；真实工具和 HPC 终止按实际可用环境验证 |
| 人工事后复查 | 基础报告已展示实际命令，快照版本/身份校验及缺插件回退已加强；N1 新增核心 wheel 独装的三条审计命令与五类历史结果验收 | 正式发行与真实环境证据仍需分别核验；不能把合成结果的基础审计验收当作真实科学分析认证 |
| 可选分析插件 | 核心与八插件分包、同版本及精确核心依赖验证、Release 构建/安装/附加插件已接通 | 安装用户路径验收、科学计算依赖归属、下载后发行物集合/哈希检查；远端发布状态未核验 |
| 获取、绘图和 Study 外部负责 | Study 与 SciPlot 主体退役；下载脚本已移出核心 wheel；运行时镜像就绪与拒绝获取约束已有修复 | plasmid 四个独立绘图节点已退役，专属脚本/注册项/环境仍待清理；核心仍含部署和插件专属资产；准备提示及维护文档仍有旧语义 |

v0.26 确认并由 N1 修复的行为问题：恢复身份曾将上游生成、下游消费的中间文件误归为外部输入，文件从不存在变为存在就拒绝合法恢复。现依据有效步骤声明的具体产物区分中间输入，原始输入仍绑定内容；两步执行器回归验证合法恢复不再调用工具、真实输入变化仍重新执行。详细边界与证据见 15.6。

同时纠正旧清理判断：六个插件的 `execute_dry_run` 只是 `_execute_generic_dry_run` 薄封装，`wgs_bacannot` 是有特定职责的外部 Nextflow 适配，plasmid 走通用回退。不存在已证明需要重写的“七套执行主干”；不安排逐插件大迁移，不为统一方法名新增框架。保留一组共享行为及外部适配回归即可。

### 15.4 下一步工作包、依赖与验收

以下是 v0.24 批次 1–6 的收口切片，按行为和职责拆小提交，不另建一套重构主线。

| 顺序 | 改动范围及边界 | 验收出口 |
| --- | --- | --- |
| N1：补主线行为与安装验收（本地验收完成） | 修复恢复误判；扩展三形态脚本，核心独装读取最小历史结果；单插件与完整组合执行实际入口探针 | 恢复、核心独装五类历史审计、单插件和完整八插件组合均通过；不借用系统依赖，不执行真实生物工具 |
| N2：退役活动绘图（执行入口切片已实施） | 移除 plasmid 的可选 visualization 节点、报告依赖、专属渲染脚本/注册项/环境依赖；保留分析计算及结构化结果 | DAG 依赖和严格契约有效；插件报告不要求生成科学图；比较分析等有科学用途的结果不随图件删除；外部需要的声明无核心加载义务 |
| N3：缩小核心分发 | 将 numpy/pandas/scipy 按实际调用方归入插件依赖；审查 envs、examples、golden_traces 与辅助脚本归属；保持核心必需的环境映射和宿主适配资源 | 核心独装及 N1 历史审计不需无关科学依赖；受影响插件单独安装仍可执行必要统计；sdist→wheel、Docker 构建上下文与安装形态检查通过 |
| N4：完成发行物验证 | 复用现有构建和三形态验收；验证核心 sdist/wheel + 八插件 wheel 的预期集合、版本、依赖及哈希，下载后同样核验 | 缺包、额外包、错版本、字节变化均在发布前被拒绝；避免再复制一套冒烟脚本；不改变四工作流或可信发布身份，不重用已发布版本 |
| N5：清理开发与文档入口 | 同步 AGENTS.md、README/CLAUDE 与双语指南、release_check.sh、过时准备提示；清理空 report extra 及调用方；确认 CMake 等调用方后统一格式化入口；整理产品测试与本地论文测试边界 | 文档不再指导访问已删除目录/入口；本地论文绘图依赖不回流核心；恢复真实冻结证据并保留检验；双语构建 0/0 |

N1 本地验收已完成；当前继续收口 N2 的资产与依赖清理（执行入口切片见 15.7）；N5 的独立文档清理可以并行准备。N3 应在绘图归属明确后进行，先在本规划中补充核心 wheel / 插件 wheel / sdist / Docker 的资产归属表再删资产；N4 复用 N1 的验收。每批运行与改动相称的质量门槛，整体结束前必须得到完整产品测试汇总；真实环境不可用时按能力明确标注未认证。四后端和八种分析继续保留，核心安全与审计不能成为可关闭组件。

### 15.5 v0.26 复核证据与测试取舍（历史记录）

- 主代理运行 `.venv/bin/pytest tests/unit/test_verify_install_forms.py tests/test_documentation_artifacts.py tests/unit/test_docker_configuration.py -q --tb=short`：**38 passed**。这证明元数据和配置回归通过，不等于重新构建、干净安装或实际发布。
- Luna 核心定向集合：**267 passed、1 skipped**，覆盖输入保护、历史、审计、恢复、计划漂移、运行时终止及容器就绪。范围复核另运行文档资产 **13 passed**、插件契约 **21 passed**；集合有重叠，不合计为独立测试总数。共享 dry-run 集成测试在另一子代理中约 60 秒无汇总后中止，不将该次运行记作通过或失败。最小中间输入探针由子代理与主代理分别复现，未使用真实生物工具。
- 重查历史失败时，被忽略的 `test_create_real_data_case_study_figures.py` 因本轮环境没有 matplotlib 在**收集阶段报 1 个错误**；单独运行 Linux 能力证据测试得到 **1 failed**，原因仍为本地缺少受跟踪的冻结 JSON（skip-worktree 标记）。历史“3 failed”不能当成本轮全量结果。本轮不安装绘图库来满足已退出产品职责的本地论文测试，也不通过缺证据自动跳过来放宽门槛。
- 文档构建初次因沙箱 DNS 无法读取 Python 官方索引失败；联网重跑 `bash docs/build_docs.sh` 后双语均 **0/0 诊断，通过**。未修改零警告门槛。
- 保留授权、输入保护、历史、恢复、取消、契约、独立审计和发行身份测试；优先补真实用户路径和正常成功路径。重复 fixture/行为才可合并；不新增固定代码行数、方法数量或单纯文件存在性的测试。
- 下一轮产品测试应在明确的收集边界下得到完整汇总；本地论文复现保留为明确选择的外部研究任务，冻结平台证据维持既有强度。未运行真实生物工具、远端 HPC、Docker 实际构建或发布。

核心定向集合的复现命令（267 passed、1 skipped）：

```bash
./.venv/bin/pytest -q --disable-warnings --tb=short \
  tests/integration/test_input_protection.py tests/integration/test_result_history.py \
  tests/integration/test_easymetagenome_handlers.py tests/unit/test_executor_boundaries.py \
  tests/unit/test_provenance.py tests/unit/test_audit.py tests/unit/test_results.py \
  tests/unit/test_results_ext.py tests/unit/test_report_generic.py tests/unit/test_agent_interface.py \
  tests/unit/test_compiled_plan_runtime.py tests/unit/test_resume_identity.py \
  tests/unit/test_container_runtime.py tests/unit/test_hpc_runtime.py \
  tests/unit/test_nextflow_runtime.py tests/unit/test_snakemake_runtime.py \
  tests/integration/test_runtime_timeout_evidence.py tests/unit/test_external_workflows.py
```

### 15.6 N1 实施与验收（2026-09-15，未提交/未发布）

本批主体由两个 GPT-5.6-Luna 子代理分别实现恢复修复与安装审计。Luna 后续额度耗尽，用户明确允许主代理完成收尾；主代理修正安装脚本的相对路径解析、补齐质粒/Bacannot 的试运行样本要求，并校正双语旧记录说明。未启动 N2–N5。

- **恢复身份。** 有效步骤声明的具体上游产物不再作为外部输入重复绑定；跳过的步骤不参与产物索引，`output_dir` 不作为目录内所有文件的所有权凭据。样本原始输入优先保留，聚合目录中的非 ABI 产物仍检查内容。未增加新执行器或全局身份服务。
- **行为验收。** 两步执行器首次生成中间文件，第二次恢复时工具调用次数为零、两步均为 `resumed`；外部原始文件变化仍触发两步重新执行。输出目录内原始输入、符号链接和聚合目录里的用户文件继续参与漂移判断；既有产物校验和与失败清理检查保留。
- **独装审计。** 扩展现有 `verify_install_forms.py`，在无插件的核心 wheel 环境实际调用 inspect、report 和严格非空表 validate-result，覆盖成功、失败、恢复、缺快照与坏快照。夹具包含非空表、真实格式的命令记录和恢复关联，仅用于软件验收，不是科研证据；检查保存的命令、状态与 schema 回退，不只检查文件存在。
- **安装隔离。** 子进程使用临时工作目录并清除继承的 PYTHONPATH/PYTHONHOME；输入 wheel 目录先转为绝对路径，使 CI 的相对路径参数也能工作。单插件与完整组合的输出目录互相隔离，完整组合逐个执行八插件 dry-run。质粒使用显式规划样本表，Bacannot 使用临时合成双端 reads，均不执行真实工具。
- **兼容边界。** 旧结果保持可读；缺少有效恢复身份证据时不能仅凭文件存在承诺复用。原始输入采集、部署、绘图职责不回流核心。`--reuse-system-deps` 仅是开发者降级选项，本次正式安装验收未使用它。

验证记录：

| 检查 | 结果与范围 |
| --- | --- |
| 恢复、输入保护、历史、审计及受影响后端定向集合 | **185 passed、1 skipped**；含新两步恢复回归及安装脚本单测，不代表全套 CI |
| Ruff lint / format、mypy | 全源与测试 lint/format 通过；mypy **159 个源文件无错误**；脚本收尾后再跑相关检查 |
| 默认核心构建与插件构建 | 默认隔离 sdist→wheel 已通过，八插件 wheel 已构建；配置镜像一度不能提供受约束的构建后端，临时使用官方 PyPI 源成功，未修改仓库依赖或源配置 |
| 最终产物一致性 | 最终重建的核心 wheel 与通过干净安装的 wheel **逐字节相同**；sdist 内安装脚本及双语规范与最终源码一致，核心 wheel 的恢复实现亦一致 |
| 三种干净安装 | **全部通过**：核心独装五类历史审计、单插件 dry-run、完整八插件 dry-run；按 CI 的相对路径参数运行，未使用 `--reuse-system-deps` |
| Twine | 核心与八插件产物通过；插件仍有已有的长描述缺失警告，未隐藏 |
| 双语文档 | 修正后的双语构建 **0/0 诊断，通过** |

相对路径验收从临时构建目录运行：`PIP_NO_INDEX=1 PIP_FIND_LINKS=<临时依赖wheel目录> python /home/bker/abi/scripts/verify_install_forms.py --dist-dir core --plugin-dist-dir plugins`。依赖先按声明下载；三个 venv 都全新创建并解析依赖，这与复用系统 site-packages 不同。

未运行真实生物工具、真实集群取消、实际 Docker 镜像构建或远端发布。全套测试仍需按 15.5 中记录的论文材料与冻结证据边界完成；本批不降低覆盖门槛、不删除冻结证据检查。


### 15.7 N2 执行入口切片（2026-09-17，未提交/未发布）

以当前源码核对 v0.27 后实施：移除 `visualization_clinker_gene_maps`、
`visualization_pycirclize`、`visualization_network`、`visualization_dna_features`
四个节点及报告对应依赖，移除专属输出阶段目录声明。保留 `comparative_clinker`、
BLAST/MUMmer、FastSpar 与宿主关联计算，也保留历史 `visualization_outputs` 表与解析器。
旧 visualization 配置不再生成独立绘图步骤；基础报告无需这些图件。
双语质粒指南同步说明边界；实际 DAG 为 87 节点（修改前 91 节点，旧文档的 90 已过时）。

新增五平台的旧绘图配置回归：验证拓扑可排序、依赖不悬空、报告保留且比较分析仍在报告之前。
新增共享 dry-run 后直接生成质粒 Markdown/HTML 报告的集成回归，验证缺少绘图目录时报告仍包含
结果摘要和局限说明。验证结果见下表。

本地环境不同于 15.6：当前目录不具备可用 Git 元数据，无法核对提交身份或工作树差异；
未修改 Git 元数据。默认 Python 3.14 缺少 pydantic，首次 pytest 在收集阶段失败；
使用 `/tmp/abi-refactor-venv` 隔离安装测试依赖，历史验收数字不作为本次结果。

后续顺序与验收：

1. **N2 资产收口**：移除仅服务于三个专属渲染器的注册项、契约、脚本和工具→环境映射；
   保留比较分析 clinker 所需环境，不能直接删除整个 `autoplasm-visualization`。
   同步生成 Conda YAML，检查外部 figure_specs 声明的归属；历史结果读取兼容保持。
   该切片触及发行面，须补 Docker 配置测试、Compose 配置验证、默认 sdist→wheel 构建及插件验收。
2. **N3 分发归属**：先列核心 wheel / 插件 wheel / sdist / Docker 资产归属表；
   逐调用方迁移科学计算依赖，复用 N1 干净安装审计，避免仅凭 import 搜索删除依赖。
3. **N4 发行物完整性**：在现有构建与安装脚本上验证集合、版本、依赖和哈希；不执行发布。
4. **N5 入口清理与整体验收**：更新开发指南，明确论文测试与产品测试边界，完成产品测试汇总；
   保留冻结证据检查。真实生物工具、HPC 终止和容器构建按实际证据单独认证。

本次不将 N2 整包或全部重构标记为完成。


本批验证（均使用上述隔离环境，Python 3.14；不替代 CI 的 Python 版本矩阵）：

| 命令 | 结果 |
| --- | --- |
| 下列定向 pytest 集合（含共享 dry-run 与规划 smoke） | **158 passed，57.00s**；新回归初版夹具/API 错误已修正为生产 `UniversalDAG` 与完整配置，最终集合全通过 |
| `ruff check src/ tests/` | 通过 |
| `ruff format --check src/ tests/` | 379 文件通过 |
| `mypy src/abi/ --ignore-missing-imports` | 159 源文件通过 |
| `PYTHONPATH=src python -m abi.cli contract-lint --type metagenomic_plasmid --strict` | 通过，0 error / 0 warning |
| `bash docs/build_docs.sh` | 首次因沙箱 DNS 获取 intersphinx 索引失败；授权联网重跑双语 0/0 通过 |

定向测试复现命令：

```bash
/tmp/abi-refactor-venv/bin/pytest \
  tests/unit/test_pipeline_dag.py tests/unit/test_contract_lint.py \
  tests/unit/test_contract_lint_source_checks.py tests/unit/test_metagenomic_plasmid_policy.py \
  tests/unit/test_parsers.py tests/integration/test_dry_run_shared.py \
  tests/smoke/test_dry_run_smoke.py -q --tb=short
```

未运行全套产品测试、真实生物工具、远端 HPC、Docker 实际构建和发布。
本批未更改发行面文件；构建与三形态安装须在后续 N2 资产/依赖切片重新验收。


### 15.8 N2–N5 收口与发行目标（进行中）

用户已授权完成剩余重构、全量产品测试、推送、CI/CD 与正式发布；后续发布依旧遵循不可变版本、
已验证 master 和 Trusted Publishing 规则。通过独立克隆远端恢复比对基准，保留当前工作区；
远端当前 HEAD 为 `3615dcf94a64b1343ff96a1001880f7ccea9637c`。缺失的 Linux 冻结证据从该提交
原样恢复，不生成替代证据。GitHub 登录尚待可用，代码开发与本地验证继续。

N3 资产归属（先明确归属再调整打包）：

| 资产 | 核心 wheel | 插件 wheel | sdist / Docker 构建上下文 |
| --- | --- | --- | --- |
| 安全、执行、审计、运行时与资源配置 | 保留 | 调用核心 | 保留 |
| `environments.yaml` 工具环境映射 | 保留 `abi/data/` | 由核心解析 | 保留 |
| Conda `envs/` 与部署脚本 | 不打包 | 不打包 | 保留供外部准备 |
| `examples/`、`data/examples/`、`golden_traces/` | 不打包 | 不打包 | 保留开发与验收用途 |
| 三个质粒输出标准化 shell 脚本 | 不打包 | 质粒插件打包，维持现有安装相对路径 | 保留源文件 |
| 插件实现、DAG、契约、结果 schema、外部 figure_specs | 不打包 | 各自同址打包；图形声明没有核心加载义务 | 保留 |
| 宿主平台 integrations | 保留 | 不重复打包 | 保留 |
| numpy / pandas / scipy | 移除必需依赖 | EasyMeta 声明 numpy；RNA-seq 声明三者，供其统计脚本 | 测试环境通过 dev 依赖具备必要计算库 |

产品测试保留所有安全、契约、审计与冻结证据检查；被 git 忽略的本地论文绘图测试属于显式选择的
外部研究任务，不应让 matplotlib 回流核心。后续结果据实填写，不复用旧验收数字。


本轮实现（2026-09-17）：

- **N1**：四后端恢复身份、输入保护、失败/超时与重试证据沿用统一核心实现；恢复身份的生成目录索引改为单次构建，避免多样本规划反复扫描全部输出。保留原始输入与符号链接内容校验。
- **N2**：四个活动绘图节点及三个专属渲染器的脚本、注册项、契约、依赖已退役；比较分析 clinker 与历史图表解析兼容保留。Conda 清单和生成 YAML 已同步。
- **N3**：核心 wheel 不再包含运行环境、示例和质粒专属标准化脚本；三个脚本迁入质粒插件。科学计算依赖由实际使用的 RNA-seq / EasyMeta 插件声明；核心独装校验禁止科学计算和绘图库回流。
- **N4**：发行验证器绑定一个核心 sdist、九个 wheel 的精确集合、版本、核心依赖及 SHA-256。构建端写入不可覆盖清单，发布端验证 GitHub Release 下载的原字节。共享安装探针覆盖核心独装、RNA-seq/EasyMeta 单插件及全部八插件。
- **N5**：清理 CMake、开发指南、内置技能中的过期命令；论文绘图任务保持显式选择；产品测试保留冻结证据与全部安全检查。工作流复用安装探针，避免重复维护插件样本夹具。

发布流程先生成经过质量门禁的 GitHub Release 草稿，再由已认证维护者发布草稿，触发独立的 `release.published` Trusted Publishing 工作流。原因是使用 `GITHUB_TOKEN` 产生的事件不能触发后续工作流；不添加长期 PyPI token 或新的自动发布入口。

当前本地发行检查：

| 检查 | 本轮结果 |
| --- | --- |
| Ruff / 格式 | 通过，376 个 Python 文件格式合规 |
| mypy | 155 个源文件通过 |
| 工作流、发行清单与 Docker 配置定向回归 | 42 passed |
| 八插件 strict contract-lint | 全部通过，均 0 error / 0 warning |
| Compose 配置验证 | 通过 |
| 双语文档 `bash docs/build_docs.sh` | 通过 |
| 1.7.0 核心默认 sdist→wheel + 八插件 wheel | 全部构建成功 |
| `twine check` | 全部通过；插件保留缺少长描述的非阻断警告 |
| 发行物 SHA-256 清单生成与再校验 | 通过 |
| `check_release_identity.py` | 1.7.0 通过 |
| 干净核心 wheel 安装 MCP extra 与 `abi-mcp --help` | 通过 |
| 最终三形态干净安装 | 全部通过，含 RNA-seq / EasyMeta 独立统计与八插件 dry-run |
| Linux x86_64 wheel 能力检查 | 通过，21 环境映射、8 插件 |
| Codex / Claude Code / OpenCode wheel 安装与诊断 | 全部通过 |
| 恢复身份与百样本性能回归 | 11 passed，10.86s |
| 全量测试与覆盖率 | 2597 passed / 3 skipped / 11 deselected，420.25s；分支感知总覆盖率 82.79% |
| 关键模块覆盖率门禁 | 全部通过 |
| Migration Gate | 5/5 通过，使用本轮 coverage.json |
| 远端 CI / 正式发布 | 待 GitHub 认证及 Git 提交身份配置后执行 |

完整构建产物暂存 `/tmp/abi-release-1.7.0/`，供本地验收；正式发布必须使用远端 Release 工作流生成并通过清单验证的产物，不上传本地重构产物。真实工具、远端 HPC 终止认证和实际 Docker 镜像构建尚未执行，不以 dry-run 代替这些证据。


本轮可复现验收命令（Python 3.12，干净依赖环境；执行日志保存在本机 `/tmp/abi-*-170.log`）：

```bash
ruff check src/ tests/ scripts/verify_install_forms.py scripts/verify_release_artifacts.py scripts/build_plugin_wheels.py
ruff format --check src/ tests/
mypy src/abi/ --ignore-missing-imports
pytest tests/ --strict-markers -m "not requires_tools" --cov=src/abi --cov-branch --cov-report=term-missing --cov-report=json:coverage.json --cov-fail-under=75 -q --tb=short
python scripts/check_module_coverage.py --coverage coverage.json
python scripts/migration_gate.py
pytest tests/test_documentation_artifacts.py tests/unit/test_release_artifacts.py tests/unit/test_docker_configuration.py -q --tb=short
pytest tests/unit/test_resume_identity.py tests/performance/test_core_performance.py -q --tb=short
for plugin in metagenomic_plasmid metatranscriptomics rnaseq_expression amplicon_16s wgs_bacteria wgs_bacannot easymetagenome viral_viwrap; do abi contract-lint --type "$plugin" --strict || exit; done
docker compose -f docker/docker-compose.yml config --quiet
bash docs/build_docs.sh
python scripts/check_release_identity.py
python -m build --outdir /tmp/abi-release-1.7.0/core
python scripts/build_plugin_wheels.py --outdir /tmp/abi-release-1.7.0/plugins --build
python -m twine check /tmp/abi-release-1.7.0/core/* /tmp/abi-release-1.7.0/plugins/*.whl
python scripts/verify_install_forms.py --dist-dir /tmp/abi-release-1.7.0/core --plugin-dist-dir /tmp/abi-release-1.7.0/plugins
# 将上述十个分发文件汇集至独立 release 目录后，只写一次清单，再验证原文件。
python scripts/verify_release_artifacts.py --dist-dir /tmp/abi-release-1.7.0/release --tag v1.7.0 --write-manifest
python scripts/verify_release_artifacts.py --dist-dir /tmp/abi-release-1.7.0/release --tag v1.7.0
```


本地验收已完成；`11 deselected` 为 CI 规则排除的 `requires_tools` 测试，不代表真实工具认证通过。全量命令退出码为 0。尚未创建提交、推送或打标签：本机 `gh auth status` 未登录，Git `user.name` / `user.email` 未配置。认证完成后的顺序为：复核差异并提交 → 推送并验证完整 CI 矩阵与 Migration Gate → 从已验证 master 再核验版本未被占用 → 创建不可变 v1.7.0 标签 → 校验 Release 草稿产物 → 发布草稿并验证 Trusted Publishing、PyPI 哈希及干净安装。不得将当前本地通过状态记为远端通过或已发布。


发行推进更新：GitHub 身份与 Git 提交身份现已配置，开始在 `refactor/abi-1.7.0-release` 分支提交本轮已验证修改；远端 CI 结果与发布状态以随后实际运行记录为准。前述认证阻塞记录保留为历史，不再是当前阻塞。


### 15.9 PR 审查与远端验收（2026-09-19）

PR #16 的首轮 CI（run `35197237306`，提交 `eeeb168`）已通过 Python 3.10–3.13、原生 Linux arm64 与 Migration Gate；PR 的 Pages 跳过符合预期。审查发现干净插件安装后的脚本路径问题：RNA-seq 三个脚本依赖源码相对路径，质粒 DESeq2 契约依赖已不存在的顶层插件目录。本轮改为使用各插件根目录解析脚本输入；新增非源码目录规划回归，并将脚本存在性检查加入全插件干净安装验收。CMake 实际执行目标补齐 `--confirm-execution`。

发布说明同步明确草稿发布环节与八个新 PyPI 插件项目的 Pending Trusted Publisher 配置要求。当前尚未合并、打标签或正式发布；审查修复须通过新一轮 CI 后方可继续。


### 15.10 插件独立仓库与 GitHub-only 分发（2026-09-19）

用户明确要求：保留 PyPI 核心包名 `abi-agent` 与命令名 `abi`；插件新建 `abi-plugin`
仓库，不上传 PyPI，只通过 GitHub 按需下载。此决定取代 15.8–15.9 的九包 PyPI 集合及
插件 Pending Trusted Publisher 要求；没有在 PyPI 新增插件权限。

实现边界：

- 插件源码及打包脚本迁到公开仓库 `https://github.com/sleepinlava/abi-plugin`；主仓库在
  `src/abi/plugins` 固定子模块提交，源码开发、容器和完整 CI 通过递归 checkout 获取。
- 主仓库只保留插件构建转发入口与共享核心 API。核心 wheel 仅提供插件命名空间兼容接口；
  核心 sdist 排除插件源码，主仓库无第二份插件实现。
- 移除会从 PyPI 查找插件的 `plugins` extra；双语安装说明使用具体 GitHub Release wheel URL。
  每个 wheel 保留独立入口点、同址数据和精确的核心版本依赖。
- 核心 Release 清单只允许一个核心 wheel 加一个 sdist，额外插件 wheel 会被拒绝。
  CI 仍构建全部插件并验证核心独装、单插件、全插件安装，但不会把插件加入 PyPI 上传目录。
- 插件仓库独立 CI 覆盖 Python 3.10–3.13，GitHub Release 只包含八个 wheel 与 SHA256SUMS.json；
  无 PyPI workflow、token 或 Trusted Publisher。版本标签和发布产物保持不可变。

当前证据：插件独立 CI `35428643515` 已通过；主仓库 50 项定向打包、发行及 Docker 回归通过；
默认核心 sdist→wheel 构建通过，直接检查证实 wheel 仅有 `abi/plugins/__init__.py`，sdist
不含插件源码；核心与插件各自的精确集合及哈希验证均通过。完整产品测试、干净组合安装和新一轮
主仓库 CI 继续执行，完成前不标记分发迁移或正式发布完成。

2026-09-20 更新：分仓 PR #17（`738fa54`）的 Python 3.10–3.13、原生 arm64 与
Migration Gate 全部通过（run `35430962120`）；本地完整套件 2594 passed、8 skipped、
11 deselected，分支覆盖率 82.26%，干净组合安装、双语文档及迁移检查通过。
发布前进一步发现三个输出标准化脚本为空，补齐实现及固定样例行为测试，并修正
HiFiAdapterFilt 的 prefix 调用方式，使用私有副本保护原始输入。实现归属插件仓库，
主仓库仅保留兼容转发脚本；打包检查拒绝空脚本。此修复必须重新通过两个仓库的 CI，
上述旧提交的通过结果不能替代新提交验收。尚未发布 1.7.0。
