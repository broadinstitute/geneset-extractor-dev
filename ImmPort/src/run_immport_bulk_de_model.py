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

from immport_selection_io import default_model_manifest_path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from enrich_provenance import enrich_provenance  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one ImmPort bulk RNA-seq DE model: a wrapper around the dig rna_de_prepare workflow "
        "and the rna_deg converter."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--study_id", required=True, help="Unique partition key (one row per study/contrast).")
    parser.add_argument(
        "--study_accession",
        default="",
        help="Real ImmPort study accession used for signature naming/provenance (defaults to --study_id).",
    )
    parser.add_argument("--study_label", default="")
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--expression_tsv", help="Gene-by-sample expression matrix TSV (gene_id, gene_symbol, <samples...>). Required unless --released_de_tsv is given.")
    parser.add_argument("--sample_metadata_tsv", help="Sample metadata TSV including the contrast group column. Required unless --released_de_tsv is given.")
    parser.add_argument("--group_column", default="", help="Metadata column defining case/control groups (counts->DE mode only).")
    parser.add_argument("--case_label", required=True)
    parser.add_argument("--control_label", required=True)
    parser.add_argument("--covariates", default="", help="Comma-separated fixed-effect covariates (optional).")
    parser.add_argument(
        "--released_de_tsv",
        help="Precomputed differential-expression table shipped by the study. When given, the rna_de_prepare "
        "workflow is skipped and this table is fed directly to the rna_deg converter (released-DE mode).",
    )
    parser.add_argument("--de_gene_id_column", default="gene.id")
    parser.add_argument("--de_gene_symbol_column", default="gene.name")
    parser.add_argument("--de_stat_column", default="stat")
    parser.add_argument("--de_logfc_column", default="log2FoldChange")
    parser.add_argument("--de_pvalue_column", default="pvalue")
    parser.add_argument("--de_padj_column", default="padj")
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


def signature_name(study_id: str, case_label: str, control_label: str) -> str:
    return f"ImmPort_{study_id}_{case_label}_vs_{control_label}"


def write_manifest(
    *,
    manifest_path: Path,
    model_id: str,
    study_id: str,
    workflow_out: Path,
    extractor_out: Path,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> None:
    payload = {
        "model_id": model_id,
        "study_id": study_id,
        "workflow_dir": str(workflow_out),
        "extractor_dir": str(extractor_out),
        "provenance_mirror_local_prefix": provenance_mirror_local_prefix,
        "provenance_mirror_remote_prefix": provenance_mirror_remote_prefix,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_model_sidecar(
    *,
    path: Path,
    model_id: str,
    study_id: str,
    study_accession: str,
    study_label: str,
    case_label: str,
    control_label: str,
    covariates: str,
    settings: dict[str, str],
    released: bool,
    released_de_object: str,
) -> None:
    sig = signature_name(study_accession, case_label, control_label)
    if released:
        workflow_name = "released_de"
        score_mode = manifest_value(settings, "extractor_score_mode_released", "stat")
    else:
        workflow_name = "rna_de_prepare"
        score_mode = manifest_value(settings, "extractor_score_mode", "signed_neglog10padj")
    parameters = {
        "study_id": study_id,
        "study_accession": study_accession,
        "study_label": study_label,
        "case_label": case_label,
        "control_label": control_label,
        "score_mode": score_mode,
        "select": manifest_value(settings, "extractor_select", "top_k"),
        "top_k": manifest_value(settings, "extractor_top_k", "250"),
    }
    if released:
        parameters["de_source"] = "study_published_de_table"
        parameters["released_de_object"] = released_de_object
    else:
        parameters["group_column"] = settings.get("group_column", "")
        parameters["covariates"] = covariates
        parameters["backend"] = manifest_value(settings, "workflow_backend", "r_limma_voom")
        parameters["padj_max"] = manifest_value(settings, "extractor_padj_max", "0.05")
    payload = {
        "schema_version": "1",
        "library": "ImmPort",
        "model_id": model_id,
        "model_group": "bulk_de",
        "model_label": "per_study_case_vs_control",
        "workflow_name": workflow_name,
        "extractor_name": "rna_deg",
        "parameters": parameters,
        "inputs": {
            "organism": "human",
            "genome_build": "hg38",
        },
        "naming": {
            "comparison_style": "case_vs_control",
            "comparison_label": sig,
            "gene_set_pattern": f"{sig}_up|dn",
        },
    }
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_workflow_cmd(
    *,
    python_bin: str,
    expression_tsv: Path,
    sample_metadata_tsv: Path,
    group_column: str,
    case_label: str,
    control_label: str,
    covariates: str,
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
        "rna_de_prepare",
        "--modality",
        "bulk",
        "--counts_tsv",
        str(expression_tsv),
        "--matrix_orientation",
        "gene_by_sample",
        "--feature_id_column",
        "gene_id",
        "--matrix_gene_symbol_column",
        "gene_symbol",
        "--sample_id_column",
        "sample_id",
        "--sample_metadata_tsv",
        str(sample_metadata_tsv),
        "--group_column",
        group_column,
        "--comparison_mode",
        "condition_a_vs_b",
        "--condition_a",
        case_label,
        "--condition_b",
        control_label,
        "--backend",
        manifest_value(settings, "workflow_backend", "r_limma_voom"),
        "--out_dir",
        str(workflow_out),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
    ]
    if covariates:
        cmd.extend(["--covariates", covariates])
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def build_extractor_cmd(
    *,
    python_bin: str,
    deg_tsv: Path,
    extractor_out: Path,
    sig_name: str,
    settings: dict[str, str],
    released: bool,
    de_columns: dict[str, str] | None,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    if released:
        # Published DE tables are pre-filtered to a significance cutoff and often ship
        # p-values rounded to low precision, so rank by the signed test statistic.
        score_mode = manifest_value(settings, "extractor_score_mode_released", "stat")
    else:
        score_mode = manifest_value(settings, "extractor_score_mode", "signed_neglog10padj")
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg",
        "--deg_tsv",
        str(deg_tsv),
        "--out_dir",
        str(extractor_out),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--signature_name",
        sig_name,
        "--postprocess_mode",
        manifest_value(settings, "extractor_postprocess_mode", "harmonizome"),
        "--score_mode",
        score_mode,
        "--select",
        manifest_value(settings, "extractor_select", "top_k"),
        "--top_k",
        manifest_value(settings, "extractor_top_k", "250"),
        "--gmt_require_symbol",
        manifest_value(settings, "extractor_gmt_require_symbol", "true"),
        "--gmt_min_genes",
        manifest_value(settings, "extractor_gmt_min_genes", "5"),
        "--gmt_max_genes",
        manifest_value(settings, "extractor_gmt_max_genes", "500"),
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
    ]
    if released and de_columns:
        cmd.extend(["--gene_id_column", de_columns["gene_id"]])
        cmd.extend(["--gene_symbol_column", de_columns["gene_symbol"]])
        cmd.extend(["--stat_column", de_columns["stat"]])
        cmd.extend(["--logfc_column", de_columns["logfc"]])
        cmd.extend(["--pvalue_column", de_columns["pvalue"]])
        cmd.extend(["--padj_column", de_columns["padj"]])
    # In released-DE mode the table is already significance-filtered upstream, so skip padj_max.
    padj_max = "" if released else manifest_value(settings, "extractor_padj_max", "")
    if padj_max:
        cmd.extend(["--padj_max", padj_max])
    min_abs_logfc = manifest_value(settings, "extractor_min_abs_logfc", "")
    if min_abs_logfc:
        cmd.extend(["--min_abs_logfc", min_abs_logfc])
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def build_provenance_rebuild_cmd(
    *,
    python_bin: str,
    metadata_json: Path,
    upstream_provenance_graph_json: Path | None,
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
    ]
    if upstream_provenance_graph_json is not None:
        cmd.extend(["--upstream_provenance_graph_json", str(upstream_provenance_graph_json)])
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
    workflow_cmd: list[str] | None,
    extractor_cmd: list[str],
    provenance_cmd: list[str],
    dig_dir: Path,
) -> None:
    lines = [f"# Commands For {model_id}", ""]
    if workflow_cmd is not None:
        lines += [
            "## Workflow (rna_de_prepare)",
            "",
            "```bash",
            f"cd {shlex.quote(str(dig_dir))}",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {shell_join(workflow_cmd)}",
            "```",
            "",
        ]
    else:
        lines += [
            "## Workflow",
            "",
            "Released-DE mode: no DE workflow is run; the study's published differential-expression "
            "table is fed directly to the rna_deg converter.",
            "",
        ]
    lines += [
        "## Extractor (rna_deg)",
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
        "geneset-extractor-dev only orchestrates; differential expression and GMT emission are owned by "
        "dig-gene-set-extractors (rna_de_prepare + rna_deg).",
        "",
    ]
    write_text(model_out / "commands.md", "\n".join(lines))


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]

    released = bool(args.released_de_tsv)
    study_accession = (args.study_accession or "").strip() or args.study_id

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
    sig_name = signature_name(study_accession, args.case_label, args.control_label)

    de_columns = {
        "gene_id": args.de_gene_id_column,
        "gene_symbol": args.de_gene_symbol_column,
        "stat": args.de_stat_column,
        "logfc": args.de_logfc_column,
        "pvalue": args.de_pvalue_column,
        "padj": args.de_padj_column,
    }
    released_de_object = ""

    if released:
        released_de_tsv = require_existing_file(args.released_de_tsv, "released DE table")
        released_de_object = Path(args.released_de_tsv).name
        workflow_cmd = None
        deg_tsv = released_de_tsv
        # No upstream workflow graph: provenance roots directly at the published DE file,
        # which the rna_deg converter records as an input File node.
        upstream_graph = None
    else:
        expression_tsv = require_existing_file(args.expression_tsv, "expression TSV")
        sample_metadata_tsv = require_existing_file(args.sample_metadata_tsv, "sample metadata TSV")
        if not args.group_column:
            raise SystemExit("--group_column is required in counts->DE mode")
        workflow_cmd = build_workflow_cmd(
            python_bin=python_bin,
            expression_tsv=expression_tsv,
            sample_metadata_tsv=sample_metadata_tsv,
            group_column=args.group_column,
            case_label=args.case_label,
            control_label=args.control_label,
            covariates=args.covariates,
            workflow_out=workflow_out,
            settings=settings,
            provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
            provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
        )
        deg_tsv = workflow_out / "deg_long.tsv"
        upstream_graph = workflow_out / "deg_long.provenance_graph.json"

    extractor_cmd = build_extractor_cmd(
        python_bin=python_bin,
        deg_tsv=deg_tsv,
        extractor_out=extractor_out,
        sig_name=sig_name,
        settings=settings,
        released=released,
        de_columns=de_columns,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    prov_cmd_kwargs = dict(
        python_bin=python_bin,
        metadata_json=extractor_out / "geneset.meta.json",
        provenance_out=extractor_out / "geneset.provenance.json",
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    provenance_cmd = build_provenance_rebuild_cmd(
        upstream_provenance_graph_json=upstream_graph,
        **prov_cmd_kwargs,
    )
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        extractor_cmd=extractor_cmd,
        provenance_cmd=provenance_cmd,
        dig_dir=dig_dir,
    )
    settings_with_group = {**settings, "group_column": args.group_column}

    def _write_sidecar() -> None:
        write_model_sidecar(
            path=extractor_out / "geneset.model.json",
            model_id=args.model_id,
            study_id=args.study_id,
            study_accession=study_accession,
            study_label=args.study_label,
            case_label=args.case_label,
            control_label=args.control_label,
            covariates=args.covariates,
            settings=settings_with_group,
            released=released,
            released_de_object=released_de_object,
        )

    if args.write_model_only:
        _write_sidecar()
        return 0
    if args.write_commands_only:
        return 0

    model_log = model_out / "run.log"
    if workflow_cmd is not None:
        run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
    _write_sidecar()
    run_command(provenance_cmd, cwd=dig_dir, env=env, log_path=model_log)

    # Enrich provenance with resource / study / pipeline / preprocessing metadata.
    if released:
        score_mode = manifest_value(settings, "extractor_score_mode_released", "stat")
        pipeline = "released_de -> rna_deg"
        preprocessing = (
            f"Study-published differential-expression table ({released_de_object}); genes ranked by "
            f"signed {score_mode}; signed up/down gene sets via rna_deg "
            f"(top-{manifest_value(settings, 'extractor_top_k', '250')}, "
            f"min size {manifest_value(settings, 'extractor_gmt_min_genes', '5')})."
        )
    else:
        pipeline = "rna_de_prepare (limma_voom) -> rna_deg"
        preprocessing = (
            f"Raw counts matrix; sample groups from metadata column '{args.group_column}'; "
            f"limma-voom differential expression {args.case_label} vs {args.control_label}"
            + (f" adjusting for {args.covariates}" if args.covariates else "")
            + f"; signed up/down gene sets via rna_deg (score_mode "
            f"{manifest_value(settings, 'extractor_score_mode', 'signed_neglog10padj')})."
        )
    enrich_provenance(
        extractor_out / "geneset.provenance.json",
        resource="ImmPort",
        study_id=study_accession,
        pipeline=pipeline,
        preprocessing=preprocessing,
    )

    summary_rows = [{"source_gmt": "genesets.gmt", **row} for row in parse_gmt(extractor_out / "genesets.gmt")]
    write_tsv(extractor_out / "signature_summary.tsv", summary_rows, ["source_gmt", "set_name", "description", "gene_count"])
    write_manifest(
        manifest_path=extractor_out / "run_manifest.json",
        model_id=args.model_id,
        study_id=args.study_id,
        workflow_out=workflow_out,
        extractor_out=extractor_out,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
