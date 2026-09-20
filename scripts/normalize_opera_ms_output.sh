#!/bin/sh
# Compatibility entry point; implementation belongs to abi-plugin.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec sh "$root/src/abi/plugins/scripts/normalize_opera_ms_output.sh" "$@"
