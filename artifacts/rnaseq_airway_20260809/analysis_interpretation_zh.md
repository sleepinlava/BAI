# Airway RNA-seq：dexamethasone vs untreated 分析解读

## 数据与统计设计

- 8 个样本，4 个供体，每个供体包含 untreated/dex 配对样本。
- 差异模型：`~ donor + condition`，比较 `dex_vs_untreated`。
- `padj < 0.05`：4,549 个差异基因；进一步要求 `|log2FC| >= 1` 后，上调 587 个、下调 608 个。
- 富集分析使用 GO 与 Reactome 离线快照；GSEA 使用 1,000 次置换，探索性阈值 FDR < 0.25。

## 样本结构

修正后的 PCA 使用 log2 标准化表达量中方差最高的 5,000 个基因。PC1 解释 31.0% 方差，
将 dex 与 untreated 样本完全分开；PC2 解释 26.3% 方差，主要体现供体差异。说明处理效应强，
同时供体背景不可忽略，因此配对模型是必要的。相关性图中所有样本总体仍高度相关，符合来源相同
的细胞体系在药物处理前后发生定向转录变化，而不是样本身份或严重质量异常。

## 差异基因

强上调基因包括 `CACNB2`、`PDPN`、`STEAP2`、`NEXN`、`DUSP1`、`SPARCL1`、`MAOA`、
`TIMP4`；强下调基因包括 `PRSS35`、`DNM1`、`ADAM12`、`VCAM1`、`CDKN1A`、`WNT2`、
`CXCL12`。其中 `DUSP1`、`TSC22D1`、`KLF15`、`PER1` 等与糖皮质激素应答相符；
`VCAM1` 和 `CXCL12` 下调支持黏附/趋化信号受抑，但 RNA 水平不能直接等同于蛋白功能。

## 通路层面的生物学意义

1. **收缩与细胞骨架程序增强。** Smooth Muscle Contraction、actin cytoskeleton、RHO–ROCK
   和肌动蛋白聚合相关通路位于上调端，核心基因包括 `ACTA2`、`ACTG2`、`LMOD1`、`MYL9`、
   `ROCK2`。这提示 dexamethasone 使气道平滑肌细胞的收缩/骨架表型发生重编程。
2. **细胞外基质不是单向变化，而是组成重塑。** 胶原形成、胶原三聚化和 ECM 组织在下调基因
   ORA 中富集，而 laminin interactions 在上调端富集。更合适的解释是胶原型基质程序受抑、
   层粘连蛋白/黏附连接程序相对增强，而不是笼统地说“ECM 全面升高”。
3. **PI3K/STAT、PDGF 与受体酪氨酸激酶网络增强。** Reactome GSEA 的核心基因包括
   `PIK3R1`、`STAT3`、`STAT5A/B`、`PTPN11`、`PDGFRA/B`。这表明生长因子及下游信号网络
   整体向上富集，但不能由此认定某一配体被直接激活。
4. **金属硫蛋白/氧化应激防御明显。** 铜、镉应答、无机物解毒及锌稳态通路由 `MT2A`、
   `MT1X`、`MT1E` 等驱动，更可能代表 glucocorticoid 诱导的金属硫蛋白和抗氧化防御，
   不能解释为样本真实暴露于重金属。
5. **炎症与黏附信号受到调节。** `VCAM1`、`CXCL12` 等下调与抗炎/抗趋化方向一致；同时
   Interleukin signaling 的上调富集说明网络并非简单整体关闭，而是部分共享信号模块被重排。

## 解释限制

- 仅有 4 个供体，尽管采用配对设计，跨人群外推仍有限。
- bulk RNA-seq 测量稳态转录本，不代表蛋白丰度、磷酸化状态或实际收缩功能。
- GO 条目高度冗余；“Erythropoietin signaling”“细菌附着”等标签可能由共享的
  JAK/STAT/PI3K 或 ECM 基因驱动，不等于发生相应生理事件。
- GSEA 的 FDR < 0.25 为探索性阈值；优先关注在 ORA、GSEA 和差异基因三个层面均一致的主题。
- 原 ABI 标准 PCA 和 top-DEG 热图误读了长格式表达表；本目录中的 `supplementary_figures`
  是从 ABI 标准 TSV 重建的修正版，未改变上游统计结果。
