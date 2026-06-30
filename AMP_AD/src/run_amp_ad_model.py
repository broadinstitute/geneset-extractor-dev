#!/usr/bin/env python3
import argparse
import csv
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Dict, List

from amp_ad_selection_io import default_model_manifest_path, repo_root


CONTRAST_COLUMNS = ["Study", "Tissue", "Model", "Comparison", "Sex"]
REQUIRED_COLUMNS = [
    "Study",
    "Tissue",
    "Model",
    "Comparison",
    "Sex",
    "ensembl_gene_id",
    "hgnc_symbol",
    "logFC",
    "t",
    "P.Value",
    "adj.P.Val",
]
SAFE_RE = re.compile(r"[^A-Za-z0-9._=-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the AMP-AD ADKP released DEG model as a wrapper around DIG rna_deg_multi."
    )
    parser.add_argument("--model_id", default="AD1")
    parser.add_argument("--input_tsv", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--dig_dir", default=str(repo_root() / "dig-gene-set-extractors"))
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--write_commands_only", action="store_true")
    parser.add_argument("--write_model_only", action="store_true")
    return parser.parse_args()


def manifest_value(settings, key, default):
    value = str(settings.get(key, "")).strip()
    if not value or value == "NA":
        return default
    return value


def manifest_bool(settings, key, default):
    value = manifest_value(settings, key, "true" if default else "false").lower()
    return value in {"1", "true", "yes", "y"}


def load_model_settings(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    out = {}  # type: Dict[str, Dict[str, str]]
    for row in rows:
        model_id = str(row.get("model_id", "")).strip()
        if model_id:
            out[model_id] = {str(key): str(value) for key, value in row.items()}
    if not out:
        raise SystemExit(f"No model settings found in {path}")
    return out


def safe_component(value):
    text = SAFE_RE.sub("_", str(value).strip())
    text = text.strip("_")
    return text or "NA"


def make_comparison_id(row):
    return "__".join(safe_component(row.get(col, "")) for col in CONTRAST_COLUMNS)


def make_comparison_name(row):
    return " / ".join(str(row.get(col, "")).strip() or "NA" for col in CONTRAST_COLUMNS)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def shell_join(cmd):
    return " ".join(shlex.quote(part) for part in cmd)


def prepare_deg_long(input_tsv, output_tsv, contrast_summary_tsv, run_summary_json):
    output_tsv.parent.mkdir(parents=True, exist_ok=True)
    contrast_counts = {}  # type: Dict[str, int]
    contrast_names = {}  # type: Dict[str, str]
    row_count = 0
    with input_tsv.open("r", encoding="utf-8", newline="") as in_handle:
        reader = csv.DictReader(in_handle, delimiter="\t")
        if not reader.fieldnames:
            raise SystemExit(f"Input TSV has no header: {input_tsv}")
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise SystemExit(f"Input TSV is missing required columns: {', '.join(missing)}")
        fieldnames = ["comparison_id", "comparison_name"] + list(reader.fieldnames)
        with output_tsv.open("w", encoding="utf-8", newline="") as out_handle:
            writer = csv.DictWriter(out_handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for row in reader:
                comparison_id = make_comparison_id(row)
                comparison_name = make_comparison_name(row)
                row_out = {"comparison_id": comparison_id, "comparison_name": comparison_name}
                row_out.update(row)
                writer.writerow(row_out)
                contrast_counts[comparison_id] = contrast_counts.get(comparison_id, 0) + 1
                contrast_names.setdefault(comparison_id, comparison_name)
                row_count += 1

    with contrast_summary_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            delimiter="\t",
            fieldnames=["comparison_id", "comparison_name", "n_rows"],
            lineterminator="\n",
        )
        writer.writeheader()
        for comparison_id in sorted(contrast_counts):
            writer.writerow(
                {
                    "comparison_id": comparison_id,
                    "comparison_name": contrast_names[comparison_id],
                    "n_rows": contrast_counts[comparison_id],
                }
            )

    payload = {
        "input_tsv": str(input_tsv),
        "prepared_deg_tsv": str(output_tsv),
        "n_rows": row_count,
        "n_comparisons": len(contrast_counts),
        "comparison_id_columns": CONTRAST_COLUMNS,
    }
    write_text(run_summary_json, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_extractor_cmd(*, python_bin, prepared_tsv, extractor_out, settings):
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg_multi",
        "--deg_tsv",
        str(prepared_tsv),
        "--comparison_column",
        "comparison_id",
        "--comparison_name_column",
        "comparison_name",
        "--out_dir",
        str(extractor_out),
        "--organism",
        "human",
        "--genome_build",
        manifest_value(settings, "genome_build", "hg19"),
        "--signature_name",
        manifest_value(settings, "signature_name", "AMP_AD_bulk_brain_RNA"),
        "--gene_id_column",
        "ensembl_gene_id",
        "--gene_symbol_column",
        "hgnc_symbol",
        "--stat_column",
        "t",
        "--logfc_column",
        "logFC",
        "--padj_column",
        "adj.P.Val",
        "--pvalue_column",
        "P.Value",
        "--postprocess_mode",
        manifest_value(settings, "extractor_postprocess_mode", "harmonizome"),
        "--score_mode",
        manifest_value(settings, "extractor_score_mode", "signed_neglog10padj"),
        "--select",
        manifest_value(settings, "extractor_select", "top_k"),
        "--gmt_require_symbol",
        "true" if manifest_bool(settings, "extractor_gmt_require_symbol", True) else "false",
        "--emit_small_gene_sets",
        "true" if manifest_bool(settings, "extractor_emit_small_gene_sets", False) else "false",
        "--top_k",
        manifest_value(settings, "extractor_top_k", "250"),
        "--gmt_source",
        manifest_value(settings, "extractor_gmt_source", "selected"),
        "--gmt_topk_list",
        manifest_value(settings, "extractor_gmt_topk_list", "250"),
        "--gmt_min_genes",
        manifest_value(settings, "extractor_gmt_min_genes", "5"),
        "--gmt_max_genes",
        manifest_value(settings, "extractor_gmt_max_genes", "500"),
    ]
    for key, flag in [
        ("extractor_padj_max", "--padj_max"),
        ("extractor_pvalue_max", "--pvalue_max"),
        ("extractor_min_abs_logfc", "--min_abs_logfc"),
        ("extractor_min_score", "--min_score"),
    ]:
        value = manifest_value(settings, key, "NA")
        if value != "NA":
            cmd.extend([flag, value])
    if manifest_bool(settings, "extractor_disable_default_excludes", False):
        cmd.append("--disable_default_excludes")
    return cmd


def write_model_commands(model_out, prep_cmd, extractor_cmd, dig_dir):
    text = "\n".join(
        [
            "# AMP-AD Model Commands",
            "",
            "## Prepare Released DEG Table",
            "",
            "```bash",
            shell_join(prep_cmd),
            "```",
            "",
            "## Extract Gene Sets",
            "",
            "```bash",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))}:$PYTHONPATH {shell_join(extractor_cmd)}",
            "```",
            "",
        ]
    )
    write_text(model_out / "commands.md", text)


def read_manifest_rows(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_model_sidecars(extractor_out, model_id, settings):
    manifest_path = extractor_out / "manifest.tsv"
    rows = read_manifest_rows(manifest_path)
    root_payload = {
        "schema_version": "1",
        "library": "AMP_AD",
        "model_id": model_id,
        "model_group": "AD",
        "model_label": "adkp_released_dea",
        "workflow_name": "amp_ad_prepare_released_dea",
        "extractor_name": "rna_deg_multi",
        "parameters": {
            "comparison_id_columns": CONTRAST_COLUMNS,
            "postprocess_mode": manifest_value(settings, "extractor_postprocess_mode", "harmonizome"),
            "score_mode": manifest_value(settings, "extractor_score_mode", "signed_neglog10padj"),
            "padj_max": manifest_value(settings, "extractor_padj_max", "0.05"),
            "select": manifest_value(settings, "extractor_select", "top_k"),
        },
        "inputs": {
            "organism": "human",
            "genome_build": manifest_value(settings, "genome_build", "hg19"),
        },
        "naming": {
            "comparison_style": "Study__Tissue__Model__Comparison__Sex",
            "gene_set_pattern": "AMP_AD_bulk_brain_RNA_<comparison>_up|dn",
        },
    }
    write_text(extractor_out / "geneset.model.json", json.dumps(root_payload, indent=2, sort_keys=True) + "\n")
    for row in rows:
        meta_rel = str(row.get("meta_path", "")).strip()
        if not meta_rel:
            continue
        payload = dict(root_payload)
        payload["naming"] = {
            **root_payload["naming"],
            "comparison_label": str(row.get("label", "")).strip(),
        }
        write_text((extractor_out / meta_rel).with_name("geneset.model.json"), json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_command(cmd, log_path, env):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_handle:
        log_handle.write(f"$ {shell_join(cmd)}\n")
        log_handle.flush()
        subprocess.run(cmd, check=True, stdout=log_handle, stderr=subprocess.STDOUT, env=env)


def main():
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest).resolve())
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unknown model_id {args.model_id}; available: {', '.join(sorted(settings_by_model))}")
    settings = settings_by_model[args.model_id]

    input_tsv = Path(args.input_tsv).expanduser().resolve()
    if not input_tsv.is_file():
        raise SystemExit(f"Missing input_tsv: {input_tsv}")
    dig_dir = Path(args.dig_dir).expanduser().resolve()
    if not (dig_dir / "src" / "geneset_extractors").is_dir():
        raise SystemExit(f"dig_dir does not look like dig-gene-set-extractors: {dig_dir}")

    model_out = Path(args.run_root).expanduser().resolve() / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "extractor"
    prepared_tsv = workflow_out / "adkp_ampad_deg_long.tsv"
    contrast_summary = workflow_out / "contrast_summary.tsv"
    run_summary = workflow_out / "run_summary.json"
    log_path = model_out / "run.log"

    prep_cmd = [
        str(Path(args.python_bin).resolve()),
        str(Path(__file__).resolve()),
        "--model_id",
        args.model_id,
        "--input_tsv",
        str(input_tsv),
        "--run_root",
        str(Path(args.run_root).expanduser().resolve()),
        "--dig_dir",
        str(dig_dir),
        "--model_manifest",
        str(Path(args.model_manifest).resolve()),
    ]
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        prepared_tsv=prepared_tsv,
        extractor_out=extractor_out,
        settings=settings,
    )
    write_model_commands(model_out, prep_cmd, extractor_cmd, dig_dir)

    if args.write_model_only:
        write_model_sidecars(extractor_out, args.model_id, settings)
        return 0
    if args.write_commands_only:
        return 0

    prepare_deg_long(input_tsv, prepared_tsv, contrast_summary, run_summary)

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{dig_dir / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    run_command(extractor_cmd, log_path, env)
    write_model_sidecars(extractor_out, args.model_id, settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
