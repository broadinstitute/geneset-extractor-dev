#!/usr/bin/env python3
"""Test-only thin wrapper that simulates the declared DIG CLI invocation."""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["--smoke", "full"], required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    if not Path(args.input).is_file():
        raise SystemExit("missing declared synthetic fixture")
    print(f"SIMULATED DIG ENTRYPOINT: geneset-extractors list ({args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
