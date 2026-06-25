#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shlex
import subprocess
import sys
from pathlib import Path

from motrpac_selection_io import default_model_list_path, default_model_manifest_path, default_tissue_list_path


LEGACY_TISSUE_TERMS: dict[str, str] = {
    "blood": "T30-Blood-RNA",
    "hippocampus": "T52-Hippocampus",
    "cortex": "T53-Cortex",
    "hypothalamus": "T54-Hypothalamus",
    "gastrocnemius": "T55-Gastrocnemius",
    "vastus_lateralis": "T56-Vastus-Lateralis",
    "heart": "T58-Heart",
    "kidney": "T59-Kidney",
    "adrenals": "T60-Adrenal",
    "colon": "T61-Colon",
    "spleen": "T62-Spleen",
    "testes": "T63-Testes",
    "ovaries": "T64-Ovaries",
    "lung": "T66-Lung",
    "small_intestine": "T67-Small-Intestine",
    "liver": "T68-Liver",
    "brown_adipose": "T69-Brown-Adipose",
    "white_adipose": "T70-White-Adipose",
    "vena_cava": "T99-Vena-Cava",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a MoTrPAC raw-count aggregated HZ model by deriving per-tissue raw contrasts and aggregating them into a library."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--raw_counts_dir", required=True)
    parser.add_argument("--transcript_metadata_tsv", required=True)
    parser.add_argument("--phenotype_metadata_tsv", required=True)
    parser.add_argument("--feature_to_gene_tsv", required=True)
    parser.add_argument("--rat_to_human_tsv", required=True)
    parser.add_argument("--model_list", default=str(default_model_list_path()))
    parser.add_argument("--tissue_list", default=str(default_tissue_list_path()))
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--write_commands_only", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def row_map(rows: list[dict[str, str]], key_field: str) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for row in rows:
        key = str(row.get(key_field, "")).strip()
        if key:
            mapping[key] = {str(k): str(v) for k, v in row.items()}
    return mapping


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


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


def resolve_raw_counts_tsv(raw_counts_dir: Path, raw_counts_object: str) -> Path:
    object_name = str(raw_counts_object).strip()
    candidates = [
        raw_counts_dir / f"{object_name}.tsv.gz",
        raw_counts_dir / "raw_counts_by_tissue" / f"{object_name}.tsv.gz",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise SystemExit(
        "Missing raw counts TSV for "
        f"{object_name}. Looked in: {', '.join(str(path) for path in candidates)}"
    )


def manifest_value(settings: dict[str, str], key: str, default: str) -> str:
    value = str(settings.get(key, "")).strip()
    if not value or value == "NA":
        return default
    return value


def build_signed_term_rows_from_pooled(
    deg_rows: list[dict[str, str]],
    *,
    tissue_id: str,
    padj_max: float,
) -> list[dict[str, str]]:
    base_term = LEGACY_TISSUE_TERMS.get(tissue_id, tissue_id)
    term = f"{base_term}_Consensus"
    out_rows: list[dict[str, str]] = []
    for row in deg_rows:
        gene_id = str(row.get("gene_id", "")).strip()
        gene_symbol = str(row.get("gene_symbol", "")).strip()
        if not gene_id or not gene_symbol:
            continue
        try:
            padj = float(str(row.get("padj", "")).strip())
            logfc = float(str(row.get("logFC", "")).strip())
        except ValueError:
            continue
        if padj <= 0.0 or padj > padj_max or logfc == 0.0:
            continue
        sign = 1.0 if logfc > 0 else -1.0
        signed_score = -math.log10(padj) * sign
        out_rows.append(
            {
                "term": term,
                "gene_id": gene_id,
                "gene_symbol": gene_symbol,
                "score": str(signed_score),
                "sign": str(sign),
            }
        )
    return out_rows


def build_signed_term_rows_from_stratified(
    deg_rows: list[dict[str, str]],
    *,
    tissue_id: str,
    padj_max: float,
) -> list[dict[str, str]]:
    base_term = LEGACY_TISSUE_TERMS.get(tissue_id, tissue_id)
    out_rows: list[dict[str, str]] = []
    for row in deg_rows:
        comparison_id = str(row.get("comparison_id", "")).strip()
        gene_id = str(row.get("gene_id", "")).strip()
        gene_symbol = str(row.get("gene_symbol", "")).strip()
        if not comparison_id or not gene_id or not gene_symbol:
            continue
        try:
            padj = float(str(row.get("padj", "")).strip())
            logfc = float(str(row.get("logFC", "")).strip())
        except ValueError:
            continue
        if padj <= 0.0 or padj > padj_max or logfc == 0.0:
            continue
        parts = comparison_id.split("_")
        if len(parts) == 3:
            sex = parts[1].capitalize()
            timepoint = parts[2].upper()
            term = f"{base_term}_{sex}_{timepoint}"
        elif len(parts) == 2:
            timepoint = parts[1].upper()
            term = f"{base_term}_{timepoint}"
        else:
            term = comparison_id
        sign = 1.0 if logfc > 0 else -1.0
        signed_score = -math.log10(padj) * sign
        out_rows.append(
            {
                "term": term,
                "gene_id": gene_id,
                "gene_symbol": gene_symbol,
                "score": str(signed_score),
                "sign": str(sign),
            }
        )
    return out_rows


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


def build_workflow_cmd(
    *,
    python_bin: str,
    workflow_out: Path,
    settings: dict[str, str],
    raw_counts_dir: Path,
    transcript_metadata_tsv: Path,
    phenotype_metadata_tsv: Path,
    feature_to_gene_tsv: Path,
    rat_to_human_tsv: Path,
    tissue_list_tsv: Path,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    source_model_id = manifest_value(settings, "workflow_source_model", "")
    if source_model_id == "TR1":
        workflow_mode = "pooled"
        covariates = "sex"
    elif source_model_id == "TR2":
        workflow_mode = "pooled"
        covariates = "none"
    elif source_model_id == "TW1":
        workflow_mode = "stratified_sex_timepoint"
        covariates = "none"
    elif source_model_id == "TW2":
        workflow_mode = "stratified_timepoint"
        covariates = "sex"
    else:
        raise SystemExit(f"Unsupported workflow_source_model for raw aggregated HZ workflow: {source_model_id}")
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "motrpac_raw_aggregated",
        "--raw_counts_dir",
        str(raw_counts_dir),
        "--transcript_metadata_tsv",
        str(transcript_metadata_tsv),
        "--phenotype_metadata_tsv",
        str(phenotype_metadata_tsv),
        "--feature_to_gene_tsv",
        str(feature_to_gene_tsv),
        "--rat_to_human_tsv",
        str(rat_to_human_tsv),
        "--tissue_list_tsv",
        str(tissue_list_tsv),
        "--out_dir",
        str(workflow_out),
        "--workflow_mode",
        workflow_mode,
        "--rscript_bin",
        "Rscript",
        "--covariates",
        covariates,
        "--min_samples_per_group",
        manifest_value(settings, "workflow_min_samples_per_group", "5"),
        "--padj_max",
        manifest_value(settings, "workflow_padj_max", "0.05"),
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


def main() -> int:
    args = parse_args()
    dig_dir = Path(args.dig_dir).resolve()
    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "extractor"
    model_log = model_out / "run.log"
    settings_by_model = row_map(read_tsv(Path(args.model_manifest).resolve()), "model_id")
    settings = settings_by_model.get(args.model_id)
    if settings is None:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")

    raw_counts_dir = Path(args.raw_counts_dir).resolve()
    transcript_metadata_tsv = Path(args.transcript_metadata_tsv).resolve()
    phenotype_metadata_tsv = Path(args.phenotype_metadata_tsv).resolve()
    feature_to_gene_tsv = Path(args.feature_to_gene_tsv).resolve()
    rat_to_human_tsv = Path(args.rat_to_human_tsv).resolve()
    tissue_list_tsv = Path(args.tissue_list).resolve()

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(dig_dir / "src")
    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        workflow_out=workflow_out,
        settings=settings,
        raw_counts_dir=raw_counts_dir,
        transcript_metadata_tsv=transcript_metadata_tsv,
        phenotype_metadata_tsv=phenotype_metadata_tsv,
        feature_to_gene_tsv=feature_to_gene_tsv,
        rat_to_human_tsv=rat_to_human_tsv,
        tissue_list_tsv=tissue_list_tsv,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    signed_term_path = workflow_out / "motrpac_signed_term_gene.tsv"

    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        signed_term_tsv=signed_term_path,
        extractor_out=extractor_out,
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    provenance_cmd = build_provenance_rebuild_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        metadata_json=extractor_out / "geneset.meta.json",
        upstream_provenance_graph_json=workflow_out / "motrpac_signed_term_gene.provenance_graph.json",
        provenance_out=extractor_out / "geneset.provenance.json",
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    write_text(
        model_out / "commands.md",
        "\n".join(
            [
                f"# Commands For {args.model_id}",
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
            ]
        ),
    )
    if args.write_commands_only:
        return 0

    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(provenance_cmd, cwd=dig_dir, env=env, log_path=model_log)
    gmt_rows = parse_gmt(extractor_out / "genesets.gmt")
    write_tsv(extractor_out / "signature_summary.tsv", gmt_rows, ["set_name", "description", "gene_count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
