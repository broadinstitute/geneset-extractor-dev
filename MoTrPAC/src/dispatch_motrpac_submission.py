"""Thin MoTrPAC submission dispatcher; DIG owns scientific processing."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def required_file(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value).expanduser() if value else None
    if path is None or not path.is_file():
        raise SystemExit(f"missing required input {name}; see reproduction/input_manifest.tsv")
    return path.resolve()


def required_dir(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value).expanduser() if value else None
    if path is None or not path.is_dir():
        raise SystemExit(f"missing required input {name}; see reproduction/input_manifest.tsv")
    return path.resolve()


def run(command: list[str]) -> int:
    print("$ " + " ".join(command), flush=True)
    return subprocess.run(command, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--smoke", action="store_true")
    modes.add_argument("--full", action="store_true")
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dig_repo = Path(os.environ.get("DIG_REPO", root.parents[1] / "dig-gene-set-extractors")).resolve()
    if not (dig_repo / "src/geneset_extractors").is_dir():
        raise SystemExit("DIG_REPO must identify a dig-gene-set-extractors checkout")
    out_root = Path(args.out_root).resolve()
    if args.smoke:
        command = [
            sys.executable, str(root / "src/run_motrpac_hz_released_dea_model.py"),
            "--model_id", "HZ1", "--run_root", str(out_root / "smoke/genesets/all_tissues/models"),
            "--python_bin", sys.executable, "--dig_dir", str(dig_repo),
            "--feature_annot", str(root / "tests/fixtures/motrpac_smoke_feature_annot.tsv"),
            "--dea_dir", str(root / "tests/fixtures/dea"),
            "--mapping_file", str(root / "tests/fixtures/motrpac_smoke_mapping.tsv"),
            "--model_manifest", str(root / "config/smoke_model_manifest.tsv"),
        ]
        return run(command)
    command = [
        sys.executable, str(root / "src/build_motrpac_genesets.py"),
        "--models", "all", "--tissues", "all", "--python_bin", sys.executable,
        "--dig_dir", str(dig_repo), "--out_root", str(out_root), "--overwrite",
        "--raw_counts_dir", str(required_dir("MOTRPAC_RAW_COUNTS_DIR")),
        "--transcript_metadata_tsv", str(required_file("MOTRPAC_TRANSCRIPT_METADATA_TSV")),
        "--phenotype_metadata_tsv", str(required_file("MOTRPAC_PHENOTYPE_METADATA_TSV")),
        "--feature_to_gene_tsv", str(required_file("MOTRPAC_FEATURE_TO_GENE_TSV")),
        "--rat_to_human_tsv", str(required_file("MOTRPAC_RAT_TO_HUMAN_TSV")),
        "--feature_annot", str(required_file("MOTRPAC_FEATURE_ANNOT")),
        "--dea_dir", str(required_dir("MOTRPAC_DEA_DIR")),
        "--mapping_file", str(required_file("MOTRPAC_MAPPING_FILE")),
    ]
    return run(command)


if __name__ == "__main__":
    raise SystemExit(main())
