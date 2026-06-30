#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from igvf_selection_io import (
    default_model_list_path,
    default_model_manifest_path,
    default_out_root,
    read_tsv,
    resolve_requested_ids,
    row_map,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="all")
    parser.add_argument("--models_file")
    parser.add_argument("--model_list", default=str(default_model_list_path()))
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--expression_tsv", required=True, help="Processed per-perturbation signature matrix TSV.")
    parser.add_argument("--mapping_file", help="Optional gene id->symbol mapping TSV.")
    parser.add_argument(
        "--analysis_set_id",
        default="all_signatures",
        help="IGVF analysis-set accession; used as the output partition and recorded in the model sidecar.",
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


def existing_output_message(*, model_id: str, path: Path) -> str:
    return (
        f"Output already exists for model={model_id}:\n{path}\n\n"
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
    selected_models = resolve_requested_ids(
        csv_text=args.models,
        file_path=args.models_file,
        rows=model_rows,
        key_field="model_id",
    )
    model_by_id = row_map(model_rows, "model_id")

    out_root = Path(args.out_root).resolve()
    outputs_root = out_root / "genesets"
    src_root = Path(__file__).resolve().parent

    model_manifest = require_existing_file(args.model_manifest, "model manifest")
    expression_tsv = require_existing_file(args.expression_tsv, "expression TSV")
    mapping_file = require_existing_file(args.mapping_file, "mapping file") if args.mapping_file else None
    dig_dir = Path(args.dig_dir).expanduser().resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    conflicts: list[str] = []
    for model_id in selected_models:
        model_out = outputs_root / args.analysis_set_id / "models" / model_id
        if dir_nonempty(model_out):
            conflicts.append(existing_output_message(model_id=model_id, path=model_out))
    if conflicts and not args.overwrite:
        raise SystemExit("\n\n".join(conflicts))

    if args.overwrite:
        for model_id in selected_models:
            overwrite_dir(outputs_root / "all_signatures" / "models" / model_id)

    for model_id in selected_models:
        model_family = str(model_by_id[model_id].get("model_family", "")).strip()
        if model_family != "perturbseq":
            raise SystemExit(f"Unsupported IGVF model family for {model_id}: {model_family}")
        run_command(
            [
                str(Path(args.python_bin).resolve()),
                str(src_root / "run_igvf_perturbseq_model.py"),
                "--model_id",
                model_id,
                "--analysis_set_id",
                args.analysis_set_id,
                "--run_root",
                str(outputs_root / args.analysis_set_id / "models"),
                "--python_bin",
                str(Path(args.python_bin).resolve()),
                "--dig_dir",
                str(dig_dir),
                "--expression_tsv",
                str(expression_tsv),
                "--model_manifest",
                str(model_manifest),
            ]
            + (["--mapping_file", str(mapping_file)] if mapping_file else [])
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
