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

from lincs_l1000_selection_io import default_model_manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one LINCS L1000 HZ model as a wrapper around dig workflows and signed term-gene conversion."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--expression_tsv", required=True)
    parser.add_argument("--mapping_file", required=True)
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
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


def model_workflow_info(model_id: str) -> tuple[str, str]:
    if model_id == "HZ1":
        return ("chempert", "lincs_l1000_chempert")
    if model_id == "HZ2":
        return ("crisprko", "lincs_l1000_crisprko")
    raise SystemExit(f"Unsupported LINCS L1000 HZ model_id: {model_id}")


def lincs_term_prefix(model_id: str) -> str:
    if model_id == "HZ1":
        return "LINCS_L1000_Chem_Pert"
    if model_id == "HZ2":
        return "LINCS_L1000_CRISPR_KO"
    raise SystemExit(f"Unsupported LINCS L1000 HZ model_id: {model_id}")


def build_workflow_cmd(
    *,
    python_bin: str,
    expression_tsv: Path,
    mapping_file: Path,
    workflow_out: Path,
    settings: dict[str, str],
    workflow_name: str,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        workflow_name,
        "--expression_tsv",
        str(expression_tsv),
        "--mapping_file",
        str(mapping_file),
        "--out_dir",
        str(workflow_out),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--gmt_name",
        manifest_value(settings, "workflow_gmt_name", "gene_set_library_crisp.gmt"),
        "--min_gmt_size",
        manifest_value(settings, "workflow_min_gmt_size", "5"),
    ]
    if workflow_name == "lincs_l1000_chempert":
        cmd.extend(["--z_threshold", manifest_value(settings, "workflow_z_threshold", "3.0")])
    else:
        cmd.extend(["--top_n", manifest_value(settings, "workflow_top_n", "250")])
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def build_extractor_cmd(
    *,
    python_bin: str,
    signed_term_tsv: Path,
    term_prefix: str,
    extractor_out: Path,
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
        "--term_prefix",
        term_prefix,
        "--gene_id_column",
        "gene_id",
        "--gene_symbol_column",
        "gene_symbol",
        "--score_column",
        "score",
        "--sign_column",
        "sign",
        "--gmt_name_separator",
        "_",
        "--gmt_signed_labels",
        "up_dn",
        "--gmt_min_genes",
        "5",
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
            "The authoritative GMT outputs are written by dig-gene-set-extractors from the processed notebook-style term-gene table.",
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

    expression_tsv = require_existing_file(args.expression_tsv, "expression TSV")
    mapping_file = require_existing_file(args.mapping_file, "mapping file")
    _kind, workflow_name = model_workflow_info(args.model_id)
    term_prefix = lincs_term_prefix(args.model_id)

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
        expression_tsv=expression_tsv,
        mapping_file=mapping_file,
        workflow_out=workflow_out,
        settings=settings,
        workflow_name=workflow_name,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    signed_term_tsv = workflow_out / "lincs_l1000_signed_term_gene.tsv"
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        signed_term_tsv=signed_term_tsv,
        term_prefix=term_prefix,
        extractor_out=extractor_out,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    provenance_cmd = build_provenance_rebuild_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        metadata_json=extractor_out / "geneset.meta.json",
        upstream_provenance_graph_json=workflow_out / "lincs_l1000_signed_term_gene.provenance_graph.json",
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
    if args.write_commands_only:
        return 0

    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
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
