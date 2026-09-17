from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

from abi.plugins.easymetagenome.handlers import (
    bracken_merge_handler,
    cleanup_taxonomy_intermediates_handler,
    compress_reads_handler,
    kneaddata_summary_handler,
    report_handler,
    taxonomy_diversity_handler,
    taxonomy_filter_handler,
)
from abi.runtimes import RuntimeOptions
from abi.workflow import WorkflowCoordinator

_CANONICAL_REPORT_SCHEMA = (
    Path(__file__).parents[2]
    / "src/abi/plugins/easymetagenome/schemas/abi_report_manifest.schema.json"
)


def _assert_json_schema(value, schema):
    if "const" in schema:
        assert value == schema["const"]
    if "enum" in schema:
        assert value in schema["enum"]
    schema_type = schema.get("type")
    if schema_type == "object":
        assert isinstance(value, dict)
        assert set(schema.get("required", ())) <= set(value)
        assert len(value) >= schema.get("minProperties", 0)
        properties = schema.get("properties", {})
        for name, item in value.items():
            if name in properties:
                _assert_json_schema(item, properties[name])
                continue
            additional = schema.get("additionalProperties", True)
            assert additional is not False
            if isinstance(additional, dict):
                _assert_json_schema(item, additional)
    elif schema_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool)
        assert value >= schema.get("minimum", value)
    elif schema_type == "string":
        assert isinstance(value, str)
        assert len(value) >= schema.get("minLength", 0)


def _assert_matches_canonical_report_schema(payload):
    schema = json.loads(_CANONICAL_REPORT_SCHEMA.read_text(encoding="utf-8"))
    _assert_json_schema(payload, schema)


def _manifest(tmp_path: Path) -> Path:
    r1 = tmp_path / "S1_R1.fastq.gz"
    r2 = tmp_path / "S1_R2.fastq.gz"
    r1.write_bytes(b"reads")
    r2.write_bytes(b"reads")
    manifest = tmp_path / "samples.tsv"
    manifest.write_text(
        "sample_id\tr1\tr2\tgroup\nS1\tS1_R1.fastq.gz\tS1_R2.fastq.gz\tcase\n",
        encoding="utf-8",
    )
    return manifest


def test_taxonomy_cleanup_preserves_kneaddata_summary_from_standard_table(tmp_path):
    outdir = tmp_path / "result"
    inputs = {}
    raw_read1 = outdir / "01_preprocessing/S1/S1_R1.fastq.gz"
    raw_read2 = outdir / "01_preprocessing/S1/S1_R2.fastq.gz"
    raw_read1.parent.mkdir(parents=True, exist_ok=True)
    raw_read1.write_bytes(b"original read 1")
    raw_read2.write_bytes(b"original read 2")
    inputs.update(raw_read1=str(raw_read1), raw_read2=str(raw_read2))
    for key, relative in (
        ("clean_read1", "01_preprocessing/S1/S1_1.fastq.gz"),
        ("clean_read2", "01_preprocessing/S1/S1_2.fastq.gz"),
        ("dehost_read1", "02_host_removal/S1/S1_1_kneaddata_paired_1.fastq.gz"),
        ("dehost_read2", "02_host_removal/S1/S1_1_kneaddata_paired_2.fastq.gz"),
        ("classifications", "03_taxonomy/S1/S1.kraken2.output"),
    ):
        path = outdir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if key.startswith("dehost"):
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                handle.write("@r1\nACGT\n+\nIIII\n")
        else:
            path.write_text("intermediate\n", encoding="utf-8")
        inputs[key] = str(path)

    tables_dir = outdir / "tables"
    tables_dir.mkdir(parents=True)
    (tables_dir / "host_removal_summary.tsv").write_text(
        "sample_id\tdehost_read_pairs\ttool\tsource_file\nS1\t1\tkneaddata\tfixture\n",
        encoding="utf-8",
    )
    receipt = outdir / "provenance/intermediate_cleanup/S1.taxonomy.json"
    context = SimpleNamespace(outdir=outdir, tables_dir=tables_dir)

    cleanup_taxonomy_intermediates_handler(
        SimpleNamespace(
            sample_id="S1",
            inputs=inputs,
            outputs={"cleanup_receipt": str(receipt)},
        ),
        {},
        context,
    )
    summary = outdir / "04_summary/kneaddata_summary.tsv"
    result = kneaddata_summary_handler(
        SimpleNamespace(
            inputs={"dehost_reads": [inputs["dehost_read1"]]},
            outputs={"summary_table": str(summary)},
        ),
        {},
        context,
    )

    assert raw_read1.read_bytes() == b"original read 1"
    assert raw_read2.read_bytes() == b"original read 2"
    assert all(not Path(path).exists() for key, path in inputs.items() if key.startswith("clean"))
    assert not Path(inputs["dehost_read1"]).exists()
    assert not Path(inputs["dehost_read2"]).exists()
    assert not Path(inputs["classifications"]).exists()
    cleanup = json.loads(receipt.read_text(encoding="utf-8"))
    assert cleanup["dehost_read_pairs"] == 1
    tombstone = Path(cleanup["tombstone_manifest"])
    assert tombstone.is_file()
    deleted = json.loads(tombstone.read_text(encoding="utf-8"))["artifacts"]
    assert len(deleted) == len(inputs) - 2
    assert all(len(item["sha256"]) == 64 and item["status"] == "deleted" for item in deleted)
    assert result.tables == {}
    assert summary.read_text(encoding="utf-8").splitlines() == [
        "sample_id\tdehost_read_pairs",
        "S1\t1",
    ]


def test_taxonomy_cleanup_preserves_raw_read_symlink_and_target(tmp_path):
    outdir = tmp_path / "result"
    source = tmp_path / "external" / "S1_R1.fastq.gz"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"external original read")
    raw_link = outdir / "inputs/S1_R1.fastq.gz"
    raw_link.parent.mkdir(parents=True)
    raw_link.symlink_to(source)
    raw_read2 = outdir / "inputs/S1_R2.fastq.gz"
    raw_read2.write_bytes(b"original read 2")

    dehost = outdir / "02_host_removal/S1/S1_1_kneaddata_paired_1.fastq.gz"
    dehost.parent.mkdir(parents=True)
    with gzip.open(dehost, "wt", encoding="utf-8") as handle:
        handle.write("@r1\nACGT\n+\nIIII\n")
    clean = outdir / "01_preprocessing/S1/clean.fastq.gz"
    clean.parent.mkdir(parents=True, exist_ok=True)
    clean.write_text("temporary\n", encoding="utf-8")
    classification = outdir / "03_taxonomy/S1/output.kraken"
    classification.parent.mkdir(parents=True, exist_ok=True)
    classification.write_text("temporary\n", encoding="utf-8")
    receipt = outdir / "provenance/intermediate_cleanup/S1.taxonomy.json"

    cleanup_taxonomy_intermediates_handler(
        SimpleNamespace(
            sample_id="S1",
            inputs={
                "raw_read1": str(raw_link),
                "raw_read2": str(raw_read2),
                "clean_read1": str(clean),
                "dehost_read1": str(dehost),
                "classifications": str(classification),
            },
            outputs={"cleanup_receipt": str(receipt)},
        ),
        {},
        SimpleNamespace(outdir=outdir, tables_dir=outdir / "tables"),
    )

    assert raw_link.is_symlink()
    assert raw_link.read_bytes() == b"external original read"
    assert raw_read2.read_bytes() == b"original read 2"


def test_compress_reads_preserves_original_inputs_inside_kneaddata_dir(tmp_path):
    outdir = tmp_path / "result"
    output_dir = outdir / "02_host_removal/S1"
    output_dir.mkdir(parents=True)
    raw_target = tmp_path / "source" / "S1_R1.fastq.gz"
    raw_target.parent.mkdir(parents=True)
    raw_target.write_bytes(b"original read 1")
    raw_link = output_dir / "S1_R1.fastq.gz"
    raw_link.symlink_to(raw_target)
    raw_read2 = output_dir / "S1_R2.fastq.gz"
    raw_read2.write_bytes(b"original read 2")

    dehost_read1 = output_dir / "S1_1.fastq"
    dehost_read2 = output_dir / "S1_2.fastq"
    dehost_read1.write_text("@r1\nACGT\n+\nIIII\n", encoding="utf-8")
    dehost_read2.write_text("@r2\nTGCA\n+\nIIII\n", encoding="utf-8")
    compressed_read1 = output_dir / "S1_1_kneaddata_paired_1.fastq.gz"
    compressed_read2 = output_dir / "S1_1_kneaddata_paired_2.fastq.gz"
    receipt = outdir / "provenance/intermediate_cleanup/S1.compress.json"

    result = compress_reads_handler(
        SimpleNamespace(
            sample_id="S1",
            inputs={"dehost_read1": str(dehost_read1), "dehost_read2": str(dehost_read2)},
            outputs={
                "dehost_read1": str(compressed_read1),
                "dehost_read2": str(compressed_read2),
                "cleanup_receipt": str(receipt),
            },
            params={"threads": 1},
        ),
        {"threads": 1},
        SimpleNamespace(
            outdir=outdir,
            tables_dir=outdir / "tables",
            protected_input_paths=frozenset({raw_link, raw_read2}),
        ),
    )

    assert result.status == "success"
    assert raw_link.is_symlink()
    assert raw_link.read_bytes() == b"original read 1"
    assert raw_read2.read_bytes() == b"original read 2"
    assert not dehost_read1.exists()
    assert not dehost_read2.exists()
    assert compressed_read1.is_file()
    assert compressed_read2.is_file()


def test_taxonomy_internal_handlers_merge_filter_diversity_and_report(tmp_path):
    inputs = {}
    outputs = {}
    for level, name in (("P", "phylum"), ("G", "genus"), ("S", "species")):
        table = tmp_path / f"S1.{level}.brk"
        table.write_text(
            "name\ttaxonomy_id\tnew_est_reads\nA\t1\t10\nB\t2\t0\n",
            encoding="utf-8",
        )
        inputs[f"{name}_tables"] = [str(table)]
        outputs[f"{name}_table"] = str(tmp_path / "merged" / f"{name}.tsv")

    result = bracken_merge_handler(SimpleNamespace(inputs=inputs, outputs=outputs), {}, None)

    assert result.message == "Merged Bracken P/G/S tables"
    assert all(Path(path).is_file() for path in outputs.values())

    filter_outputs = {
        f"filtered_{name}": str(tmp_path / "filtered" / f"{name}.tsv")
        for name in ("phylum", "genus", "species")
    }
    taxonomy_filter_handler(
        SimpleNamespace(
            inputs={
                f"{name}_table": outputs[f"{name}_table"] for name in ("phylum", "genus", "species")
            },
            outputs=filter_outputs,
            params={"prevalence": 1.0},
        ),
        {},
        None,
    )

    species_rows = Path(filter_outputs["filtered_species"]).read_text(encoding="utf-8")
    assert "A\t1\t10" in species_rows
    assert "B\t2\t0" not in species_rows

    diversity = taxonomy_diversity_handler(
        SimpleNamespace(
            inputs={"species_table": outputs["species_table"]},
            outputs={
                "alpha_table": str(tmp_path / "diversity" / "alpha.tsv"),
                "beta_table": str(tmp_path / "diversity" / "beta.tsv"),
            },
        ),
        {},
        None,
    )
    assert Path(diversity.artifacts["alpha"]).is_file()
    assert Path(diversity.artifacts["beta"]).is_file()

    tables_dir = tmp_path / "tables"
    tables_dir.mkdir()
    for name in ("qc_summary", "host_removal_summary", "taxonomy_abundance"):
        (tables_dir / f"{name}.tsv").write_text("id\tvalue\na\t1\nb\t2\n", encoding="utf-8")

    report = report_handler(
        SimpleNamespace(
            inputs={
                "species_table": outputs["species_table"],
                "ignored": ["not", "a", "path"],
            },
            outputs={
                "report_markdown": str(tmp_path / "report" / "report.md"),
                "report_manifest": str(tmp_path / "report" / "manifest.json"),
            },
        ),
        {"input": {"sample_sheet": str(_manifest(tmp_path))}},
        SimpleNamespace(tables_dir=tables_dir),
    )

    assert report.message == "EasyMetagenome report generated"
    manifest = json.loads(Path(report.artifacts["manifest"]).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "abi.report-manifest.v1"
    assert manifest["workflow"] == "p0_taxonomy"
    assert manifest["sample_count"] == 1
    assert set(manifest["artifacts"]) == {"species_table"}
    assert manifest["consistency"] == {
        "standard_table_count": 3,
        "standard_row_count": 6,
    }


def test_p0_runner_executes_chain_and_writes_report(tmp_path, monkeypatch):
    reads = [tmp_path / "S1_R1.fastq.gz", tmp_path / "S1_R2.fastq.gz"]
    for read in reads:
        with gzip.open(read, "wt", encoding="utf-8") as handle:
            handle.write("@r1\nACGT\n+\nIIII\n")
    manifest = tmp_path / "samples.tsv"
    manifest.write_text(
        f"sample_id\tr1\tr2\tgroup\nS1\t{reads[0]}\t{reads[1]}\tcase\n",
        encoding="utf-8",
    )
    database = tmp_path / "db"
    host = tmp_path / "host"
    database.mkdir()
    host.mkdir()
    registry = tmp_path / "db.yaml"
    registry.write_text(
        "database_id: fixture\npath: ${EASY_KRAKEN_DB}\nhost_db: ${EASY_HOST_DB}\nchecks: []\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EASY_KRAKEN_DB", str(database))
    monkeypatch.setenv("EASY_HOST_DB", str(host))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_script = bin_dir / "fixture_tool.py"
    tool_script.write_text(
        """#!/usr/bin/env python3
import gzip
import json
import pathlib
import sys

name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if '--version' in args or args == ['version']:
    print(name + ' 1.0')
    raise SystemExit(0)
def value(flag):
    return pathlib.Path(args[args.index(flag) + 1])
if name == 'seqkit':
    print('file\\tnum_seqs')
    print('fixture\\t1')
elif name == 'fastp':
    for flag in ('-o', '-O'):
        path = value(flag); path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, 'wt') as handle: handle.write('@r1\\nACGT\\n+\\nIIII\\n')
    html = value('-h'); html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text('<html>fixture</html>\\n')
    report = value('-j'); report.parent.mkdir(parents=True, exist_ok=True)
    data = {'summary': {
        'before_filtering': {'total_reads': 2},
        'after_filtering': {'total_reads': 2, 'q30_rate': 1.0},
    }, 'filtering_result': {'passed_filter_reads': 2}}
    report.write_text(json.dumps(data))
elif name == 'kneaddata':
    out = value('-o'); out.mkdir(parents=True, exist_ok=True)
    for suffix in ('paired_1.fastq', 'paired_2.fastq'):
        (out / ('S1_1_kneaddata_' + suffix)).write_text('@r1\\nACGT\\n+\\nIIII\\n')
    (out / '_temp.sam').write_text('temporary\\n')
elif name == 'kraken2':
    for flag in ('--report', '--output'):
        path = value(flag)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('classified\\n')
elif name == 'bracken':
    table = value('-o'); table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text('name\\ttaxonomy_id\\tnew_est_reads\\nBacteria\\t2\\t10\\n')
    value('-w').write_text('name\\ttaxonomy_id\\nBacteria\\t2\\n')
""",
        encoding="utf-8",
    )
    tool_script.chmod(0o755)
    for name in ("seqkit", "fastp", "kneaddata", "kraken2", "bracken"):
        (bin_dir / name).symlink_to(tool_script)
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join((str(bin_dir), str(Path(sys.executable).parent), os.environ["PATH"])),
    )

    # WP10: the deprecated P0Workflow.run() entry is retired — the canonical
    # coordinator path carries the same protections (cleanup receipts, workers
    # propagation, progress events, provenance persistence).
    # WP10：弃用的 P0Workflow.run() 入口已退役——canonical 协调器路径承载同样
    # 的保护（清理回执、workers 传播、进度事件、溯源持久化）。
    import yaml as yaml_lib

    from abi.runtimes import RuntimeOptions
    from abi.workflow import WorkflowCoordinator

    registry_data = yaml_lib.safe_load(registry.read_text(encoding="utf-8"))
    coordinator = WorkflowCoordinator()
    prepared = coordinator.prepare(
        "easymetagenome",
        overrides={
            "input": {"sample_sheet": str(manifest)},
            "workflow": {"preset": "p0_taxonomy"},
            "resources": {
                # expandvars replicates the retired _expand_registry_path
                "host_db": os.path.expandvars(str(registry_data["host_db"])),
                "kraken2_db": os.path.expandvars(str(registry_data["path"])),
            },
            "outdir": str(tmp_path / "result"),
            "log_dir": str(tmp_path / "logs"),
        },
        check_files=False,
        options=RuntimeOptions(engine="local"),
    )
    result = coordinator.run(prepared)
    assert result.status == "success"

    host_removed = tmp_path / "result/02_host_removal/S1"
    assert not (host_removed / "S1_1_kneaddata_paired_1.fastq").exists()
    assert not (host_removed / "_temp.sam").exists()
    assert not (host_removed / "S1_1_kneaddata_paired_1.fastq.gz").exists()
    cleanup_receipt = tmp_path / "result/provenance/intermediate_cleanup/S1.taxonomy.json"
    assert json.loads(cleanup_receipt.read_text(encoding="utf-8"))["dehost_read_pairs"] == 1
    assert (tmp_path / "result/tables/host_removal_summary.tsv").is_file()
    progress_events = [
        json.loads(line)
        for line in (tmp_path / "result/provenance/progress.jsonl").read_text().splitlines()
    ]
    compression_event = next(
        event
        for event in progress_events
        if event["event"] == "step_completed"
        and event["payload"]["step_id"] == "S1_host_removal_internal"
    )
    assert "workers=" in compression_event["payload"]["reason"]
    assert int(compression_event["payload"]["reason"].rsplit("workers=", 1)[1]) > 1
    assert (tmp_path / "result/execution_plan.json").is_file()
    assert (tmp_path / "result/provenance/commands.tsv").is_file()
    summary = json.loads(
        (tmp_path / "result/provenance/run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "success"
    # WP10: the legacy root-level alias files retired with P0Workflow.run();
    # the canonical artifacts carry the same information.
    canonical_paths = [
        "provenance/config.resolved.yaml",
        "provenance/run_summary.json",
        "provenance/commands.tsv",
        "provenance/audit_snapshot.json",
        "report/report.md",
        "report/report.html",
        "tables/host_removal_summary.tsv",
        "tables/taxonomy_abundance.tsv",
    ]
    assert all((tmp_path / "result" / path).stat().st_size > 0 for path in canonical_paths)
    resolved_config = yaml.safe_load(
        (tmp_path / "result/provenance/config.resolved.yaml").read_text(encoding="utf-8")
    )
    assert resolved_config["resources"]["host_db"] == str(host)
    assert resolved_config["resources"]["kraken2_db"] == str(database)

    # Canonical report manifest: the structured-result contract (WP7 keeps
    # tables/facts; figures belong to external tooling).
    report_manifest_path = tmp_path / "result/report/report_manifest.json"
    canonical_manifest = json.loads(report_manifest_path.read_text(encoding="utf-8"))
    assert canonical_manifest["schema_version"] == "abi.report-manifest.v1"
    assert canonical_manifest["workflow"] == "p0_taxonomy"
    assert canonical_manifest["sample_count"] == 1

    # WP10: resume reuses the persisted per-step evidence (history is never
    # overwritten; prior evidence is archived under provenance/previous_runs/).
    # WP10：恢复复用持久化的步骤级证据（历史不被覆盖；先前证据归档于
    # provenance/previous_runs/）。
    resumed_prepared = coordinator.prepare(
        "easymetagenome",
        overrides={
            "input": {"sample_sheet": str(manifest)},
            "workflow": {"preset": "p0_taxonomy"},
            "resources": {
                "host_db": os.path.expandvars(str(registry_data["host_db"])),
                "kraken2_db": os.path.expandvars(str(registry_data["path"])),
            },
            "outdir": str(tmp_path / "result"),
            "log_dir": str(tmp_path / "logs"),
        },
        check_files=False,
        options=RuntimeOptions(engine="local", resume=True),
    )
    resumed_result = coordinator.run(resumed_prepared)
    assert resumed_result.status == "success"

    second_summary = json.loads(
        (tmp_path / "result/provenance/run_summary.json").read_text(encoding="utf-8")
    )
    assert second_summary["run_id"] != summary["run_id"]
    if second_summary.get("resumes_run_id"):
        assert second_summary["resumes_run_id"] == summary["run_id"]
    assert (tmp_path / "result/report/report_manifest.json").is_file()


def test_humann4_dag_executes_end_to_end_with_fixture_tools(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    resources = {}
    for name in ("host_db", "humann_nucleotide_db", "humann_protein_db", "metaphlan_db"):
        path = tmp_path / name
        path.mkdir()
        resources[name] = str(path)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fixture_tool = bin_dir / "fixture_humann_tool.py"
    fixture_tool.write_text(
        """#!/usr/bin/env python3
import gzip
import json
import pathlib
import shutil
import sys

name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
def value(flag):
    return pathlib.Path(args[args.index(flag) + 1])
def write_table(path, feature):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# Feature\\tS1-RPKs\\n' + feature + '\\t4.5\\n')
if name == 'seqkit':
    print('file\\tnum_seqs\\tsum_len')
    print('reads.fastq.gz\\t1\\t4')
elif name == 'fastp':
    for flag in ('-o', '-O'):
        path = value(flag); path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, 'wt') as handle: handle.write('@r1\\nACGT\\n+\\nIIII\\n')
    report = value('-j'); report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'summary': {
        'before_filtering': {'total_reads': 2},
        'after_filtering': {'total_reads': 2, 'q30_rate': 1.0},
    }, 'filtering_result': {'passed_filter_reads': 2}}))
    value('-h').write_text('<html>fixture</html>\\n')
elif name == 'kneaddata':
    out = value('-o'); out.mkdir(parents=True, exist_ok=True)
    for suffix in ('paired_1.fastq', 'paired_2.fastq'):
        (out / ('S1_1_kneaddata_' + suffix)).write_text('@r1\\nACGT\\n+\\nIIII\\n')
elif name == 'humann':
    out = value('--output'); sample = args[args.index('--output-basename') + 1]
    write_table(out / (sample + '_genefamilies.tsv'), 'UniRef90_A')
    write_table(out / (sample + '_pathabundance.tsv'), 'PWY-1')
    write_table(out / (sample + '_pathcoverage.tsv'), 'PWY-1')
    temp = out / (sample + '_humann_temp'); temp.mkdir()
    (temp / 'translated.tsv').write_text('temporary\\n')
    (out / (sample + '.log')).write_text('retain this result log\\n')
elif name == 'humann_join_tables':
    write_table(value('--output'), 'UniRef90_A' if 'genefamilies' in args else 'PWY-1')
elif name in ('humann_renorm_table', 'humann_regroup_table'):
    source = value('--input')
    output_flag = '--output'
    destination = value(output_flag)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
elif name == 'humann_split_stratified_table':
    out = value('--output'); out.mkdir(parents=True, exist_ok=True)
    write_table(out / 'unstratified.tsv', 'UniRef90_A')
""",
        encoding="utf-8",
    )
    fixture_tool.chmod(0o755)
    for name in (
        "seqkit",
        "fastp",
        "kneaddata",
        "humann",
        "humann_join_tables",
        "humann_renorm_table",
        "humann_regroup_table",
        "humann_split_stratified_table",
    ):
        (bin_dir / name).symlink_to(fixture_tool)
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join((str(bin_dir), str(Path(sys.executable).parent), os.environ["PATH"])),
    )

    coordinator = WorkflowCoordinator()
    prepared = coordinator.prepare(
        "easymetagenome",
        overrides={
            "input": {"sample_sheet": str(manifest)},
            "workflow": {"preset": "p1_humann4"},
            "resources": resources,
            "threads": 1,
            "outdir": str(tmp_path / "result"),
            "log_dir": str(tmp_path / "logs"),
        },
        options=RuntimeOptions(engine="local", check_runtime=False),
    )
    runtime_result = coordinator.run(prepared)
    outputs = runtime_result.outputs

    summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
    assert summary["status"] == "success"
    assert summary["completed_step_count"] == len(prepared.plan.steps)
    functional_table = Path(prepared.config["outdir"]) / "tables/functional_abundance.tsv"
    assert len(functional_table.read_text(encoding="utf-8").splitlines()) > 1
    assert outputs["report_markdown"] == (
        Path(prepared.config["outdir"]) / "report/easymetagenome_functional_report.md"
    )
    manifest_payload = json.loads(outputs["report_manifest"].read_text(encoding="utf-8"))
    _assert_matches_canonical_report_schema(manifest_payload)
    assert manifest_payload["schema_version"] == "abi.report-manifest.v1"
    assert manifest_payload["workflow"] == "p1_humann4"
    assert manifest_payload["standard_tables"]["functional_abundance"] == {
        "path": str(functional_table),
        "rows": 10,
    }
    result_dir = Path(prepared.config["outdir"])
    assert not (result_dir / "01_preprocessing/S1/S1_1.fastq.gz").exists()
    assert not (result_dir / "01_preprocessing/S1/S1_2.fastq.gz").exists()
    assert not (result_dir / "02_host_removal/S1/S1_1_kneaddata_paired_1.fastq.gz").exists()
    assert not (result_dir / "02_host_removal/S1/S1_1_kneaddata_paired_2.fastq.gz").exists()
    assert not (result_dir / "04_function/sample/S1/S1.merged.fastq.gz").exists()
    assert not (result_dir / "04_function/sample/S1/S1_humann_temp").exists()
    assert (result_dir / "04_function/sample/S1/S1.log").is_file()
    cleanup_receipt = result_dir / "provenance/intermediate_cleanup/S1.json"
    assert json.loads(cleanup_receipt.read_text(encoding="utf-8"))["status"] == "success"
