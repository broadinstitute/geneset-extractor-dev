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
import re

from selection_io import default_age_binned_model_manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one GTEx age-binned model and emit extractor outputs."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--tissue_id")
    parser.add_argument("--tissue_label", required=True)
    parser.add_argument("--expression_gct")
    parser.add_argument("--sample_attributes_tsv")
    parser.add_argument("--subject_phenotypes_tsv")
    parser.add_argument("--tissue_column")
    parser.add_argument("--tissue_value")
    parser.add_argument("--prepared_dir")
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--organism", default="human", choices=["human", "mouse"])
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--gtf")
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--age_binned_model_manifest", default=str(default_age_binned_model_manifest_path()))
    parser.add_argument("--write_commands_only", action="store_true")
    parser.add_argument("--write_model_only", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_input_path(path_value: str | None, *, base_dir: Path) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def compact_name_token(value: str) -> str:
    parts = [part for part in re.sub(r"[^A-Za-z0-9]+", " ", str(value).strip()).split() if part]
    return "".join(parts) or "tissue"


def gtex_aging_signature_name(tissue_label: str) -> str:
    return f"GTEx_aging_{compact_name_token(tissue_label)}"


def load_model_settings(manifest_path: Path) -> dict[str, dict[str, str]]:
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


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def model_group(model_id: str) -> str:
    return "".join(ch for ch in str(model_id) if ch.isalpha()) or str(model_id)


def model_label(model_id: str) -> str:
    group = model_group(model_id)
    if group == "AB":
        return "age_binned"
    if group == "HZ":
        return "age_reference_matched"
    return group.lower()


def write_json(path: Path, payload: dict[str, object]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_model_sidecar_payload(
    *,
    model_id: str,
    tissue_id: str,
    tissue_label: str,
    settings: dict[str, str],
    comparison_label: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1",
        "library": "GTEx",
        "model_id": model_id,
        "model_group": model_group(model_id),
        "model_label": model_label(model_id),
        "workflow_name": "gtex_age_binned",
        "extractor_name": "rna_deg_multi",
        "parameters": {
            "de_mode": settings["workflow_de_mode"],
            "balance_groups": settings["workflow_balance_groups"],
            "balance_seed": settings["workflow_balance_seed"],
            "gene_filter_scope": settings["workflow_gene_filter_scope"],
            "backend": settings["workflow_backend"],
            "covariates": settings["workflow_covariates"],
            "postprocess_mode": settings["extractor_postprocess_mode"],
            "score_mode": settings["extractor_score_mode"],
            "select": settings["extractor_select"],
        },
        "inputs": {
            "tissue_id": tissue_id,
            "tissue_label": tissue_label,
            "organism": "human",
            "genome_build": "hg38",
        },
        "naming": {
            "signature_name": gtex_aging_signature_name(tissue_label),
            "comparison_label": comparison_label or "",
            "comparison_style": "age_pair",
            "gene_set_pattern": "GTEx_aging_<tissue>_<ageGroup1>_<ageGroup2>_up|dn",
        },
    }


def write_grouped_model_sidecars(
    *,
    extractor_out: Path,
    model_id: str,
    tissue_id: str,
    tissue_label: str,
    settings: dict[str, str],
) -> None:
    manifest_path = extractor_out / "manifest.tsv"
    if not manifest_path.exists():
        return
    for row in read_tsv_rows(manifest_path):
        meta_rel = str(row.get("meta_path", "")).strip()
        if not meta_rel:
            continue
        sidecar_path = (extractor_out / meta_rel).with_name("geneset.model.json")
        write_json(
            sidecar_path,
            build_model_sidecar_payload(
                model_id=model_id,
                tissue_id=tissue_id,
                tissue_label=tissue_label,
                settings=settings,
                comparison_label=str(row.get("label", "")).strip(),
            ),
        )


def build_workflow_cmd(
    *,
    python_bin: str,
    workflow_out: Path,
    organism: str,
    genome_build: str,
    tissue_id: str,
    tissue_label: str,
    expression_gct: Path,
    sample_attributes_tsv: Path,
    subject_phenotypes_tsv: Path,
    tissue_column: str | None,
    tissue_value: str | None,
    settings: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "gtex_age_binned",
        "--expression_gct",
        str(expression_gct),
        "--sample_attributes_tsv",
        str(sample_attributes_tsv),
        "--subject_phenotypes_tsv",
        str(subject_phenotypes_tsv),
        "--tissue_id",
        tissue_id,
        "--tissue_label",
        tissue_label,
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
    if tissue_column and tissue_value:
        cmd.extend(["--tissue_column", tissue_column, "--tissue_value", tissue_value])
    if settings["workflow_covariates"] != "none":
        cmd.extend(["--covariates", settings["workflow_covariates"]])
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
    organism: str,
    genome_build: str,
    tissue_label: str,
    settings: dict[str, str],
    gtf_path: str | None,
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
        str(deg_tsv),
        "--comparison_column",
        "comparison_id",
        "--comparison_name_column",
        "gmt_comparison_label",
        "--out_dir",
        str(extractor_out),
        "--organism",
        organism,
        "--genome_build",
        genome_build,
        "--signature_name",
        gtex_aging_signature_name(tissue_label),
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
    if settings["extractor_gmt_biotype_allowlist"]:
        cmd.extend(["--gmt_biotype_allowlist", settings["extractor_gmt_biotype_allowlist"]])
    if gtf_path:
        cmd.extend(["--gtf", gtf_path])
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


def rebuild_grouped_provenance(
    *,
    python_bin: str,
    extractor_out: Path,
    upstream_provenance_graph_json: Path,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
) -> None:
    manifest_path = extractor_out / "manifest.tsv"
    if not manifest_path.exists():
        return
    for row in read_tsv_rows(manifest_path):
        meta_rel = str(row.get("meta_path", "")).strip()
        prov_rel = str(row.get("provenance_path", "")).strip()
        if not meta_rel or not prov_rel:
            continue
        provenance_cmd = build_provenance_rebuild_cmd(
            python_bin=python_bin,
            metadata_json=extractor_out / meta_rel,
            upstream_provenance_graph_json=upstream_provenance_graph_json,
            provenance_out=extractor_out / prov_rel,
            provenance_mirror_local_prefix=provenance_mirror_local_prefix,
            provenance_mirror_remote_prefix=provenance_mirror_remote_prefix,
        )
        run_command(provenance_cmd, cwd=cwd, env=env, log_path=log_path)


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
            "Note: `rna_deg_multi` writes grouped extractor outputs and this wrapper rebuilds per-group provenance from `manifest.tsv`.",
        ]
    )
    write_text(model_out / "commands.md", text)


def main() -> int:
    args = parse_args()
    repo = repo_root()
    run_root = Path(args.run_root).resolve()
    dig_dir = Path(args.dig_dir).resolve()
    manifest_path = Path(args.age_binned_model_manifest).resolve()
    resolved_gtf = resolve_input_path(args.gtf, base_dir=repo)
    model_settings = load_model_settings(manifest_path)
    if args.model_id not in model_settings:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = model_settings[args.model_id]
    tissue_id = str(args.tissue_id).strip()
    tissue_label = str(args.tissue_label).strip()

    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "extractor"
    model_out.mkdir(parents=True, exist_ok=True)
    model_log = model_out / "run.log"

    if args.write_model_only:
        write_json(
            extractor_out / "geneset.model.json",
            build_model_sidecar_payload(
                model_id=args.model_id,
                tissue_id=tissue_id,
                tissue_label=tissue_label,
                settings=settings,
            ),
        )
        return 0

    if not args.expression_gct or not args.sample_attributes_tsv or not args.subject_phenotypes_tsv:
        raise SystemExit(
            "--expression_gct, --sample_attributes_tsv, and --subject_phenotypes_tsv are required unless --write_model_only is used"
        )

    expression_gct = Path(args.expression_gct).resolve()
    sample_attributes_tsv = Path(args.sample_attributes_tsv).resolve()
    subject_phenotypes_tsv = Path(args.subject_phenotypes_tsv).resolve()

    if settings["annotation_mode"] == "gtf_annotated" and not resolved_gtf:
        raise SystemExit(f"Model {args.model_id} requires --gtf")

    workflow_cmd = build_workflow_cmd(
        python_bin=args.python_bin,
        workflow_out=workflow_out,
        organism=args.organism,
        genome_build=args.genome_build,
        tissue_id=tissue_id,
        tissue_label=tissue_label,
        expression_gct=expression_gct,
        sample_attributes_tsv=sample_attributes_tsv,
        subject_phenotypes_tsv=subject_phenotypes_tsv,
        tissue_column=args.tissue_column,
        tissue_value=args.tissue_value,
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(dig_dir / "src")
    log_line(model_log, f"[run_age_binned_model] model_id={args.model_id}")
    deg_tsv_for_extractor = workflow_out / "deg_long.tsv"
    extractor_cmd = build_extractor_cmd(
        python_bin=args.python_bin,
        deg_tsv=deg_tsv_for_extractor,
        extractor_out=extractor_out,
        organism=args.organism,
        genome_build=args.genome_build,
        tissue_label=tissue_label,
        settings=settings,
        gtf_path=resolved_gtf,
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

    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    extractor_cmd = build_extractor_cmd(
        python_bin=args.python_bin,
        deg_tsv=deg_tsv_for_extractor,
        extractor_out=extractor_out,
        organism=args.organism,
        genome_build=args.genome_build,
        tissue_label=tissue_label,
        settings=settings,
        gtf_path=resolved_gtf,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
    write_grouped_model_sidecars(
        extractor_out=extractor_out,
        model_id=args.model_id,
        tissue_id=tissue_id,
        tissue_label=tissue_label,
        settings=settings,
    )
    rebuild_grouped_provenance(
        python_bin=args.python_bin,
        extractor_out=extractor_out,
        upstream_provenance_graph_json=workflow_out / "deg_long.provenance_graph.json",
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
        cwd=dig_dir,
        env=env,
        log_path=model_log,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
