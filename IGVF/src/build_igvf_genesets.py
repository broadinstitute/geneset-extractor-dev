#!/usr/bin/env python3
"""Thin IGVF model and analysis-set selector that dispatches the DIG workflow."""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="PS1")
    parser.add_argument("--analysis-set-id", required=True)
    parser.add_argument("--inputs-root", required=True)
    parser.add_argument("--expression-tsv", help="Explicit input for a declared smoke fixture.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--python-bin", default=sys.executable)
    args = parser.parse_args()
    models = {row["model_id"]: row for row in _rows(ROOT / "config/model_list.tsv")}
    if args.model_id not in models or models[args.model_id].get("enabled", "").lower() != "true":
        raise SystemExit(f"Unknown or disabled model: {args.model_id}")
    partitions = {row["analysis_set_id"]: row for row in _rows(ROOT / "config/partition_list.tsv")}
    if args.analysis_set_id not in partitions or partitions[args.analysis_set_id].get("enabled", "").lower() != "true":
        raise SystemExit(f"Unknown or disabled analysis set: {args.analysis_set_id}")
    analyses = {row["analysis_set_id"]: row for row in _rows(ROOT / "config/analysis_set_list.tsv")}
    analysis = analyses.get(args.analysis_set_id)
    if analysis is None:
        raise SystemExit(f"No analysis configuration for: {args.analysis_set_id}")
    expression = Path(args.expression_tsv).resolve() if args.expression_tsv else Path(args.inputs_root).resolve() / analysis["file_relpath"]
    command = [
        args.python_bin, "-m", "geneset_extractors.cli", "workflows", "igvf_perturbseq",
        "--expression_tsv", str(expression), "--analysis_set_manifest", str(ROOT / "config/analysis_set_list.tsv"),
        "--analysis_set_id", args.analysis_set_id, "--out_dir", str(Path(args.out_dir).resolve()),
        "--organism", "human", "--genome_build", "hg38", "--gmt_name", "gene_set_library_crisp.gmt", "--min_gmt_size", "5",
    ]
    subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
