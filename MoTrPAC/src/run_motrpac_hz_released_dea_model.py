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

from motrpac_selection_io import default_model_manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MoTrPAC HZ1 from released DEA tables and emit notebook-style outputs in pipeline layout."
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


def require_existing_file(path_text: str, label: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_file():
        raise SystemExit(f"Expected {label} to be a file: {path}")
    return path


def require_existing_dir(path_text: str, label: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_dir():
        raise SystemExit(f"Expected {label} to be a directory: {path}")
    return path


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
    runner_script: Path,
    feature_annot: Path,
    dea_dir: Path,
    mapping_file: Path,
    gene_info: Path | None,
    gene_csv: Path | None,
    workflow_out: Path,
    settings: dict[str, str],
) -> list[str]:
    cmd = [
        python_bin,
        str(runner_script),
        "--feature-annot",
        str(feature_annot),
        "--dea-dir",
        str(dea_dir),
        "--mapping-file",
        str(mapping_file),
        "--output-dir",
        str(workflow_out),
        "--mode",
        manifest_value(settings, "workflow_mode", "gmt"),
        "--gmt-format",
        manifest_value(settings, "workflow_gmt_format", "legacy"),
        "--padj-max",
        manifest_value(settings, "workflow_padj_max", "0.05"),
        "--min-genes",
        manifest_value(settings, "workflow_min_genes", "5"),
    ]
    if gene_info is not None:
        cmd.extend(["--gene-info", str(gene_info)])
    if gene_csv is not None:
        cmd.extend(["--gene-csv", str(gene_csv)])
    if bool_manifest_value(settings, "workflow_write_matrices", False):
        cmd.append("--write-matrices")
    if bool_manifest_value(settings, "workflow_visualizations", False):
        cmd.append("--visualizations")
    if bool_manifest_value(settings, "workflow_include_sql", False):
        cmd.append("--include-sql")
    if bool_manifest_value(settings, "workflow_stop_at_notebook_error_cell", False):
        cmd.append("--stop-at-notebook-error-cell")
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


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


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


def load_source_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("motrpac_hz1_source", script_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load source script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_signed_term_input(*, source_script: Path, processed_tsv: Path, out_tsv: Path) -> None:
    module = load_source_module(source_script)
    if not hasattr(module, "_legacy_base_term"):
        raise SystemExit(f"Source script does not expose _legacy_base_term(): {source_script}")
    legacy_base_term = getattr(module, "_legacy_base_term")

    with processed_tsv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
    out_rows: list[dict[str, str]] = []
    for row in rows:
        term = str(row.get("term", "")).strip()
        gene = str(row.get("gene", "")).strip()
        score_text = str(row.get("adj_p_value", "")).strip()
        sign_text = str(row.get("threshold", "")).strip()
        if not term or not gene or not score_text or not sign_text:
            continue
        sign = float(sign_text)
        if sign == 0.0:
            continue
        out_rows.append(
            {
                "term": str(legacy_base_term(term)).strip(),
                "gene_id": gene,
                "gene_symbol": gene,
                "score": str(float(score_text)),
                "sign": str(sign),
            }
        )
    write_tsv(out_tsv, out_rows, ["term", "gene_id", "gene_symbol", "score", "sign"])


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


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]

    feature_annot = require_existing_file(args.feature_annot, "feature annotation")
    dea_dir = require_existing_dir(args.dea_dir, "DEA directory")
    mapping_file = require_existing_file(args.mapping_file, "mapping file")
    gene_info = require_existing_file(args.gene_info, "gene_info") if args.gene_info else None
    gene_csv = require_existing_file(args.gene_csv, "gene.csv") if args.gene_csv else None

    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "tissue_extractor"
    runner_script = Path(__file__).resolve().parent / "build_motrpac_rat_endurance_gmt_hz1.py"
    source_script = Path(__file__).resolve().parents[3] / "notebooks_adapted" / "build_motrpac_rat_endurance_gmt.py"
    dig_dir = Path(args.dig_dir).resolve()

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        runner_script=runner_script,
        feature_annot=feature_annot,
        dea_dir=dea_dir,
        mapping_file=mapping_file,
        gene_info=gene_info,
        gene_csv=gene_csv,
        workflow_out=workflow_out,
        settings=settings,
    )
    signed_term_tsv = workflow_out / "motrpac_signed_term_gene.tsv"
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

    processed_tsv = workflow_out / "motrpac_processed.tsv"
    if not processed_tsv.exists():
        raise SystemExit(f"Expected processed workflow table: {processed_tsv}")
    build_signed_term_input(source_script=source_script, processed_tsv=processed_tsv, out_tsv=signed_term_tsv)
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
