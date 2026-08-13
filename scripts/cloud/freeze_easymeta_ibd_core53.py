#!/usr/bin/env python3
"""Create the preregistered SRP131166 core-53 ABI sample sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from abi.plugins.easymetagenome.reproduction import freeze_core53


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table1", type=Path, required=True)
    parser.add_argument("--reads-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = freeze_core53(args.table1, args.output, reads_root=args.reads_root)
    print(f"Frozen {len(rows)} SRP131166 samples at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
