#!/usr/bin/env bash
set -euo pipefail

resource_parent=${ABI_RESOURCE_PARENT:-/root/autodl-tmp/resources/autoplasm}
target=${resource_parent}/kraken2_pluspf_20240605
identity_dir=${resource_parent}/identities
identity=${identity_dir}/kraken2_pluspf_20240605.json
archive=${resource_parent}/.k2_pluspf_20240605.tar.gz
source_url=https://genome-idx.s3.amazonaws.com/kraken/k2_pluspf_20240605.tar.gz
checksums_url=https://genome-idx.s3.amazonaws.com/kraken/pluspf_20240605/pluspf.md5
archive_md5=8ae51462e36cc9b55f7b454dcd65767f
lock_file=${resource_parent}/.k2_pluspf_20240605.lock

mkdir -p "${resource_parent}"
exec 9>"${lock_file}"
flock -n 9 || { echo "PlusPF installer is already running" >&2; exit 75; }

if [[ -s ${target}/hash.k2d && -s ${target}/opts.k2d && -s ${target}/taxo.k2d \
      && -s ${identity} ]]; then
  echo "PlusPF 20240605 is already installed at ${target}"
  exit 0
fi
[[ ! -e ${target} ]] || { echo "Refusing to overwrite incomplete target: ${target}" >&2; exit 1; }

available_bytes=$(df --output=avail -B1 "${resource_parent}" | tail -n 1 | tr -d ' ')
minimum_bytes=$((155 * 1024 * 1024 * 1024))
(( available_bytes >= minimum_bytes )) || {
  echo "At least 155 GiB free is required for atomic download and extraction" >&2
  exit 1
}

if command -v aria2c >/dev/null 2>&1; then
  aria2c --continue=true --max-connection-per-server=16 --split=16 \
    --min-split-size=64M --file-allocation=none \
    --dir "${resource_parent}" --out "$(basename "${archive}").part" "${source_url}"
else
  curl --fail --location --retry 8 --retry-all-errors --continue-at - \
    --output "${archive}.part" "${source_url}"
fi
mv "${archive}.part" "${archive}"
printf '%s  %s\n' "${archive_md5}" "${archive}" | md5sum --check --status
archive_sha256=$(sha256sum "${archive}" | awk '{print $1}')

staging=$(mktemp -d "${resource_parent}/.kraken2_pluspf_20240605.staging.XXXXXX")
cleanup() {
  if [[ ${staging} == "${resource_parent}/.kraken2_pluspf_20240605.staging."* ]]; then
    rm -rf -- "${staging}"
  fi
}
trap cleanup EXIT

tar xzf "${archive}" -C "${staging}"
curl --fail --location --retry 5 --output "${staging}/pluspf.md5" "${checksums_url}"
(
  cd "${staging}"
  md5sum --check --status pluspf.md5
)
for required in hash.k2d opts.k2d taxo.k2d database150mers.kmer_distrib; do
  [[ -s ${staging}/${required} ]] || { echo "Missing extracted file: ${required}" >&2; exit 1; }
done

content_sha256=$(PYTHONPATH="$(cd "$(dirname "$0")/../.." && pwd)/src" \
  python -c 'import sys; from abi.workflow.manifest import checksum_path; print(checksum_path(sys.argv[1]))' \
  "${staging}")
mkdir -p "${identity_dir}"
identity_staging=$(mktemp "${identity_dir}/.kraken2_pluspf_20240605.XXXXXX")
cat >"${identity_staging}" <<EOF
{
  "database_id": "kraken2_pluspf",
  "version": "pluspf_20240605",
  "source_url": "${source_url}",
  "publisher_md5_url": "${checksums_url}",
  "archive_md5": "${archive_md5}",
  "archive_sha256": "${archive_sha256}",
  "content_sha256": "${content_sha256}"
}
EOF

mv -T "${staging}" "${target}"
staging=
mv -T "${identity_staging}" "${identity}"
rm -f -- "${archive}"
echo "Installed PlusPF 20240605 at ${target} (archive SHA-256 ${archive_sha256})"
