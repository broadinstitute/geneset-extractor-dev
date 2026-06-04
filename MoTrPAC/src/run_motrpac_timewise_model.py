#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from motrpac_selection_io import default_model_manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one MoTrPAC timewise model via dig workflows and grouped DEG conversion."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--tissue_id", required=True)
    parser.add_argument("--prepared_dir", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--organism", default="human", choices=["human", "mouse"])
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--write_commands_only", action="store_true")
    return parser.parse_args()


def load_model_settings(manifest_path: Path) -> dict[str, dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    settings: dict[str, dict[str, str]] = {}
    for row in rows:
        model_id = str(row.get("model_id", "")).strip()
        if model_id:
            settings[model_id] = {str(key): str(value) for key, value in row.items()}
    if not settings:
        raise SystemExit(f"No model settings found in {manifest_path}")
    return settings


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def manifest_value(settings: dict[str, str], key: str, default: str) -> str:
    value = str(settings.get(key, "")).strip()
    if not value or value == "NA":
        return default
    return value


def build_workflow_cmd(
    *,
    python_bin: str,
    prepared_dir: Path,
    workflow_out: Path,
    organism: str,
    genome_build: str,
    settings: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "motrpac_timewise",
        "--counts_tsv",
        str(prepared_dir / "tissue_counts.tsv"),
        "--sample_metadata_tsv",
        str(prepared_dir / "sample_metadata.tsv"),
        "--out_dir",
        str(workflow_out),
        "--organism",
        organism,
        "--genome_build",
        genome_build,
        "--min_samples_per_group",
        manifest_value(settings, "workflow_min_samples_per_group", "5"),
    ]
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def build_extractor_cmd(
    *,
    python_bin: str,
    workflow_out: Path,
    extractor_out: Path,
    organism: str,
    genome_build: str,
    settings: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
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
        "--comparison_name_column",
        "comparison_id",
        "--out_dir",
        str(extractor_out),
        "--organism",
        organism,
        "--genome_build",
        genome_build,
        "--signature_name",
        "__comparison_only__",
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
        "--gmt_name_separator",
        "_",
        "--gmt_signed_labels",
        "up_dn",
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
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
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
    dig_dir: Path,
    extractor_cmd: list[str],
) -> None:
    lines = [
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
    write_text(model_out / "commands.md", "\n".join(lines))


def read_manifest_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_run_manifest(
    *,
    path: Path,
    model_id: str,
    tissue_id: str,
    workflow_out: Path,
    extractor_out: Path,
) -> None:
    payload = {
        "model_id": model_id,
        "tissue_id": tissue_id,
        "workflow_dir": str(workflow_out),
        "tissue_extractor_dir": str(extractor_out),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]

    prepared_dir = Path(args.prepared_dir).resolve()
    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "tissue_extractor"
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        prepared_dir=prepared_dir,
        workflow_out=workflow_out,
        organism=args.organism,
        genome_build=args.genome_build,
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        workflow_out=workflow_out,
        extractor_out=extractor_out,
        organism=args.organism,
        genome_build=args.genome_build,
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        dig_dir=dig_dir,
        extractor_cmd=extractor_cmd,
    )
    if args.write_commands_only:
        return 0

    env = dict(os.environ)
    env["PYTHONPATH"] = str(dig_dir / "src")
    rscript_parent = str(Path(args.rscript_bin).expanduser().resolve().parent) if Path(args.rscript_bin).expanduser().is_absolute() else ""
    if rscript_parent:
        env["PATH"] = rscript_parent + os.pathsep + env.get("PATH", "")
    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)

    manifest_rows = read_manifest_rows(extractor_out / "manifest.tsv")
    summary_rows = [
        {
            "comparison_id": str(row.get("comparison", "")).strip(),
            "label": str(row.get("label", "")).strip(),
            "extractor_out_dir": str(row.get("path", "")).strip(),
            "meta_path": str(row.get("meta_path", "")).strip(),
            "provenance_path": str(row.get("provenance_path", "")).strip(),
        }
        for row in manifest_rows
    ]
    write_tsv(
        extractor_out / "signature_summary.tsv",
        summary_rows,
        ["comparison_id", "label", "extractor_out_dir", "meta_path", "provenance_path"],
    )
    write_run_manifest(
        path=extractor_out / "run_manifest.json",
        model_id=args.model_id,
        tissue_id=args.tissue_id,
        workflow_out=workflow_out,
        extractor_out=extractor_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
