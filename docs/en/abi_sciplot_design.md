# ABI Scientific Figure Compiler (`abi-sciplot`)

`abi-sciplot` turns a declarative `FigureSpec` into validated, linted, and
traceable scientific figures:

```text
FigureSpec -> validate data -> render with Matplotlib
           -> export PDF/SVG/PNG/TIFF -> lint -> provenance
```

The implementation lives in `src/abi/sciplot/`. The Pydantic schema in
`schema/figure_spec.py`, not this guide, is the source of truth.

## Install

The CLI entry point is installed with `abi-agent`; rendering dependencies come
from the report extra:

```bash
pip install "abi-agent[report]"
abi-sciplot list-plot-types
```

Planning-only imports are lazy. If NumPy, pandas, or Matplotlib is absent,
`import abi.sciplot` still works, while rendering returns an actionable missing
dependency error.

## Supported plot types

The current renderer advertises 15 types:

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

Use `abi-sciplot list-plot-types` in automation instead of hard-coding this
list.

## Minimal FigureSpec

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

Data formats are `csv`, `tsv`, and `parquet`. Mappings can use `x`, `y`,
`hue`, `label`, `group`, and `value`; required mappings depend on the plot type.
Output formats are `pdf`, `svg`, `png`, and `tiff`.

For figures that encode significance, declare the test and columns:

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

## Validate, render, and lint

```bash
abi-sciplot validate --spec figure.yaml
abi-sciplot render --spec figure.yaml
abi-sciplot render --spec figure.yaml --output-dir results/figures --strict
abi-sciplot lint --spec figure.yaml
abi-sciplot lint --spec figure.yaml --figure results/figures/treatment_response.pdf
```

`validate` checks schema and source data. `render` validates, renders all
requested formats, writes provenance, and runs lint. `--strict` also fails on
warnings. `lint` can check only the specification or include an existing
rendered output.

## Themes and quality rules

Built-in themes are:

| Theme | Intended use | Default raster DPI |
| --- | --- | ---: |
| `abi_nature` | Compact manuscript figures | 300 |
| `abi_cell` | Larger labels and multi-panel work | 300 |
| `abi_report` | Screen-oriented reports | 150 |

`FigureSpec.style` may override dimensions and DPI. Current lint rules check:

- figure identity and whitelisted type;
- forbidden palettes such as rainbow/jet;
- minimum physical dimensions;
- declared statistics and multiple-testing correction;
- labels;
- raster DPI and presence of a vector format;
- generated provenance.

PNG/TIFF output below 300 DPI is a lint error. `abi_report` defaults to 150 DPI
for screens, so explicitly set `style.dpi: 300` when requesting a
publication-grade raster.

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

`render_figure()` returns output paths, a lint-report path, a provenance path,
and any rendering errors. Check the returned object instead of assuming that
requested files were produced.

## Relationship to plugin reports

Workflow plugins declare figures in
`plugins/<analysis_type>/figure_specs.yaml`. Report generation adapts those
plugin specs to `FigureSpec` and may skip optional figures when source tables
are empty or incompatible. Scientific claims still belong in reviewed tables,
methods, and limitations; a successfully rendered figure is not biological
validation.

Tests for schemas, all renderers, lint, Unicode layout, CLI/API behavior, and
error paths live in `src/abi/sciplot/tests/`.
