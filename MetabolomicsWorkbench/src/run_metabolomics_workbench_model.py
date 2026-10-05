#!/usr/bin/env python3
"""Thin wrapper for the DIG-owned Metabolomics Workbench HZ1 converter."""
from __future__ import annotations
import argparse, os, shutil, subprocess, sys
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edges", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--dig-repo", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    model = args.run_root.resolve() / "HZ1"; extractor = model / "extractor"
    if model.exists():
        if not args.overwrite: raise SystemExit(f"output exists: {model}; pass --overwrite")
        shutil.rmtree(model)
    env = {**os.environ, "PYTHONPATH": str(args.dig_repo.resolve() / "src") + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
    command = [sys.executable, "-m", "geneset_extractors.cli", "convert", "metabolomics_workbench_hz1", "--edges", str(args.edges.resolve()), "--out_dir", str(extractor), "--model_id", "HZ1", "--min_genes", "5"]
    print("$ " + " ".join(command), flush=True); subprocess.run(command, check=True, env=env)
    refresh = ["bash", str(root.parent / "run/refresh_model_metadata_and_provenance.sh"), "--model_id", "HZ1", "--model_dir", str(model), "--description_template_tsv", str(root / "config/model_description_templates.tsv"), "--python_bin", sys.executable]
    print("$ " + " ".join(refresh), flush=True); subprocess.run(refresh, check=True, env={**env, "DIG_DIR": str(args.dig_repo.resolve())})
    return 0
if __name__ == "__main__": raise SystemExit(main())
