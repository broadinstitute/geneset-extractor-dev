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
        description="Run MoTrPAC HZ1 from released DEA tables via dig workflow and signed term-gene conversion."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--feature_annot", required=True)
    parser.add_argument("--dea_dir", required=True)
    parser.add_argument("--mapping_file", required=True)
    parser.add_argument("--gene_info")
    parser.add_argument("--gene_csv")
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


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_value(settings: dict[str, str], key: str, default: str) -> str:
    value = str(settings.get(key, "")).strip()
    if not value or value == "NA":
        return default
    return value


def bool_manifest_value(settings: dict[str, str], key: str, default: bool = False) -> bool:
    value = str(settings.get(key, "")).strip().lower()
    if not value or value == "na":
        return default
    return value == "true"


def build_workflow_cmd(
    *,
    python_bin: str,
    feature_annot: Path,
    dea_dir: Path,
    mapping_file: Path,
    workflow_out: Path,
    settings: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "motrpac_released_dea",
        "--feature_annot",
        str(feature_annot),
        "--dea_dir",
        str(dea_dir),
        "--mapping_file",
        str(mapping_file),
        "--out_dir",
        str(workflow_out),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--padj_max",
        manifest_value(settings, "workflow_padj_max", "0.05"),
    ]
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def build_extractor_cmd(
    *,
    python_bin: str,
    signed_term_tsv: Path,
    extractor_out: Path,
    settings: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "signed_term_gene",
        "--table_tsv",
        str(signed_term_tsv),
        "--out_dir",
        str(extractor_out),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--term_column",
        "term",
        "--gene_id_column",
        "gene_id",
        "--gene_symbol_column",
        "gene_symbol",
        "--score_column",
        "score",
        "--sign_column",
        "sign",
        "--emit_mode",
        "ternary_matrix_notebook",
        "--gmt_name_separator",
        "_",
        "--gmt_signed_labels",
        "up_dn",
        "--gmt_min_genes",
        manifest_value(settings, "workflow_min_genes", "5"),
        "--gmt_require_symbol",
        "true",
        "--emit_small_gene_sets",
        "false",
    ]
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
            "## Notes",
            "",
            "The authoritative GMT outputs are written by dig-gene-set-extractors from the released-DEA signed term-gene table.",
            "",
        ]
    )
    write_text(model_out / "commands.md", text)


def parse_gmt(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            rows.append(
                {
                    "set_name": parts[0],
                    "description": parts[1],
                    "gene_count": str(len(parts) - 2),
                }
            )
    return rows


def write_manifest(
    *,
    manifest_path: Path,
    model_id: str,
    workflow_out: Path,
    extractor_out: Path,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> None:
    payload = {
        "model_id": model_id,
        "workflow_dir": str(workflow_out),
        "tissue_extractor_dir": str(extractor_out),
        "provenance_mirror_local_prefix": provenance_mirror_local_prefix,
        "provenance_mirror_remote_prefix": provenance_mirror_remote_prefix,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_supported_settings(settings: dict[str, str]) -> None:
    unsupported_true_flags = [
        "workflow_write_matrices",
        "workflow_visualizations",
        "workflow_include_sql",
        "workflow_stop_at_notebook_error_cell",
    ]
    enabled = [key for key in unsupported_true_flags if bool_manifest_value(settings, key, False)]
    if enabled:
        raise SystemExit(
            "The dig-native MoTrPAC HZ workflow currently supports only the core released-DEA processing path. "
            f"Unsupported enabled settings: {', '.join(enabled)}"
        )


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]
    ensure_supported_settings(settings)

    feature_annot = Path(args.feature_annot).resolve()
    dea_dir = Path(args.dea_dir).resolve()
    mapping_file = Path(args.mapping_file).resolve()
    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "tissue_extractor"
    dig_dir = Path(args.dig_dir).resolve()

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        feature_annot=feature_annot,
        dea_dir=dea_dir,
        mapping_file=mapping_file,
        workflow_out=workflow_out,
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    signed_term_tsv = workflow_out / "motrpac_signed_term_gene.tsv"
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        signed_term_tsv=signed_term_tsv,
        extractor_out=extractor_out,
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
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

    env = dict(os.environ)
    env["PYTHONPATH"] = str(dig_dir / "src")
    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    if not signed_term_tsv.exists():
        raise SystemExit(f"Expected signed term-gene table after workflow: {signed_term_tsv}")
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)

    summary_rows = [{"source_gmt": "genesets.gmt", **row} for row in parse_gmt(extractor_out / "genesets.gmt")]
    write_tsv(
        extractor_out / "signature_summary.tsv",
        summary_rows,
        ["source_gmt", "set_name", "description", "gene_count"],
    )
    write_manifest(
        manifest_path=extractor_out / "run_manifest.json",
        model_id=args.model_id,
        workflow_out=workflow_out,
        extractor_out=extractor_out,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
