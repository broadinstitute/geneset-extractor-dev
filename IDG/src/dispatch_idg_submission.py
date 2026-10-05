#!/usr/bin/env python3
"""Thin IDG submission dispatcher; all extraction is implemented in DIG."""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path


def _models(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["model_id"]: row["dig_identifier"] for row in csv.DictReader(handle, delimiter="\t") if row["enabled"] == "true"}


FULL_INPUTS = {
    "HZ1": ("IDG_DRUG_TARGETS_GMT", "IDG_DRUG_TARGETS_SOURCE_URL", "https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName=IDG_Drug_Targets_2022"),
    "HZ2": ("IDG_ARCHS4_COEXP_GMT", "IDG_ARCHS4_COEXP_SOURCE_URL", "https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName=ARCHS4_IDG_Coexp"),
}


def _full_input(model_id: str) -> tuple[Path, str] | None:
    path_variable, source_variable, default_url = FULL_INPUTS[model_id]
    raw_path = os.environ.get(path_variable, "")
    if not raw_path:
        return None
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"{path_variable} must identify an existing GMT file")
    return path, os.environ.get(source_variable, default_url)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--models", default="all")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dig = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    if not (dig / "src/geneset_extractors").is_dir():
        raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    available = _models(root / "config/task_manifest.tsv")
    selected = list(available) if args.models == "all" else [value.strip() for value in args.models.split(",")]
    unknown = sorted(set(selected) - set(available))
    if unknown:
        raise SystemExit(f"unknown IDG model id(s): {', '.join(unknown)}")
    fixtures = {"HZ1": root / "tests/fixtures/IDG_Drug_Targets_2022.small.gmt", "HZ2": root / "tests/fixtures/ARCHS4_IDG_Coexp.small.gmt"}
    for model_id in selected:
        out_dir = Path(args.out_root).resolve() / "genesets/idg/models" / model_id / "extractor"
        command = [sys.executable, "-m", "geneset_extractors.cli", "convert", available[model_id], "--out_dir", str(out_dir)]
        if args.smoke:
            command.extend(["--input_gmt", str(fixtures[model_id]), "--source_url", fixtures[model_id].as_uri()])
        elif (full_input := _full_input(model_id)) is not None:
            input_gmt, source_url = full_input
            command.extend(["--input_gmt", str(input_gmt), "--source_url", source_url])
        if args.overwrite:
            command.append("--overwrite")
        print("$ " + " ".join(command), flush=True)
        env = {**os.environ, "PYTHONPATH": str(dig / "src") + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
        subprocess.run(command, check=True, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
