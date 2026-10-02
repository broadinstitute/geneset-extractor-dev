#!/usr/bin/env python3
"""Run one RummaGEO model: selection, source provenance, and reconstruction."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dispatch_rummageo_submission import _source_uris, _write_source_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_id", required=True, choices=("HZ1", "HZ2"))
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--dig_repo", required=True)
    parser.add_argument("--human_gmt", required=True)
    parser.add_argument("--mouse_gmt", required=True)
    parser.add_argument("--query_records_json", required=True)
    parser.add_argument("--drug_terms_json")
    parser.add_argument("--human_gene_info", required=True)
    parser.add_argument("--mouse_gene_info", required=True)
    parser.add_argument("--gene_orthologs", required=True)
    parser.add_argument("--local_input_source_map_tsv")
    parser.add_argument("--legacy_gmt")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    paths = {name: Path(getattr(args, name)).resolve() for name in ("human_gmt", "mouse_gmt", "query_records_json", "human_gene_info", "mouse_gene_info", "gene_orthologs")}
    if args.model_id == "HZ1":
        if not args.drug_terms_json:
            raise SystemExit("HZ1 requires --drug_terms_json")
        paths["drug_terms_json"] = Path(args.drug_terms_json).resolve()
    for name, path in paths.items():
        if not path.is_file():
            raise SystemExit(f"missing {name}: {path}")
    dig_repo = Path(args.dig_repo).resolve()
    if not (dig_repo / "src/geneset_extractors").is_dir():
        raise SystemExit("--dig_repo must identify a dig-gene-set-extractors checkout")
    model_root = Path(args.run_root).resolve() / args.model_id
    if model_root.exists():
        if not args.overwrite:
            raise SystemExit(f"output already exists for model={args.model_id}: {model_root}; pass --overwrite to replace it")
        shutil.rmtree(model_root)
    selection_dir, out_dir = model_root / "workflow/selection", model_root / "extractor"
    pythonpath = str(dig_repo / "src") + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    env = {**os.environ, "PYTHONPATH": pythonpath}
    selection = [sys.executable, "-m", "geneset_extractors.cli", "convert", "rumma_geo_selection", "--query_records_json", str(paths["query_records_json"]), "--model_id", args.model_id, "--out_dir", str(selection_dir)]
    if args.model_id == "HZ1": selection.extend(["--drug_terms_json", str(paths["drug_terms_json"])])
    print("$ " + " ".join(selection), flush=True); subprocess.run(selection, check=True, env=env)
    source_paths = {"human_rummageo_gmt": paths["human_gmt"], "mouse_rummageo_gmt": paths["mouse_gmt"], "recorded_selection_manifest": paths["query_records_json"], "ncbi_human_gene_info": paths["human_gene_info"], "ncbi_mouse_gene_info": paths["mouse_gene_info"], "ncbi_gene_orthologs": paths["gene_orthologs"]}
    if args.model_id == "HZ1": source_paths["sigcom_lincs_drug_terms"] = paths["drug_terms_json"]
    source_manifest = model_root / "workflow/source_manifest.json"
    _write_source_manifest(source_manifest, source_paths, _source_uris(Path(args.local_input_source_map_tsv).resolve()) if args.local_input_source_map_tsv else None)
    command = [sys.executable, "-m", "geneset_extractors.cli", "convert", "rumma_geo", "--human_gmt", str(paths["human_gmt"]), "--mouse_gmt", str(paths["mouse_gmt"]), "--human_gene_info", str(paths["human_gene_info"]), "--mouse_gene_info", str(paths["mouse_gene_info"]), "--gene_orthologs", str(paths["gene_orthologs"]), "--selection_manifest", str(selection_dir / "selection_manifest.tsv"), "--source_manifest", str(source_manifest), "--model_id", args.model_id, "--out_dir", str(out_dir)]
    if args.legacy_gmt: command.extend(["--legacy_gmt", args.legacy_gmt])
    print("$ " + " ".join(command), flush=True); subprocess.run(command, check=True, env=env)
    return 0


if __name__ == "__main__": raise SystemExit(main())
