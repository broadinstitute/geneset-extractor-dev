#!/usr/bin/env python3
"""Thin GlyGen submission adapter; DIG owns both scientific reconstructions."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _file(variable: str) -> Path:
    path = Path(os.environ.get(variable, "")).expanduser()
    if not path.is_file(): raise SystemExit(f"missing required input {variable}; see reproduction/input_manifest.tsv")
    return path.resolve()


def _run(command: list[str], env: dict[str, str]) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True); mode.add_argument("--smoke", action="store_true"); mode.add_argument("--full", action="store_true")
    parser.add_argument("--out-root", required=True); parser.add_argument("--models", default="all"); parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(); root = Path(__file__).resolve().parents[1]
    dig = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    if not (dig / "src/geneset_extractors").is_dir(): raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    available = ["HZ1", "HZ2"]
    selected = available if args.models == "all" else args.models.split(",")
    if set(selected) - set(available): raise SystemExit("unknown GlyGen model id")
    fixture = root / "tests/fixtures"
    pythonpath = str(dig / "src") + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    env = {**os.environ, "PYTHONPATH": pythonpath}
    for model in selected:
        model_root = Path(args.out_root).resolve() / ("smoke" if args.smoke else "full") / "genesets/all_glycans/models" / model
        if model_root.exists():
            if not args.overwrite: raise SystemExit(f"output exists: {model_root}; pass --overwrite")
            shutil.rmtree(model_root)
        out = model_root / "extractor"
        if model == "HZ1":
            inputs = {"unicarbkb": fixture / "glycosylation_unicarbkb.csv", "harvard": fixture / "glycosylation_harvard.csv", "glyconnect": fixture / "glycosylation_glyconnect.csv", "masterlist": fixture / "human_protein_masterlist.csv"} if args.smoke else {"unicarbkb": _file("GLYGEN_UNICARBKB_CSV"), "harvard": _file("GLYGEN_HARVARD_CSV"), "glyconnect": _file("GLYGEN_GLYCONNECT_CSV"), "masterlist": _file("GLYGEN_PROTEIN_MASTERLIST_CSV")}
            command = [sys.executable, "-m", "geneset_extractors.cli", "convert", "glygen_glycosylated_proteins", "--model_id", "HZ1", "--out_dir", str(out)]
            for name, path in inputs.items(): command.extend([f"--{name}", str(path)])
        else:
            manifest = fixture / "glygen_api_manifest.tsv" if args.smoke else _file("GLYGEN_API_CACHE_MANIFEST_TSV")
            command = [sys.executable, "-m", "geneset_extractors.cli", "convert", "glygen_glycan_synthesizing_enzymes", "--model_id", "HZ2", "--cache_manifest", str(manifest), "--out_dir", str(out)]
        _run(command, env)
    return 0


if __name__ == "__main__": raise SystemExit(main())
