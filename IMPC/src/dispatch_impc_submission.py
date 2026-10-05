#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, subprocess, sys
from pathlib import Path
def required(variable: str) -> Path:
    path = Path(os.environ.get(variable, "")).expanduser()
    if not path.is_file(): raise SystemExit(f"missing {variable}; see reproduction/input_manifest.tsv")
    return path.resolve()
def main() -> int:
    p=argparse.ArgumentParser(); mode=p.add_mutually_exclusive_group(required=True); mode.add_argument("--smoke", action="store_true"); mode.add_argument("--full", action="store_true"); p.add_argument("--out-root", required=True); p.add_argument("--overwrite", action="store_true"); a=p.parse_args(); root=Path(__file__).resolve().parents[1]; dig=Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    assertions=root/"tests/fixtures/impc_smoke_assertions.csv" if a.smoke else required("IMPC_ASSERTIONS_CSV_GZ")
    mapping=root/"tests/fixtures/impc_smoke_mapping.tsv" if a.smoke else required("IMPC_SYMBOL_MAPPING_FILE")
    cmd=[sys.executable, str(root/"src/run_impc_model.py"), "--assertions", str(assertions), "--symbol-mapping", str(mapping), "--run-root", str(Path(a.out_root).resolve()/"genesets/all_phenotypes/models"), "--dig-repo", str(dig)]
    if a.overwrite: cmd.append("--overwrite")
    print("$ " + " ".join(cmd), flush=True); return subprocess.run(cmd, check=False).returncode
if __name__ == "__main__": raise SystemExit(main())
