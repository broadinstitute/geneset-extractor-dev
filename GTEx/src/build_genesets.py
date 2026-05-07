#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from selection_io import (
    default_model_list_path,
    default_tissue_list_path,
    gtex_root,
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
    parser.add_argument("--sample_metadata_tsv", default=str(repo_root() / "inputs" / "GTEx" / "v10" / "GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt"))
    parser.add_argument("--subject_metadata_tsv", default=str(repo_root() / "inputs" / "GTEx" / "v10" / "GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt"))
    parser.add_argument("--gtf", default=str(repo_root() / "inputs" / "GTEx" / "v10" / "gencode.v26.annotation.gtf.gz"))
    parser.add_argument("--outputs_root", default=str(gtex_root() / "outputs" / "genesets"))
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
    outputs_root = Path(args.outputs_root).resolve()
    src_root = gtex_root() / "src"

    age_binned_models = [model_id for model_id in selected_models if model_group_for(model_id) == "age_binned"]
    continuous_age_models = [model_id for model_id in selected_models if model_group_for(model_id) == "continuous_age"]
    unsupported_models = [model_id for model_id in selected_models if model_group_for(model_id) == "tissue_versus"]
    if unsupported_models:
        raise SystemExit("TV* geneset building is not implemented yet")

    conflicts: list[str] = []
    for tissue_id in selected_tissues:
        tissue_root = outputs_root / tissue_id
        prepared_dir = tissue_root / "prepared"
        if dir_nonempty(prepared_dir):
            conflicts.append(existing_output_message(tissue_id=tissue_id, model_id=None, path=prepared_dir))
        for model_id in [*age_binned_models, *continuous_age_models]:
            model_out = tissue_root / "models" / model_id
            if dir_nonempty(model_out):
                conflicts.append(existing_output_message(tissue_id=tissue_id, model_id=model_id, path=model_out))
    if conflicts and not args.overwrite:
        raise SystemExit("\n\n".join(conflicts))

    for tissue_id in selected_tissues:
        tissue_row = tissue_by_id[tissue_id]
        counts_gct = relative_or_absolute_path(str(tissue_row.get("counts_gct", "")).strip())
        if not counts_gct.exists():
            raise SystemExit(f"Missing counts file for {tissue_id}: {counts_gct}")
        tissue_label = str(tissue_row.get("tissue_label", "")).strip()
        if not tissue_label:
            raise SystemExit(f"Missing tissue_label for {tissue_id} in tissue list")
        tissue_root = outputs_root / tissue_id
        prepared_dir = tissue_root / "prepared"
        models_root = tissue_root / "models"
        if args.overwrite:
            overwrite_dir(prepared_dir)
            for model_id in [*age_binned_models, *continuous_age_models]:
                overwrite_dir(models_root / model_id)

        run_command(
            [
                str(Path(args.python_bin).resolve()),
                str(src_root / "build_tissue_inputs.py"),
                "--counts_gct",
                str(counts_gct),
                "--sample_metadata_tsv",
                str(relative_or_absolute_path(args.sample_metadata_tsv)),
                "--subject_metadata_tsv",
                str(relative_or_absolute_path(args.subject_metadata_tsv)),
                "--tissue_label",
                tissue_label,
                "--out_dir",
                str(prepared_dir),
            ]
        )

        for model_id in age_binned_models:
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
                    "--gtf",
                    str(relative_or_absolute_path(args.gtf)),
                ]
            )

        if continuous_age_models:
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
                    "--model_ids",
                    ",".join(continuous_age_models),
                    "--gtf",
                    str(relative_or_absolute_path(args.gtf)),
                ]
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
