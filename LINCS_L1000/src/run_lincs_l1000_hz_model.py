#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shlex
import subprocess
import sys
from pathlib import Path

from lincs_l1000_selection_io import default_model_manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one LINCS L1000 HZ model and emit dig-authored GMT outputs in pipeline layout."
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


def load_source_module(script_path: Path):
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load source script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def model_source_info(model_id: str) -> tuple[str, Path]:
    repo = Path(__file__).resolve().parents[3]
    if model_id == "HZ1":
        return (
            "chempert",
            repo / "notebooks_adapted" / "build_lincs_l1000_chempert_gmt_only.py",
        )
    if model_id == "HZ2":
        return (
            "crisprko",
            repo / "notebooks_adapted" / "build_lincs_l1000_crisprko_gmt_only.py",
        )
    raise SystemExit(f"Unsupported LINCS L1000 HZ model_id: {model_id}")


def build_workflow_cmd(
    *,
    python_bin: str,
    runner_script: Path,
    expression_tsv: Path,
    mapping_file: Path,
    workflow_out: Path,
    settings: dict[str, str],
    kind: str,
) -> list[str]:
    cmd = [
        python_bin,
        str(runner_script),
        "--expression-tsv",
        str(expression_tsv),
        "--mapping-file",
        str(mapping_file),
        "--output-dir",
        str(workflow_out),
        "--gmt-name",
        manifest_value(settings, "workflow_gmt_name", "gene_set_library_crisp.gmt"),
        "--min-gmt-size",
        manifest_value(settings, "workflow_min_gmt_size", "5"),
    ]
    if kind == "chempert":
        cmd.extend(["--z-threshold", manifest_value(settings, "workflow_z_threshold", "3.0")])
    elif kind == "crisprko":
        cmd.extend(["--top-n", manifest_value(settings, "workflow_top_n", "250")])
    return cmd


def build_extractor_cmd(
    *,
    python_bin: str,
    signed_term_tsv: Path,
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


def run_command(cmd: list[str], *, cwd: Path, log_path: Path) -> None:
    log_line(log_path, f"$ {shell_join(cmd)}")
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
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
            shell_join(workflow_cmd),
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
            "The authoritative GMT outputs are written by dig-gene-set-extractors from the processed notebook-style term-gene table.",
            "",
        ]
    )
    write_text(model_out / "commands.md", text)


def build_chempert_tables(*, module, expression_tsv: Path, mapping_file: Path, settings: dict[str, str], workflow_out: Path) -> Path:
    z_threshold = float(manifest_value(settings, "workflow_z_threshold", "3.0"))
    min_gmt_size = int(manifest_value(settings, "workflow_min_gmt_size", "5"))
    chempert = module.preprocess_chempert(expression_tsv, mapping_file, z_threshold)
    processed_rows = [
        {
            "gene": str(row["Gene"]),
            "term": str(row["Chemical Perturbation"]),
            "score": str(abs(float(row["z"]))),
            "signed_score": str(float(row["z"])),
            "sign": str(int(row["threshold"])),
        }
        for _, row in chempert.iterrows()
    ]
    write_tsv(workflow_out / "lincs_l1000_processed.tsv", processed_rows, ["gene", "term", "score", "signed_score", "sign"])

    notebook_gmt = workflow_out / "gene_set_library_crisp.gmt"
    module.write_combined_gmt(chempert, notebook_gmt, min_gmt_size)

    signed_rows = sorted(
        [
            {
                "term": row["term"],
                "gene_id": row["gene"],
                "gene_symbol": row["gene"],
                "score": row["score"],
                "sign": row["sign"],
            }
            for row in processed_rows
        ],
        key=lambda row: (
            row["term"],
            -int(row["sign"]),
            row["gene_symbol"],
        ),
    )
    signed_tsv = workflow_out / "lincs_l1000_signed_term_gene.tsv"
    write_tsv(signed_tsv, signed_rows, ["term", "gene_id", "gene_symbol", "score", "sign"])
    return signed_tsv


def build_crisprko_tables(*, module, expression_tsv: Path, mapping_file: Path, settings: dict[str, str], workflow_out: Path) -> Path:
    top_n = int(manifest_value(settings, "workflow_top_n", "250"))
    min_gmt_size = int(manifest_value(settings, "workflow_min_gmt_size", "5"))
    l1000 = module.preprocess_crisprko(expression_tsv, mapping_file, top_n)
    processed_rows = [
        {
            "gene": str(row["Gene"]),
            "term": str(row["Gene KO"]),
            "score": str(abs(float(row[0]))),
            "signed_score": str(float(row[0])),
            "sign": str(int(row["Threshold Value"])),
        }
        for _, row in l1000.iterrows()
    ]
    write_tsv(workflow_out / "lincs_l1000_processed.tsv", processed_rows, ["gene", "term", "score", "signed_score", "sign"])

    notebook_gmt = workflow_out / "gene_set_library_crisp.gmt"
    module.write_combined_gmt(l1000, notebook_gmt, min_gmt_size)

    signed_tsv = workflow_out / "lincs_l1000_signed_term_gene.tsv"
    signed_rows = [
        {
            "term": row["term"],
            "gene_id": row["gene"],
            "gene_symbol": row["gene"],
            "score": row["score"],
            "sign": row["sign"],
        }
        for row in processed_rows
    ]
    write_tsv(signed_tsv, signed_rows, ["term", "gene_id", "gene_symbol", "score", "sign"])
    return signed_tsv


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]

    expression_tsv = require_existing_file(args.expression_tsv, "expression TSV")
    mapping_file = require_existing_file(args.mapping_file, "mapping file")
    kind, source_script = model_source_info(args.model_id)
    if not source_script.exists():
        raise SystemExit(f"Missing source script for {args.model_id}: {source_script}")
    module = load_source_module(source_script)

    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "tissue_extractor"
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    runner_script = (
        Path(__file__).resolve().parent / "build_lincs_l1000_chempert_hz1.py"
        if args.model_id == "HZ1"
        else Path(__file__).resolve().parent / "build_lincs_l1000_crisprko_hz2.py"
    )

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        runner_script=runner_script,
        expression_tsv=expression_tsv,
        mapping_file=mapping_file,
        workflow_out=workflow_out,
        settings=settings,
        kind=kind,
    )
    signed_term_tsv = workflow_out / "lincs_l1000_signed_term_gene.tsv"
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        signed_term_tsv=signed_term_tsv,
        extractor_out=extractor_out,
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

    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=model_out, log_path=model_log)

    if kind == "chempert":
        build_chempert_tables(
            module=module,
            expression_tsv=expression_tsv,
            mapping_file=mapping_file,
            settings=settings,
            workflow_out=workflow_out,
        )
    else:
        build_crisprko_tables(
            module=module,
            expression_tsv=expression_tsv,
            mapping_file=mapping_file,
            settings=settings,
            workflow_out=workflow_out,
        )

    run_command(extractor_cmd, cwd=dig_dir, log_path=model_log)

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
