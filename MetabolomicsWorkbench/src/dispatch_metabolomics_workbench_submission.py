#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path

def required(variable: str) -> Path:
    path = Path(os.environ.get(variable, "")).expanduser()
    if not path.is_file(): raise SystemExit(f"missing {variable}; see reproduction/input_manifest.tsv")
    return path.resolve()

def main() -> int:
    parser = argparse.ArgumentParser(); mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true"); mode.add_argument("--full", action="store_true")
    parser.add_argument("--out-root", required=True); parser.add_argument("--overwrite", action="store_true"); args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dig = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    edges = root / "tests/fixtures/mw_hz1_smoke_edges.tsv" if args.smoke else required("MW_HARMONIZOME_EDGES_TSV_GZ")
    command = [sys.executable, str(root / "src/run_metabolomics_workbench_model.py"), "--edges", str(edges), "--run-root", str(Path(args.out_root).resolve() / "genesets/all_metabolites/models"), "--dig-repo", str(dig)]
    if args.overwrite: command.append("--overwrite")
    print("$ " + " ".join(command), flush=True)
    return subprocess.run(command, check=False).returncode
if __name__ == "__main__": raise SystemExit(main())
