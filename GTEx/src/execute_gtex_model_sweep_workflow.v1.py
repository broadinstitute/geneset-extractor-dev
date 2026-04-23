#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("execute_gtex_model_sweep_workflow_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow_name", required=True)
    parser.add_argument("--workflow_plan_tsv", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--workflow_repo", required=True)
    parser.add_argument("--python_executable", default=sys.executable)
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def configure_logging(level: str, log_path: Path) -> None:
    resolved_level = getattr(logging, str(level).upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(resolved_level)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(resolved_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)
    LOGGER.info("wrote table: %s shape=%s", path, df.shape)


def load_module(module_name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_moved_gtex_path(path_str: str, repo_root: Path) -> Path:
    path = Path(str(path_str))
    if path.exists():
        return path
    old_prefix = Path("/home/ryank/work/geneset_extractors/gtex")
    try:
        relative = path.relative_to(old_prefix)
    except ValueError:
        return path
    return repo_root / relative


def run_one_tissue(
    *,
    workflow_repo: Path,
    python_executable: str,
    row: dict[str, str],
    workflow_cfg: dict[str, str],
    tissue_out_dir: Path,
    env: dict[str, str],
) -> tuple[Path, Path, Path]:
    cmd = [
        python_executable,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "rna_de_prepare",
        "--modality",
        "bulk",
        "--counts_tsv",
        str(Path(row["matrix_tsv"])),
        "--matrix_orientation",
        "gene_by_sample",
        "--feature_id_column",
        "Name",
        "--matrix_gene_symbol_column",
        "Description",
        "--sample_metadata_tsv",
        str(Path(row["sample_metadata_tsv"])),
        "--sample_id_column",
        "sample_id",
        "--group_column",
        "age_bin",
        "--comparisons_tsv",
        str(Path(row["comparisons_tsv"])),
        "--de_mode",
        workflow_cfg["workflow_de_mode"],
        "--backend",
        workflow_cfg["workflow_backend"],
        "--gene_filter_scope",
        workflow_cfg["workflow_gene_filter_scope"],
        "--balance_groups",
        workflow_cfg["workflow_balance_groups"],
        "--balance_seed",
        workflow_cfg["workflow_balance_seed"],
        "--out_dir",
        str(tissue_out_dir),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
    ]
    covariates = str(workflow_cfg["workflow_covariates"]).strip()
    if covariates:
        cmd.extend(["--covariates", covariates])
    LOGGER.info("running workflow tissue=%s", row["legacy_tissue"])
    subprocess.run(cmd, cwd=workflow_repo, env=env, check=True)
    return tissue_out_dir / "deg_long.tsv", tissue_out_dir / "comparison_audit.tsv", tissue_out_dir / "comparison_manifest.tsv"


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    repo_root = output_dir.parent.parent
    configure_logging(args.log_level, output_dir / "execute_gtex_model_sweep_workflow.v1.log")
    workflow_plan_df = pd.read_csv(Path(args.workflow_plan_tsv).resolve(), sep="\t", dtype=str)
    workflow_row = workflow_plan_df.loc[workflow_plan_df["workflow_name"] == args.workflow_name]
    if workflow_row.empty:
        raise ValueError(f"workflow_name not found: {args.workflow_name}")
    workflow = workflow_row.iloc[0].to_dict()

    for key in ["deg_long_tsv", "comparison_audit_tsv", "comparison_manifest_tsv"]:
        workflow[key] = str(Path(workflow[key]).resolve())

    if str(workflow["workflow_source"]).startswith("reuse"):
        for key in ["deg_long_tsv", "comparison_audit_tsv", "comparison_manifest_tsv"]:
            if not Path(workflow[key]).exists():
                raise FileNotFoundError(workflow[key])
        LOGGER.info("validated reused workflow=%s", args.workflow_name)
        return

    workflow_repo = Path(args.workflow_repo).resolve()
    harmonizome_module = load_module("gtex_harmonizome_v1", repo_root / "src" / "run_gtex_harmonizome_analysis.v1.py")
    base_prepared_dir = repo_root / "outputs" / "gtex_no_harmonizome_analysis_v1" / "prepared"
    matrix_manifest_df = pd.read_csv(base_prepared_dir / "tissue_matrix_manifest.v1.tsv", sep="\t", dtype=str)
    for column in ["matrix_tsv", "sample_metadata_tsv", "comparisons_tsv"]:
        matrix_manifest_df[column] = matrix_manifest_df[column].map(lambda value: str(resolve_moved_gtex_path(value, repo_root)))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(workflow_repo / "src")
    r_libs_user = repo_root / "outputs" / "r_libs_4.5"
    if r_libs_user.exists():
        env["R_LIBS_USER"] = str(r_libs_user.resolve())

    workflow_dir = Path(workflow["workflow_dir"])
    workflow_rows: list[dict[str, str]] = []
    workflow_cfg = {
        "workflow_de_mode": str(workflow["workflow_de_mode"]),
        "workflow_balance_groups": str(workflow["workflow_balance_groups"]),
        "workflow_balance_seed": str(workflow["workflow_balance_seed"]),
        "workflow_gene_filter_scope": str(workflow["workflow_gene_filter_scope"]),
        "workflow_covariates": str(workflow["workflow_covariates"]),
        "workflow_backend": str(workflow["workflow_backend"]),
    }
    for row in matrix_manifest_df.to_dict(orient="records"):
        tissue_name = str(row["legacy_tissue"])
        tissue_out_dir = workflow_dir / "rna_de_prepare" / f"{tissue_name}.v1"
        deg_long_tsv = tissue_out_dir / "deg_long.tsv"
        comparison_audit_tsv = tissue_out_dir / "comparison_audit.tsv"
        comparison_manifest_tsv = tissue_out_dir / "comparison_manifest.tsv"
        if args.resume and deg_long_tsv.exists() and comparison_audit_tsv.exists() and comparison_manifest_tsv.exists():
            LOGGER.info("reusing completed tissue=%s", tissue_name)
        else:
            deg_long_tsv, comparison_audit_tsv, comparison_manifest_tsv = run_one_tissue(
                workflow_repo=workflow_repo,
                python_executable=args.python_executable,
                row=row,
                workflow_cfg=workflow_cfg,
                tissue_out_dir=tissue_out_dir,
                env=env,
            )
        workflow_rows.append(
            {
                "legacy_tissue": tissue_name,
                "deg_long_tsv": str(deg_long_tsv),
                "comparison_audit_tsv": str(comparison_audit_tsv),
                "comparison_manifest_tsv": str(comparison_manifest_tsv),
            }
        )
    workflow_manifest_df = pd.DataFrame(workflow_rows).sort_values("legacy_tissue").reset_index(drop=True)
    write_dataframe(workflow_manifest_df, workflow_dir / "rna_de_prepare_manifest.v1.tsv")
    harmonizome_module.combine_workflow_outputs(workflow_manifest_df, workflow_dir)


if __name__ == "__main__":
    main()
