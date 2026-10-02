#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

from lincs_l1000_selection_io import (
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
    parser.add_argument("--chempert_expression_tsv")
    parser.add_argument("--crisprko_expression_tsv")
    parser.add_argument("--cp_coeff_gctx")
    parser.add_argument("--cp_block_size", type=int, default=256)
    parser.add_argument(
        "--hz4_partition_mode",
        choices=["all_signatures", "cell_line_time"],
        default="all_signatures",
        help="HZ4 only: export all signatures together or use cell-line × perturbation-time task worklists.",
    )
    parser.add_argument(
        "--hz4_partition_plan_dir",
        help="HZ4 cell_line_time task-plan directory (defaults below --out_root).",
    )
    parser.add_argument(
        "--hz4_task_id",
        help="HZ4 cell_line_time task id from task_manifest.tsv to export.",
    )
    parser.add_argument(
        "--hz4_max_signatures_per_task",
        type=int,
        default=10000,
        help="HZ4 cell_line_time maximum retained signatures per task (default: 10000).",
    )
    parser.add_argument("--mapping_file")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--out_root", default=str(default_out_root()))
    parser.add_argument("--overwrite", action="store_true")
    return parser


def run_command(command: list[str], env: dict[str, str] | None = None) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


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


def read_hz4_task(plan_dir: Path, task_id: str) -> dict[str, str]:
    manifest_path = plan_dir / "task_manifest.tsv"
    if not manifest_path.is_file():
        raise SystemExit(f"Missing HZ4 task manifest: {manifest_path}")
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    matches = [row for row in rows if row.get("task_id") == task_id]
    if len(matches) != 1:
        raise SystemExit(f"HZ4 task id {task_id!r} was not found exactly once in {manifest_path}")
    row = matches[0]
    index_path = Path(row.get("raw_indices_tsv", "")).resolve()
    if not index_path.is_file():
        raise SystemExit(f"Missing HZ4 raw-index worklist for {task_id}: {index_path}")
    return row


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
    mapping_file = require_existing_file(args.mapping_file, "mapping file") if any(model in {"HZ1", "HZ2"} for model in selected_models) else None
    dig_dir = Path(args.dig_dir).expanduser().resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    input_by_model = {
        "HZ1": require_existing_file(args.chempert_expression_tsv, "chempert expression TSV") if "HZ1" in selected_models else None,
        "HZ2": require_existing_file(args.crisprko_expression_tsv, "crisprko expression TSV") if "HZ2" in selected_models else None,
        "HZ3": require_existing_file(args.cp_coeff_gctx, "CP coefficient GCTX") if "HZ3" in selected_models else None,
        "HZ4": require_existing_file(args.cp_coeff_gctx, "CP coefficient GCTX") if "HZ4" in selected_models else None,
    }

    hz4_task: dict[str, str] | None = None
    hz4_plan_dir: Path | None = None
    if args.hz4_partition_mode == "cell_line_time":
        if "HZ4" not in selected_models:
            raise SystemExit("--hz4_partition_mode cell_line_time requires --models HZ4")
        if len(selected_models) != 1:
            raise SystemExit("--hz4_partition_mode cell_line_time supports HZ4 alone; submit HZ1/HZ2 separately")
        hz4_plan_dir = Path(args.hz4_partition_plan_dir).resolve() if args.hz4_partition_plan_dir else outputs_root / "hz4_cell_line_time_plan"
        if args.hz4_task_id:
            hz4_task = read_hz4_task(hz4_plan_dir, args.hz4_task_id)
        else:
            plan_env = {**os.environ, "PYTHONPATH": str(dig_dir / "src") + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    "-m",
                    "geneset_extractors.cli",
                    "workflows",
                    "lincs_l1000_cp",
                    "--gctx_path",
                    str(input_by_model["HZ4"]),
                    "--plan_cell_line_time",
                    "--partition_plan_dir",
                    str(hz4_plan_dir),
                    "--max_signatures_per_task",
                    str(args.hz4_max_signatures_per_task),
                ],
                env=plan_env,
            )
            print(
                f"HZ4 partition plan written to {hz4_plan_dir}. "
                "Re-run with --hz4_task_id TASK_ID to export one task.",
                flush=True,
            )
            return 0
    elif args.hz4_task_id or args.hz4_partition_plan_dir:
        raise SystemExit("--hz4_task_id and --hz4_partition_plan_dir require --hz4_partition_mode cell_line_time")

    conflicts: list[str] = []
    for model_id in selected_models:
        partition_id = hz4_task["task_id"] if model_id == "HZ4" and hz4_task else "all_signatures"
        model_out = outputs_root / partition_id / "models" / model_id
        if dir_nonempty(model_out):
            conflicts.append(existing_output_message(model_id=model_id, path=model_out))
    if conflicts and not args.overwrite:
        raise SystemExit("\n\n".join(conflicts))

    if args.overwrite:
        for model_id in selected_models:
            partition_id = hz4_task["task_id"] if model_id == "HZ4" and hz4_task else "all_signatures"
            overwrite_dir(outputs_root / partition_id / "models" / model_id)

    for model_id in selected_models:
        model_family = str(model_by_id[model_id].get("model_family", "")).strip()
        if model_family == "consensus_median":
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "run_lincs_l1000_consensus_median_model.py"),
                    "--run_root", str(outputs_root / "all_signatures" / "models"),
                    "--python_bin", str(Path(args.python_bin).resolve()),
                    "--dig_dir", str(dig_dir),
                    "--gctx_path", str(input_by_model[model_id]),
                ]
            )
            continue
        if model_family == "cd_signature_export":
            partition_id = hz4_task["task_id"] if hz4_task else "all_signatures"
            run_command(
                [
                    str(Path(args.python_bin).resolve()),
                    str(src_root / "run_lincs_l1000_cp_model.py"),
                    "--run_root", str(outputs_root / partition_id / "models"),
                    "--python_bin", str(Path(args.python_bin).resolve()),
                    "--dig_dir", str(dig_dir),
                    "--gctx_path", str(input_by_model[model_id]),
                    "--block_size", str(args.cp_block_size),
                ]
                + (["--raw_indices_tsv", hz4_task["raw_indices_tsv"]] if hz4_task else [])
                + (["--partition_id", partition_id] if hz4_task else [])
                + (["--cell_line", hz4_task["cell_line"]] if hz4_task else [])
                + (["--pert_time", hz4_task["pert_time"]] if hz4_task else [])
            )
            continue
        if model_family != "hz_released_matrix":
            raise SystemExit(f"Unsupported LINCS_L1000 model family for {model_id}")
        expression_tsv = input_by_model.get(model_id)
        if expression_tsv is None:
            raise SystemExit(f"Missing expression input for model {model_id}")
        run_command(
            [
                str(Path(args.python_bin).resolve()),
                str(src_root / "run_lincs_l1000_hz_model.py"),
                "--model_id",
                model_id,
                "--run_root",
                str(outputs_root / "all_signatures" / "models"),
                "--python_bin",
                str(Path(args.python_bin).resolve()),
                "--dig_dir",
                str(dig_dir),
                "--expression_tsv",
                str(expression_tsv),
                "--mapping_file",
                str(mapping_file),
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
