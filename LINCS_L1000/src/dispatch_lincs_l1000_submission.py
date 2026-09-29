"""Thin LINCS L1000 submission adapter; DIG owns matrix processing and GMT construction."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _required_file(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value).expanduser() if value else None
    if path is None or not path.is_file():
        raise SystemExit(f"missing required input {name}; see reproduction/input_manifest.tsv")
    return path.resolve()


def _run(command: list[str]) -> int:
    print("$ " + " ".join(command), flush=True)
    return subprocess.run(command, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--smoke", action="store_true")
    modes.add_argument("--full", action="store_true")
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dig_repo = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    if not (dig_repo / "src/geneset_extractors").is_dir():
        raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    out_root = Path(args.out_root).resolve()
    if args.smoke:
        command = [sys.executable, str(root / "src/build_lincs_l1000_genesets.py"), "--models", "HZ1", "--python_bin", sys.executable, "--chempert_expression_tsv", str(root / "tests/fixtures/lincs_smoke_chempert.tsv"), "--mapping_file", str(root / "tests/fixtures/lincs_smoke_mapping.tsv"), "--model_manifest", str(root / "config/smoke_model_manifest.tsv"), "--dig_dir", str(dig_repo), "--out_root", str(out_root / "smoke"), "--overwrite"]
        return _run(command)
    command = [sys.executable, str(root / "src/build_lincs_l1000_genesets.py"), "--models", "all", "--python_bin", sys.executable, "--chempert_expression_tsv", str(_required_file("LINCS_CHEMPERT_EXPRESSION_TSV")), "--crisprko_expression_tsv", str(_required_file("LINCS_CRISPRKO_EXPRESSION_TSV")), "--mapping_file", str(_required_file("LINCS_MAPPING_FILE")), "--dig_dir", str(dig_repo), "--out_root", str(out_root), "--overwrite"]
    return _run(command)


if __name__ == "__main__":
    raise SystemExit(main())
