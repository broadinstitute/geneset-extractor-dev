"""Thin HuBMAP submission adapter; DIG owns ASCT+B processing and GMT construction."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _required_environment_file(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value).expanduser() if value else None
    if path is None or not path.is_file():
        raise SystemExit(f"missing required input {name}; see reproduction/input_manifest.tsv")
    return path.resolve()


def _required_environment_dir(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value).expanduser() if value else None
    if path is None or not path.is_dir():
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
        raw_asctb_dir = root / "tests/fixtures/asctb"
        human_gene_info = root / "tests/fixtures/hubmap_smoke_human_gene_info.tsv"
        run_root = out_root / "smoke/genesets/all_signatures/models"
        command = [sys.executable, str(root / "src/run_hubmap_hz_model.py"), "--model_id", "HZ1", "--run_root", str(run_root), "--python_bin", sys.executable, "--dig_dir", str(dig_repo), "--raw_asctb_dir", str(raw_asctb_dir), "--human_gene_info", str(human_gene_info), "--model_manifest", str(root / "config/model_manifest.tsv")]
        return _run(command)
    raw_asctb_dir = _required_environment_dir("HUBMAP_RAW_ASCTB_DIR")
    human_gene_info = _required_environment_file("HUBMAP_HUMAN_GENE_INFO")
    command = [sys.executable, str(root / "src/build_hubmap_genesets.py"), "--models", "all", "--python_bin", sys.executable, "--raw_asctb_dir", str(raw_asctb_dir), "--human_gene_info", str(human_gene_info), "--dig_dir", str(dig_repo), "--out_root", str(out_root), "--overwrite"]
    return _run(command)


if __name__ == "__main__":
    raise SystemExit(main())
