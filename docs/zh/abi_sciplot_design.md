# ABI 科研图形编译器（`abi-sciplot`）

`abi-sciplot` 把声明式 `FigureSpec` 编译为经过验证、质检且可追溯的科研图形：

```text
FigureSpec -> 验证数据 -> 使用 Matplotlib 渲染
           -> 导出 PDF/SVG/PNG/TIFF -> lint -> provenance
```

实现位于 `src/abi/sciplot/`。`schema/figure_spec.py` 中的 Pydantic schema
才是单一事实源，本文档不是替代 schema。

## 安装

`abi-agent` 提供 CLI 入口；渲染依赖由 `report` extra 安装：

```bash
pip install "abi-agent[report]"
abi-sciplot list-plot-types
```

规划环境采用惰性导入。即使没有 NumPy、pandas 或 Matplotlib，
`import abi.sciplot` 仍可使用；真正渲染时会返回可操作的缺少依赖错误。

## 支持的图形类型

当前渲染器公布 15 种类型：

```text
alpha_stats_boxplot
barplot
boxplot_with_points
differential_volcano
genus_heatmap
heatmap
lineplot
ordination_plot
pcoa_plot
phylogenetic_heatmap
phylum_stacked_bar
scatterplot
stacked_barplot
violin_with_box
volcano_plot
```

自动化应调用 `abi-sciplot list-plot-types`，不要硬编码该列表。

## 最小 FigureSpec

```yaml
figure_id: treatment_response
figure_type: scatterplot

data:
  table: results/summary.tsv
  format: tsv
  required_columns: [dose, response, group]

mapping:
  x: dose
  y: response
  hue: group

style:
  theme: abi_nature
  palette: colorblind_safe_8
  width_mm: 90
  height_mm: 70
  dpi: 300

labels:
  title: Treatment response
  x_label: Dose
  y_label: Response
  legend_title: Group

export:
  output_dir: results/figures
  basename: treatment_response
  formats: [pdf, svg, png]

provenance:
  workflow_name: my_analysis
  input_data_role: Reviewed summary table
```

数据格式支持 `csv`、`tsv` 和 `parquet`。映射字段包括 `x`、`y`、`hue`、
`label`、`group` 和 `value`，各图形类型所需映射不同。输出格式支持
`pdf`、`svg`、`png` 和 `tiff`。

如果图形表达显著性，必须声明检验和所用字段：

```yaml
statistics:
  test: DESeq2 Wald test
  correction: Benjamini-Hochberg
  pvalue_column: padj
  fold_change_column: log2_fold_change
  significance_rule:
    padj_lt: 0.05
    abs_log2fc_gt: 1.0
```

## 验证、渲染与质检

```bash
abi-sciplot validate --spec figure.yaml
abi-sciplot render --spec figure.yaml
abi-sciplot render --spec figure.yaml --output-dir results/figures --strict
abi-sciplot lint --spec figure.yaml
abi-sciplot lint --spec figure.yaml --figure results/figures/treatment_response.pdf
```

`validate` 检查 schema 与源数据；`render` 完成验证、所有请求格式的渲染、
provenance 写入和 lint；`--strict` 会把 warning 也作为失败。`lint` 可只检查
规范，也可同时检查已有渲染文件。

## 主题与质量规则

内置主题：

| 主题 | 用途 | 默认栅格 DPI |
| --- | --- | ---: |
| `abi_nature` | 紧凑论文图 | 300 |
| `abi_cell` | 较大标签与多面板图 | 300 |
| `abi_report` | 屏幕报告 | 150 |

`FigureSpec.style` 可以覆盖尺寸与 DPI。当前 lint 检查：

- 图形身份和白名单类型；
- rainbow/jet 等禁用调色板；
- 最小物理尺寸；
- 统计检验与多重校正声明；
- 标签；
- 栅格 DPI 和矢量格式；
- 生成的 provenance。

PNG/TIFF 低于 300 DPI 会产生 lint error。`abi_report` 面向屏幕，默认 150
DPI；需要论文级栅格图时应显式设置 `style.dpi: 300`。

## Python API

```python
from abi.sciplot import lint_figure, load_spec, render_figure, validate_spec

spec = load_spec("figure.yaml")
validation = validate_spec(spec)
if validation["errors"]:
    raise ValueError(validation)

result = render_figure(spec)
print(result.to_dict())
report = lint_figure(spec, result.output_files, result.provenance_path)
```

`render_figure()` 返回输出路径、lint 报告路径、provenance 路径和渲染错误。
调用方必须检查返回对象，不能假定请求文件一定已生成。

## 与插件报告的关系

工作流插件在 `plugins/<analysis_type>/figure_specs.yaml` 中声明图形。报告生成器
会把插件规范适配为 `FigureSpec`；如果源表为空或结构不兼容，可选图形可能被跳过。
科学主张仍应落在审查过的表格、方法和限制中；图形成功渲染不等于生物学验证。

schema、全部渲染器、lint、Unicode 排版、CLI/API 和错误路径测试位于
`src/abi/sciplot/tests/`。
