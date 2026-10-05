#!/usr/bin/env python3
"""Run the DIG-owned IMPC HZ1 converter and refresh submission metadata."""
from __future__ import annotations
import argparse, os, shutil, subprocess, sys
from pathlib import Path

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--assertions", required=True, type=Path); p.add_argument("--symbol-mapping", required=True, type=Path); p.add_argument("--run-root", required=True, type=Path); p.add_argument("--dig-repo", required=True, type=Path); p.add_argument("--overwrite", action="store_true"); args = p.parse_args()
    root = Path(__file__).resolve().parents[1]; model = args.run_root.resolve() / "HZ1"; extractor = model / "extractor"
    if model.exists():
        if not args.overwrite: raise SystemExit(f"output exists: {model}; pass --overwrite")
        shutil.rmtree(model)
    command = [sys.executable, "-m", "geneset_extractors.cli", "convert", "impc_hz1", "--assertions", str(args.assertions.resolve()), "--symbol_mapping", str(args.symbol_mapping.resolve()), "--out_dir", str(extractor), "--model_id", "HZ1", "--min_genes", "5"]
    env = {**os.environ, "PYTHONPATH": str(args.dig_repo.resolve() / "src") + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
    print("$ " + " ".join(command), flush=True); subprocess.run(command, check=True, env=env)
    refresh = ["bash", str(root.parent / "run/refresh_model_metadata_and_provenance.sh"), "--model_id", "HZ1", "--model_dir", str(model), "--description_template_tsv", str(root / "config/model_description_templates.tsv"), "--python_bin", sys.executable]
    print("$ " + " ".join(refresh), flush=True); subprocess.run(refresh, check=True, env={**env, "DIG_DIR": str(args.dig_repo.resolve())})
    return 0
if __name__ == "__main__": raise SystemExit(main())
