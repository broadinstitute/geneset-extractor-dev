#!/usr/bin/env python3
"""Thin RummaGEO submission adapter; DIG owns all scientific processing."""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _model_ids(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [row["model_id"] for row in csv.DictReader(handle, delimiter="\t") if row.get("enabled") == "true"]


def _required_env_file(name: str) -> Path:
    raw = os.environ.get(name, "")
    path = Path(raw).expanduser() if raw else None
    if path is None or not path.is_file():
        raise SystemExit(f"missing required input {name}; see reproduction/input_manifest.tsv")
    return path.resolve()


def _full_inputs(selected: list[str]) -> dict[str, Path]:
    inputs = {
        "human_gmt": _required_env_file("RUMMAGEO_HUMAN_GMT"),
        "mouse_gmt": _required_env_file("RUMMAGEO_MOUSE_GMT"),
        "query_records_json": _required_env_file("RUMMAGEO_QUERY_RECORDS_JSON"),
        "source_manifest": _required_env_file("RUMMAGEO_SOURCE_MANIFEST"),
        "human_gene_info": _required_env_file("RUMMAGEO_HUMAN_GENE_INFO"),
        "mouse_gene_info": _required_env_file("RUMMAGEO_MOUSE_GENE_INFO"),
        "gene_orthologs": _required_env_file("RUMMAGEO_GENE_ORTHOLOGS"),
    }
    if "HZ1" in selected:
        inputs["drug_terms_json"] = _required_env_file("RUMMAGEO_DRUG_TERMS_JSON")
    return inputs


def _smoke_inputs(root: Path, selected: list[str]) -> dict[str, Path]:
    fixture = root / "tests/fixtures"
    inputs = {
        "human_gmt": fixture / "human.gmt",
        "mouse_gmt": fixture / "mouse.gmt",
        "query_records_json": fixture / "query_records.json",
        "source_manifest": fixture / "source_manifest.json",
        "human_gene_info": fixture / "human_gene_info.tsv",
        "mouse_gene_info": fixture / "mouse_gene_info.tsv",
        "gene_orthologs": fixture / "gene_orthologs.tsv",
    }
    if "HZ1" in selected:
        inputs["drug_terms_json"] = fixture / "drug_terms.json"
    return inputs


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--models", default="all", help="Comma-separated model ids, or all.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dig_repo = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    if not (dig_repo / "src/geneset_extractors").is_dir():
        raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    available = _model_ids(root / "config/model_list.tsv")
    selected = available if args.models == "all" else args.models.split(",")
    unknown = sorted(set(selected) - set(available))
    if unknown:
        raise SystemExit(f"unknown RummaGEO model ids: {', '.join(unknown)}")
    inputs = _smoke_inputs(root, selected) if args.smoke else _full_inputs(selected)
    for key, path in inputs.items():
        if not path.is_file():
            raise SystemExit(f"missing declared {key}: {path}")
    pythonpath = str(dig_repo / "src") + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    for model_id in selected:
        model_root = Path(args.out_root).resolve() / "genesets/all_signatures/models" / model_id
        out_dir = model_root / "extractor"
        selection_dir = model_root / "workflow" / "selection"
        if model_root.exists():
            if not args.overwrite:
                raise SystemExit(f"output already exists for model={model_id}: {model_root}; pass --overwrite to replace it")
            shutil.rmtree(model_root)
        selection_command = [
            sys.executable, "-m", "geneset_extractors.cli", "convert", "rumma_geo_selection",
            "--query_records_json", str(inputs["query_records_json"]),
            "--model_id", model_id,
            "--out_dir", str(selection_dir),
        ]
        if model_id == "HZ1":
            selection_command.extend(["--drug_terms_json", str(inputs["drug_terms_json"])])
        print("$ " + " ".join(selection_command), flush=True)
        subprocess.run(selection_command, check=True, env={**os.environ, "PYTHONPATH": pythonpath})
        command = [sys.executable, "-m", "geneset_extractors.cli", "convert", "rumma_geo"]
        for key, path in inputs.items():
            if key in {"query_records_json", "drug_terms_json"}:
                continue
            command.extend([f"--{key}", str(path)])
        command.extend(["--selection_manifest", str(selection_dir / "selection_manifest.tsv")])
        command.extend(["--model_id", model_id, "--out_dir", str(out_dir)])
        legacy_env = "RUMMAGEO_DRUG_LEGACY_GMT" if model_id == "HZ1" else "RUMMAGEO_GENE_LEGACY_GMT"
        if os.environ.get(legacy_env):
            command.extend(["--legacy_gmt", str(_required_env_file(legacy_env))])
        print("$ " + " ".join(command), flush=True)
        subprocess.run(command, check=True, env={**os.environ, "PYTHONPATH": pythonpath})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
