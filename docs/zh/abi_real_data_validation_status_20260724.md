# ABI 真实数据验证：当前结论与下一步执行说明

> 状态日期：2026-07-24（当日已完成 v2 全部门禁，SCAPP 本轮标记为完成）  
> 当前优先级：`metagenomic_plasmid` / SCAPP human-gut plasmidome  
> 样本：SRR11038083  
> 云端数据根目录：`/root/autodl-tmp/abi-real-data`  
> 本文用途：冻结已经得到的可靠结论、明确不可使用的旧结果，并给出下一阶段的执行和验收顺序。

## 1. 结论先行

当前已经证明：

1. ABI 的质粒工作流能够在真实 human-gut plasmidome 数据上完整运行并产生可审计结果；
2. ABI retry7 得到 157 条 consensus plasmid predictions，AMR 和 mobility 补充分析均已完成；
3. 独立 metaSPAdes K127 truth reconstruction 已在修正内存和线程配置后成功完成；
4. 第一版论文方法计分 `paper_method_v1` 存在确定的软件汇总缺陷，因此其中的
   `Recall=100%`、`FN=0` 和相应 F1 **不得用于论文、图表或 ABI 正确性声明**；
5. 根据 v1 冻结 TSV 独立重算，当前应得到：

   - TP predictions：12；
   - FP predictions：145；
   - truth references：88；
   - recalled truth references：64；
   - FN truth references：24；
   - Precision：12/157 = 7.6433%；
   - Recall：64/88 = 72.7273%；
   - F1：13.8329%。

上述数值说明 ABI 的结果具有两面性：它恢复了 72.7% 的重建 truth，但 157 条预测中仅
12 条满足严格的论文方法匹配条件。该现象不能简单解释为“ABI 产生了 145 条生物学假阳性”，
因为未匹配预测中仍可能存在 PLSDB 2018 未收录的新质粒、短质粒、结构变体或只有功能证据的
候选。严格的表述应是：

> ABI 对重建 truth 的敏感性中等偏高，但与该冻结 reference set 的严格序列一致性 precision
> 较低；未匹配预测需要结合 circularity、MOB、replicon、AMR、丰度和长读长证据进一步分层。

## 2. 已完成并有证据支持的工作

### 2.1 ABI 真实质粒工作流

`plasmid_scapp_core_retry7` 已成功完成，主要结果如下：

| 项目 | 已验证结果 | 证据含义 |
| --- | ---: | --- |
| consensus plasmid predictions | 157 | ABI 质粒检测和结果汇总链路成功 |
| MOB-typer 完整覆盖 | 157/157 | 每条 consensus prediction 均有 mobility 分类 |
| mobilizable | 20 | 具有可动员特征的候选 |
| non-mobilizable | 137 | 未被 MOB-typer 判为可动员 |
| AMRFinderPlus / ABRicate | TEM-116 一致 | 两条独立 AMR 工具链对关键命中达成一致 |

这些结果证明工作流能运行、结果能标准化且不同工具可以交叉核验；它们本身不等同于已经证明
157 条全部为真实质粒。

### 2.2 metaSPAdes K127 独立 truth reconstruction

原始 metaSPAdes 运行在 K55 阶段因操作系统内存分配失败退出，旧
`metaspades_screen.exit_code=68` 已保留为失败证据。随后恢复过程如下：

| 尝试 | 处理 | 结论 |
| --- | --- | --- |
| attempt1 | `--memory 750` 从 K55 恢复 | 云容器重建导致外部中断，不是算法失败 |
| attempt2 | 发现继承的 `OMP_NUM_THREADS=0` | 为修正实际单线程问题而受控停止，exit 255 不算算法失败 |
| attempt3 | OMP/MKL 线程显式设为 16 | 成功完成，recovery exit=0，watcher exit=0 |

attempt3 的已验证运行参数：

- k-mer：`21,33,55,77,99,127`；
- SPAdes threads：16；
- `OMP_NUM_THREADS=16`；
- `OMP_THREAD_LIMIT=16`；
- `MKL_NUM_THREADS=16`；
- SPAdes memory limit：750 GB；
- metaSPAdes：4.3.0。

K55 recovered snapshot 和 `paper_method_v1` 的 SHA-256 manifest 均曾通过
`sha256sum -c`。旧 exit 68、attempt1 和 attempt2 应继续保留，它们记录了真实的恢复路径，
但不能混入算法准确率。

### 2.3 SCAPP 论文方法边界

已经按 supplementary methods S5 冻结以下规则：

- metaSPAdes 最大 k 为 127；
- truth reconstruction：
  - identity 严格大于 85%；
  - contig coverage 严格大于 85%；
  - reference coverage 严格大于 90%；
- prediction scoring：
  - identity 严格大于 80%；
  - prediction 和 reference 双向 coverage 均严格大于 90%；
- 对匹配同一非空 reference signature 的重复 predictions，只允许一条计为 TP，其余计为 FP。

官方 PLSDB 2018-12-05 archive 含 14,739 条记录；论文报告去重后为 13,469 条，但没有发布
具体去重清单或评价代码。因此本项目的结果必须称为：

> **paper-method reconstruction; not paper-exact**

不能称为论文评价的精确复现。

### 2.4 云端空间清理

为优先保证质粒验证，已删除 RNA-seq retry4 中可重新生成的 clean FASTQ 和 STAR BAM，
共 40,637,715,826 bytes。以下内容被保留：

- 原始 reads；
- fastp JSON/HTML；
- STAR 日志；
- featureCounts；
- count matrix；
- DESeq2 表；
- 报告和 provenance；
- retained-evidence SHA-256 manifest。

Bakta 当前为 v6 full 数据库，不应删除或降回 v5。

## 3. `paper_method_v1` 为什么失败

### 3.1 观测到的内部矛盾

`paper_method_v1` 的 SHA-256 校验通过，但“文件没有损坏”不代表“计算逻辑正确”。独立核算发现：

| 证据 | 观测结果 |
| --- | ---: |
| `prediction_status.tsv` | 12 TP、145 FP |
| `prediction_reference_pairs.tsv` | 12 个 predictions 匹配 64 个唯一 truth references |
| `truth_status.tsv` | 64 recalled=true、24 recalled=false |
| `score_summary.json` | 错写为 88 recalled、0 FN |
| `machine_readable_evidence.json` | 错写为 Recall=1.0 |
| `figure_directional_recovery.tsv` | 错写为 truth 88 matched、0 unmatched |

因此 v1 的 JSON 和图表派生表与其自身逐条 TSV 矛盾。

### 3.2 根因

根因位于 `scripts/score_scapp_predictions.py`：

1. `recalled_by` 是 `defaultdict(list)`；
2. 生成逐 truth 表时，对未召回 reference 使用了 `recalled_by[reference_id]`；
3. 该读取操作把 24 个缺失 key 自动插入字典；
4. 随后用 `len(recalled_by)` 计算 recalled truth 数，导致 64 被膨胀为 88。

这是汇总实现错误，不是 BLAST、metaSPAdes、ABI prediction 或生物学数据本身的错误。

## 4. 已完成的代码修复

### 4.1 召回汇总修复

未召回 reference 现在使用无副作用的：

```python
recalled_by.get(reference_id, [])
```

因此生成逐 truth 行时不再修改 `recalled_by`。

### 4.2 回归测试

已增加断言，要求在三个 predictions 均未达到严格 threshold、一个 truth 未召回时：

- `recalled_truth_references == 0`；
- `false_negative_truth_references == 1`；
- `recall == 0`；
- truth row 的 `matching_prediction_count == 0`；
- truth row 的 `matching_prediction_ids == ""`。

本地聚焦测试结果：3 passed。Ruff lint 和 format check 均通过。

### 4.3 机器证据一致性门禁

`scripts/build_scapp_machine_evidence.py` 已增加发布前独立核算：

- 从 `prediction_status.tsv` 重算 TP、两类 FP 和 prediction 总数；
- 从 `truth_status.tsv` 重算 recalled truth、FN 和 truth 总数；
- 从上述计数重新计算 Precision、Recall 和 F1；
- 任一 TSV、JSON count 或 metric 不一致时直接抛出错误，不生成机器证据。

该门禁已在云端对 v1 做负向验证：

- exit code：1；
- 未生成新的 machine evidence；
- 错误信息准确指出 observed 为 64 recalled / 24 FN，而 v1 summary 写成 88 / 0。

### 4.4 v2 证据身份

machine evidence 的 `evidence_id` 已参数化。新输出使用：

```text
scapp_srr11038083_plsdb_2018_12_05_paper_method_v2
```

schema 仍为 `abi.scapp.paper_method_evidence.v1`，因为 JSON 结构没有改变；v2 指的是证据运行和
计分修正版，不是 schema 版本。

## 5. v2 最终确认（2026-07-24 已完成）

2026-07-23 启动的不可覆盖完整重建 `paper_method_v2` 已于当日 02:50（云端时区）成功完成。
2026-07-24 重新连接云端后，以下事项全部确认：

2026-07-23 已启动不可覆盖的完整重建：

```text
/root/autodl-tmp/abi-real-data/references/scapp/independent_truth_20260717/paper_method_v2
```

启动后已确认：

- v2 目标在启动前不存在；
- PLSDB BLAST database 正常构建；
- 随后进入 16 线程 `blastn`；
- 运行时约 650 MB RSS；
- 数据盘当时约 158 GB 可用；
- 新的一致性门禁已在进入 evidence builder 之前同步到云端。

2026-07-24 通过 `.codex/abi-cloud-ssh` 恢复连接后，全部待确认项已核实通过：

- `paper_method_v2.exit_code == 0`，无残留验证进程；
- `VALIDATION_COMPLETE == complete`；
- `sha256sum -c SHA256SUMS` 全部通过（无非 OK 行）；
- v1 原目录与哈希保持不变，未被覆盖；
- 从 `prediction_status.tsv` / `truth_status.tsv` 独立重算为 12 TP、145 FP（0 duplicate）、
  64 recalled、24 FN；`prediction_reference_pairs.tsv` 中 matched pair 覆盖 12 条唯一
  predictions 和 64 条唯一 truth references，三表交叉一致；
- `score_summary.json`、`machine_readable_evidence.json`、两个 figure TSV 与 TSV 重算
  四者一致：Precision 7.6433%、Recall 72.7273%、F1 13.8329%；
- `evidence_id == scapp_srr11038083_plsdb_2018_12_05_paper_method_v2`，
  `evaluation_scope == "paper-method reconstruction; not paper-exact"`；
- provenance 中 truth builder、prediction scorer、evidence builder 的 SHA-256 与本地
  修复版逐一一致；metaSPAdes 为 K127 / 16 threads / 750 GB（attempt3 成功路径）。

v2 现标记为 **final**。第六节的执行顺序已全部完成，第七节验收清单全部勾验。

## 6. 执行顺序（2026-07-24 已全部完成）

> 第一至第七步均已执行并通过；以下保留原始步骤说明作为审计记录。
> 实际执行结果：第一步只读检查确认 exit=0 且无残留进程；第二、三步完整性与独立
> 重算全部通过；第四步 12 个小型证据文件已下载至
> `docs/zh/figures/data/scapp_paper_method_v2_20260724/`（含 `analysis/` 分层输出），
> 下载后 SHA-256 与云端 manifest 逐一复核一致；第五步分层分析在云端以
> `paper_method_prediction_status` 模式完成；第六步五张 `scapp_paper_method_*` 图通过
> `abi-sciplot validate` 与 `--strict` 渲染（零错误零警告）并逐张人工视觉复核；
> 第七步 `metrics.tsv`、`scapp_status.tsv`、`limitations.tsv` 和
> `real_data_validation_datasets.md`（新增 9.7 节）已更新，
> `docs/zh/figures/scapp_paper_method_v2_evidence.SHA256SUMS`（49 项）已生成并校验，
> Ruff、聚焦 pytest（11 passed）和 `bash docs/build_docs.sh` 均通过。

### 第一步：恢复连接并只读检查，不先重启

使用仓库的安全助手，禁止打印 `.key`：

```bash
/home/bker/abi/.codex/abi-cloud-ssh \
  'hostname; date -Is; \
   base=/root/autodl-tmp/abi-real-data/references/scapp/independent_truth_20260717; \
   test -f "$base/paper_method_v2.exit_code" && cat "$base/paper_method_v2.exit_code" || echo RUNNING; \
   pgrep -af "run_scapp_paper_method_validation|blastn.*paper_method_v2" || true'
```

判定规则：

- 进程仍健康：继续等待，不重启；
- exit=0 且目录完整：进入第二步；
- exit 非 0：保留 v2 日志和 staging 证据，查明原因后使用新身份 `paper_method_v3`，不得覆盖 v2；
- 无进程、无 exit marker：按基础设施中断处理，先冻结日志、时间和哈希，再决定恢复。

### 第二步：验证 v2 完整性和身份

必须同时满足：

```bash
cd /root/autodl-tmp/abi-real-data/references/scapp/independent_truth_20260717/paper_method_v2
test "$(cat ../paper_method_v2.exit_code)" = "0"
test "$(cat VALIDATION_COMPLETE)" = "complete"
sha256sum -c SHA256SUMS
```

并确认：

- `evidence_id` 以 `paper_method_v2` 结尾；
- `status == "complete"`；
- `evaluation_scope == "paper-method reconstruction; not paper-exact"`；
- provenance 中 scorer、builder、assembly、PLSDB、predictions 和 supplementary method 均有哈希；
- `prediction_scorer_sha256` 与本地修复版一致；
- v1 原目录和哈希保持不变。

### 第三步：独立重算最终指标

不能只读取 JSON。必须从 TSV 独立得到：

```text
prediction_status:
  true_positive = 12
  false_positive_no_match = 145
  false_positive_duplicate_match_signature = 0

truth_status:
  recalled=true = 64
  recalled=false = 24
```

然后独立计算：

```text
precision = 12 / 157 = 0.076433121019...
recall    = 64 / 88  = 0.727272727273...
f1        = 0.138328530259...
```

只有 TSV、`score_summary.json`、`machine_readable_evidence.json` 和派生 figure TSV 四者一致，
才可把上述值列为 final。

### 第四步：下载小型证据到仓库

建议新建：

```text
docs/zh/figures/data/scapp_paper_method_v2_20260724/
```

只下载论文、复核和绘图需要的小型文件：

- `machine_readable_evidence.json`；
- `score_summary.json`；
- `truth_summary.json`；
- `run_provenance.tsv`；
- `prediction_status.tsv`；
- `truth_status.tsv`；
- `prediction_reference_pairs.tsv`；
- `figure_metrics.tsv`；
- `figure_directional_recovery.tsv`；
- `evidence_match_table.tsv`；
- `SHA256SUMS`；
- `VALIDATION_COMPLETE`。

大型 BLAST TSV 和 FASTA 继续保留在云端大数据盘，不提交 Git。

### 第五步：完成质粒证据分层

使用：

```bash
python scripts/analyze_scapp_plasmid_evidence.py \
  --result-dir /root/autodl-tmp/abi-real-data/results/plasmid_scapp_core_retry7 \
  --match-table <paper_method_v2>/evidence_match_table.tsv \
  --mob-table /root/autodl-tmp/abi-real-data/results/plasmid_scapp_core_retry7/supplementary/amr_mobility_20260720/raw/mob_typer/SRR11038083.mob_typer.tsv \
  --output-dir <paper_method_v2_analysis>
```

重点比较 TP 和 FP prediction 组的：

- circularity / terminal overlap；
- PlasmidFinder；
- MOB replicon；
- relaxase；
- oriT；
- predicted mobility；
- abundance；
- length；
- AMR hit。

这里的目标不是把辅助证据当作 truth，而是解释严格 reference mismatch 的来源。

### 第六步：生成并严格渲染最终图

生成五个 `scapp_paper_method_*` FigureSpec：

1. Precision / Recall / F1；
2. truth 与 predictions 的方向性 matched/unmatched 构成；
3. TP/FP 组的辅助证据率；
4. abundance–length 分布；
5. mobility composition。

所有图必须：

- 使用 v2 冻结表；
- 通过 `abi-sciplot validate`；
- 通过严格 FigureLint；
- 输出 PNG、PDF、SVG 和 provenance；
- 人工视觉检查标签、图例、百分比归一化和截断；
- 不再展示 v1 的 100% Recall；
- 图注显式写明 `paper-method reconstruction; not paper-exact`。

### 第七步：文档与发布门禁

最终需要更新：

- `docs/zh/real_data_validation_datasets.md`；
- 对应英文说明；
- v2 小型证据目录；
- 图表 SHA-256 清单；
- 最终机器可读验证清单。

代码质量门禁至少包括：

```bash
ruff check --no-cache \
  scripts/score_scapp_predictions.py \
  scripts/build_scapp_machine_evidence.py \
  tests/unit/test_score_scapp_predictions.py \
  tests/unit/test_build_scapp_machine_evidence.py

ruff format --check --no-cache \
  scripts/score_scapp_predictions.py \
  scripts/build_scapp_machine_evidence.py \
  tests/unit/test_score_scapp_predictions.py \
  tests/unit/test_build_scapp_machine_evidence.py

pytest -q \
  tests/unit/test_score_scapp_predictions.py \
  tests/unit/test_build_scapp_machine_evidence.py

bash docs/build_docs.sh
```

## 7. 最终验收清单

以下项目已于 2026-07-24 全部满足，SCAPP 这一轮标记为完成：

- [x] `paper_method_v2.exit_code == 0`
- [x] `VALIDATION_COMPLETE == complete`
- [x] `sha256sum -c SHA256SUMS` 全部通过
- [x] v2 evidence ID 正确且 v1 未被覆盖
- [x] metaSPAdes 参数为 K127 / 16 threads / 750 GB
- [x] scorer 和 evidence builder 哈希对应修复版
- [x] prediction TSV 独立重算为 12 TP / 145 FP
- [x] truth TSV 独立重算为 64 recalled / 24 FN
- [x] JSON 为 Precision 7.6433% / Recall 72.7273% / F1 13.8329%
- [x] machine evidence 一致性门禁通过
- [x] `evaluation_scope` 明确为 not paper-exact
- [x] 小型证据已下载到仓库
- [x] 分层分析完成
- [x] 五张 SciPlot 图严格渲染并视觉复核
- [x] 中英文文档和最终清单已更新
- [x] v1 错误结果仍保留为失败证据，但不会被任何最终图表引用

## 8. 当前研究判断

这轮工作已经证明 ABI 不只是“能跑”：它可以记录运行时资源、恢复基础设施中断、冻结
数据库与代码哈希、产生逐条审计表，并通过独立复核发现自身汇总错误。对论文而言，这类
可追溯失败和修复本身是 ABI utility 的重要证据。

v2 完整门禁已通过并确认上述重算结果，论文结论应按两层表述：

1. **严格 reference concordance**：Precision 7.64%、Recall 72.73%、F1 13.83%；
2. **辅助生物学证据**：报告未匹配 predictions 中 circularity、MOB、replicon、AMR 和丰度
   支持的比例，说明 reference-negative 不等价于 biological false-positive。

这比只展示一个“正确度”柱状图更科学，也更能说明 ABI 的实际价值和当前边界。
