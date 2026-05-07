#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from selection_io import (
    default_out_root,
    default_model_list_path,
    default_tissue_list_path,
    planning_root,
    load_model_rows,
    load_tissue_rows,
    model_group_for,
    resolve_requested_ids,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="all")
    parser.add_argument("--models_file")
    parser.add_argument("--tissues", default="all")
    parser.add_argument("--tissues_file")
    parser.add_argument("--model_list", default=str(default_model_list_path()))
    parser.add_argument("--tissue_list", default=str(default_tissue_list_path()))
    parser.add_argument("--out_root", default=str(default_out_root()))
    parser.add_argument("--pigean_root")
    parser.add_argument("--genesets_root")
    parser.add_argument("--planning_root", default=str(planning_root()))
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--top_n", type=int, default=5)
    return parser


def run_command(command: list[str]) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    args = build_parser().parse_args()
    model_rows = load_model_rows(Path(args.model_list))
    tissue_rows = load_tissue_rows(Path(args.tissue_list))
    selected_models = resolve_requested_ids(csv_text=args.models, file_path=args.models_file, rows=model_rows, key_field="model_id")
    selected_tissues = resolve_requested_ids(csv_text=args.tissues, file_path=args.tissues_file, rows=tissue_rows, key_field="tissue_id")
    out_root = Path(args.out_root).resolve()
    pigean_root = Path(args.pigean_root).resolve() if args.pigean_root else (out_root / "pigean_eaggl")
    genesets_root = Path(args.genesets_root).resolve() if args.genesets_root else (out_root / "genesets")
    groups = sorted({model_group_for(model_id) for model_id in selected_models})
    script_path = Path(__file__).resolve().parent / "summarize_top_models.py"
    for tissue_id in selected_tissues:
        run_command(
            [
                str(Path(args.python_bin).resolve()),
                str(script_path),
                "--pigean_root",
                str(pigean_root),
                "--genesets_root",
                str(genesets_root),
                "--planning_root",
                str(Path(args.planning_root).resolve()),
                "--tissue",
                tissue_id,
                "--model_groups",
                ",".join(groups),
                "--models",
                ",".join(selected_models),
                "--top_n",
                str(args.top_n),
            ]
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
