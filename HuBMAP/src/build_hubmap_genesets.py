#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from hubmap_selection_io import (
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
    parser.add_argument("--raw_asctb_dir")
    parser.add_argument("--asctb_dir")
    parser.add_argument("--input_matrix")
    parser.add_argument("--human_gene_info", required=True)
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


def require_existing_dir(path_text: str | None, label: str) -> Path:
    if not path_text:
        raise SystemExit(f"Missing required argument for {label}")
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_dir():
        raise SystemExit(f"Expected {label} to be a directory: {path}")
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
    human_gene_info = require_existing_file(args.human_gene_info, "human_gene_info")
    dig_dir = Path(args.dig_dir).expanduser().resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    raw_asctb_dir = require_existing_dir(args.raw_asctb_dir, "raw ASCT+B directory") if args.raw_asctb_dir else None
    asctb_dir = Path(args.asctb_dir).expanduser().resolve() if args.asctb_dir else None
    input_matrix = require_existing_file(args.input_matrix, "input matrix") if args.input_matrix else None

    conflicts: list[str] = []
    for model_id in selected_models:
        model_out = outputs_root / "all_signatures" / "models" / model_id
        if dir_nonempty(model_out):
            conflicts.append(existing_output_message(model_id=model_id, path=model_out))
    if conflicts and not args.overwrite:
        raise SystemExit("\n\n".join(conflicts))

    if args.overwrite:
        for model_id in selected_models:
            overwrite_dir(outputs_root / "all_signatures" / "models" / model_id)

    for model_id in selected_models:
        model_family = str(model_by_id[model_id].get("model_family", "")).strip()
        if model_family != "hz_released_asctb":
            raise SystemExit(f"Unsupported HuBMAP model family for {model_id}")
        cmd = [
            str(Path(args.python_bin).resolve()),
            str(src_root / "run_hubmap_hz_model.py"),
            "--model_id",
            model_id,
            "--run_root",
            str(outputs_root / "all_signatures" / "models"),
            "--python_bin",
            str(Path(args.python_bin).resolve()),
            "--dig_dir",
            str(dig_dir),
            "--human_gene_info",
            str(human_gene_info),
            "--model_manifest",
            str(model_manifest),
        ]
        if model_id == "HZ1":
            if raw_asctb_dir is None:
                raise SystemExit("HZ1 requires --raw_asctb_dir")
            cmd.extend(["--raw_asctb_dir", str(raw_asctb_dir)])
        elif model_id == "HZ2":
            resolved_input_matrix = input_matrix
            if resolved_input_matrix is None:
                sibling_hz1_matrix = outputs_root / "all_signatures" / "models" / "HZ1" / "workflow" / "gene_attribute_matrix.txt.gz"
                if sibling_hz1_matrix.exists():
                    resolved_input_matrix = sibling_hz1_matrix
                elif "HZ1" in selected_models:
                    resolved_input_matrix = sibling_hz1_matrix
                else:
                    raise SystemExit("HZ2 requires --input_matrix or an existing HZ1 workflow gene_attribute_matrix.txt.gz")
            cmd.extend(["--input_matrix", str(resolved_input_matrix)])
        if args.provenance_mirror_local_prefix:
            cmd.extend(["--provenance_mirror_local_prefix", args.provenance_mirror_local_prefix])
        if args.provenance_mirror_remote_prefix:
            cmd.extend(["--provenance_mirror_remote_prefix", args.provenance_mirror_remote_prefix])
        run_command(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
