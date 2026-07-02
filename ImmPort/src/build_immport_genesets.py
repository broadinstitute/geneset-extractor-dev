#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from immport_selection_io import (
    default_model_list_path,
    default_model_manifest_path,
    default_out_root,
    default_study_list_path,
    read_tsv,
    resolve_requested_ids,
    row_map,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="all")
    parser.add_argument("--models_file")
    parser.add_argument("--studies", default="all")
    parser.add_argument("--studies_file")
    parser.add_argument("--model_list", default=str(default_model_list_path()))
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--study_list", default=str(default_study_list_path()))
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument(
        "--inputs_root",
        required=True,
        help="Directory containing per-study input subdirectories: <inputs_root>/<study_id>/<expression_object> etc.",
    )
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


def existing_output_message(*, model_id: str, study_id: str, path: Path) -> str:
    return (
        f"Output already exists for study={study_id} model={model_id}:\n{path}\n\n"
        "Refusing to continue because --overwrite was not provided.\n"
        "Re-run with --overwrite to replace this output."
    )


def require_existing_file(path_text: str | None, label: str) -> Path:
    if not path_text:
        raise SystemExit(f"Missing required argument for {label}")
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_file():
        raise SystemExit(f"Expected {label} to be a file: {path}")
    return path


def main() -> int:
    args = build_parser().parse_args()
    model_rows = read_tsv(Path(args.model_list))
    study_rows = read_tsv(Path(args.study_list))
    selected_models = resolve_requested_ids(
        csv_text=args.models, file_path=args.models_file, rows=model_rows, key_field="model_id"
    )
    selected_studies = resolve_requested_ids(
        csv_text=args.studies, file_path=args.studies_file, rows=study_rows, key_field="study_id"
    )
    model_by_id = row_map(model_rows, "model_id")
    study_by_id = row_map(study_rows, "study_id")

    out_root = Path(args.out_root).resolve()
    outputs_root = out_root / "genesets"
    src_root = Path(__file__).resolve().parent
    inputs_root = Path(args.inputs_root).expanduser().resolve()

    model_manifest = require_existing_file(args.model_manifest, "model manifest")
    dig_dir = Path(args.dig_dir).expanduser().resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    conflicts: list[str] = []
    for study_id in selected_studies:
        for model_id in selected_models:
            model_out = outputs_root / study_id / "models" / model_id
            if dir_nonempty(model_out):
                conflicts.append(existing_output_message(model_id=model_id, study_id=study_id, path=model_out))
    if conflicts and not args.overwrite:
        raise SystemExit("\n\n".join(conflicts))

    if args.overwrite:
        for study_id in selected_studies:
            for model_id in selected_models:
                overwrite_dir(outputs_root / study_id / "models" / model_id)

    for study_id in selected_studies:
        study = study_by_id[study_id]
        case_label = str(study.get("case_label", "")).strip()
        control_label = str(study.get("control_label", "")).strip()
        covariates = str(study.get("covariates", "")).strip()
        study_accession = str(study.get("study_accession", "")).strip() or study_id
        released_de_object = str(study.get("released_de_object", "")).strip()

        if released_de_object:
            # Released-DE mode: the study ships a precomputed DE table. Its path is resolved
            # relative to inputs_root (it may live under the real accession's data subdir,
            # decoupled from the partition key study_id).
            released_de_tsv = require_existing_file(
                str(inputs_root / released_de_object), f"released DE table for {study_id}"
            )
            expression_tsv = None
            sample_metadata_tsv = None
            group_column = ""
            if not (case_label and control_label):
                raise SystemExit(f"study_list row for {study_id} missing case_label/control_label")
        else:
            study_inputs = inputs_root / study_id
            released_de_tsv = None
            expression_tsv = require_existing_file(
                str(study_inputs / str(study.get("expression_object", "")).strip()), f"expression for {study_id}"
            )
            sample_metadata_tsv = require_existing_file(
                str(study_inputs / str(study.get("sample_metadata_object", "")).strip()),
                f"sample metadata for {study_id}",
            )
            group_column = str(study.get("group_column", "")).strip()
            if not (group_column and case_label and control_label):
                raise SystemExit(f"study_list row for {study_id} missing group_column/case_label/control_label")

        for model_id in selected_models:
            model_family = str(model_by_id[model_id].get("model_family", "")).strip()
            if model_family != "bulk_de":
                raise SystemExit(f"Unsupported ImmPort model family for {model_id}: {model_family}")
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "run_immport_bulk_de_model.py"),
                    "--model_id",
                    model_id,
                    "--study_id",
                    study_id,
                    "--study_accession",
                    study_accession,
                    "--study_label",
                    str(study.get("study_label", "")).strip(),
                    "--run_root",
                    str(outputs_root / study_id / "models"),
                    "--python_bin",
                    str(Path(args.python_bin).resolve()),
                    "--dig_dir",
                    str(dig_dir),
                    "--case_label",
                    case_label,
                    "--control_label",
                    control_label,
                    "--model_manifest",
                    str(model_manifest),
                ]
                + (["--released_de_tsv", str(released_de_tsv)] if released_de_tsv else [])
                + (["--expression_tsv", str(expression_tsv)] if expression_tsv else [])
                + (["--sample_metadata_tsv", str(sample_metadata_tsv)] if sample_metadata_tsv else [])
                + (["--group_column", group_column] if group_column else [])
                + (["--covariates", covariates] if covariates else [])
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
