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
    parser.add_argument("--run_root")
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--top_n", type=int, default=20)
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
    run_root = Path(args.run_root).resolve() if args.run_root else (Path(args.out_root).resolve() / "pigean_eaggl")
    groups = sorted({model_group_for(model_id) for model_id in selected_models})
    script_path = Path(__file__).resolve().parent / "summarize_model_enrichment.py"
    for tissue_id in selected_tissues:
        for group in groups:
            group_models = [model_id for model_id in selected_models if model_group_for(model_id) == group]
            if not group_models:
                continue
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(script_path),
                    "--run_root",
                    str(run_root),
                    "--tissue",
                    tissue_id,
                    "--model_group",
                    group,
                    "--models",
                    ",".join(group_models),
                    "--top_n",
                    str(args.top_n),
                ]
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
