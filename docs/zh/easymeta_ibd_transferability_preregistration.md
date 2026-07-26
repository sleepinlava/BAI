# EasyMeta IBD 迁移性验证预注册（起草，2026-07-25）

本文件预注册对 Frontiers in Microbiology 2025 论文（DOI: 10.3389/fmicb.2025.1578005，
PMCID: PMC12239758）前半部分流程的 ABI 迁移性验证。验证目标是 ABI `easymetagenome`
插件在外部数据、外部端点上的端点恢复能力，不是对该论文全部结论的复现。

## 原文已钉死的流程与资源

- 上游流程：EasyMetagenome（作者既往发表的 pipeline）。KneadData v0.6.1
  （Trimmomatic v0.39 去接头/低质 + Bowtie2 v2.3.5.1 比对 GRCh37/hg19 去宿主）。
- 分类：Kraken2 默认参数，数据库 pluspf 20240605
  （https://genome-idx.s3.amazonaws.com/k2_pluspf_20240605.tar.gz），输出相对丰度。
- 数据：ENA metagenome 266 样本（39 NC / 197 CD / 30 UC），样本清单冻结于
  `docs/zh/figures/data/easymeta_ibd_20260725/Table_1.csv`（SHA256SUMS 同目录）。
  项目分组：ERP017091（109 CD）、PRJNA737472/SRP324954（22 NC + 10 UC）、
  SRP075633（4 NC + 48 CD）、SRP131166（13 NC + 40 CD + 20 UC）。
- 端点参照：属水平组均值与显著性冻结于同目录 `Table_3.csv`；alpha 多样性组间关系
  （Shannon/Chao1：NC>CD、NC>UC、CD≈UC）与 PERMANOVA p<0.001 取自正文。

## 不可复现边界（预先声明）

- 论文未提供逐样本丰度矩阵，只有组均值（Table S3）；因此对比粒度为组均值与方向/
  显著性模式，不做逐样本相关。
- k-mer 特征脚本 `GetKmerSignature.py` 与下游 ML 代码未公开；k-mer 方法至多可
  重实现（reimplementation），其诊断 AUC 不作为本验证的验收端点。
- KneadData v0.6.1 / Trimmomatic v0.39 / Bowtie2 v2.3.5.1 为 legacy 版本；若云端
  只能用更新版本运行，记为声明的兼容替代并写入 provenance。

## 预注册子集（核心 53 样本，单项目防批次混杂）

SRP131166 全部 NC（13）+ 全部 UC（20）+ 按 run accession 字典序取前 20 个 CD，
共 53 样本。若时间允许，追加 PRJNA737472 全部 NC（22）作为 NC 加强组（扩展子集，
单独报告，不混入核心子集端点）。原始 reads 逐样本流式处理（下载→处理→删除），
只保留丰度表与 QC 表；磁盘占用控制在 60GB 以内。

## 预注册验收端点

| 端点 | 定义 | 阈值 |
| --- | --- | --- |
| E1 组均值一致性 | ABI 与 Table_3 组均值在共享属上的 Spearman 相关（NC/CD/UC 各一） | ρ ≥ 0.90 |
| E2 差异方向一致率 | sign(diff_CD_NC) 与 sign(diff_UC_NC) 在共享属上的一致率 | ≥ 90% |
| E3 显著属恢复 | Table_3 中 starred（p<0.01）属的方向匹配恢复率 | ≥ 80% |
| E4 alpha 多样性模式 | 由 ABI 丰度表计算 Shannon/Chao1：NC>CD、NC>UC（Dunn），CD≈UC 不显著 | 全部满足 |
| E5 组间结构 | PERMANOVA 显著 | p < 0.05 |

任何端点未达标时如实报告 divergent 并归因（子集构成、db 版本、legacy 版本替代），
不得改写为通过。

## 执行前提（SCAPP 主线收尾后启动）

1. 构建 legacy 环境（KneadData v0.6.1 组合）并验证可运行。
2. 下载 pluspf 20240605 数据库（~8GB）与 GRCh37/hg19 Bowtie2 索引，冻结 SHA256。
3. 子集 manifest（53 runs + ENA MD5）写入机器可读清单。
4. ABI `easymetagenome` 插件完整生命周期执行，validate-result 通过后计算 E1-E5。
