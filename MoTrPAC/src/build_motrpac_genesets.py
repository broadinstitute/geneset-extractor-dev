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
    parser.add_argument("--transcript_metadata_tsv")
    parser.add_argument("--phenotype_metadata_tsv")
    parser.add_argument("--feature_to_gene_tsv")
    parser.add_argument("--rat_to_human_tsv")
    parser.add_argument("--raw_counts_dir")
    parser.add_argument("--feature_annot")
    parser.add_argument("--dea_dir")
    parser.add_argument("--mapping_file")
    parser.add_argument("--gene_info")
    parser.add_argument("--gene_csv")
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


def require_existing_dir(path_text: str, label: str) -> Path:
    path = relative_or_absolute_path(path_text)
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_dir():
        raise SystemExit(f"Expected {label} to be a directory: {path}")
    return path


def resolve_raw_counts_tsv(raw_counts_dir: Path, raw_counts_object: str) -> Path:
    object_name = str(raw_counts_object).strip()
    if not object_name:
        raise SystemExit("Missing raw_counts_object in tissue list row")
    candidates = [
        raw_counts_dir / f"{object_name}.tsv.gz",
        raw_counts_dir / "raw_counts_by_tissue" / f"{object_name}.tsv.gz",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise SystemExit(
        "Missing raw counts TSV for "
        f"{object_name}. Looked in: {', '.join(str(path) for path in candidates)}"
    )


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
    selected_model_families = {str(model_by_id[model_id].get("model_family", "")).strip() for model_id in selected_models}
    tissue_scoped_models = [
        model_id
        for model_id in selected_models
        if str(model_by_id[model_id].get("model_family", "")).strip() in {"training", "timewise"}
    ]
    raw_aggregated_models = [
        model_id
        for model_id in selected_models
        if str(model_by_id[model_id].get("model_family", "")).strip() == "hz_raw_aggregated"
    ]

    out_root = Path(args.out_root).resolve()
    outputs_root = out_root / "genesets"
    src_root = Path(__file__).resolve().parent

    model_manifest = require_existing_file(args.model_manifest, "model manifest")
    dig_dir = Path(relative_or_absolute_path(args.dig_dir)).resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")
    transcript_metadata_tsv = None
    phenotype_metadata_tsv = None
    feature_to_gene_tsv = None
    rat_to_human_tsv = None
    raw_counts_dir = None
    if selected_model_families & {"training", "timewise", "hz_raw_aggregated"}:
        if not args.raw_counts_dir:
            raise SystemExit("Timewise/training/raw-aggregated MoTrPAC models require --raw_counts_dir.")
        transcript_metadata_tsv = require_existing_file(args.transcript_metadata_tsv, "transcript metadata TSV")
        phenotype_metadata_tsv = require_existing_file(args.phenotype_metadata_tsv, "phenotype metadata TSV")
        feature_to_gene_tsv = require_existing_file(args.feature_to_gene_tsv, "feature-to-gene TSV")
        rat_to_human_tsv = require_existing_file(args.rat_to_human_tsv, "rat-to-human mapping TSV")
        raw_counts_dir = require_existing_dir(args.raw_counts_dir, "raw counts directory")
    feature_annot = require_existing_file(args.feature_annot, "feature annotation") if args.feature_annot else None
    dea_dir = Path(args.dea_dir).resolve() if args.dea_dir else None
    if dea_dir is not None and (not dea_dir.exists() or not dea_dir.is_dir()):
        raise SystemExit(f"Missing DEA directory: {dea_dir}")
    mapping_file = require_existing_file(args.mapping_file, "mapping file") if args.mapping_file else None
    gene_info = require_existing_file(args.gene_info, "gene_info") if args.gene_info else None
    gene_csv = require_existing_file(args.gene_csv, "gene.csv") if args.gene_csv else None

    released_hz_models = [
        model_id
        for model_id in selected_models
        if str(model_by_id[model_id].get("model_family", "")).strip() == "hz_released_dea"
    ]

    conflicts: list[str] = []
    for model_id in released_hz_models:
        model_out = outputs_root / "all_tissues" / "models" / model_id
        if dir_nonempty(model_out):
            conflicts.append(existing_output_message(tissue_id="all_tissues", model_id=model_id, path=model_out))
    for model_id in raw_aggregated_models:
        model_out = outputs_root / "all_tissues" / "models" / model_id
        if dir_nonempty(model_out):
            conflicts.append(existing_output_message(tissue_id="all_tissues", model_id=model_id, path=model_out))
    for tissue_id in selected_tissues:
        tissue_root = outputs_root / tissue_id
        for model_id in tissue_scoped_models:
            model_out = tissue_root / "models" / model_id
            if dir_nonempty(model_out):
                conflicts.append(existing_output_message(tissue_id=tissue_id, model_id=model_id, path=model_out))
    if conflicts and not args.overwrite:
        raise SystemExit("\n\n".join(conflicts))

    if "hz_released_dea" in selected_model_families:
        for model_id in released_hz_models:
            if args.overwrite:
                overwrite_dir(outputs_root / "all_tissues" / "models" / model_id)
        if feature_annot is None or dea_dir is None or mapping_file is None:
            raise SystemExit(
                "Released-DEA MoTrPAC HZ models require --feature_annot, --dea_dir, and --mapping_file."
            )
        for model_id in released_hz_models:
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "run_motrpac_hz_released_dea_model.py"),
                    "--model_id",
                    model_id,
                    "--run_root",
                    str(outputs_root / "all_tissues" / "models"),
                    "--python_bin",
                    str(Path(args.python_bin).resolve()),
                    "--dig_dir",
                    str(dig_dir),
                    "--feature_annot",
                    str(feature_annot),
                    "--dea_dir",
                    str(dea_dir),
                    "--mapping_file",
                    str(mapping_file),
                    "--model_manifest",
                    str(model_manifest),
                ]
                + (["--gene_info", str(gene_info)] if gene_info is not None else [])
                + (["--gene_csv", str(gene_csv)] if gene_csv is not None else [])
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

    if "hz_raw_aggregated" in selected_model_families:
        for model_id in raw_aggregated_models:
            if args.overwrite:
                overwrite_dir(outputs_root / "all_tissues" / "models" / model_id)
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "run_motrpac_hz_raw_aggregated_model.py"),
                    "--model_id",
                    model_id,
                    "--run_root",
                    str(outputs_root / "all_tissues" / "models"),
                    "--python_bin",
                    str(Path(args.python_bin).resolve()),
                    "--rscript_bin",
                    args.rscript_bin,
                    "--dig_dir",
                    str(dig_dir),
                    "--raw_counts_dir",
                    str(raw_counts_dir),
                    "--transcript_metadata_tsv",
                    str(transcript_metadata_tsv),
                    "--phenotype_metadata_tsv",
                    str(phenotype_metadata_tsv),
                    "--feature_to_gene_tsv",
                    str(feature_to_gene_tsv),
                    "--rat_to_human_tsv",
                    str(rat_to_human_tsv),
                    "--model_list",
                    str(Path(args.model_list).resolve()),
                    "--tissue_list",
                    str(Path(args.tissue_list).resolve()),
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

    for tissue_id in selected_tissues:
        if not tissue_scoped_models:
            continue
        tissue_row = tissue_by_id[tissue_id]
        raw_counts_object = str(tissue_row.get("raw_counts_object", "")).strip()
        if not raw_counts_object:
            raise SystemExit(f"Missing raw_counts_object for tissue={tissue_id} in {Path(args.tissue_list).resolve()}")
        counts_tsv = resolve_raw_counts_tsv(raw_counts_dir, raw_counts_object)
        tissue_label = str(tissue_row.get("tissue_label", "")).strip()
        transcript_tissue_label = str(tissue_row.get("transcript_tissue_label", "")).strip()
        if not tissue_label or not transcript_tissue_label:
            raise SystemExit(f"Missing tissue label fields for tissue={tissue_id} in {Path(args.tissue_list).resolve()}")

        tissue_root = outputs_root / tissue_id
        models_root = tissue_root / "models"
        if args.overwrite:
            for model_id in tissue_scoped_models:
                overwrite_dir(models_root / model_id)

        for model_id in tissue_scoped_models:
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
                    "--counts_tsv",
                    str(counts_tsv),
                    "--tissue_label",
                    tissue_label,
                    "--transcript_tissue_label",
                    transcript_tissue_label,
                    "--run_root",
                    str(models_root),
                    "--raw_counts_tsv",
                    str(counts_tsv),
                    "--transcript_metadata_tsv",
                    str(transcript_metadata_tsv),
                    "--phenotype_metadata_tsv",
                    str(phenotype_metadata_tsv),
                    "--feature_to_gene_tsv",
                    str(feature_to_gene_tsv),
                    "--rat_to_human_tsv",
                    str(rat_to_human_tsv),
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
