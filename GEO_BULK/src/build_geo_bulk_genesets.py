#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from geo_bulk_selection_io import (
    default_dataset_list_path,
    default_model_list_path,
    read_tsv,
    resolve_ids,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", default="all")
    parser.add_argument("--models", default="all")
    parser.add_argument("--dataset_list", default=str(default_dataset_list_path()))
    parser.add_argument("--model_list", default=str(default_model_list_path()))
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--input_root", required=True)
    parser.add_argument("--out_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--backend")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    datasets = resolve_ids(args.datasets, read_tsv(Path(args.dataset_list)), "dataset_id")
    models = resolve_ids(args.models, read_tsv(Path(args.model_list)), "model_id")
    runner = Path(__file__).resolve().parent / "run_geo_bulk_model.py"
    for dataset_id in datasets:
        for model_id in models:
            command = [
                str(Path(args.python_bin).resolve()),
                str(runner),
                "--dataset_id",
                dataset_id,
                "--model_id",
                model_id,
                "--dataset_list",
                str(Path(args.dataset_list).resolve()),
                "--dig_dir",
                str(Path(args.dig_dir).resolve()),
                "--input_root",
                str(Path(args.input_root).resolve()),
                "--out_root",
                str(Path(args.out_root).resolve()),
                "--python_bin",
                str(Path(args.python_bin).resolve()),
            ]
            if args.backend:
                command.extend(["--backend", args.backend])
            if args.overwrite:
                command.append("--overwrite")
            if args.offline:
                command.append("--offline")
            subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
