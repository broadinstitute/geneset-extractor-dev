#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("execute_gtex_model_sweep_model_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", required=True)
    parser.add_argument("--model_run_plan_tsv", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--reference_gmt_gz", required=True)
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


def load_module(module_name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    LOGGER.info("wrote text: %s", path)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    repo_root = output_dir.parent.parent
    configure_logging(args.log_level, output_dir / "execute_gtex_model_sweep_model.v1.log")

    model_plan_df = pd.read_csv(Path(args.model_run_plan_tsv).resolve(), sep="\t", dtype=str)
    model_row = model_plan_df.loc[model_plan_df["model_name"] == args.model_name]
    if model_row.empty:
        raise ValueError(f"model_name not found: {args.model_name}")
    row = model_row.iloc[0]

    named_model_gmt_gz = Path(str(row["named_model_gmt_gz"]))
    comparison_md = Path(str(row["comparison_to_reference_md"]))
    if args.resume and named_model_gmt_gz.exists() and comparison_md.exists():
        LOGGER.info("reusing completed model=%s", args.model_name)
        return

    deg_long_tsv = Path(str(row["deg_long_tsv"]))
    if not deg_long_tsv.exists():
        raise FileNotFoundError(f"expected workflow DEG table not found: {deg_long_tsv}")

    workflow_repo = Path(args.workflow_repo).resolve()
    harmonizome_module = load_module("gtex_harmonizome_v1", repo_root / "src" / "run_gtex_harmonizome_analysis.v1.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workflow_repo / "src")
    model_dir = Path(str(row["model_dir"]))
    rna_deg_multi_out_dir = model_dir / "rna_deg_multi.v1"

    cmd = [
        args.python_executable,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg_multi",
        "--deg_tsv",
        str(deg_long_tsv),
        "--comparison_column",
        "comparison_id",
        "--out_dir",
        str(rna_deg_multi_out_dir),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--postprocess_mode",
        str(row["extractor_postprocess_mode"]),
        "--score_mode",
        str(row["extractor_score_mode"]),
        "--select",
        str(row["extractor_select"]),
        "--top_k",
        str(row["extractor_top_k"]),
        "--gmt_source",
        str(row["extractor_gmt_source"]),
        "--gmt_topk_list",
        str(row["extractor_gmt_topk_list"]),
        "--gmt_min_genes",
        str(row["extractor_gmt_min_genes"]),
        "--gmt_max_genes",
        str(row["extractor_gmt_max_genes"]),
    ]
    if str(row["extractor_disable_default_excludes"]).lower() == "true":
        cmd.extend(["--disable_default_excludes", "true"])
    if str(row["extractor_gmt_biotype_allowlist"]).strip():
        cmd.extend(["--gmt_biotype_allowlist", str(row["extractor_gmt_biotype_allowlist"])])
    if str(row["extractor_padj_max"]).strip():
        cmd.extend(["--padj_max", str(row["extractor_padj_max"])])
    if str(row["extractor_pvalue_max"]).strip():
        cmd.extend(["--pvalue_max", str(row["extractor_pvalue_max"])])
    if str(row["extractor_min_abs_logfc"]).strip():
        cmd.extend(["--min_abs_logfc", str(row["extractor_min_abs_logfc"])])

    LOGGER.info("running model=%s", args.model_name)
    subprocess.run(cmd, cwd=workflow_repo, env=env, check=True)
    generated_gmt_tsv = model_dir / "rna_deg_multi.v1" / "genesets.gmt"
    if not generated_gmt_tsv.exists():
        raise FileNotFoundError(generated_gmt_tsv)
    _, legacy_gmt_gz = harmonizome_module.convert_generated_gmt_to_legacy_names(generated_gmt_tsv, model_dir)
    harmonizome_module.compare_to_reference(Path(args.reference_gmt_gz).resolve(), legacy_gmt_gz, model_dir)
    shutil.copyfile(legacy_gmt_gz, named_model_gmt_gz)
    write_text(" ".join(cmd) + "\n", model_dir / "extractor_command.v1.sh")


if __name__ == "__main__":
    main()
