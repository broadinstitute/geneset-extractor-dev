#!/usr/bin/env python3
"""Thin GlyGen submission dispatcher; single-model runners own execution."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _file(variable: str) -> Path:
    path = Path(os.environ.get(variable, "")).expanduser()
    if not path.is_file(): raise SystemExit(f"missing required input {variable}; see reproduction/input_manifest.tsv")
    return path.resolve()


def _dir(variable: str) -> Path:
    path = Path(os.environ.get(variable, "")).expanduser()
    if not path.is_dir(): raise SystemExit(f"missing required input directory {variable}; see reproduction/input_manifest.tsv")
    return path.resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True); mode.add_argument("--smoke", action="store_true"); mode.add_argument("--full", action="store_true")
    parser.add_argument("--out-root", required=True); parser.add_argument("--models", default="all"); parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(); root = Path(__file__).resolve().parents[1]
    dig = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    if not (dig / "src/geneset_extractors").is_dir(): raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    selected = ["HZ1", "HZ2"] if args.models == "all" else args.models.split(",")
    if set(selected) - {"HZ1", "HZ2"}: raise SystemExit("unknown GlyGen model id")
    fixture = root / "tests/fixtures"
    for model in selected:
        command = [sys.executable, str(root / "src/run_glygen_model.py"), "--model_id", model, "--run_root", str(Path(args.out_root).resolve() / "genesets/all_glycans/models"), "--dig_repo", str(dig)]
        if model == "HZ1":
            inputs = {"unicarbkb": fixture / "glycosylation_unicarbkb.csv", "harvard": fixture / "glycosylation_harvard.csv", "glyconnect": fixture / "glycosylation_glyconnect.csv", "masterlist": fixture / "human_protein_masterlist.csv"} if args.smoke else {"unicarbkb": _file("GLYGEN_UNICARBKB_CSV"), "harvard": _file("GLYGEN_HARVARD_CSV"), "glyconnect": _file("GLYGEN_GLYCONNECT_CSV"), "masterlist": _file("GLYGEN_PROTEIN_MASTERLIST_CSV")}
            for name, path in inputs.items(): command.extend([f"--{name}", str(path)])
        else:
            command.extend(["--cache_dir", str(fixture / "glygen_api_cache" if args.smoke else _dir("GLYGEN_API_CACHE_DIR"))])
        if os.environ.get("LOCAL_INPUT_SOURCE_MAP_TSV"): command.extend(["--local_input_source_map_tsv", os.environ["LOCAL_INPUT_SOURCE_MAP_TSV"]])
        if args.overwrite: command.append("--overwrite")
        print("$ " + " ".join(command), flush=True)
        subprocess.run(command, check=True)
    return 0


if __name__ == "__main__": raise SystemExit(main())
