# ABI 论文当前结论与下一步工作说明

更新时间：2026-07-24

本文档记录当前已经完成的论文定位、证据整理、benchmark 处理原则、真实数据例子和后续执行门禁。它用于团队内部继续推进写作与计算；凡是尚未完成验证的内容，在本文档中均不写成已经成立的论文结论。

## 1. 当前论文主张

当前主张应表述为：

> ABI 是面向隐私型智能体生物信息分析的插件化、契约编译控制层。

它不是一个单一插件，也不是“由 YAML 格式加 DAG 规划自动完成生物学学习”的系统。更准确的边界是：

- 插件保存研究特异的生物学选择，包括样本模型、配置 schema、DAG、工具、资源、输出断言、标准表、报告元数据和限制声明。
- ABI 核心把这些插件契约编译成可检查、可授权、可溯源的执行计划。
- YAML 和 `pipeline_dag.yaml` 是重要事实源，但只有与插件代码、运行时适配器、工具/数据库身份、输出校验、标准表、provenance 和报告限制结合后，才构成完整证据链。
- 论文需要区分两条证据轨道：Agent 可操作性和生物学有效性。前者回答 ABI 是否帮助本地模型更可靠地完成工作流操作；后者回答真实数据运行是否恢复预注册生物学端点。

这一定义已经写入 `docs/zh/paper_outline.md` 与 `docs/en/paper_outline.md`，Introduction 已按六段式结构重写。

## 2. Benchmark 当前结论

benchmark 的主要设计方向是合理的：使用可本地化部署的模型进行评测，更贴近真实生物学和临床隐私需求。论文应明确把结论限制在实际测量过的 checkpoint、量化、推理引擎、硬件、上下文长度、temperature、timeout 和 retry policy 上，不能外推到所有本地模型。

当前处理原则已经确定：

- 所有既有 ABI-Bench 结果都不进入本轮论文分析。
- 根目录 `metrics.tsv` 中 Agent 可操作性相关行保持 `pending_new_run`，estimate 留空。
- 新 benchmark 必须从干净 commit、冻结 suite、冻结 model registry 和冻结 runtime attestation 开始。
- 主要比较为 G3 ABI 生命周期相对于 G1 README+shell、G2 通用工具调用、G4 信息量匹配静态文档的配对差异。
- 统计外推单位应是模型家族，而不是单次运行或任务数。

已写入的评测协议见 `docs/zh/paper_evaluation.md` 与 `docs/en/paper_evaluation.md`。

## 3. 已经可以使用的真实数据证据

真实数据证据与被抛弃的历史 benchmark 结果无关，当前可以作为论文材料继续使用。

### Airway RNA-seq running example

Airway 使用 GSE52778，比较 Dex 与 untreated，并保留 donor-aware 设计。当前可报告端点包括：

- 正式执行完成：26/26 steps。
- 与冻结 GEO 表可映射基因：13,725。
- Dex log2FC 排名一致性：Spearman rho = 0.927。
- 效应方向一致率：90.8%。
- 预注册 sentinel genes：7/7 同向。
- 显著集重叠：302 genes，Jaccard = 0.0627。

限制与修复路径：当前 Airway 证据不应把“GRCh37.75 与 hg19”写成主要生物学差异；二者属于同一人类参考版本家族，关键差异来自 STAR/featureCounts/DESeq2 与原始 GEO Cuffdiff 表之间的比对、计数、转录本到基因聚合、离散度估计和多重检验流程。因此，当前可稳健支持的是 log2FC 排名、效应方向和 sentinel gene 一致性；不能要求 per-gene p-value、FDR 或显著基因数逐项一致。显著集 Jaccard 仍作为方法敏感指标报告，但不作为唯一有效性端点。若要进一步消除此限制，下一步应增加 Airway original-method parity 或 sensitivity run：冻结相同样本、相同 Dex-versus-untreated 方向和相同 gene-ID 映射，尽量复现 TopHat/Cuffdiff 或使用明确声明的兼容替代流程，并把 ABI-DESeq2 与 parity 结果分开报告。

### ST93 MRSA WGS running example

WGS 使用 PRJNA286158 的六株 ST93 MRSA paired-end isolate。当前 ABI WGS 插件层面可报告端点包括：

- 正式执行完成：30/30 steps。
- MLST：6/6 为 ST93。
- `mecA`：6/6 检出，且每条 call 为 100% amino-acid coverage 和 identity。
- AMR 标准表：145 行工具证据。

文献 core-SNP 端点已由严格双轨对比恢复（见第 5 节）：

- `paper_spandx` 轨（原版 SPANDx v2.6、完整 82 株论文上下文矩阵）：六株 pairwise SNP 距离 min=7、median=47、max=60，落在文献 7-60（mean 44）区间内，`paper_exact_candidate`。
- `abi_bcftools` 轨（BWA mem + bcftools haploid joint calling）：10-73（median 55），标记 `abi_reproduction_not_paper_method`，仅作并列对照。

限制：145 行是工具 call 行数，不等于 145 个不同耐药基因。core-SNP 恢复归功于外部原文工具链轨，ABI `wgs_bacteria` 插件自身仍无 core-SNP 模块；`abi_bcftools` 轨数值不得写成原文复现。

### SCAPP flagship case study

SCAPP 已放到旗舰 case study 位置。当前可报告的是执行和描述性生物学证据：

- SRR11038083 运行完成：10/10 steps。
- primary calls：167。
- consensus plasmids：157。
- terminal-repeat evidence：54/157。
- mobilizable calls：20/157。

限制：headline precision、recall 和 F1 仍然受独立 truth 门禁约束，不能使用早期 provisional 结果。独立 K127 two-stage truth reconstruction 完成前，`metrics.tsv` 中相关行保持 `pending_independent_truth`。

## 4. 已生成资产

当前已经生成并纳入 docs 的主要资产：

- 主张级指标注册表：`metrics.tsv`。
- Airway/WGS running example：`docs/zh/airway_wgs_running_example.md` 与 `docs/en/airway_wgs_running_example.md`。
- 论文大纲与六段式 Introduction：`docs/zh/paper_outline.md` 与 `docs/en/paper_outline.md`。
- 评测协议：`docs/zh/paper_evaluation.md` 与 `docs/en/paper_evaluation.md`。
- 机器可读证据表：`docs/paper_examples/*.tsv`。
- FigureSpec：`docs/paper_examples/*figure.yaml`。
- 真实数据图：`docs/_static/paper_examples/airway_biological_validation.*`、`wgs_biological_validation.*`、`scapp_biological_evidence.*`。
- 图形生成脚本：`scripts/create_real_data_case_study_figures.py`。
- WGS SNP 验证脚本：`scripts/cloud/validate_wgs_st93_snps.sh`。

这些材料已经把 Airway、WGS 和 SCAPP 整理为机器可读表、图、方法和限制说明。

## 5. WGS SNP 严格复现与 ABI 对比状态

完整 strict SNP comparison 已于 2026-07-25 02:02（UTC+8）在云端完成，immutable 输出目录为 `wgs_st93_strict_snp_20260724_attempt3`，169 个 shim 作业全程零失败。文献端点已恢复，`metrics.tsv` 与 `docs/paper_examples/` 已写入实测值并通过全部门禁（第 6 节步骤 10-11 已完成）。

最终结果：

- `paper_spandx` 轨：JKD6159 `CP002114.2` 参考，SPANDx v2.6 default 加 `-m yes`，输入为六株 PRJNA286158 研究样本 + 20 株 PRJEB3144 NT context（按论文 Table S1 白名单过滤）+ 55 株 PRJNA232112 既有 ST93 背景，ENA reads 全部经 MD5 校验；Ortho SNP matrix 含 82 样本。六株 pairwise SNP 距离 min=7、median=47、max=60，恢复文献 7-60（mean 44），标记 `paper_exact_candidate`。移动遗传元件未排除，与原文一致。
- `abi_bcftools` 轨：六株 PRJNA286158 cleaned read pairs，BWA mem + samtools + bcftools haploid joint biallelic SNP calling（depth >= 10、QUAL >= 30），221 个高质量变异位点，callable fraction >= 98.77%。pairwise 10-73（median 55），标记 `abi_reproduction_not_paper_method`，与 paper 轨并列对照，不得写成原文复现。
- 已发布到仓库的机器可读资产：`docs/paper_examples/wgs_snp_pairwise_distances.tsv`（双轨 30 对距离）、`docs/paper_examples/wgs_snp_track_comparison.tsv`（轨道级对比）；WGS 图已扩展为端点恢复网格 + 双轨 SNP heatmap。云端完整资产（summary、provenance、SHA256SUMS）保留在 `wgs_st93_strict_snp_20260724_attempt3` 输出目录。

此前已修正并仍然有效的运行风险记录：

- 云端非登录 shell 不暴露全局 Python；脚本默认使用 `/root/miniconda3/bin/python`，可用 `PYTHON=` 覆盖。
- SPANDx v2.6 tarball 已确认可访问，云端解包到 `/root/autodl-tmp/tools/SPANDx_v2.6`；脚本自动把 `SPANDx.config` 中的 `SPANDx_LOCATION` 修正为真实安装路径。
- SPANDx v2.6 内置 `samtools 0.1.19` 需要 legacy `libncurses.so.5`；云端已通过 `apt-get install libncurses5 libtinfo5` 补齐。
- `SPANDx.config` 在严格 shell 下会因未定义 `PERL5LIB` 失败；脚本自动改为 `${PERL5LIB:-}` 形式。
- `samtools depth` 使用 base quality 与 mapping quality 的正确参数顺序。
- `bwa` 版本记录避免在 `set -euo pipefail` 下因帮助信息非零退出中断脚本。
- SPANDx v2.6、PRJEB3144、PRJNA232112 有显式门禁；严格模式下缺少任一关键输入时脚本阻止 paper-exact 声明。

除上述修复外，本次运行还解决了以下运行风险：

- SPANDx v2.6 需要 GATK 3.8（`GenomeAnalysisTK.jar`，官方 gatk-software 分发桶）与 OpenJDK 8，已部署到云端并纳入运行时 PATH。
- SPANDx 面向 PBS 集群设计；云端为其 `qsub` 提供了本地 shim：支持并发上限（可经 `qsub_max_jobs` 运行中热调）、`-W depend=afterok:...` 依赖等待（依赖失败则直接失败）、后台子 shell 与父进程 fd 隔离，避免伪串行和挂起。
- bwa 0.7.19 的 `-R` 拒绝真实 tab，read group 改用转义形式 `"@RG\\tID:...\\tSM:...\\tPL:ILLUMINA"`（bwa 自行转换为 tab）。此前文档中“read group 参数使用真实 tab”的说法已过时，以本条为准。
- `Ortho_SNP_matrix.nex` 是 transposed nexus（行=位点、列=taxa，taxlabels 在头部），解析器已按该格式实现。
- NCBI efetch 参考 FASTA 需去除空行和 CR，否则 SPANDx 拒绝。
- python heredoc 缩进与 `spandx_toolchain_ready` 在 `set -euo pipefail` 下的误判（legacy bwa/samtools 打印用法时退出码为 1）均已修正。

`abi_bcftools` 轨与 paper 轨的系统性差异（10-73 vs 7-60）来自 calling 与过滤策略不同，属预期；两条轨道在文档和图中并列呈现，互不冒充。

## 6. 下一步执行顺序

WGS SNP 严格复现链路（原步骤 1、3-11）已全部完成：本地质量检查、SPANDx-only preflight、三项目上下文 reads 下载与 ENA MD5 校验、双轨 10k read pairs preflight、完整 strict comparison run（`wgs_st93_strict_snp_20260724_attempt3`，零失败）、发布资产回拷与 SHA256SUMS 校验、`docs/paper_examples/`、`metrics.tsv`、中英 running example 和 WGS 图更新、图形重新生成与目视检查，以及 focused pytest、ruff、mypy、`bash docs/build_docs.sh`、`git diff --check`、TSV rectangularity 全部门禁。paper 轨恢复 7-60，SNP 距离指标已按门禁写为 claim-eligible。

剩余事项按以下顺序推进：

1. 增加 Airway 方法一致性修复项：设计 original-method parity 或 sensitivity run，至少冻结 gene-ID 映射、比较方向、显著性阈值和报告 schema；完成前不把 p-value/FDR 逐项一致写成已支持端点。
2. 论文写作按第 7 节推进，WGS SNP 结果可引用 `docs/paper_examples/wgs_snp_track_comparison.tsv` 与扩展后的 WGS 图。
3. 云端收尾（需用户确认）：`wgs_st93_strict_snp_20260724_attempt3` 的 `paper_spandx/work` 中间文件约 51GB 与 `raw/wgs_st93_mrsa_paper` 原始 reads 约 50GB 是否清理，由用户决定；小型发布资产已全部回拷并通过校验。

## 7. 论文写作下一步

写作上建议先固定以下结构：

- Introduction 使用当前六段式版本，不再把 ABI 描述为插件或 YAML+DAG 系统。
- Methods 分为 ABI contract lifecycle、local-model benchmark protocol、real-data biological validation 三部分。
- Results 先报告真实数据 running example，再报告 SCAPP flagship case study；Agent benchmark 只在新 clean run 完成后填数。
- Discussion 明确隐私型本地模型评测的价值，也明确本地模型结论的边界。
- Limitations 必须包括：历史 benchmark 排除、Airway 当前只支持方向/排名/sentinel gene 层面的跨方法一致性而非 p-value/FDR 逐项复现、WGS core-SNP 恢复归功于外部原版 SPANDx 轨而非 ABI 插件能力、SCAPP headline metrics 受独立 truth 门禁、Airway/WGS/SCAPP 都不是群体级泛化准确率估计。

## 8. 当前不可写成结论的内容

以下内容目前不能作为论文结论：

- 任何历史 ABI-Bench 分数。
- 任何尚未完成 clean rerun 的本地模型胜率、准确率或效率提升。
- 把 WGS core-SNP 结果写成 ABI 插件自身能力：7-60 的恢复来自外部原版 SPANDx v2.6 轨；`abi_bcftools` 轨的 10-73 也不得写成原文复现。
- SCAPP paper-method precision、recall 和 F1。
- 将 SCAPP 当前 terminal-repeat 或 mobility evidence 解释为独立准确率。
- 将 ABI 的贡献写成新的生物学学习算法。

当前最稳妥的叙事是：ABI 已经建立了可审计的契约执行与证据发布框架，并在 Airway、WGS 和 SCAPP 的真实公开数据上完成了不同层级的生物学端点验证；WGS 文献 core-SNP 端点已由外部原版工具链轨在 pairwise 距离层面恢复（7-60，paper_exact_candidate）；Agent benchmark 与 SCAPP headline accuracy 仍需按门禁补齐后再进入定量主张。
