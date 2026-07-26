# RNA-seq 表达工作流（`rnaseq_expression`）

当前内置 RNA-seq 工作流是面向 Illumina 双端数据的 5 节点流程：

```text
fastp
  -> STAR
  -> featureCounts
  -> build_count_matrix.py
  -> DESeq2
```

`plugins/rnaseq_expression/pipeline_dag.yaml` 是拓扑单一事实源；
`tool_registry.yaml` 定义 5 个可执行工具，`standard_tables.yaml`、
`figure_specs.yaml` 和 `limitations.yaml` 定义发布结果契约。HISAT2 仅保留为
旧结果的只读解析兼容别名，不是当前 DAG 可运行的备选工具。Salmon、Kallisto、
edgeR、clusterProfiler 和 gseapy 也没有注册到该插件。

## 初始化工作空间

不要复制不存在的示例路径，直接使用 `abi init`：

```bash
abi init --type rnaseq_expression --outdir work/rnaseq
```

该命令会写入：

```text
work/rnaseq/
├── config/rnaseq_expression.yaml
└── samples.tsv
```

在 `samples.tsv` 中填入唯一的样本 ID 和真实双端 FASTQ 路径。必需列是
`sample_id`、`read1` 和 `read2`。差异分析应保留 `condition`；配对或分层设计
还可增加 `donor` 等列。

修改生成的配置，并替换两个资源占位符：

```yaml
input:
  sample_sheet: samples.tsv

resources:
  genome_index: /data/references/hg38/star_index
  annotation_gtf: /data/references/hg38/gencode.annotation.gtf

differential_expression:
  comparison: treatment_vs_control
  design: "~ condition"
  alpha: 0.05
```

覆盖配置中的相对路径以该配置文件所在目录为基准解析。配对研究可使用
`~ donor + condition`，并确保样本表含有 `donor` 列。

## 规划、检查与执行

```bash
abi plan \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml \
  --sample-sheet work/rnaseq/samples.tsv \
  --outdir results/rnaseq-plan

abi check \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml \
  --sample-sheet work/rnaseq/samples.tsv

abi check-resources \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml

abi dry-run \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml \
  --sample-sheet work/rnaseq/samples.tsv \
  --outdir results/rnaseq-dry-run

abi run \
  --type rnaseq_expression \
  --config work/rnaseq/config/rnaseq_expression.yaml \
  --sample-sheet work/rnaseq/samples.tsv \
  --outdir results/rnaseq \
  --confirm-execution
```

`abi run` 支持 `--engine local|nextflow|snakemake|hpc`。真实执行需要
`rnaseq` Conda 环境（fastp、STAR、featureCounts、R/DESeq2）、STAR 索引和
与参考序列匹配的 GTF。

## 结果

插件发布以下标准表：

| 表 | 内容 |
| --- | --- |
| `qc_summary` | fastp 指标 |
| `alignment_summary` | STAR 比对指标 |
| `gene_expression` | 各样本的 featureCounts 计数 |
| `count_matrix` | 跨样本长表形式的原始计数矩阵 |
| `normalized_expression` | DESeq2 归一化计数 |
| `differential_expression` | base mean、fold change、统计量、p 值与校正 p 值 |

当前图形规范包含必需的 QC、比对率和火山图，以及可选的 PCA、热图和 MA 图。
当当前渲染器无法使用对应表结构时，可选矩阵图可能被跳过；应检查生成报告，
不要假定每张可选图一定存在。

```bash
abi inspect --result-dir results/rnaseq
abi validate-result --type rnaseq_expression --result-dir results/rnaseq
abi report --type rnaseq_expression --result-dir results/rnaseq
```

## 局限性

权威清单位于 `plugins/rnaseq_expression/limitations.yaml`，并会自动写入报告。
重要边界包括参考序列/注释敏感性、DESeq2 设计假设、低计数不确定性、批次效应，
以及 RNA 丰度不能直接代表蛋白质丰度。
