# ABI 实验设计与论文主张对齐评估

更新时间：2026-07-26

## 结论

拟议实验**不会自动把 ABI 的创新点改成“给小模型加入改良版 skills”**。ABI 的既定创新仍然是：
把插件中的工作流契约编译为可检查、需授权、可执行、可诊断和可审计的生命周期，而不是向
模型补充一份操作说明。仓库的正式定位明确把 ABI 定义为 systems/technique contribution，
其证据链包括运行时检查、输出断言、标准表、provenance、报告和限制声明
（`docs/en/paper_outline.md:9-15`）；README 也把 typed tools、执行确认和完整溯源列为核心能力
（`README.md:19-25`）。草稿进一步明确区分了 skills 的咨询性指导与 ABI 在步骤前后强制执行
契约、结构化诊断和失败运行溯源的机制（`abi paper writing/BAI Paper.md:28-38`）。

真正的问题是**构念与实验不对齐**：如果论文只展示“Kimi K3 + ABI 得到了与论文相关的
Airway/WGS 结果”，以及“强模型用 ABI 比自由 Shell 更容易复现质粒结果”，读者实际看到的
主要证据会是预封装工作流给 Agent 提供了知识和操作捷径。因为安全门控、错误阻断、诊断恢复
和审计完整性没有被直接测量，ABI 即使在架构上不是 skill，也会在实证上看起来像一个
workflow skill。需要调整的是实验识别策略，而不是核心创新点。

## 当前方案中的主要混杂

1. **模型、接口和工作流相互混杂。** 如果 Kimi 只在 Airway/WGS 使用 ABI，而 Gemma/Qwen
   只在质粒任务比较 ABI 与 Shell，就无法判断差异来自模型、接口还是工作流难度。正式协议
   要求在每个模型配置内保持 prompt、fixture、工具实现和 serving policy 一致
   （`docs/en/paper_evaluation.md:23-36`）。
2. **真实数据一致性不能替代接口效应。** 仓库已明确把 Agent operability 与 biological
   validity 分成两条证据轨道；成功 case study 本身不能证明 ABI 相对 baseline 帮助了 Agent
   （`docs/en/paper_evaluation.md:5-10`）。因此 Airway/WGS 相关性可支持“输出保持/端点恢复”，
   不能单独支持“更安全、更可靠”。
3. **Shell 对照可能同时改变分析方法和信息量。** 若 Shell 组让模型临时设计 pipeline，而
   ABI 组获得已编码的 biological choices、DAG、数据库、参数和输出断言，差值混合了专家知识、
   方法选择和控制层效应。现有协议因此设置 G4 信息量匹配静态文档，并以配对
   `G3−G1/G2/G4` 隔离生命周期控制（`docs/en/paper_evaluation.md:38-50`）。
4. **只看最终输出会漏掉核心机制。** 论文主张包括确定性可审查计划、显式授权、可恢复的软件/
   数据库身份，以及执行成功与生物学有效性的分离（`docs/en/paper_outline.md:54-69`）。
   相关性或最终表格一致性没有测量未经授权执行、坏输入、缺资源、旧输出污染、错误诊断和
   provenance 缺失。
5. **“小模型增益”并未被当前矩阵识别。** 两个候选本地模型在草稿中都被列为“强能力本地
   开源模型”（`abi paper writing/BAI Paper.md:99-109`）。若要主张 ABI 特别帮助小模型，
   必须在同一模型家族内加入匹配量化/精度的小、中配置并检验
   `interface × model_size` 交互；正式大纲已经要求这种设计
   （`docs/en/paper_outline.md:99-105`）。否则不应写“小模型增强”，只应限定到实测 checkpoint。
6. **当前生物学端点有明确边界。** Airway 可稳健支持 log2FC 排名、方向和 sentinel genes，
   但不能把 per-gene p-value/FDR 或显著基因数逐项一致作为当前复现结论
   （`docs/zh/current_conclusions_next_steps.md:42-51`）。WGS 的论文 core-SNP 端点由外部
   SPANDx paper-method 轨恢复，不能归因于 ABI `wgs_bacteria` 插件
   （`docs/zh/current_conclusions_next_steps.md:55-67`）。SCAPP/plasmid 的 headline
   precision、recall、F1 在独立 truth 完成前仍不可报告
   （`docs/zh/current_conclusions_next_steps.md:69-79`）。

## 推荐的主张对齐设计

### 轨道 A：契约控制层的因果评测

对每个纳入论文定量结论的模型，都在**相同任务、数据、运行时、prompt、token/时间预算和重试
规则**下运行配对条件：

| 条件 | 接口 | 识别目标 |
| --- | --- | --- |
| G1 | README + Shell | 实际文档与自由 Shell 基线 |
| G3 | ABI 生命周期 | 完整契约控制层 |
| G4 | 信息量匹配静态文档 + Shell | 排除 ABI 仅提供更多工作流知识 |
| G2（资源允许时） | 通用工具调用 | 排除“任何 tool calling 都足够” |

Gemma 与 Qwen 至少都应在同一个 Airway、WGS 或可控的 plasmid 任务集合上完成 G1/G3/G4；
不能把某一接口固定给某一模型或某一工作流。Kimi 若只能运行 ABI，可作为用户故事或外部
case study，不能进入 ABI-vs-Shell 的因果估计；若要进入主比较，也必须增加同模型 Shell/G4
配对。若 Kimi 不是冻结的本地自托管配置，还应与论文的隐私型本地模型主张分开报告，因为
当前正式协议把结论限定在实测的本地 checkpoint、量化、推理引擎和硬件
（`docs/en/paper_evaluation.md:12-18`）。

轨道 A 的主要指标应直接对应创新点：

- 非法或未授权执行率；
- 损坏输入、参考不匹配和缺失资源在耗费计算前的阻断率；
- 过期/污染输出的拒绝率；
- 结构化根因诊断正确率与恢复成功率；
- 输出契约断言通过率及假成功率；
- provenance、工具/数据库身份、命令和限制声明的完整率；
- 任务完成率；时间、token、重试和人工干预作为次要效率指标。

正式论文若要跨模型外推，仍应遵循至少三个独立模型家族、重复运行、以模型家族而不是任务数
或单次运行为外推单位的协议（`docs/en/paper_evaluation.md:23-36`）。若资源只允许 Gemma 和
Qwen，则可以先做两模型研究，但结论必须写成“在两个冻结配置上观察到”，不能写成本地模型的
普遍规律。

### 轨道 B：真实数据的生物学有效性

Airway、ST93 MRSA WGS 和 plasmid case study 继续保留，但其目标是证明 ABI **没有破坏既定
分析，并能发布可审计的端点证据**，不是估计 ABI 相对 Shell 的安全因果效应。仓库正式大纲
已经采用这一分工：Airway/WGS 是配对 running example，SCAPP 是旗舰 case study
（`docs/en/paper_outline.md:17-24`）。

评分必须读取冻结的机器产物，而不是只比较 Agent 最终文本：

- Airway：预注册的排名相关、效应方向、sentinel genes，并明确跨方法限制；
- WGS：ABI 插件自身的 MLST、`mecA` 和 AMR 端点；SPANDx core-SNP 作为独立
  paper-method 对照轨；
- plasmid：执行、描述性证据和通过门禁的 paper-method precision/recall/F1 可以报告；
  但必须标记为 not paper-exact，且 precision 是严格参考一致性而非生物学假阳性率；
- 所有任务记录输出 checksum、工具/数据库版本、参数、退出状态和证据状态。

## 论文叙事建议

核心句应保持为：

> ABI 是一个面向隐私型 Agent 生物信息分析的插件化、契约编译控制层；它把工作流开发者声明
> 的生物学选择和执行契约转化为可检查、需授权、可诊断、可溯源且有明确证据边界的运行。

然后把证据分成两句：

1. 配对接口实验检验 ABI 是否比 Shell、通用工具和信息量匹配文档更安全可靠地完成操作；
2. 真实数据 case study 检验通过该控制层执行时是否恢复预注册生物学端点。

不要把论文改写成“ABI 提升小模型知识或推理能力”。更准确的说法是：ABI **缩小了 Agent
必须自由推理和临时拼装 Shell 的操作空间**；若较小模型获益更大，那是控制层效果的一个
次级调节结果，而不是 ABI 的定义性创新。当前最稳妥的仓库结论也正是“已建立可审计的契约
执行与证据发布框架；Agent benchmark 定量主张仍待 clean run”
（`docs/zh/current_conclusions_next_steps.md:148-159`）。
