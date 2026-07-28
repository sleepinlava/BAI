from __future__ import annotations

import gzip
import importlib.util
import math
from pathlib import Path

import pandas as pd
import pytest

_SCRIPT = Path("plugins/rnaseq_expression/scripts/run_enrichment.py")
_SPEC = importlib.util.spec_from_file_location("abi_rnaseq_enrichment_script", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_offline_annotation_and_ora_use_gene_symbols(tmp_path: Path) -> None:
    gtf = tmp_path / "Homo_sapiens.GRCh37.75.gtf"
    gtf.write_text(
        "chr1\tENSEMBL\tgene\t1\t10\t.\t+\t.\t"
        'gene_id "ENSG1"; gene_name "CRISPLD2";\n'
        "chr1\tENSEMBL\tgene\t20\t30\t.\t+\t.\t"
        'gene_id "ENSG2"; gene_name "DUSP1";\n',
        encoding="utf-8",
    )
    assert _MODULE.parse_gtf_symbols(gtf, {"ENSG1", "ENSG2"}) == {
        "ENSG1": "CRISPLD2",
        "ENSG2": "DUSP1",
    }

    go_obo = tmp_path / "go-basic.obo"
    go_obo.write_text(
        "[Term]\nid: GO:0000001\nname: glucocorticoid response\n"
        "namespace: biological_process\nis_a: GO:0000002 ! response to stress\n\n"
        "[Term]\nid: GO:0000002\nname: response to stress\n"
        "namespace: biological_process\n\n",
        encoding="utf-8",
    )
    go_gaf = tmp_path / "goa_human.gaf.gz"
    with gzip.open(go_gaf, "wt") as handle:
        for symbol in ("CRISPLD2", "DUSP1", "KLF15"):
            fields = ["UniProtKB", symbol, symbol, "", "GO:0000001", "PMID:1", "EXP", "", "P"]
            handle.write("\t".join(fields) + "\n")

    universe = {"CRISPLD2", "DUSP1", "KLF15", "ACTB"}
    names = _MODULE.parse_go_names(go_obo)
    _, parents = _MODULE.parse_go_ontology(go_obo)
    gene_sets, aspects = _MODULE.parse_go_sets(go_gaf, universe, names, parents)
    assert gene_sets["GO:0000002 | response to stress"] == {
        "CRISPLD2",
        "DUSP1",
        "KLF15",
    }
    result = _MODULE.ora(
        {"CRISPLD2", "DUSP1", "KLF15"},
        universe,
        gene_sets,
        "GO",
        "up",
        aspects,
        min_size=1,
        max_size=10,
    )

    assert result.iloc[0]["overlap_genes"] == "CRISPLD2,DUSP1,KLF15"
    assert result.iloc[0]["pvalue"] == pytest.approx(0.25)
    plotted = _MODULE._add_plot_columns(result, "ORA")
    assert "CRISPLD2,DUSP1" in plotted.iloc[0]["plot_label"]
    assert plotted.iloc[0]["gene_symbols"] == "CRISPLD2,DUSP1,KLF15"
    assert plotted.iloc[0]["score"] == pytest.approx(-math.log10(0.25))


def test_ora_adjusts_over_all_eligible_gene_sets() -> None:
    result = _MODULE.ora(
        {"A", "B", "C"},
        {"A", "B", "C", "D"},
        {
            "overlap": {"A", "B", "C"},
            "no overlap": {"D"},
        },
        "GO",
        "up",
        min_size=1,
        max_size=10,
    )

    assert set(result["term"]) == {"overlap", "no overlap"}
    assert result.set_index("term").loc["overlap", "padj"] == pytest.approx(0.5)
    assert result.set_index("term").loc["no overlap", "pvalue"] == pytest.approx(1.0)


def test_plot_preview_excludes_terms_above_fdr_threshold() -> None:
    table = pd.DataFrame(
        {
            "direction": ["up", "up", "up", "down", "down"],
            "term": [
                "up significant",
                "up stronger",
                "up non-significant",
                "down significant",
                "down non-significant",
            ],
            "padj": ["1e-2", "9e-3", "3e-1", "2e-1", "2.6e-1"],
            "pvalue": ["1e-3", "8e-4", "2e-1", "1e-1", "2e-1"],
        }
    )

    plotted = _MODULE._top_by_direction(table, top_n=5, max_padj=0.25)

    assert plotted["term"].tolist() == [
        "down significant",
        "up stronger",
        "up significant",
    ]
