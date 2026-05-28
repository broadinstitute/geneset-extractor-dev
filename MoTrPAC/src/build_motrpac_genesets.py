#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from motrpac_selection_io import (
    default_model_list_path,
    default_model_manifest_path,
    default_out_root,
    default_tissue_list_path,
    read_tsv,
    relative_or_absolute_path,
    resolve_requested_ids,
    row_map,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="all")
    parser.add_argument("--models_file")
    parser.add_argument("--tissues", default="all")
    parser.add_argument("--tissues_file")
    parser.add_argument("--model_list", default=str(default_model_list_path()))
    parser.add_argument("--tissue_list", default=str(default_tissue_list_path()))
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--transcript_metadata_tsv", required=True)
    parser.add_argument("--phenotype_metadata_tsv", required=True)
    parser.add_argument("--feature_to_gene_tsv", required=True)
    parser.add_argument("--rat_to_human_tsv", required=True)
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--out_root", default=str(default_out_root()))
    parser.add_argument("--overwrite", action="store_true")
    return parser


def run_command(command: list[str]) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def dir_nonempty(path: Path) -> bool:
    return path.exists() and path.is_dir() and any(path.iterdir())


def overwrite_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def existing_output_message(*, tissue_id: str, model_id: str, path: Path) -> str:
    return (
        f"Output already exists for tissue={tissue_id} model={model_id}:\n{path}\n\n"
        "Refusing to continue because --overwrite was not provided.\n"
        "Re-run with --overwrite to replace this output."
    )


def require_existing_file(path_text: str, label: str) -> Path:
    path = relative_or_absolute_path(path_text)
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_file():
        raise SystemExit(f"Expected {label} to be a file: {path}")
    return path


def main() -> int:
    args = build_parser().parse_args()
    model_rows = read_tsv(Path(args.model_list))
    tissue_rows = read_tsv(Path(args.tissue_list))
    selected_models = resolve_requested_ids(
        csv_text=args.models,
        file_path=args.models_file,
        rows=model_rows,
        key_field="model_id",
    )
    selected_tissues = resolve_requested_ids(
        csv_text=args.tissues,
        file_path=args.tissues_file,
        rows=tissue_rows,
        key_field="tissue_id",
    )
    model_by_id = row_map(model_rows, "model_id")
    tissue_by_id = row_map(tissue_rows, "tissue_id")

    out_root = Path(args.out_root).resolve()
    outputs_root = out_root / "genesets"
    src_root = Path(__file__).resolve().parent

    transcript_metadata_tsv = require_existing_file(args.transcript_metadata_tsv, "transcript metadata TSV")
    phenotype_metadata_tsv = require_existing_file(args.phenotype_metadata_tsv, "phenotype metadata TSV")
    feature_to_gene_tsv = require_existing_file(args.feature_to_gene_tsv, "feature-to-gene TSV")
    rat_to_human_tsv = require_existing_file(args.rat_to_human_tsv, "rat-to-human mapping TSV")
    model_manifest = require_existing_file(args.model_manifest, "model manifest")
    dig_dir = Path(relative_or_absolute_path(args.dig_dir)).resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    conflicts: list[str] = []
    for tissue_id in selected_tissues:
        tissue_root = outputs_root / tissue_id
        for model_id in selected_models:
            model_out = tissue_root / "models" / model_id
            if dir_nonempty(model_out):
                conflicts.append(existing_output_message(tissue_id=tissue_id, model_id=model_id, path=model_out))
    if conflicts and not args.overwrite:
        raise SystemExit("\n\n".join(conflicts))

    for tissue_id in selected_tissues:
        tissue_row = tissue_by_id[tissue_id]
        counts_tsv_value = str(tissue_row.get("counts_tsv", "")).strip()
        if not counts_tsv_value:
            raise SystemExit(f"Missing counts_tsv for tissue={tissue_id} in {Path(args.tissue_list).resolve()}")
        counts_tsv = require_existing_file(counts_tsv_value, f"counts TSV for {tissue_id}")
        tissue_label = str(tissue_row.get("tissue_label", "")).strip()
        transcript_tissue_label = str(tissue_row.get("transcript_tissue_label", "")).strip()
        if not tissue_label or not transcript_tissue_label:
            raise SystemExit(f"Missing tissue label fields for tissue={tissue_id} in {Path(args.tissue_list).resolve()}")

        tissue_root = outputs_root / tissue_id
        prepared_dir = tissue_root / "prepared"
        models_root = tissue_root / "models"
        if args.overwrite:
            for model_id in selected_models:
                overwrite_dir(models_root / model_id)
        if not dir_nonempty(prepared_dir):
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "build_motrpac_tissue_inputs.py"),
                    "--counts_tsv",
                    str(counts_tsv),
                    "--transcript_metadata_tsv",
                    str(transcript_metadata_tsv),
                    "--phenotype_metadata_tsv",
                    str(phenotype_metadata_tsv),
                    "--feature_to_gene_tsv",
                    str(feature_to_gene_tsv),
                    "--rat_to_human_tsv",
                    str(rat_to_human_tsv),
                    "--tissue_label",
                    tissue_label,
                    "--transcript_tissue_label",
                    transcript_tissue_label,
                    "--out_dir",
                    str(prepared_dir),
                ]
            )

        for model_id in selected_models:
            model_family = model_by_id[model_id].get("model_family", "").strip()
            if model_family == "training":
                runner_name = "run_motrpac_training_model.py"
            elif model_family == "timewise":
                runner_name = "run_motrpac_timewise_model.py"
            else:
                raise SystemExit(f"Unsupported MoTrPAC model family for {model_id}")
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / runner_name),
                    "--model_id",
                    model_id,
                    "--tissue_id",
                    tissue_id,
                    "--prepared_dir",
                    str(prepared_dir),
                    "--run_root",
                    str(models_root),
                    "--python_bin",
                    str(Path(args.python_bin).resolve()),
                    "--rscript_bin",
                    args.rscript_bin,
                    "--dig_dir",
                    str(dig_dir),
                    "--model_manifest",
                    str(model_manifest),
                ]
                + (
                    ["--provenance_mirror_local_prefix", args.provenance_mirror_local_prefix]
                    if args.provenance_mirror_local_prefix
                    else []
                )
                + (
                    ["--provenance_mirror_remote_prefix", args.provenance_mirror_remote_prefix]
                    if args.provenance_mirror_remote_prefix
                    else []
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
