# BIB 目标文章与 ABI 投稿定位研究笔记

> 调研日期：2026-07-23  
> 资料边界：只采用 Oxford University Press（OUP）与 *Briefings in Bioinformatics*（BIB）官方页面。目标范文为 Bonidia et al., “MathFeature: feature extraction package for DNA, RNA and protein sequences based on mathematical descriptors” ([HTML](https://academic.oup.com/bib/article/23/1/bbab434/6423525), [DOI](https://doi.org/10.1093/bib/bbab434))。

## 一句话结论

ABI 可以借鉴 MathFeature 的“明确缺口—系统能力分类—真实数据案例—可获得性”写法，但按 BIB 当前栏目，最适合申报 **Problem solving protocol**，而不是把自己写成普通软件介绍或复现论文。正文应控制在 **2,000–5,000 words**，围绕一个清楚的生物信息学瓶颈，比较替代方案，并用真实实验数据同时证明 agent operability 与 biological validity。[BIB Author Guidelines](https://academic.oup.com/bib/pages/author-guidelines)

## 1. 目标文章是什么

- OUP 页面将 MathFeature 标为 **Journal Article**；发表于 BIB 23(1)，2021-11-08 online，DOI `10.1093/bib/bbab434`。[目标文章](https://academic.oup.com/bib/article/23/1/bbab434/6423525)
- 页面没有给出更细的栏目标签，因此不能据官方页面断言它当时就是 “Problem solving protocol”。本文与 BIB 当前该类型高度相似，但这是**基于当前栏目定义的适配判断**，不是对其历史稿件类型的事实判断。
- 它是一篇 package/method paper：核心不是提出全新预测任务，而是把文献中分散、未被现有工具充分实现的数学序列描述符整合进开源包，并用真实 benchmark case studies 证明这些描述符有用。

## 2. MathFeature 的章节与叙事结构

### 2.1 显式章节

1. Abstract
2. Background
3. Related works
4. Package description
5. Results
   - Experimental scenario
   - Case study I–IX
6. Discussion（跨案例总结）
7. Conclusion
8. Key Points
9. Acknowledgments
10. Availability of data and materials
11. Financial support
12. Availability and implementation
13. Author biographies
14. References

以上结构可直接从[文章全文](https://academic.oup.com/bib/article/23/1/bbab434/6423525)核对。值得注意的是，它没有独立的 Methods/Implementation 章节；实现细节主要在 “Package description”，实验设置与结果主要混写在每个 case study 中。

### 2.2 叙事链

文章的论证顺序很稳定：

> 生物序列机器学习需要数值表示 → 现有包覆盖了大量常规描述符，但缺少已被证明有价值的数学描述符 → MathFeature 将这些能力汇入一个可用的软件包 → 用 taxonomy 和横向表格证明覆盖缺口 → 用九个真实案例证明能力跨 DNA/RNA/protein 与多种任务可用 → 公布代码、文档与数据。

摘要也遵循同一顺序：问题、现有工具缺口、软件及其能力、九个案例、数值结果、意义。其最值得 ABI 学习的不是章节名，而是**每一类主张都有对应证据**：覆盖主张由 capability tables 支持，工作流主张由流程图支持，实用性主张由真实数据案例支持。[目标文章摘要与正文](https://academic.oup.com/bib/article/23/1/bbab434/6423525)

### 2.3 Related works 的作用

Related works 不是泛泛罗列：作者先调查 17 个相关软件、归纳 173 个描述符为 15 组，再用表格定位 MathFeature 的覆盖差异。它服务的是“为什么需要这个包”而非背景百科。[目标文章 Related works](https://academic.oup.com/bib/article/23/1/bbab434/6423525)

对 ABI 的对应启发是：相关工作应按它们解决的控制问题来比较，例如自由 shell/文档、generic tool calling、workflow engines、scientific agents，而不是只列 agent 名称；比较轴应是 executable contract、permission gate、deterministic plan、diagnostics/resume、provenance、biological evidence boundary。

## 3. 图、表与实验组织

### 3.1 图表配置

目标文章主文有 **2 幅图、6 张表**：

| 项目 | 功能 |
|---|---|
| Figure 1 | 数学描述符 pipeline，解释五类核心能力 |
| Figure 2 | 四步使用/执行 workflow |
| Table 1 | 相关软件中的描述符类别与覆盖 |
| Table 2 | MathFeature 与其他包的能力数量比较 |
| Tables 3–5 | 数学描述符、常规描述符及其生成特征的完整能力目录 |
| Table 6 | 九个案例的总览：问题、参考、序列类型、样本量、分类器 |

此外，补充材料承担了应用分类、Venn 图和 GUI 等细节。[目标文章图表与补充材料入口](https://academic.oup.com/bib/article/23/1/bbab434/6423525)

这种安排体现了清楚的分工：图解释“系统怎样工作”，表回答“系统具体覆盖什么、相对现有工具多了什么、在哪些任务上测过”。

### 3.2 九个案例的统一微结构

每个 case study 基本都按以下模板写：

1. 生物学预测问题与 benchmark 数据集；
2. 训练/测试规模或交叉验证方式；
3. 使用的 MathFeature 描述符与分类器；
4. 评价指标；
5. 数值结果；
6. 与原研究或已有工具报告值比较。

Table 6 先集中呈现九个案例的范围，从而避免读者在长结果段落中迷失。案例覆盖 DNA、RNA 与 protein，并使用 CatBoost、SVM、Random Forest 和 deep learning；指标随原 benchmark 改变，包括 ACC/BACC、F1、AUC、MCC 和 kappa。[目标文章 Results](https://academic.oup.com/bib/article/23/1/bbab434/6423525)

### 3.3 实验设计的可借鉴处与局限

可借鉴：

- 使用真实 benchmark 数据，而不是仅演示 toy input；
- 先给全局实验矩阵，再逐案例报告；
- 在案例内明确数据、方法、指标和比较对象；
- 代码、文档、数据与实验仓库公开。[目标文章 Availability](https://academic.oup.com/bib/article/23/1/bbab434/6423525)

不能照搬：

- 九个案例采用不同分类器、划分和指标，适合证明广泛可用性，却不适合汇总成一个统一因果效应；ABI 的 G1–G4 必须固定模型、任务、预算、重试、超时和评分协议，并做配对比较。
- 目标文章有时把实现覆盖数量直接当成优势；ABI 不能用 plugin/command 数量替代方法贡献，必须证明 contract compilation、permissions、diagnostics 或 provenance 改变了结果。
- 它多处引用既有论文的报告值作比较。ABI 的核心 baseline 应在同一 harness 中重跑；否则只能称 historical/reference comparison，不能称公平 head-to-head comparison。
- 它的 Methods 与 Results 边界较弱。ABI 涉及 agent、权限、安全和生物学有效性，必须拆开写，防止实验协议被结果反向塑造。
- 文章结论“所有 descriptors 都能改善模型”等广泛表述超出了九个选择性案例能稳健支持的范围；ABI 应限定到预注册任务、模型族、工作流与终点。

## 4. BIB 当前投稿规则及其对 ABI 的含义

以下以 2026-07-23 可见的[BIB Author Guidelines](https://academic.oup.com/bib/pages/author-guidelines)为准；2021 年范文是写作先例，不是当前合规清单。

### 4.1 稿件类型

BIB 当前接受的相关类型包括：

- **Problem solving protocols（2,000–5,000 words）**：基于比较、新软件或既有软件新 pipeline 的方法，用于解决一个具体 bioinformatics problem；必须分析真实实验数据，且应展示对有意义生物学问题的新方法应用；也接受原创算法。
- **Case studies（2,000–5,000 words）**：方法、pipeline 或软件对某一具体 bioinformatics problem 的新应用，期待真实实验数据分析具有显著新颖性。
- Reviews 为 2,000–7,000 words；其他短类型不适合 ABI 系统论文。

ABI 是新的 software/control layer，并且希望通过多个 workflow 解决“AI agent 安全、可靠地操作异构生物信息学流程”的方法学问题，因此首选 **Problem solving protocol**。如果最终创新主要剩下“把既有 ABI 用到某一个生物问题”，才应转为 Case study。

### 4.2 BIB 明确偏好的内容

期刊要求主题对实验生物学家和 bioinformatics 专家都界定清楚，解释底层概念、正确工具的选择、局限和结果解释。官方特别列出 software comparison/benchmarking、预测或提取信息的准确性、HPC/cloud、standards，以及 replicability/reproducibility；还要求提供足够信息使应用可重新实现，并在适当时提供测试数据及结果。[BIB Author Guidelines](https://academic.oup.com/bib/pages/author-guidelines)

这与 ABI 的契合点很强，但题目和引言不能写成泛化的“LLM agent framework”。必须把瓶颈定义为一个生物信息学方法问题，例如：

> How can an AI agent execute heterogeneous, long-running and data-sensitive bioinformatics workflows without inventing shell procedures, bypassing permissions, or confusing execution success with biological validity?

### 4.3 形式要求

- 初投可 **format-free submission**，但论文必须用清楚、专业的英文写作；期刊不应被当作营销特定产品或服务的渠道。
- title page 包括题名、作者、单位及通讯作者联系信息。
- 提供短 abstract；最多 6 个 keywords。BIB 页面明确要求 review/software review 配 abstract，但 ABI 作为研究型 protocol 仍应遵循近期同类文章惯例提供结果型摘要。
- **Key Points 为 3–5 个简短句子**，在文末显示。
- 参考文献最终采用 **Oxford SCIMED** style；初投可免期刊格式。
- graphical abstract 为单幅横向图，作为单独文件提交并命名为 `graphical_abstract`；文字须在社交媒体缩放场景仍可读，并考虑无障碍。
- 必须有 data availability statement；官方强烈鼓励公开支撑结论的数据与代码，并在 reference list 中完整引用在线数据/软件。
- Funding 需在 acknowledgements 后以独立小节完整声明机构和 grant number。
- BIB 自 2024 年第 25 卷起为 fully open access；接受后适用 APC，可能有机构 Read and Publish 或 waiver/discount。[BIB Open Access](https://academic.oup.com/bib/pages/open-access)

### 4.4 AI/LLM 使用规则：当前项目的高风险事项

BIB 当前规则明确写道：

- LLM/相关技术不能列为作者；
- 可接受的 AI 使用要在 cover letter，并在 Methods 或 Acknowledgements 中披露；
- 若 LLM 帮助产生论文的文字、图或其他内容，还需在 supplementary materials 中以足够细节记录；
- **不可接受直接从 prompt 用 LLM 起草论文，包括 text、figures、tables 和 references；论文必须由研究者撰写**；若使用场景不明确，应联系编辑或 editorial office。[BIB AI policy（Author Guidelines）](https://academic.oup.com/bib/pages/author-guidelines)

因此，本项目应立即把 Codex 的角色限定为：文献检索辅助、证据审计、结构建议、语言问题标注、代码/分析辅助和人类作者稿件的编辑反馈；不要把 AI 生成段落直接作为投稿正文。需要保留 AI usage log，由研究者逐项验证并自行撰写最终文本，并在投稿前依据实际使用情况准备 cover letter、Methods/Acknowledgements 和补充披露。由于官方禁令表述严格，建议在正式写作前向 BIB editorial office 书面确认允许边界。

## 5. ABI 应怎样“写成这样”

### 5.1 建议主文结构（Problem solving protocol，目标 4,000–5,000 words）

1. **Abstract**：具体瓶颈 → ABI 机制 → 受控 benchmark → 真实生物数据结果 → 有限结论。
2. **Background**：从 RNA-seq/WGS 等真实操作场景切入；解释为何自由 shell、静态文档、generic tools 和 workflow engine 仍留下 agent control gap。
3. **Related work and problem formulation**：像 MathFeature 一样建立分类比较表，但比较机制而非产品数量；明确 trust boundary、威胁模型、成功定义和非目标。
4. **ABI protocol and implementation**：plugin contract、contract compilation、query/plan/check/authorize/run/inspect/report 生命周期、backend adapter、diagnostics/resume、provenance/evidence boundary。
5. **Evaluation design**：先用一张总览表声明 RQ、数据、G1–G4、模型、重复、主要指标、统计方法和排除规则。
6. **Results I — Agent operability**：任务成功、安全执行、silent failure、诊断/恢复、token/time、人为干预；给配对效应与置信区间，并做核心组件消融。
7. **Results II — Biological validity on real data**：Airway、ST93 MRSA、SCAPP；每个案例使用“数据和预注册终点 → ABI 执行 → 数值结果 → 与参考证据比较 → 明确未复现部分”的统一微结构。
8. **Discussion**：适用边界、plugin 维护成本、底层工具错误、模型泛化、隐私部署条件、SCAPP truth gate、WGS core-SNP 缺口。
9. **Conclusion**：只总结由实验支持的范围。
10. **Key Points / Availability / Funding / Conflict / AI disclosure**。

### 5.2 推荐图表包

为兼顾 BIB 5,000-word 上限和 MathFeature 的“图讲过程、表讲覆盖”风格，建议主文保持精简：

| 编号 | 内容 | 回答的问题 |
|---|---|---|
| Figure 1 | motivating example + ABI contract-compiled lifecycle | ABI 解决什么问题、如何工作？ |
| Figure 2 | 受控实验 G1–G4 与两层证据轨道 | 如何验证 agent operability 与 biological validity？ |
| Figure 3 | agent benchmark 主结果、置信区间和失败类型 | ABI 是否更可靠/安全，代价是什么？ |
| Figure 4 | Airway + ST93 关键生物学终点；SCAPP 可视证据或放补充 | 执行是否保留生物学有效性？ |
| Table 1 | 与 shell/docs、generic tools、workflow engines、scientific agents 的机制比较 | 新颖性在哪里？ |
| Table 2 | ABI contract 与 lifecycle 定义 | 方法可重实现吗？ |
| Table 3 | evaluation matrix（任务、数据、模型、baseline、endpoint） | 实验覆盖是什么？ |
| Table 4 | 全部数值结果与 evidence status | 哪些结论已验证、哪些仍 gated？ |

详细 plugin catalog、CLI/API、逐任务 prompts、模型配置、额外失败轨迹、SCAPP truth reconstruction 和完整 provenance 放 Supplementary Materials/公开仓库。

### 5.3 必须保持的双轨证据边界

MathFeature 的案例都围绕预测表现，可以在同一个结果空间中叙述；ABI 不同。必须明确分开：

- **Agent operability**：任务完成、unsafe action、silent failure、diagnostic recovery、token/time/human intervention；
- **Biological validity**：Airway effect concordance、ST93/mecA、SCAPP structural/mobility evidence 等预注册终点。

“workflow completed”不能推出“biological conclusion reproduced”；“生物学终点一致”也不能证明 ABI 比 baseline 更安全。摘要、图题、结果和结论均应保持这一边界。

## 6. 采用与不采用清单

### 应采用

- 用具体缺口启动，而不是先介绍产品；
- Related work 形成分类框架和对照表；
- 系统能力用 taxonomy + workflow figure 解释；
- 先给全局实验矩阵，再用统一模板展开真实数据案例；
- 公开代码、文档、测试数据、结果与补充材料；
- 文末 Key Points 用 3–5 句总结可验证信息。

### 不应照搬

- 不以“功能/插件数量更多”作为主要创新；
- 不把多个异质案例的最好结果拼成单一性能区间；
- 不用文献中的历史数字冒充同条件 baseline；
- 不混写方法协议与结果；
- 不把 biological case studies 称为完整复现，除非预注册主要终点均满足；
- 不依据 2021 范文忽略 2026 当前的稿件类型、OA、data availability 与 AI disclosure 规则；
- 不直接把 AI 生成的提纲或段落变成投稿正文。

## 7. 投稿前 Go/No-Go 检查

只有下列条件同时满足，才建议按 BIB Problem solving protocol 推进完整英文稿：

1. 一个明确且有生物学意义的 problem statement，而不是泛化 agent 平台宣传；
2. ABI-Bench 的 G1–G4 在同一受控 harness 中完成，并预先冻结主要 endpoint；
3. 至少一个真实数据案例有完整、可审计、可引用的 biological endpoint；
4. 所有摘要数字均能追溯到公开或可审计 artifact；
5. 代码、数据、模型/运行配置、版本、随机种子、任务 prompt 和 scoring protocol 足以重实现；
6. 研究者完成最终文本写作并准备符合 BIB 当前规则的 AI 使用披露；
7. 4,000–5,000-word 主文仍能讲清方法、比较、限制与结果；其余移到补充材料。

## 官方来源

1. Bonidia RP, Domingues DS, Sanches DS, de Carvalho ACPLF. [MathFeature: feature extraction package for DNA, RNA and protein sequences based on mathematical descriptors](https://academic.oup.com/bib/article/23/1/bbab434/6423525). *Briefings in Bioinformatics*. 2022;23(1):bbab434.
2. BIB. [Author Guidelines](https://academic.oup.com/bib/pages/author-guidelines)（稿件类型、scope、格式、Key Points、数据/代码、AI 使用政策、费用与投稿要求）。
3. BIB. [Open Access](https://academic.oup.com/bib/pages/open-access)（自 2024 年起 fully OA、APC、waiver/discount 与 Read and Publish）。
