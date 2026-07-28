#!/usr/bin/env bash
# Install the upstream SCAPP and PlasClass Python packages reproducibly.
#
# Both projects publish distribution names ending in "-dpellow" while their
# repository and import names omit that suffix. Their setup.py dependency
# pins also predate the substitutions validated for ABI's Python 3.8 Conda
# environment. Runtime dependencies are therefore owned by environments.yaml,
# and only the two packages themselves are installed here.

set -euo pipefail

PYTHON_BIN="${1:?usage: install_scapp_packages.sh /path/to/python}"
PLASCLASS_COMMIT="bcf19c7de9022344afc075edbfa2facf8bf38c57"
SCAPP_COMMIT="bf47bee384c2f203f63d62647a4935ecb5f30449"

"${PYTHON_BIN}" -m pip install --no-deps \
  "plasclass-dpellow @ https://github.com/Shamir-Lab/PlasClass/archive/${PLASCLASS_COMMIT}.tar.gz" \
  "scapp-dpellow @ https://github.com/Shamir-Lab/SCAPP/archive/${SCAPP_COMMIT}.tar.gz"

"${PYTHON_BIN}" -c "import plasclass, scapp"
