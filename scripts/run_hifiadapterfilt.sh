#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec sh "$root/src/abi/plugins/scripts/run_hifiadapterfilt.sh" "$@"
