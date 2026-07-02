#!/usr/bin/env python3
"""Build the full IGVF Perturb-seq library: one analysis set per row of analysis_set_list.tsv.

For each enabled analysis set, this writes a one-row model manifest carrying that set's
long_de column mapping + thresholds, then invokes build_igvf_genesets.py for that set
(partition = analysis_set_id). Run INSIDE the container (it calls the dig CLI).

Usage (in container):
  python IGVF/run/build_all_igvf_sets.py --inputs_root inputs/IGVF --dig_dir <DIG> \
      --out_root igvf_all_models [--only IGVFDS....,IGVFDS....] [--overwrite]
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
CONFIG = HERE.parent / "config"

# analysis_set_list column -> manifest workflow_* key
COLMAP = {
    "sep": "workflow_sep",
    "term_column": "workflow_term_column",
    "gene_symbol_column": "workflow_gene_symbol_column",
    "gene_id_column": "workflow_gene_id_column",
    "effect_column": "workflow_effect_column",
    "ratio_column": "workflow_ratio_column",
    "score_column": "workflow_score_column",
    "pvalue_column": "workflow_pvalue_column",
    "pvalue_max": "workflow_pvalue_max",
    "score_threshold": "workflow_score_threshold",
    "top_k_per_direction": "workflow_top_k_per_direction",
}


def write_manifest(row: dict[str, str], path: Path) -> None:
    fields = ["model_id", "workflow_input_mode", "workflow_gmt_name", "workflow_min_gmt_size",
              "workflow_z_threshold", "workflow_orientation"] + list(COLMAP.values())
    values = {
        "model_id": "PS1",
        "workflow_input_mode": "long_de",
        "workflow_gmt_name": "gene_set_library_crisp.gmt",
        "workflow_min_gmt_size": "5",
        "workflow_z_threshold": "3.0",
        "workflow_orientation": "perturbation_by_gene",
    }
    for src_col, mkey in COLMAP.items():
        values[mkey] = str(row.get(src_col, "NA")).strip() or "NA"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, delimiter="\t", fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerow(values)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis_set_list", default=str(CONFIG / "analysis_set_list.tsv"))
    ap.add_argument("--inputs_root", required=True)
    ap.add_argument("--dig_dir", required=True)
    ap.add_argument("--out_root", required=True)
    ap.add_argument("--only", help="comma-separated analysis_set_ids to build (default: all enabled)")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--python_bin", default=sys.executable or "python3")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.analysis_set_list, encoding="utf-8", newline=""), delimiter="\t"))
    only = {x.strip() for x in args.only.split(",")} if args.only else None
    inputs_root = Path(args.inputs_root).resolve()
    tmpdir = Path(tempfile.mkdtemp(prefix="igvf_manifests_"))

    results: list[tuple[str, str]] = []
    for row in rows:
        sid = str(row.get("analysis_set_id", "")).strip()
        if not sid or str(row.get("enabled", "true")).strip().lower() != "true":
            continue
        if only and sid not in only:
            continue
        expr = inputs_root / str(row.get("file_relpath", "")).strip()
        if not expr.is_file():
            results.append((sid, f"SKIP missing file {expr}"))
            continue
        manifest = tmpdir / f"{sid}_manifest.tsv"
        write_manifest(row, manifest)
        cmd = [
            str(Path(args.python_bin).resolve()), str(SRC / "build_igvf_genesets.py"),
            "--models", "PS1",
            "--expression_tsv", str(expr),
            "--analysis_set_id", sid,
            "--dig_dir", str(Path(args.dig_dir).resolve()),
            "--out_root", str(Path(args.out_root).resolve()),
            "--model_manifest", str(manifest),
        ]
        if args.overwrite:
            cmd.append("--overwrite")
        print(f"\n===== building {sid} ({row.get('schema','')}) =====", flush=True)
        rc = subprocess.run(cmd).returncode
        results.append((sid, "ok" if rc == 0 else f"FAILED rc={rc}"))

    print("\n===== SUMMARY =====")
    for sid, status in results:
        print(f"  {sid}: {status}")
    n_ok = sum(1 for _, s in results if s == "ok")
    print(f"{n_ok}/{len(results)} sets built")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
