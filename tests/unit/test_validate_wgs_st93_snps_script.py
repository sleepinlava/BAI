import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/cloud/validate_wgs_st93_snps.sh"


def test_embedded_python_heredocs_compile() -> None:
    content = SCRIPT.read_text(encoding="utf-8")
    blocks = re.findall(r"<<'?PY'?\n(.*?)\nPY\n", content, re.S)
    assert blocks, "expected embedded Python heredocs in the script"
    for index, block in enumerate(blocks):
        compile(block, f"{SCRIPT.name}<heredoc{index}>", "exec")


def test_wgs_snp_validation_is_immutable_and_truth_bounded() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "[[ ! -e ${OUTPUT_ROOT} ]]" in content
    assert "paper_spandx" in content
    assert "abi_bcftools" in content
    assert "SPANDx v2.6/default" in content
    assert "SPANDX_TARBALL_URL" in content
    assert "DOWNLOAD_PAPER_CONTEXT" in content
    assert "PRJEB3144_TABLE_S1_RUNS" in content
    assert "ERR192209" in content
    assert "skipped_not_in_table_s1" in content
    assert "ThreadPoolExecutor" in content
    assert "REQUIRE_PAPER_EXACT_INPUTS" in content
    assert "configure_spandx()" in content
    assert "SPANDx_LOCATION=" in content
    assert 'PERL5LIB="${PERL5LIB:-}"' in content
    assert "spandx_toolchain_ready()" in content
    assert 'bwa_out=$("${SPANDX_ROOT}/bwa" 2>&1 || true)' in content
    assert "GenomeAnalysisTK.jar" in content
    assert "qsub-shim" in content
    assert ".qsub_shim_state" in content
    assert "QSUB_SHIM_MAX_JOBS" in content
    assert "taxlabels" in content
    assert "-W*afterok*" in content
    assert "exited non-zero" in content
    assert "transposed SNP matrix row" in content
    assert "libncurses.so.5" in content
    assert "PRJEB3144" in content
    assert "PRJNA232112" in content
    assert "CP002114.2" in content
    assert "REFERENCE_CACHE" in content
    assert "--retry-all-errors" in content
    assert 'sub(/\\r$/, "")' in content
    assert "SPANDx v2.6 exited non-zero" in content
    assert "autoplasm-assembly/bin/samtools" in content
    assert "autoplasm-assembly/bin/bcftools" in content
    assert "sort -o FILE" in content
    assert 'read_group="@RG\\\\tID:${sample}\\\\tSM:${sample}\\\\tPL:ILLUMINA"' in content
    assert '-R "${read_group}"' in content
    assert "--ploidy 1" in content
    assert '-q "${MIN_MAPQ}" -Q "${MIN_BASEQ}"' in content
    assert 'depth -aa -q "${MIN_BASEQ}" -Q "${MIN_MAPQ}"' in content
    assert "MIN(FMT/DP)>=${MIN_DEPTH}" in content
    assert '"paper_reproduction_status": "abi_reproduction_not_paper_method"' in content
    assert "-m yes -t Illumina -p PE" in content
    assert '"paper_exact_candidate"' in content
    assert "paper_method_partial_context" in content
    assert "strict_snp_comparison.tsv" in content
    assert "literature_endpoint.tsv" in content
    assert '"benchmark_outcomes_used": False' in content
    assert "sha256sum -c SHA256SUMS" in content
