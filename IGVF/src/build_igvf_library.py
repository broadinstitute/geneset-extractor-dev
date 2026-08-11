#!/usr/bin/env python3
"""Thin IGVF wrapper: dispatch configured released inputs to DIG."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
DIG = WORKSPACE / "dig-gene-set-extractors"


def _command(row: dict[str, str], input_path: Path, out_dir: Path) -> list[str]:
    cmd = [sys.executable, "-m", "geneset_extractors.cli", "workflows", "igvf_perturbseq", "--input_mode", "long_de", "--expression_tsv", str(input_path), "--out_dir", str(out_dir), "--organism", "human", "--genome_build", "hg38", "--gmt_name", "gene_set_library_crisp.gmt", "--min_gmt_size", "5"]
    for field, flag in (("sep", "--sep"), ("term_column", "--term_column"), ("gene_symbol_column", "--gene_symbol_column"), ("gene_id_column", "--gene_id_column"), ("effect_column", "--effect_column"), ("ratio_column", "--ratio_column"), ("score_column", "--score_column"), ("pvalue_column", "--pvalue_column"), ("pvalue_max", "--pvalue_max"), ("score_threshold", "--score_threshold"), ("top_k_per_direction", "--top_k_per_direction")):
        value = row.get(field, "").strip()
        if value and value != "NA": cmd.extend([flag, value])
    return cmd


def _extract(workflow_dir: Path, extractor_dir: Path) -> list[str]:
    return [sys.executable, "-m", "geneset_extractors.cli", "convert", "signed_term_gene", "--table_tsv", str(workflow_dir / "igvf_perturbseq_signed_term_gene.tsv"), "--out_dir", str(extractor_dir), "--organism", "human", "--genome_build", "hg38", "--term_column", "term", "--term_prefix", "IGVF_Perturb_Seq", "--gene_id_column", "gene_id", "--gene_symbol_column", "gene_symbol", "--score_column", "score", "--sign_column", "sign", "--gmt_name_separator", "_", "--gmt_signed_labels", "up_dn", "--gmt_min_genes", "5", "--gmt_require_symbol", "true", "--emit_small_gene_sets", "false"]


def _map_references() -> None:
    submission = ROOT / "submission.yaml"; reference = WORKSPACE / "adoption" / "legacy_reference.json"
    payload = json.loads(submission.read_text(encoding="utf-8")); refs = json.loads(reference.read_text(encoding="utf-8"))["reference_outputs"]
    for item in refs:
        legacy = Path(item["legacy"]); rel = legacy.relative_to(legacy.parents[4])
        item["regenerated"] = str(Path("outputs/full") / rel)
    payload["adoption"]["reference_outputs"] = refs
    submission.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    dependency_map = WORKSPACE / "adoption" / "dependency_map.json"
    dependencies = json.loads(dependency_map.read_text(encoding="utf-8"))
    for item in dependencies.get("intermediates", []):
        path = str(item.get("path", ""))
        item["producer"] = (
            "geneset-extractor-dev/IGVF/config/analysis_set_list.tsv"
            if path.startswith("config/")
            else "dig-gene-set-extractors: geneset_extractors.workflows.igvf_perturbseq"
        )
    dependency_map.write_text(json.dumps(dependencies, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs_root", required=False); parser.add_argument("--out_root", required=False); parser.add_argument("--smoke", action="store_true"); parser.add_argument("--only", help="comma-separated configured analysis-set IDs"); parser.add_argument("--write_reference_mappings", action="store_true")
    args = parser.parse_args()
    if args.write_reference_mappings:
        _map_references(); return 0
    if not args.inputs_root or not args.out_root: parser.error("--inputs_root and --out_root are required unless --write_reference_mappings is used")
    out_root = Path(args.out_root).resolve(); inputs = Path(args.inputs_root).resolve()
    rows = list(csv.DictReader((ROOT / "config" / "analysis_set_list.tsv").open(encoding="utf-8"), delimiter="\t"))
    if args.smoke:
        rows = [{"analysis_set_id": "smoke", "file_relpath": "igvf_smoke.tsv", "sep": "auto", "term_column": "term", "gene_symbol_column": "gene", "gene_id_column": "gene_id", "effect_column": "logfc", "ratio_column": "NA", "score_column": "NA", "pvalue_column": "pvalue", "pvalue_max": "0.05", "score_threshold": "NA", "top_k_per_direction": "200"}]
    elif args.only:
        requested = {value.strip() for value in args.only.split(",") if value.strip()}
        rows = [row for row in rows if row["analysis_set_id"] in requested]
    env = {**__import__("os").environ, "PYTHONPATH": str(DIG / "src")}
    for row in rows:
        if row.get("enabled", "true").lower() != "true": continue
        dataset = row["analysis_set_id"]; model = out_root / dataset / "models" / "PS1"; workflow = model / "workflow"; extractor = model / "extractor"
        source = inputs / row["file_relpath"]
        if not source.is_file(): raise FileNotFoundError(f"Missing declared IGVF source input: {source}")
        for cmd in (_command(row, source, workflow), _extract(workflow, extractor)):
            subprocess.run(cmd, cwd=DIG, env=env, check=True)
    if not args.smoke: _map_references()
    return 0


if __name__ == "__main__": raise SystemExit(main())
