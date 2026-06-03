#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def source_script() -> Path:
    return repo_root() / "notebooks_adapted" / "build_lincs_l1000_crisprko_gmt_only.py"


def load_source_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("lincs_l1000_crisprko_source", script_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load source script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    script_path = source_script()
    if not script_path.exists():
        raise SystemExit(f"Missing source script for HZ2 wrapper: {script_path}")
    module = load_source_module(script_path)
    if not hasattr(module, "main"):
        raise SystemExit(f"Source script does not define main(): {script_path}")
    entry = module.main
    args = sys.argv[1:] if argv is None else argv
    return int(entry(args))


if __name__ == "__main__":
    raise SystemExit(main())
