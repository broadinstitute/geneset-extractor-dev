#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from selection_io import (
    default_age_binned_model_manifest_path,
    default_continuous_age_model_manifest_path,
    default_out_root,
    default_model_list_path,
    default_tissue_list_path,
    load_model_rows,
    load_tissue_rows,
    model_group_for,
    relative_or_absolute_path,
    repo_root,
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
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--sample_metadata_tsv", required=True)
    parser.add_argument("--subject_metadata_tsv", required=True)
    parser.add_argument("--gtf")
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--age_binned_model_manifest", default=str(default_age_binned_model_manifest_path()))
    parser.add_argument("--continuous_age_model_manifest", default=str(default_continuous_age_model_manifest_path()))
    parser.add_argument("--dig_dir", required=True)
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


def existing_output_message(*, tissue_id: str, model_id: str | None, path: Path) -> str:
    header = f"Output already exists for tissue={tissue_id}"
    if model_id is not None:
        header += f" model={model_id}"
    return (
        f"{header}:\n{path}\n\n"
        "Refusing to continue because --overwrite was not provided.\n"
        "Re-run with --overwrite to replace this output."
    )


def model_requires_gtf(row: dict[str, str]) -> bool:
    value = str(row.get("require_gtf", "")).strip().lower()
    return value in {"true", "1", "yes"}


def require_existing_file(path_text: str, label: str) -> Path:
    path = relative_or_absolute_path(path_text)
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_file():
        raise SystemExit(f"Expected {label} to be a file: {path}")
    return path


def main() -> int:
    args = build_parser().parse_args()
    model_rows = load_model_rows(Path(args.model_list))
    tissue_rows = load_tissue_rows(Path(args.tissue_list))
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
    tissue_by_id = row_map(tissue_rows, "tissue_id")
    model_by_id = row_map(model_rows, "model_id")
    out_root = Path(args.out_root).resolve()
    outputs_root = out_root / "genesets"
    src_root = repo_root() / "geneset-extractor-dev" / "GTEx" / "src"
    sample_metadata_tsv = require_existing_file(args.sample_metadata_tsv, "sample metadata TSV")
    subject_metadata_tsv = require_existing_file(args.subject_metadata_tsv, "subject metadata TSV")
    age_binned_model_manifest = require_existing_file(args.age_binned_model_manifest, "age-binned model manifest")
    continuous_age_model_manifest = require_existing_file(args.continuous_age_model_manifest, "continuous-age model manifest")
    dig_dir = Path(relative_or_absolute_path(args.dig_dir)).resolve()
    if not dig_dir.exists():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")
    if not dig_dir.is_dir():
        raise SystemExit(f"Expected dig-gene-set-extractors path to be a directory: {dig_dir}")

    age_binned_models = [model_id for model_id in selected_models if model_group_for(model_id) == "age_binned"]
    continuous_age_models = [model_id for model_id in selected_models if model_group_for(model_id) == "continuous_age"]
    unsupported_models = [model_id for model_id in selected_models if model_group_for(model_id) == "tissue_versus"]
    if unsupported_models:
        raise SystemExit("TV* geneset building is not implemented yet")
    gtf_required_models = [model_id for model_id in selected_models if model_requires_gtf(model_by_id[model_id])]
    model_list_gtf_required_models = [
        str(row["model_id"]).strip()
        for row in model_rows
        if model_requires_gtf(row)
    ]
    resolved_gtf: Path | None = None
    if args.gtf:
        resolved_gtf = require_existing_file(args.gtf, "GTF")
    if model_list_gtf_required_models and resolved_gtf is None:
        raise SystemExit(
            "The active model_list contains models that require --gtf but none was provided: "
            + ", ".join(model_list_gtf_required_models)
        )

    conflicts: list[str] = []
    for tissue_id in selected_tissues:
        tissue_root = outputs_root / tissue_id
        for model_id in [*age_binned_models, *continuous_age_models]:
            model_out = tissue_root / "models" / model_id
            if dir_nonempty(model_out):
                conflicts.append(existing_output_message(tissue_id=tissue_id, model_id=model_id, path=model_out))
    if conflicts and not args.overwrite:
        raise SystemExit("\n\n".join(conflicts))

    for tissue_id in selected_tissues:
        tissue_row = tissue_by_id[tissue_id]
        counts_gct_value = str(tissue_row.get("counts_gct", "")).strip()
        if not counts_gct_value:
            raise SystemExit(
                f"Missing counts_gct for tissue={tissue_id} in tissue list {Path(args.tissue_list).resolve()}"
            )
        counts_gct = relative_or_absolute_path(counts_gct_value)
        if not counts_gct.exists():
            raise SystemExit(f"Missing counts file for {tissue_id}: {counts_gct}")
        tissue_label = str(tissue_row.get("tissue_label", "")).strip()
        if not tissue_label:
            raise SystemExit(f"Missing tissue_label for {tissue_id} in tissue list")
        tissue_root = outputs_root / tissue_id
        prepared_dir = tissue_root / "prepared"
        models_root = tissue_root / "models"
        if args.overwrite:
            for model_id in [*age_binned_models, *continuous_age_models]:
                overwrite_dir(models_root / model_id)
        if not dir_nonempty(prepared_dir):
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "build_tissue_inputs.py"),
                    "--counts_gct",
                    str(counts_gct),
                    "--sample_metadata_tsv",
                    str(sample_metadata_tsv),
                    "--subject_metadata_tsv",
                    str(subject_metadata_tsv),
                    "--tissue_label",
                    tissue_label,
                    "--out_dir",
                    str(prepared_dir),
                ]
            )

        for model_id in age_binned_models:
            needs_gtf = model_requires_gtf(model_by_id[model_id])
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "run_age_binned_model.py"),
                    "--model_id",
                    model_id,
                    "--prepared_dir",
                    str(prepared_dir),
                    "--run_root",
                    str(models_root),
                    "--python_bin",
                    str(Path(args.python_bin).resolve()),
                    "--dig_dir",
                    str(dig_dir),
                    "--age_binned_model_manifest",
                    str(age_binned_model_manifest),
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
                + (
                    ["--gtf", str(resolved_gtf)]
                    if resolved_gtf is not None and needs_gtf
                    else []
                )
            )

        if continuous_age_models:
            any_continuous_age_needs_gtf = any(
                model_requires_gtf(model_by_id[model_id]) for model_id in continuous_age_models
            )
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "run_continuous_age_model.py"),
                    "--python_bin",
                    str(Path(args.python_bin).resolve()),
                    "--rscript_bin",
                    args.rscript_bin,
                    "--tissue_id",
                    tissue_id,
                    "--prepared_dir",
                    str(prepared_dir),
                    "--run_root",
                    str(models_root),
                    "--dig_dir",
                    str(dig_dir),
                    "--continuous_age_model_manifest",
                    str(continuous_age_model_manifest),
                    "--model_ids",
                    ",".join(continuous_age_models),
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
                + (
                    ["--gtf", str(resolved_gtf)]
                    if resolved_gtf is not None and any_continuous_age_needs_gtf
                    else []
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
