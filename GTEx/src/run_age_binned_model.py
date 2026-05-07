#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import shlex
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one GTEx age-binned model and emit extractor outputs."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--prepared_dir", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--organism", default="human", choices=["human", "mouse"])
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--gtf")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--write_commands_only", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_manifest_path() -> Path:
    return (
        repo_root()
        / "geneset-extractor-dev"
        / "GTEx"
        / "planning"
        / "geneset_build"
        / "age_binned_models"
        / "model_manifest.tsv"
    )


def resolve_input_path(path_value: str | None, *, base_dir: Path) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def load_model_settings() -> dict[str, dict[str, str]]:
    manifest_path = default_manifest_path()
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    settings: dict[str, dict[str, str]] = {}
    for row in rows:
        model_id = str(row.get("model_id", "")).strip()
        if model_id:
            settings[model_id] = {str(key): str(value) for key, value in row.items()}
    if not settings:
        raise SystemExit(f"No age-binned model settings found in {manifest_path}")
    return settings


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def build_workflow_cmd(
    *,
    python_bin: str,
    prepared_dir: Path,
    workflow_out: Path,
    organism: str,
    genome_build: str,
    settings: dict[str, str],
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "rna_de_prepare",
        "--modality",
        "bulk",
        "--counts_tsv",
        str(prepared_dir / "tissue_counts.tsv"),
        "--matrix_orientation",
        "gene_by_sample",
        "--feature_id_column",
        "gene_id",
        "--matrix_gene_symbol_column",
        "gene_symbol",
        "--sample_metadata_tsv",
        str(prepared_dir / "sample_metadata.tsv"),
        "--sample_id_column",
        "sample_id",
        "--group_column",
        "age_bin",
        "--comparisons_tsv",
        str(prepared_dir / "comparisons.tsv"),
        "--de_mode",
        settings["workflow_de_mode"],
        "--balance_groups",
        settings["workflow_balance_groups"],
        "--balance_seed",
        settings["workflow_balance_seed"],
        "--gene_filter_scope",
        settings["workflow_gene_filter_scope"],
        "--backend",
        settings["workflow_backend"],
        "--out_dir",
        str(workflow_out),
        "--organism",
        organism,
        "--genome_build",
        genome_build,
    ]
    if settings["workflow_covariates"] != "none":
        cmd.extend(["--covariates", settings["workflow_covariates"]])
    return cmd


def build_extractor_cmd(
    *,
    python_bin: str,
    workflow_out: Path,
    extractor_out: Path,
    organism: str,
    genome_build: str,
    model_id: str,
    settings: dict[str, str],
    gtf_path: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg_multi",
        "--deg_tsv",
        str(workflow_out / "deg_long.tsv"),
        "--comparison_column",
        "comparison_id",
        "--out_dir",
        str(extractor_out),
        "--organism",
        organism,
        "--genome_build",
        genome_build,
        "--signature_name",
        model_id,
        "--postprocess_mode",
        settings["extractor_postprocess_mode"],
        "--score_mode",
        settings["extractor_score_mode"],
        "--select",
        settings["extractor_select"],
        "--normalize",
        "within_set_l1",
        "--emit_full",
        "true",
        "--emit_gmt",
        "true",
        "--gmt_split_signed",
        "true",
        "--gmt_require_symbol",
        settings["extractor_gmt_require_symbol"],
        "--emit_small_gene_sets",
        settings["extractor_emit_small_gene_sets"],
    ]
    if settings["extractor_disable_default_excludes"] == "true":
        cmd.append("--disable_default_excludes")
    for flag_name, key in [
        ("--padj_max", "extractor_padj_max"),
        ("--pvalue_max", "extractor_pvalue_max"),
        ("--min_abs_logfc", "extractor_min_abs_logfc"),
        ("--top_k", "extractor_top_k"),
        ("--min_score", "extractor_min_score"),
        ("--gmt_source", "extractor_gmt_source"),
        ("--gmt_topk_list", "extractor_gmt_topk_list"),
        ("--gmt_min_genes", "extractor_gmt_min_genes"),
        ("--gmt_max_genes", "extractor_gmt_max_genes"),
    ]:
        value = settings[key]
        if value != "NA":
            cmd.extend([flag_name, value])
    if settings["extractor_gmt_biotype_allowlist"]:
        cmd.extend(["--gmt_biotype_allowlist", settings["extractor_gmt_biotype_allowlist"]])
    if gtf_path:
        cmd.extend(["--gtf", gtf_path])
    return cmd


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> None:
    log_line(log_path, f"$ {shell_join(cmd)}")
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.stdout:
        log_line(log_path, completed.stdout.rstrip("\n"))
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)


def write_model_commands(
    *,
    model_out: Path,
    model_id: str,
    workflow_cmd: list[str],
    extractor_cmd: list[str],
    dig_dir: Path,
) -> None:
    text = "\n".join(
        [
            f"# Commands For {model_id}",
            "",
            "## Workflow",
            "",
            "```bash",
            f"cd {shlex.quote(str(dig_dir))}",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {shell_join(workflow_cmd)}",
            "```",
            "",
            "## Extractor",
            "",
            "```bash",
            f"cd {shlex.quote(str(dig_dir))}",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {shell_join(extractor_cmd)}",
            "```",
            "",
        ]
    )
    write_text(model_out / "commands.md", text)


def main() -> int:
    args = parse_args()
    repo = repo_root()
    prepared_dir = Path(args.prepared_dir).resolve()
    run_root = Path(args.run_root).resolve()
    dig_dir = Path(args.dig_dir).resolve()
    resolved_gtf = resolve_input_path(args.gtf, base_dir=repo)
    model_settings = load_model_settings()
    if args.model_id not in model_settings:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = model_settings[args.model_id]

    if settings["annotation_mode"] == "gtf_annotated" and not resolved_gtf:
        raise SystemExit(f"Model {args.model_id} requires --gtf")

    required = ["tissue_counts.tsv", "sample_metadata.tsv", "comparisons.tsv"]
    if not args.write_commands_only:
        missing = [name for name in required if not (prepared_dir / name).exists()]
        if missing:
            raise SystemExit(
                "prepared_dir must contain tissue_counts.tsv, sample_metadata.tsv, and comparisons.tsv"
            )

    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "extractor"
    model_out.mkdir(parents=True, exist_ok=True)
    model_log = model_out / "run.log"

    workflow_cmd = build_workflow_cmd(
        python_bin=args.python_bin,
        prepared_dir=prepared_dir,
        workflow_out=workflow_out,
        organism=args.organism,
        genome_build=args.genome_build,
        settings=settings,
    )
    extractor_cmd = build_extractor_cmd(
        python_bin=args.python_bin,
        workflow_out=workflow_out,
        extractor_out=extractor_out,
        organism=args.organism,
        genome_build=args.genome_build,
        model_id=args.model_id,
        settings=settings,
        gtf_path=resolved_gtf,
    )
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        extractor_cmd=extractor_cmd,
        dig_dir=dig_dir,
    )

    if args.write_commands_only:
        return 0

    env = os.environ.copy()
    env["PYTHONPATH"] = str(dig_dir / "src")
    log_line(model_log, f"[run_age_binned_model] model_id={args.model_id}")
    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
