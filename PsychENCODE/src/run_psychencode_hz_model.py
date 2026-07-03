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

from psychencode_selection_io import default_model_manifest_path


ORGANISM = "human"
GENOME_BUILD = "hg19"  # PsychENCODE released layer is GENCODE v19 / GRCh37.


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one PsychENCODE HZ model as a wrapper around dig workflows and term-gene conversion."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--input_csv", required=True, help="Released CSV for this model (DER-13 for HZ1, DER-16 for HZ2).")
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--write_commands_only", action="store_true")
    parser.add_argument("--write_model_only", action="store_true")
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


def require_existing_file(path_text: str, label: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_file():
        raise SystemExit(f"Expected {label} to be a file: {path}")
    return path


def manifest_value(settings: dict[str, str], key: str, default: str) -> str:
    value = str(settings.get(key, "")).strip()
    if not value or value == "NA":
        return default
    return value


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_gmt(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            rows.append({"set_name": parts[0], "description": parts[1], "gene_count": str(len(parts) - 2)})
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
        "extractor_dir": str(extractor_out),
        "provenance_mirror_local_prefix": provenance_mirror_local_prefix,
        "provenance_mirror_remote_prefix": provenance_mirror_remote_prefix,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def model_config(model_id: str) -> dict[str, str]:
    """Return per-model workflow/extractor wiring for the active PsychENCODE pipeline."""
    if model_id == "HZ1":
        return {
            "workflow_name": "psychencode_dex",
            "extractor_name": "signed_term_gene",
            "term_tsv_name": "psychencode_signed_term_gene.tsv",
            "model_label": "disorder_dex",
            "comparison_style": "signed_term",
            "gene_set_pattern": "PsychENCODE_<disorder>_up|dn",
            "source_file": "DER-13_Disorder_DEX_Genes.csv",
            "source_label": "PsychENCODE released cross-disorder differential-expression gene table",
        }
    if model_id == "HZ2":
        return {
            "workflow_name": "psychencode_modules",
            "extractor_name": "unsigned_term_gene",
            "term_tsv_name": "psychencode_unsigned_term_gene.tsv",
            "model_label": "coexpression_modules",
            "comparison_style": "unsigned_term",
            "gene_set_pattern": "PsychENCODE_<module>",
            "source_file": "DER-16_Disorder_Gene_Modules.csv",
            "source_label": "PsychENCODE released cross-disorder WGCNA co-expression module table",
        }
    raise SystemExit(f"Unsupported PsychENCODE HZ model_id: {model_id}")


def write_model_sidecar(
    *,
    path: Path,
    model_id: str,
    settings: dict[str, str],
) -> None:
    """Write geneset.model.json. Callable from the shared refresh flow with just
    (path, model_id, settings); workflow/extractor wiring and term prefix are derived
    internally so refresh can regenerate the sidecar without the full run context."""
    config = model_config(model_id)
    term_prefix = manifest_value(settings, "term_prefix", "PsychENCODE")
    payload = {
        "schema_version": "1",
        "library": "PsychENCODE",
        "model_id": model_id,
        "model_group": "HZ",
        "model_label": config["model_label"],
        "workflow_name": config["workflow_name"],
        "extractor_name": config["extractor_name"],
        "parameters": {
            "term_prefix": term_prefix,
            "gmt_min_genes": manifest_value(settings, "gmt_min_genes", "5"),
            "exclude_modules": manifest_value(settings, "workflow_exclude_modules", ""),
        },
        "inputs": {
            "organism": ORGANISM,
            "genome_build": GENOME_BUILD,
            "source_file": config["source_file"],
            "source_label": config["source_label"],
            "source_resource": "resource.psychencode.org",
            "source_doi": "10.1126/science.aat8127",
        },
        "naming": {
            "comparison_style": config["comparison_style"],
            "gene_set_pattern": config["gene_set_pattern"],
            "term_prefix": term_prefix,
        },
    }
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_workflow_cmd(
    *,
    python_bin: str,
    model_id: str,
    input_csv: Path,
    workflow_out: Path,
    settings: dict[str, str],
    config: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        config["workflow_name"],
        "--out_dir",
        str(workflow_out),
        "--organism",
        ORGANISM,
        "--genome_build",
        GENOME_BUILD,
    ]
    if model_id == "HZ1":
        cmd.extend(["--dex_csv", str(input_csv)])
    else:
        cmd.extend(["--modules_csv", str(input_csv)])
        cmd.extend(["--exclude_modules", manifest_value(settings, "workflow_exclude_modules", "geneM0")])
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def build_extractor_cmd(
    *,
    python_bin: str,
    term_tsv: Path,
    term_prefix: str,
    extractor_out: Path,
    settings: dict[str, str],
    config: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "convert",
        config["extractor_name"],
        "--table_tsv",
        str(term_tsv),
        "--out_dir",
        str(extractor_out),
        "--organism",
        ORGANISM,
        "--genome_build",
        GENOME_BUILD,
        "--term_column",
        "term",
        "--term_prefix",
        term_prefix,
        "--gene_id_column",
        "gene_id",
        "--gene_symbol_column",
        "gene_symbol",
        "--score_column",
        "score",
    ]
    if config["extractor_name"] == "signed_term_gene":
        cmd.extend(
            [
                "--sign_column",
                "sign",
                "--gmt_name_separator",
                "_",
                "--gmt_signed_labels",
                "up_dn",
            ]
        )
    cmd.extend(
        [
            "--gmt_min_genes",
            manifest_value(settings, "gmt_min_genes", "5"),
            "--gmt_require_symbol",
            "true",
            "--emit_small_gene_sets",
            "false",
        ]
    )
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def build_provenance_rebuild_cmd(
    *,
    python_bin: str,
    metadata_json: Path,
    upstream_provenance_graph_json: Path,
    provenance_out: Path,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "provenance",
        "build",
        str(metadata_json),
        "--out",
        str(provenance_out),
        "--upstream_provenance_graph_json",
        str(upstream_provenance_graph_json),
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
    provenance_cmd: list[str],
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
            "## Provenance",
            "",
            "```bash",
            f"cd {shlex.quote(str(dig_dir))}",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {shell_join(provenance_cmd)}",
            "```",
            "",
            "## Notes",
            "",
            "The authoritative GMT outputs are written by dig-gene-set-extractors from the "
            "workflow-authored term-gene table.",
            "",
        ]
    )
    write_text(model_out / "commands.md", text)


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]
    config = model_config(args.model_id)

    input_csv = require_existing_file(args.input_csv, "released input CSV")
    term_prefix = manifest_value(settings, "term_prefix", "PsychENCODE")

    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "extractor"
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(dig_dir / "src")
    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        model_id=args.model_id,
        input_csv=input_csv,
        workflow_out=workflow_out,
        settings=settings,
        config=config,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    term_tsv = workflow_out / config["term_tsv_name"]
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        term_tsv=term_tsv,
        term_prefix=term_prefix,
        extractor_out=extractor_out,
        settings=settings,
        config=config,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    provenance_cmd = build_provenance_rebuild_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        metadata_json=extractor_out / "geneset.meta.json",
        upstream_provenance_graph_json=workflow_out / f"{term_tsv.stem}.provenance_graph.json",
        provenance_out=extractor_out / "geneset.provenance.json",
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        extractor_cmd=extractor_cmd,
        provenance_cmd=provenance_cmd,
        dig_dir=dig_dir,
    )
    if args.write_model_only:
        write_model_sidecar(
            path=extractor_out / "geneset.model.json",
            model_id=args.model_id,
            settings=settings,
        )
        return 0
    if args.write_commands_only:
        return 0

    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
    write_model_sidecar(
        path=extractor_out / "geneset.model.json",
        model_id=args.model_id,
        settings=settings,
    )
    run_command(provenance_cmd, cwd=dig_dir, env=env, log_path=model_log)

    summary_rows = [{"source_gmt": "genesets.gmt", **row} for row in parse_gmt(extractor_out / "genesets.gmt")]
    write_tsv(extractor_out / "signature_summary.tsv", summary_rows, ["source_gmt", "set_name", "description", "gene_count"])
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
