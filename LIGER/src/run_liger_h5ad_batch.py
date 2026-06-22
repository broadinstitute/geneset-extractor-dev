#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _safe_component(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._=-]+", "_", value.strip())
    out = re.sub(r"_+", "_", out).strip("_")
    return out or "item"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the DIG LIGER h5ad workflow for all .h5ad files under an input root."
    )
    parser.add_argument("--input_root", required=True, help="Root directory scanned recursively for .h5ad files.")
    parser.add_argument("--out_root", required=True, help="Output root for one subdirectory per input .h5ad file.")
    parser.add_argument("--dataset_column", default="donor_id")
    parser.add_argument("--cell_type_column", default="cell_type__kp")
    parser.add_argument("--organism", choices=["human", "mouse"], default="human")
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--max_cells_total", type=int, default=50000)
    parser.add_argument("--liger_top_n_genes", type=int, default=250)
    parser.add_argument("--extractor_top_k", type=int, default=250)
    parser.add_argument("--liger_k_grid", default="10,12,14,16,18,20,22,24")
    parser.add_argument("--liger_n_reps", type=int, default=5)
    parser.add_argument("--liger_fixed_k", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument(
        "--manifest_out",
        help="Optional JSON manifest path. Defaults to <out_root>/run_manifest.json.",
    )
    return parser


def run_command(command: list[str], *, cwd: Path | None = None) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd) if cwd is not None else None, check=True)


def discover_h5ad_files(input_root: Path) -> list[Path]:
    return sorted(path for path in input_root.rglob("*.h5ad") if path.is_file())


def output_dir_for(out_root: Path, input_root: Path, h5ad_path: Path) -> Path:
    rel_parent = h5ad_path.parent.relative_to(input_root)
    stem = _safe_component(h5ad_path.stem)
    return out_root / rel_parent / stem


def main() -> int:
    args = build_parser().parse_args()
    input_root = Path(args.input_root).resolve()
    out_root = Path(args.out_root).resolve()

    if not input_root.exists():
        raise SystemExit(f"Missing input_root: {input_root}")
    if not input_root.is_dir():
        raise SystemExit(f"Expected input_root to be a directory: {input_root}")

    out_root.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest_out).resolve() if args.manifest_out else out_root / "run_manifest.json"

    h5ad_files = discover_h5ad_files(input_root)
    if not h5ad_files:
        raise SystemExit(f"No .h5ad files found under {input_root}")

    manifest_rows: list[dict[str, object]] = []
    for h5ad_path in h5ad_files:
        run_out_dir = output_dir_for(out_root, input_root, h5ad_path)
        if run_out_dir.exists():
            if not args.overwrite:
                raise SystemExit(
                    f"Output already exists for {h5ad_path} at {run_out_dir}. Re-run with --overwrite to replace it."
                )
            shutil.rmtree(run_out_dir)
        run_out_dir.mkdir(parents=True, exist_ok=True)

        prepare_cmd = [
            args.python_bin,
            "-m",
            "geneset_extractors.cli",
            "workflows",
            "scrna_liger_prepare",
            "--h5ad",
            str(h5ad_path),
            "--out_dir",
            str(run_out_dir),
            "--organism",
            args.organism,
            "--genome_build",
            args.genome_build,
            "--max_cells_total",
            str(args.max_cells_total),
            "--liger_top_n_genes",
            str(args.liger_top_n_genes),
            "--extractor_top_k",
            str(args.extractor_top_k),
            "--liger_k_grid",
            str(args.liger_k_grid),
            "--liger_n_reps",
            str(args.liger_n_reps),
        ]
        if args.dataset_column.strip():
            prepare_cmd.extend(["--dataset_column", args.dataset_column.strip()])
        if args.cell_type_column.strip():
            prepare_cmd.extend(["--cell_type_column", args.cell_type_column.strip()])
        if args.liger_fixed_k is not None:
            prepare_cmd.extend(["--liger_fixed_k", str(args.liger_fixed_k)])

        run_command(prepare_cmd)

        subset_dir = run_out_dir / "subsets" / "all"
        run_liger_script = subset_dir / "run_liger.sh"
        run_convert_script = subset_dir / "run_geneset_extractors_from_liger.sh"
        if not run_liger_script.exists():
            raise SystemExit(f"Expected generated LIGER script was not created: {run_liger_script}")
        if not run_convert_script.exists():
            raise SystemExit(f"Expected generated converter script was not created: {run_convert_script}")

        run_command(["bash", str(run_liger_script)], cwd=subset_dir)
        run_command(["bash", str(run_convert_script)], cwd=subset_dir)

        manifest_rows.append(
            {
                "input_h5ad": str(h5ad_path),
                "output_dir": str(run_out_dir),
                "subset_dir": str(subset_dir),
                "run_liger_script": str(run_liger_script),
                "run_convert_script": str(run_convert_script),
                "liger_output_root": str(subset_dir / "liger_out"),
            }
        )

    manifest_payload = {
        "workflow": "liger_h5ad_batch",
        "input_root": str(input_root),
        "out_root": str(out_root),
        "dataset_column": args.dataset_column,
        "cell_type_column": args.cell_type_column,
        "n_inputs": len(manifest_rows),
        "runs": manifest_rows,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"completed liger_h5ad_batch n_inputs={len(manifest_rows)} manifest={manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
