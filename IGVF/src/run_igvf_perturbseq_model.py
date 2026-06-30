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

from igvf_selection_io import default_model_manifest_path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from enrich_provenance import enrich_provenance  # noqa: E402


TERM_PREFIX = "IGVF_Perturb_Seq"
WORKFLOW_NAME = "igvf_perturbseq"
SIGNED_TSV_NAME = "igvf_perturbseq_signed_term_gene.tsv"
SIGNED_GRAPH_NAME = "igvf_perturbseq_signed_term_gene.provenance_graph.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one IGVF Perturb-seq model as a wrapper around the dig igvf_perturbseq workflow "
        "and signed term-gene conversion."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--analysis_set_id", default="", help="IGVF analysis-set accession this run is derived from.")
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--expression_tsv", required=True, help="Processed per-perturbation signature matrix TSV.")
    parser.add_argument("--mapping_file", help="Optional gene id->symbol mapping TSV.")
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


def write_model_sidecar(*, path: Path, model_id: str, analysis_set_id: str, settings: dict[str, str]) -> None:
    input_mode = manifest_value(settings, "workflow_input_mode", "matrix")
    parameters = {
        "term_prefix": TERM_PREFIX,
        "input_mode": input_mode,
        "analysis_set_id": analysis_set_id,
        "min_gmt_size": manifest_value(settings, "workflow_min_gmt_size", "5"),
    }
    if input_mode == "long_de":
        parameters["de_source"] = "igvf_processed_differential_expression"
        for key in ("workflow_term_column", "workflow_ratio_column", "workflow_effect_column", "workflow_score_column"):
            value = str(settings.get(key, "")).strip()
            if value and value != "NA":
                parameters[key.replace("workflow_", "")] = value
    else:
        parameters["orientation"] = manifest_value(settings, "workflow_orientation", "perturbation_by_gene")
        parameters["z_threshold"] = manifest_value(settings, "workflow_z_threshold", "3.0")
    payload = {
        "schema_version": "1",
        "library": "IGVF",
        "model_id": model_id,
        "model_group": "perturbseq",
        "model_label": "perturbseq_signed_signatures",
        "workflow_name": WORKFLOW_NAME,
        "extractor_name": "signed_term_gene",
        "parameters": parameters,
        "inputs": {
            "organism": "human",
            "genome_build": "hg38",
        },
        "naming": {
            "comparison_style": "signed_term",
            "gene_set_pattern": f"{TERM_PREFIX}_<perturbation>_up|dn",
        },
    }
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_workflow_cmd(
    *,
    python_bin: str,
    expression_tsv: Path,
    mapping_file: Path | None,
    workflow_out: Path,
    settings: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    input_mode = manifest_value(settings, "workflow_input_mode", "matrix")
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        WORKFLOW_NAME,
        "--input_mode",
        input_mode,
        "--expression_tsv",
        str(expression_tsv),
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
    if input_mode == "long_de":
        # Map tidy per-perturbation DE columns from the manifest; emit only those provided.
        long_flag_map = {
            "workflow_sep": "--sep",
            "workflow_term_column": "--term_column",
            "workflow_gene_symbol_column": "--gene_symbol_column",
            "workflow_gene_id_column": "--gene_id_column",
            "workflow_effect_column": "--effect_column",
            "workflow_ratio_column": "--ratio_column",
            "workflow_score_column": "--score_column",
            "workflow_pvalue_column": "--pvalue_column",
            "workflow_pvalue_max": "--pvalue_max",
            "workflow_score_threshold": "--score_threshold",
            "workflow_top_k_per_direction": "--top_k_per_direction",
        }
        for key, flag in long_flag_map.items():
            value = str(settings.get(key, "")).strip()
            if value and value != "NA":
                cmd.extend([flag, value])
    else:
        cmd.extend(["--orientation", manifest_value(settings, "workflow_orientation", "perturbation_by_gene")])
        cmd.extend(["--z_threshold", manifest_value(settings, "workflow_z_threshold", "3.0")])
    if mapping_file is not None:
        cmd.extend(["--mapping_file", str(mapping_file)])
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
        "--term_prefix",
        TERM_PREFIX,
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
        manifest_value(settings, "workflow_min_gmt_size", "5"),
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
            "The authoritative GMT outputs are written by dig-gene-set-extractors from the processed "
            "perturbation signed term-gene table.",
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
    mapping_file = require_existing_file(args.mapping_file, "mapping file") if args.mapping_file else None

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
    python_bin = str(Path(args.python_bin).resolve())

    workflow_cmd = build_workflow_cmd(
        python_bin=python_bin,
        expression_tsv=expression_tsv,
        mapping_file=mapping_file,
        workflow_out=workflow_out,
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    signed_term_tsv = workflow_out / SIGNED_TSV_NAME
    extractor_cmd = build_extractor_cmd(
        python_bin=python_bin,
        signed_term_tsv=signed_term_tsv,
        extractor_out=extractor_out,
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    provenance_cmd = build_provenance_rebuild_cmd(
        python_bin=python_bin,
        metadata_json=extractor_out / "geneset.meta.json",
        upstream_provenance_graph_json=workflow_out / SIGNED_GRAPH_NAME,
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
        write_model_sidecar(path=extractor_out / "geneset.model.json", model_id=args.model_id, analysis_set_id=args.analysis_set_id, settings=settings)
        return 0
    if args.write_commands_only:
        return 0

    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
    write_model_sidecar(path=extractor_out / "geneset.model.json", model_id=args.model_id, analysis_set_id=args.analysis_set_id, settings=settings)
    run_command(provenance_cmd, cwd=dig_dir, env=env, log_path=model_log)

    # Enrich provenance with resource / study / pipeline / preprocessing metadata.
    input_mode = manifest_value(settings, "workflow_input_mode", "matrix")
    if input_mode == "long_de":
        direction = (
            f"signed effect column '{manifest_value(settings, 'workflow_effect_column', '')}'"
            if str(settings.get("workflow_effect_column", "")).strip() not in ("", "NA")
            else f"fold-change ratio column '{manifest_value(settings, 'workflow_ratio_column', '')}' (>1 up, <1 down)"
        )
        score = manifest_value(settings, "workflow_score_column", "") or "absolute effect size"
        pmax = manifest_value(settings, "workflow_pvalue_max", "")
        topk = manifest_value(settings, "workflow_top_k_per_direction", "")
        preprocessing = (
            f"IGVF processed differential-expression table parsed long-form to a signed term->gene table; "
            f"perturbation term = '{manifest_value(settings, 'workflow_term_column', '')}'; "
            f"direction from {direction}; ranking magnitude from {score}"
            + (f"; kept rows with {manifest_value(settings,'workflow_pvalue_column','p')}<= {pmax}" if pmax else "")
            + (f"; capped to top {topk} genes per perturbation per direction" if topk else "")
            + f"; min gene-set size {manifest_value(settings, 'workflow_min_gmt_size', '5')}."
        )
        pipeline = "igvf_perturbseq (long_de) -> signed_term_gene"
    else:
        preprocessing = (
            "IGVF processed perturbation effect matrix z-scored per gene and thresholded to a signed term->gene table."
        )
        pipeline = "igvf_perturbseq (matrix) -> signed_term_gene"
    enrich_provenance(
        extractor_out / "geneset.provenance.json",
        resource="IGVF",
        study_id=args.analysis_set_id or args.model_id,
        pipeline=pipeline,
        preprocessing=preprocessing,
    )

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
