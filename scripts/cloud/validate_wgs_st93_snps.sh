#!/usr/bin/env bash
set -euo pipefail

# Strict SNP comparison for the ST93 MRSA paper endpoint:
#   1. paper_spandx: SPANDx v2.6/default against JKD6159 CP002114, with the
#      paper context cohorts when available.
#   2. abi_bcftools: ABI-adjacent BWA/samtools/bcftools reconstruction on the
#      six PRJNA286158 study isolates.
#
# The script deliberately separates the paper-method distance endpoint from ABI reproduction.
# A six-isolate-only or non-SPANDx run must not be reported as paper-method recovery.

READ_ROOT=${READ_ROOT:-/root/autodl-tmp/abi-real-data/results/wgs_st93_mrsa_retry/01_qc}
PAPER_READ_ROOT=${PAPER_READ_ROOT:-/root/autodl-tmp/abi-real-data/raw/wgs_st93_mrsa_paper}
OUTPUT_ROOT=${OUTPUT_ROOT:-/root/autodl-tmp/abi-real-data/comparisons/wgs_st93_strict_snp_20260724}
REFERENCE_URL=${REFERENCE_URL:-https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=CP002114.2&rettype=fasta}
REFERENCE_CACHE=${REFERENCE_CACHE:-/root/autodl-tmp/abi-real-data/references/JKD6159_CP002114.2.fasta}
SPANDX_ROOT=${SPANDX_ROOT:-/root/autodl-tmp/tools/SPANDx_v2.6}
SPANDX_TARBALL_URL=${SPANDX_TARBALL_URL:-https://sourceforge.net/projects/spandx/files/SPANDx_v2.6_full.tar.gz/download}
BWA=${BWA:-/root/autodl-tmp/.mamba/envs/autoplasm-assembly/bin/bwa}
SAMTOOLS=${SAMTOOLS:-/root/autodl-tmp/.mamba/envs/autoplasm-assembly/bin/samtools}
BCFTOOLS=${BCFTOOLS:-/root/autodl-tmp/.mamba/envs/autoplasm-assembly/bin/bcftools}
PYTHON=${PYTHON:-/root/miniconda3/bin/python}
THREADS=${THREADS:-8}
MIN_DEPTH=${MIN_DEPTH:-10}
MIN_MAPQ=${MIN_MAPQ:-30}
MIN_BASEQ=${MIN_BASEQ:-20}
MIN_VARIANT_QUAL=${MIN_VARIANT_QUAL:-30}
DOWNLOAD_PAPER_CONTEXT=${DOWNLOAD_PAPER_CONTEXT:-0}
# Table S1 of PMCID PMC5359412 defines the 20 NT context isolates used by the
# paper out of the 498 runs hosted under PRJEB3144; only these may enter the
# paper-method input set.
PRJEB3144_TABLE_S1_RUNS=${PRJEB3144_TABLE_S1_RUNS:-"ERR182515 ERR182523 ERR182439 ERR182441 ERR182454 ERR182457 ERR192153 ERR192154 ERR192158 ERR192175 ERR192176 ERR192181 ERR192183 ERR192185 ERR192188 ERR192192 ERR192197 ERR192199 ERR192204 ERR192209"}
DOWNLOAD_WORKERS=${DOWNLOAD_WORKERS:-4}
INSTALL_SPANDX=${INSTALL_SPANDX:-0}
RUN_PAPER_SPANDX=${RUN_PAPER_SPANDX:-1}
RUN_ABI_BCFTOOLS=${RUN_ABI_BCFTOOLS:-1}
REQUIRE_PAPER_METHOD_INPUTS=${REQUIRE_PAPER_METHOD_INPUTS:-${REQUIRE_PAPER_EXACT_INPUTS:-1}}

study_runs=(SRR2057030 SRR2057031 SRR2057032 SRR2057033 SRR2057034 SRR2057035)
paper_context_projects=(PRJNA286158 PRJEB3144 PRJNA232112)

fail() {
    printf '%s\n' "$*" >&2
    exit 2
}

require_tool() {
    command -v "$1" >/dev/null || fail "Required command is unavailable: $1"
}

resolve_python() {
    if [[ -x ${PYTHON} ]]; then
        return 0
    fi
    if command -v "${PYTHON}" >/dev/null; then
        PYTHON=$(command -v "${PYTHON}")
        return 0
    fi
    for candidate in /root/miniconda3/bin/python /root/miniconda3/bin/python3 python3 python; do
        if [[ -x ${candidate} ]]; then
            PYTHON=${candidate}
            return 0
        fi
        if command -v "${candidate}" >/dev/null; then
            PYTHON=$(command -v "${candidate}")
            return 0
        fi
    done
    fail "Python is required; set PYTHON to a valid interpreter"
}

configure_spandx() {
    [[ -f ${SPANDX_ROOT}/SPANDx.config ]] || fail "Missing SPANDx.config in ${SPANDX_ROOT}"
    "${PYTHON}" - "${SPANDX_ROOT}/SPANDx.config" "${SPANDX_ROOT}" <<'PY'
import sys
from pathlib import Path

config = Path(sys.argv[1])
root = sys.argv[2]
lines = config.read_text().splitlines()
updated = []
seen = False
for line in lines:
        if line.startswith("SPANDx_LOCATION="):
            updated.append(f"SPANDx_LOCATION={root}")
            seen = True
        elif line.startswith("export PERL5LIB=$PERL5LIB:"):
            updated.append('export PERL5LIB="${PERL5LIB:-}":$SPANDx_LOCATION/perl')
        else:
            updated.append(line)
if not seen:
    updated.insert(0, f"SPANDx_LOCATION={root}")
config.write_text("\n".join(updated) + "\n")
PY
    # SPANDx v2.6 only supports PBS/SGE qsub scheduling. On single hosts
    # without a scheduler, install a qsub shim into SPANDx_LOCATION (which
    # SPANDx.config appends to PATH). The shim runs jobs concurrently in the
    # background up to QSUB_SHIM_MAX_JOBS and honours -W depend=afterok
    # ordering so per-sample jobs parallelize while the matrix stage still
    # waits for all per-sample jobs.
    if ! command -v qsub >/dev/null; then
        cat > "${SPANDX_ROOT}/qsub" <<'QSUB'
#!/usr/bin/env bash
# Concurrent qsub replacement installed by validate_wgs_st93_snps.sh.
# Parses -v key=value lists and -W depend=afterok:id lists, ignores other
# scheduling flags, runs the job script in the background, and prints a fake
# job id on stdout. Completion markers live in .qsub_shim_state/ so the
# caller can wait for the whole batch and inspect per-job exit codes.
max_jobs=${QSUB_SHIM_MAX_JOBS:-8}
# Live-tunable override: edit qsub_max_jobs next to this shim to change the
# concurrency of an in-flight run without restarting it.
override="$(cd "$(dirname "$0")" && pwd)/qsub_max_jobs"
if [[ -f ${override} ]]; then
    max_jobs=$(cat "${override}")
fi
vars=()
deps=()
script=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -v)
            IFS=',' read -ra kv <<< "$2"
            vars+=("${kv[@]}")
            shift 2
            ;;
        -W*afterok*)
            # SPANDx passes "-W depend=afterok:id1:id2" as a single argument.
            dep_spec=${1#*afterok}
            IFS=':' read -ra dep_list <<< "${dep_spec}"
            for dep in "${dep_list[@]}"; do
                [[ -n ${dep} ]] && deps+=("${dep}")
            done
            shift
            ;;
        -W)
            dep_spec=${2#*afterok}
            IFS=':' read -ra dep_list <<< "${dep_spec}"
            for dep in "${dep_list[@]}"; do
                [[ -n ${dep} ]] && deps+=("${dep}")
            done
            shift 2
            ;;
        -N|-j|-m|-M|-l|-o|-e|-q|-S)
            shift 2
            ;;
        -*)
            shift
            ;;
        *)
            script=$1
            shift
            ;;
    esac
done
if [[ -z ${script} ]]; then
    echo "qsub-shim: no job script supplied" >&2
    exit 1
fi
state="$(pwd)/.qsub_shim_state"
mkdir -p "${state}"
id="shim-$$-${RANDOM}${RANDOM}"
# Throttle: keep at most max_jobs jobs in flight. The override file is
# re-read on every iteration so concurrency can be raised live.
while :; do
    if [[ -f ${override} ]]; then
        max_jobs=$(cat "${override}")
    fi
    submitted=$([[ -f ${state}/jobs.txt ]] && wc -l <"${state}/jobs.txt" || echo 0)
    finished=$(find "${state}" -name '*.done' 2>/dev/null | wc -l)
    (( submitted - finished < max_jobs )) && break
    sleep 5
done
echo "${id}" >>"${state}/jobs.txt"
log="${state}/${id}.log"
(
    for dep in "${deps[@]}"; do
        while [[ ! -e ${state}/${dep}.done ]]; do
            sleep 5
        done
        # afterok semantics: a failed dependency fails the dependent job.
        if [[ -f ${state}/${dep}.rc && $(cat "${state}/${dep}.rc") != 0 ]]; then
            echo "qsub-shim: dependency ${dep} exited non-zero" >&2
            echo 1 >"${state}/${id}.rc"
            touch "${state}/${id}.done"
            exit 1
        fi
    done
    env "${vars[@]}" bash "${script}" >"${log}" 2>&1
    echo $? >"${state}/${id}.rc"
    touch "${state}/${id}.done"
) >/dev/null 2>&1 </dev/null &
echo "${id}"
exit 0
QSUB
        chmod +x "${SPANDX_ROOT}/qsub"
    fi
}

spandx_toolchain_ready() {
    [[ -x ${SPANDX_ROOT}/SPANDx.sh ]] || return 1
    configure_spandx
    # Legacy bundled binaries exit non-zero when printing usage; capture their
    # output instead of piping so pipefail does not mask a working toolchain.
    local bwa_out samtools_out
    bwa_out=$("${SPANDX_ROOT}/bwa" 2>&1 || true)
    samtools_out=$("${SPANDX_ROOT}/samtools" 2>&1 || true)
    grep -q 'Version:' <<<"${bwa_out}" || return 1
    grep -Eq 'Version|Program|Usage|samtools' <<<"${samtools_out}" || return 1
    # SPANDx v2.6 bundles neither GATK (license) nor a JRE; both must be
    # provided separately for the legacy UnifiedGenotyper calls.
    [[ -f ${SPANDX_ROOT}/GenomeAnalysisTK.jar ]] || return 1
    command -v java >/dev/null || return 1
}

[[ ! -e ${OUTPUT_ROOT} ]] || fail "Immutable output already exists: ${OUTPUT_ROOT}"
require_tool curl
require_tool awk
resolve_python
mkdir -p "${OUTPUT_ROOT}/reference" "${OUTPUT_ROOT}/paper_spandx" "${OUTPUT_ROOT}/abi_bcftools"

reference=${OUTPUT_ROOT}/reference/JKD6159_CP002114.2.fasta
if [[ -s ${REFERENCE_CACHE} ]] && grep -q '^>CP002114.2' "${REFERENCE_CACHE}"; then
    cp "${REFERENCE_CACHE}" "${reference}"
else
    # NCBI efetch intermittently resets HTTP/2 streams; retry all error kinds.
    curl --fail --location --retry 8 --retry-all-errors --retry-delay 15 \
        --output "${reference}" "${REFERENCE_URL}"
    grep -q '^>CP002114.2' "${reference}" || fail "Unexpected reference FASTA header"
fi
# SPANDx and its bundled BWA/GATK reject FASTA files containing blank lines or
# CR line endings; normalize in place immediately after download.
awk '{sub(/\r$/, "")} NF > 0' "${reference}" > "${reference}.normalized"
mv "${reference}.normalized" "${reference}"
if [[ ! -s ${REFERENCE_CACHE} ]]; then
    mkdir -p "$(dirname "${REFERENCE_CACHE}")"
    cp "${reference}" "${REFERENCE_CACHE}"
fi

download_ena_project() {
    local project=$1
    local destination=${PAPER_READ_ROOT}/${project}
    local allowlist=""
    if [[ ${project} == PRJEB3144 ]]; then
        allowlist=${PRJEB3144_TABLE_S1_RUNS}
    fi
    mkdir -p "${destination}"
    local report=${destination}/ena_read_run_report.tsv
    curl --fail --location --retry 4 \
        --output "${report}" \
        "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=${project}&result=read_run&fields=run_accession,sample_alias,library_layout,fastq_ftp,fastq_md5&format=tsv"
    "${PYTHON}" - "${report}" "${destination}" "${allowlist}" "${DOWNLOAD_WORKERS}" <<'PY'
import csv
import hashlib
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

report = Path(sys.argv[1])
destination = Path(sys.argv[2])
allowlist = set(sys.argv[3].split())
workers = max(1, int(sys.argv[4]))
manifest = destination / "download_manifest.tsv"
rows = list(csv.DictReader(report.open(newline=""), delimiter="\t"))


def fetch(task):
    run, alias, index, url, expected_md5, target = task
    status = "present"
    if not target.exists():
        part = target.with_name(target.name + ".part")
        for attempt in range(3):
            try:
                urllib.request.urlretrieve(url, part)
                part.rename(target)
                break
            except Exception:
                part.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                time.sleep(10)
        status = "downloaded"
    if expected_md5:
        hasher = hashlib.md5()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest != expected_md5:
            target.unlink()
            raise SystemExit(f"MD5 mismatch for {target}: {digest} != {expected_md5}")
    return [run, alias, index, url, expected_md5, str(target), status]


records = []
tasks = []
for row in rows:
    run = row["run_accession"]
    alias = row.get("sample_alias", "")
    if allowlist and run not in allowlist:
        records.append([run, alias, "", "", "", "", "skipped_not_in_table_s1"])
        continue
    urls = [value for value in row["fastq_ftp"].split(";") if value]
    md5s = [value for value in row["fastq_md5"].split(";") if value]
    if len(urls) != 2:
        records.append([run, alias, "", "", "", "", "skipped_non_paired"])
        continue
    for index, url in enumerate(urls, start=1):
        expected_md5 = md5s[index - 1] if index <= len(md5s) else ""
        target = destination / f"{run}_{index}_sequence.fastq.gz"
        tasks.append((run, alias, index, "https://" + url, expected_md5, target))

with ThreadPoolExecutor(max_workers=workers) as pool:
    records.extend(pool.map(fetch, tasks))

with manifest.open("w", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t")
    writer.writerow(["run_accession", "sample_alias", "mate", "url", "md5", "path", "status"])
    writer.writerows(records)
PY
}

if [[ ${DOWNLOAD_PAPER_CONTEXT} == 1 ]]; then
    for project in "${paper_context_projects[@]}"; do
        download_ena_project "${project}"
    done
fi

if [[ ${INSTALL_SPANDX} == 1 && ! -x ${SPANDX_ROOT}/SPANDx.sh ]]; then
    mkdir -p "$(dirname "${SPANDX_ROOT}")"
    tmpdir=$(mktemp -d)
    trap 'rm -rf "${tmpdir}"' EXIT
    curl --fail --location --retry 4 --output "${tmpdir}/spandx.tar.gz" "${SPANDX_TARBALL_URL}"
    tar -xzf "${tmpdir}/spandx.tar.gz" -C "${tmpdir}"
    candidate=$(find "${tmpdir}" -maxdepth 3 -name SPANDx.sh -type f | head -1)
    [[ -n ${candidate} ]] || fail "SPANDx.sh was not found in ${SPANDX_TARBALL_URL}"
    mv "$(dirname "${candidate}")" "${SPANDX_ROOT}"
    configure_spandx
fi

find_read_pair() {
    local root=$1
    local run=$2
    local r1=""
    local r2=""
    for candidate in \
        "${root}/${run}/${run}_R1.clean.fastq.gz" \
        "${root}/${run}/${run}_1.fastq.gz" \
        "${root}/${run}_1_sequence.fastq.gz" \
        "${root}/PRJNA286158/${run}_1_sequence.fastq.gz" \
        "${root}/${run}_R1.clean.fastq.gz"; do
        if [[ -s ${candidate} ]]; then
            r1=${candidate}
            break
        fi
    done
    for candidate in \
        "${root}/${run}/${run}_R2.clean.fastq.gz" \
        "${root}/${run}/${run}_2.fastq.gz" \
        "${root}/${run}_2_sequence.fastq.gz" \
        "${root}/PRJNA286158/${run}_2_sequence.fastq.gz" \
        "${root}/${run}_R2.clean.fastq.gz"; do
        if [[ -s ${candidate} ]]; then
            r2=${candidate}
            break
        fi
    done
    [[ -n ${r1} && -n ${r2} ]] || return 1
    printf '%s\t%s\n' "${r1}" "${r2}"
}

write_literature_provenance() {
    cat > "${OUTPUT_ROOT}/literature_endpoint.tsv" <<'EOF'
field	value	source
paper	Whole genome sequencing to investigate a putative outbreak of ST93 MRSA	PMCID: PMC5359412
study_isolate_project	PRJNA286158	PMCID: PMC5359412 Data Summary
additional_nt_context_project	PRJEB3144	PMCID: PMC5359412 Data Summary
existing_st93_context_project	PRJNA232112	PMCID: PMC5359412 Data Bibliography
reference	JKD6159 ST93 chromosome GenBank CP002114	PMCID: PMC5359412 Methods
paper_snp_tool	SPANDx v2.6 default	PMCID: PMC5359412 Methods
paper_context	community isolates plus NT and previously published ST93 isolates	PMCID: PMC5359412 Methods
mobile_genetic_elements_excluded	false	PMCID: PMC5359412 Methods
published_six_isolate_pairwise_min	7	PMCID: PMC5359412 Results
published_six_isolate_pairwise_max	60	PMCID: PMC5359412 Results
published_six_isolate_pairwise_mean	44	PMCID: PMC5359412 Results
EOF
}

write_literature_provenance

run_paper_spandx() {
    local work=${OUTPUT_ROOT}/paper_spandx/work
    mkdir -p "${work}"
    if [[ ! -x ${SPANDX_ROOT}/SPANDx.sh ]]; then
        cat > "${OUTPUT_ROOT}/paper_spandx/status.tsv" <<EOF
track	status	reason
paper_spandx	blocked	SPANDx v2.6 is unavailable; set INSTALL_SPANDX=1 or SPANDX_ROOT to a validated v2.6 installation
EOF
        [[ ${REQUIRE_PAPER_METHOD_INPUTS} == 1 ]] && fail "SPANDx v2.6 unavailable for strict paper-method distance endpoint recovery"
        return 0
    fi
    if ! spandx_toolchain_ready; then
        cat > "${OUTPUT_ROOT}/paper_spandx/status.tsv" <<EOF
track	status	reason
paper_spandx	blocked	SPANDx v2.6 legacy bundled toolchain is not runnable; commonly this means libncurses.so.5 is missing for the bundled samtools, or GenomeAnalysisTK.jar/java is unavailable
EOF
        [[ ${REQUIRE_PAPER_METHOD_INPUTS} == 1 ]] && fail "SPANDx v2.6 legacy bundled toolchain is not runnable"
        return 0
    fi

    cp "${reference}" "${work}/JKD6159_CP002114.fasta"
    local linked=0
    printf 'run_accession\tcohort\tread1\tread2\n' > "${OUTPUT_ROOT}/paper_spandx/inputs.tsv"
    for project in "${paper_context_projects[@]}"; do
        local project_root=${PAPER_READ_ROOT}/${project}
        if [[ -d ${project_root} ]]; then
            while IFS= read -r r1; do
                local base
                local run
                local r2
                base=$(basename "${r1}")
                run=${base%%_1_sequence.fastq.gz}
                r2=${r1/_1_sequence.fastq.gz/_2_sequence.fastq.gz}
                [[ -s ${r2} ]] || continue
                ln -sf "${r1}" "${work}/${run}_1_sequence.fastq.gz"
                ln -sf "${r2}" "${work}/${run}_2_sequence.fastq.gz"
                printf '%s\t%s\t%s\t%s\n' "${run}" "${project}" "${r1}" "${r2}" \
                    >> "${OUTPUT_ROOT}/paper_spandx/inputs.tsv"
                linked=$((linked + 1))
            done < <(find "${project_root}" -maxdepth 1 -name '*_1_sequence.fastq.gz' -type f | sort)
        fi
    done
    if (( linked == 0 )); then
        for run in "${study_runs[@]}"; do
            pair=$(find_read_pair "${READ_ROOT}" "${run}") \
                || fail "Missing six-isolate read pair for ${run}; cannot run paper_spandx fallback"
            r1=${pair%%$'\t'*}
            r2=${pair#*$'\t'}
            ln -sf "${r1}" "${work}/${run}_1_sequence.fastq.gz"
            ln -sf "${r2}" "${work}/${run}_2_sequence.fastq.gz"
            printf '%s\t%s\t%s\t%s\n' "${run}" "PRJNA286158_cleaned_fallback" "${r1}" "${r2}" \
                >> "${OUTPUT_ROOT}/paper_spandx/inputs.tsv"
            linked=$((linked + 1))
        done
    fi
    if [[ ${REQUIRE_PAPER_METHOD_INPUTS} == 1 && ${linked} -lt 26 ]]; then
        fail "Paper-method distance endpoint recovery requires paper context reads; found ${linked}. Set DOWNLOAD_PAPER_CONTEXT=1 or REQUIRE_PAPER_METHOD_INPUTS=0 for partial run."
    fi

    if ! (
        cd "${work}"
        "${SPANDX_ROOT}/SPANDx.sh" -r JKD6159_CP002114 -m yes -t Illumina -p PE
    ) > "${OUTPUT_ROOT}/paper_spandx/spandx.stdout.log" 2> "${OUTPUT_ROOT}/paper_spandx/spandx.stderr.log"; then
        cat > "${OUTPUT_ROOT}/paper_spandx/status.tsv" <<EOF
track	status	reason
paper_spandx	blocked	SPANDx v2.6 exited non-zero; inspect spandx.stdout.log and spandx.stderr.log for the stage that failed
EOF
            [[ ${REQUIRE_PAPER_METHOD_INPUTS} == 1 ]] && fail "SPANDx v2.6 run failed under strict paper-method distance endpoint recovery"
        return 0
    fi

    # The qsub shim runs jobs in the background; SPANDx.sh returns after
    # submission. Wait for every submitted job and surface per-job failures.
    local shim_state=${work}/.qsub_shim_state
    if [[ -d ${shim_state} ]]; then
        while :; do
            local submitted finished
            submitted=$([[ -f ${shim_state}/jobs.txt ]] && wc -l <"${shim_state}/jobs.txt" || echo 0)
            finished=$(find "${shim_state}" -name '*.done' | wc -l)
            (( finished >= submitted )) && break
            sleep 30
        done
        local rc_failures=0
        local rc_file
        for rc_file in "${shim_state}"/*.rc; do
            [[ -e ${rc_file} ]] || continue
            [[ $(cat "${rc_file}") == 0 ]] || rc_failures=$((rc_failures + 1))
        done
        if (( rc_failures > 0 )); then
            cat > "${OUTPUT_ROOT}/paper_spandx/status.tsv" <<EOF
track	status	reason
paper_spandx	blocked	${rc_failures} qsub-shim jobs exited non-zero; inspect ${shim_state}/*.rc and *.log
EOF
            [[ ${REQUIRE_PAPER_METHOD_INPUTS} == 1 ]] && fail "SPANDx v2.6 shim jobs failed under strict paper-method distance endpoint recovery"
            return 0
        fi
    fi

    local matrix
    matrix=$(find "${work}" -name 'Ortho_SNP_matrix.nex' -o -name '*SNP_matrix*.nex' | head -1)
    [[ -n ${matrix} ]] || fail "SPANDx completed without a SNP matrix"
    cp "${matrix}" "${OUTPUT_ROOT}/paper_spandx/Ortho_SNP_matrix.nex"
    "${PYTHON}" - "${OUTPUT_ROOT}" paper_spandx "${OUTPUT_ROOT}/paper_spandx/Ortho_SNP_matrix.nex" "${study_runs[@]}" <<'PY'
import csv
import itertools
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
track = sys.argv[2]
matrix_path = Path(sys.argv[3])
study_runs = sys.argv[4:]
in_matrix = False
taxlabels = []
rows = []
for line in matrix_path.read_text(errors="replace").splitlines():
    stripped = line.strip()
    if not stripped:
        continue
    lowered = stripped.lower()
    if lowered.startswith("taxlabels"):
        taxlabels = [label.rstrip(";") for label in stripped.split()[1:]]
        continue
    if lowered.startswith("matrix"):
        in_matrix = True
        continue
    if in_matrix and stripped.startswith(";"):
        break
    if in_matrix:
        rows.append(stripped)

seqs = {}
if taxlabels:
    # SPANDx Ortho_SNP_matrix.nex is a transposed nexus: one row per SNP site
    # with one base per taxon declared in taxlabels.
    columns = {label: [] for label in taxlabels}
    for row in rows:
        parts = row.rstrip(";").split()
        bases = parts[1:]
        if len(bases) == 1 and len(bases[0]) == len(taxlabels):
            bases = list(bases[0])
        if len(bases) != len(taxlabels):
            raise SystemExit(f"Unexpected transposed SNP matrix row: {row}")
        for label, base in zip(taxlabels, bases):
            columns[label].append(base.upper())
    seqs = {label: "".join(bases) for label, bases in columns.items()}
else:
    for row in rows:
        parts = row.rstrip(",").split()
        if len(parts) >= 2:
            seqs[parts[0]] = parts[1].upper()

selected = {}
for run in study_runs:
    matches = [name for name in seqs if name == run or name.startswith(run)]
    if matches:
        selected[run] = seqs[matches[0]]
missing = [run for run in study_runs if run not in selected]
if missing:
    raise SystemExit(f"Missing study isolates in SPANDx matrix: {missing}")

distances = []
for left, right in itertools.combinations(study_runs, 2):
    distance = sum(
        a != b and a not in {"N", "-", "?", "."} and b not in {"N", "-", "?", "."}
        for a, b in zip(selected[left], selected[right])
    )
    distances.append({"sample_a": left, "sample_b": right, "snp_distance": distance})

outdir = root / track
with (outdir / "pairwise_snp_distances.tsv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["sample_a", "sample_b", "snp_distance"], delimiter="\t")
    writer.writeheader()
    writer.writerows(distances)

values = [row["snp_distance"] for row in distances]
summary = {
    "schema_version": "abi.wgs_strict_snp_comparison.v1",
    "track": track,
    "method": "SPANDx v2.6 default, explicit -m yes -t Illumina -p PE",
    "reference": "JKD6159 CP002114",
    "study_sample_count": len(study_runs),
    "matrix_sample_count": len(seqs),
    "study_pairwise_min": min(values),
    "study_pairwise_median": statistics.median(values),
    "study_pairwise_max": max(values),
    "published_six_isolate_range": {"min": 7, "max": 60, "mean": 44},
    "range_matches_published": min(values) == 7 and max(values) == 60,
    "paper_reproduction_status": (
        "paper_method_distance_endpoint_recovered"
        if len(seqs) >= 26
        else "paper_method_partial_context"
    ),
}
(outdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
PY
}

run_abi_bcftools() {
    for tool in "${BWA}" "${SAMTOOLS}" "${BCFTOOLS}"; do
        [[ -x ${tool} ]] || fail "Required executable is unavailable: ${tool}"
    done
    "${SAMTOOLS}" --version 2>&1 | grep -q '^samtools 1\.' \
        || fail "samtools must support the modern 'sort -o FILE' interface"
    "${BCFTOOLS}" --version 2>&1 | grep -q '^bcftools 1\.' \
        || fail "bcftools 1.x is required"

    local out=${OUTPUT_ROOT}/abi_bcftools
    mkdir -p "${out}/bam" "${out}/vcf"
    "${BWA}" index "${reference}"

    printf 'sample\tread1\tread2\tbam\n' > "${out}/inputs.tsv"
    bams=()
    for sample in "${study_runs[@]}"; do
        pair=$(find_read_pair "${READ_ROOT}" "${sample}") || fail "Missing ABI read pair for ${sample}"
        read1=${pair%%$'\t'*}
        read2=${pair#*$'\t'}
        bam=${out}/bam/${sample}.sorted.bam
        # bwa 0.7.19 errors on literal TAB characters in -R (E::bwa_set_rg);
        # pass escaped \t sequences, which bwa converts to TABs itself.
        read_group="@RG\\tID:${sample}\\tSM:${sample}\\tPL:ILLUMINA"
        "${BWA}" mem -t "${THREADS}" \
            -R "${read_group}" \
            "${reference}" "${read1}" "${read2}" \
            | "${SAMTOOLS}" sort -@ "${THREADS}" -o "${bam}" -
        "${SAMTOOLS}" index "${bam}"
        "${SAMTOOLS}" flagstat -@ "${THREADS}" "${bam}" > "${out}/bam/${sample}.flagstat.txt"
        printf '%s\t%s\t%s\t%s\n' "${sample}" "${read1}" "${read2}" "${bam}" >> "${out}/inputs.tsv"
        bams+=("${bam}")
    done

    raw_vcf=${out}/vcf/joint.raw.vcf.gz
    filtered_vcf=${out}/vcf/joint.biallelic_snps.dp${MIN_DEPTH}.q${MIN_VARIANT_QUAL}.vcf.gz
    "${BCFTOOLS}" mpileup --threads "${THREADS}" -Ou -f "${reference}" \
        -q "${MIN_MAPQ}" -Q "${MIN_BASEQ}" -a FORMAT/DP "${bams[@]}" \
        | "${BCFTOOLS}" call --threads "${THREADS}" --ploidy 1 -mv -Oz -o "${raw_vcf}"
    "${BCFTOOLS}" index -t "${raw_vcf}"
    "${BCFTOOLS}" view --threads "${THREADS}" -m2 -M2 -v snps -Ou "${raw_vcf}" \
        | "${BCFTOOLS}" filter --threads "${THREADS}" \
            -i "QUAL>=${MIN_VARIANT_QUAL} && MIN(FMT/DP)>=${MIN_DEPTH}" \
            -Oz -o "${filtered_vcf}"
    "${BCFTOOLS}" index -t "${filtered_vcf}"
    "${BCFTOOLS}" query -l "${filtered_vcf}" > "${out}/sample_order.txt"
    "${BCFTOOLS}" query -f '%CHROM\t%POS\t%REF\t%ALT[\t%GT\t%DP]\n' "${filtered_vcf}" \
        > "${out}/snp_genotypes.tsv"

    printf 'sample\tcallable_bases_dp_ge_%s\treference_bases\tcallable_fraction\n' "${MIN_DEPTH}" \
        > "${out}/callable_sites.tsv"
    reference_bases=$(awk '!/^>/{gsub(/[^ACGTacgt]/, ""); n+=length($0)} END{print n}' "${reference}")
    for sample in "${study_runs[@]}"; do
        bam=${out}/bam/${sample}.sorted.bam
        callable=$("${SAMTOOLS}" depth -aa -q "${MIN_BASEQ}" -Q "${MIN_MAPQ}" "${bam}" \
            | awk -v minimum="${MIN_DEPTH}" '$3 >= minimum {count++} END {print count+0}')
        awk -v sample="${sample}" -v callable="${callable}" -v total="${reference_bases}" \
            'BEGIN {printf "%s\t%d\t%d\t%.8f\n", sample, callable, total, callable/total}' \
            >> "${out}/callable_sites.tsv"
    done

    "${PYTHON}" - "${OUTPUT_ROOT}" abi_bcftools <<'PY'
import csv
import itertools
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
track = sys.argv[2]
outdir = root / track
samples = outdir.joinpath("sample_order.txt").read_text().splitlines()
sequences = {sample: [] for sample in samples}
site_count = 0
with outdir.joinpath("snp_genotypes.tsv").open(newline="") as handle:
    for row in csv.reader(handle, delimiter="\t"):
        if not row:
            continue
        genotype_depth = row[4:]
        genotypes = genotype_depth[0::2]
        if len(genotypes) != len(samples) or any(gt in {".", "./."} for gt in genotypes):
            continue
        for sample, genotype in zip(samples, genotypes):
            sequences[sample].append(genotype)
        site_count += 1

distances = []
matrix = {sample: {other: 0 for other in samples} for sample in samples}
for left, right in itertools.combinations(samples, 2):
    distance = sum(a != b for a, b in zip(sequences[left], sequences[right]))
    matrix[left][right] = distance
    matrix[right][left] = distance
    distances.append({"sample_a": left, "sample_b": right, "snp_distance": distance})

with outdir.joinpath("pairwise_snp_distances.tsv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["sample_a", "sample_b", "snp_distance"], delimiter="\t")
    writer.writeheader()
    writer.writerows(distances)

with outdir.joinpath("snp_distance_matrix.tsv").open("w", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t")
    writer.writerow(["sample", *samples])
    for sample in samples:
        writer.writerow([sample, *(matrix[sample][other] for other in samples)])

values = [row["snp_distance"] for row in distances]
callable_rows = list(csv.DictReader(outdir.joinpath("callable_sites.tsv").open(), delimiter="\t"))
summary = {
    "schema_version": "abi.wgs_strict_snp_comparison.v1",
    "track": track,
    "method": "BWA mem + samtools + bcftools haploid joint biallelic SNP calling",
    "reference": "JKD6159 CP002114.2",
    "study_sample_count": len(samples),
    "high_quality_variable_sites": site_count,
    "pairwise_comparisons": len(values),
    "study_pairwise_min": min(values),
    "study_pairwise_median": statistics.median(values),
    "study_pairwise_max": max(values),
    "published_six_isolate_range": {"min": 7, "max": 60, "mean": 44},
    "range_matches_published": min(values) == 7 and max(values) == 60,
    "paper_reproduction_status": "abi_reproduction_not_paper_method",
    "callable_fraction_min": min(float(row["callable_fraction"]) for row in callable_rows),
    "callable_fraction_max": max(float(row["callable_fraction"]) for row in callable_rows),
    "mobile_genetic_elements_excluded": False,
    "benchmark_outcomes_used": False,
}
outdir.joinpath("summary.json").write_text(json.dumps(summary, indent=2) + "\n")
PY
}

[[ ${RUN_PAPER_SPANDX} == 1 ]] && run_paper_spandx
[[ ${RUN_ABI_BCFTOOLS} == 1 ]] && run_abi_bcftools

"${PYTHON}" - "${OUTPUT_ROOT}" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for track in ("paper_spandx", "abi_bcftools"):
    summary_path = root / track / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        rows.append(
            {
                "track": track,
                "method": summary["method"],
                "status": summary["paper_reproduction_status"],
                "sample_count": summary.get("matrix_sample_count", summary.get("study_sample_count", "")),
                "study_pairwise_min": summary["study_pairwise_min"],
                "study_pairwise_median": summary["study_pairwise_median"],
                "study_pairwise_max": summary["study_pairwise_max"],
                "published_min": summary["published_six_isolate_range"]["min"],
                "published_mean": summary["published_six_isolate_range"]["mean"],
                "published_max": summary["published_six_isolate_range"]["max"],
                "range_matches_published": summary["range_matches_published"],
            }
        )
    else:
        status_path = root / track / "status.tsv"
        status = "not_run"
        if status_path.exists():
            status = "blocked"
        rows.append(
            {
                "track": track,
                "method": "",
                "status": status,
                "sample_count": "",
                "study_pairwise_min": "",
                "study_pairwise_median": "",
                "study_pairwise_max": "",
                "published_min": 7,
                "published_mean": 44,
                "published_max": 60,
                "range_matches_published": "",
            }
        )

with (root / "strict_snp_comparison.tsv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)
PY

{
    printf 'key\tvalue\n'
    printf 'completed_at\t%s\n' "$(date -Is)"
    printf 'hostname\t%s\n' "$(hostname)"
    printf 'reference_url\t%s\n' "${REFERENCE_URL}"
    printf 'reference_sha256\t%s\n' "$(sha256sum "${reference}" | awk '{print $1}')"
    printf 'spandx_root\t%s\n' "${SPANDX_ROOT}"
    printf 'spandx_config_location\t%s\n' "$(grep '^SPANDx_LOCATION=' "${SPANDX_ROOT}/SPANDx.config" 2>/dev/null | head -1 || true)"
    printf 'download_paper_context\t%s\n' "${DOWNLOAD_PAPER_CONTEXT}"
    printf 'install_spandx\t%s\n' "${INSTALL_SPANDX}"
    printf 'require_paper_method_inputs\t%s\n' "${REQUIRE_PAPER_METHOD_INPUTS}"
    printf 'bwa_version\t%s\n' "$("${BWA}" 2>&1 | sed -n 's/^Version: //p' | head -1 || true)"
    printf 'samtools_version\t%s\n' "$("${SAMTOOLS}" --version | head -1)"
    printf 'bcftools_version\t%s\n' "$("${BCFTOOLS}" --version | head -1)"
    printf 'python\t%s\n' "${PYTHON}"
    printf 'python_version\t%s\n' "$("${PYTHON}" --version 2>&1)"
} > "${OUTPUT_ROOT}/provenance.tsv"

(
    cd "${OUTPUT_ROOT}"
    sha256sum literature_endpoint.tsv provenance.tsv strict_snp_comparison.tsv \
        */summary.json */pairwise_snp_distances.tsv 2>/dev/null > SHA256SUMS || true
    [[ -s SHA256SUMS ]] && sha256sum -c SHA256SUMS >/dev/null
)

printf 'Strict SNP comparison complete: %s\n' "${OUTPUT_ROOT}"
cat "${OUTPUT_ROOT}/strict_snp_comparison.tsv"
