#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Dict

from amp_ad_selection_io import default_model_manifest_path, repo_root


CONTRAST_COLUMNS = ["Study", "Tissue", "Model", "Comparison", "Sex"]
SAFE_RE = re.compile(r"[^A-Za-z0-9._=-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the AMP-AD ADKP released DEG model through DIG-owned preparation and extraction."
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
    text = SAFE_RE.sub("_", str(value or "").strip()).strip("_")
    return text or "NA"


def comparison_human_from_id(value):
    parts = str(value or "").split("__")
    if len(parts) == len(CONTRAST_COLUMNS):
        return " / ".join(part or "NA" for part in parts)
    return str(value or "").replace("_", " ")


def comparison_gmt_from_id(value):
    parts = str(value or "").split("__")
    if len(parts) == len(CONTRAST_COLUMNS):
        return "_".join(safe_component(part) for part in parts)
    return safe_component(value)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def shell_join(cmd):
    return " ".join(shlex.quote(str(part)) for part in cmd)


def build_workflow_cmd(*, python_bin, input_tsv, workflow_out):
    return [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "amp_ad_released_dea",
        "--input_tsv",
        str(input_tsv),
        "--out_dir",
        str(workflow_out),
    ]


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
        "comparison_gmt_label",
        "--out_dir",
        str(extractor_out),
        "--organism",
        "human",
        "--genome_build",
        manifest_value(settings, "genome_build", "hg19"),
        "--signature_name",
        manifest_value(settings, "signature_name", "AMP_AD"),
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
        "--gmt_name_separator",
        "_",
        "--gmt_signed_labels",
        "up_dn",
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


def add_mirror_flags(cmd, args):
    if args.provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", args.provenance_mirror_local_prefix])
    if args.provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", args.provenance_mirror_remote_prefix])


def write_model_commands(model_out, workflow_cmd, extractor_cmd, dig_dir):
    text = "\n".join(
        [
            "# AMP-AD Model Commands",
            "",
            "## Prepare Released DEG Table With DIG",
            "",
            "```bash",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))}:$PYTHONPATH {shell_join(workflow_cmd)}",
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


def read_template(path, model_id):
    if not path or not Path(path).exists():
        return ""
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if str(row.get("model_id", "")).strip() == model_id:
                return str(row.get("description_template", "")).strip()
    return ""


def render_description(template, *, model_id, comparison_label):
    if not template:
        return (
            f"AMP-AD bulk brain RNA differential-expression gene set for {comparison_label} "
            f"using model {model_id}: library built from the AD Knowledge Portal released merged "
            "differential-expression summary table, grouped by study, tissue, model, comparison, and sex."
        )
    return template.replace("{comparison_label}", comparison_label).replace("{model.model_id}", model_id)


def patch_metadata_description(meta_path, description):
    if not meta_path.exists():
        return
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    payload.setdefault("gene_set", {})["description"] = description
    write_text(meta_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def rewrite_gmt_descriptions(gmt_path, description):
    if not gmt_path.exists():
        return
    lines = []
    for raw in gmt_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        fields = raw.split("\t")
        if len(fields) < 3:
            lines.append(raw)
            continue
        name = fields[0]
        lowered = name.lower()
        if lowered.endswith("_up"):
            desc = f"Up-regulated genes from the {description}"
        elif lowered.endswith("_dn"):
            desc = f"Down-regulated genes from the {description}"
        else:
            desc = description
        lines.append("\t".join([name, desc, *fields[2:]]))
    write_text(gmt_path, "\n".join(lines) + ("\n" if lines else ""))


def scrub_publish_paths(model_out, *, local_prefix, remote_prefix):
    if not local_prefix or not remote_prefix:
        return
    replacements = [
        (str(Path(local_prefix).resolve()), str(remote_prefix).rstrip("/")),
        (str(Path(local_prefix).resolve()).replace("/diabetes2/", "/diabetes/"), str(remote_prefix).rstrip("/")),
        (str(Path(sys.executable).resolve()), "python"),
    ]
    text_suffixes = {".json", ".md", ".txt", ".log"}
    for path in model_out.rglob("*"):
        if not path.is_file() or path.suffix not in text_suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_text = text
        for source, target in replacements:
            new_text = new_text.replace(source, target)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")


def write_model_sidecars(extractor_out, model_id, settings, *, input_tsv, template_path=None):
    manifest_path = extractor_out / "manifest.tsv"
    rows = read_manifest_rows(manifest_path)
    template = read_template(template_path, model_id)
    root_payload = {
        "schema_version": "1",
        "library": "AMP_AD",
        "model_id": model_id,
        "model_group": "AD",
        "model_label": "adkp_released_dea",
        "workflow_name": "amp_ad_released_dea",
        "extractor_name": "rna_deg_multi",
        "parameters": {
            "comparison_id_columns": CONTRAST_COLUMNS,
            "postprocess_mode": manifest_value(settings, "extractor_postprocess_mode", "harmonizome"),
            "score_mode": manifest_value(settings, "extractor_score_mode", "signed_neglog10padj"),
            "padj_max": manifest_value(settings, "extractor_padj_max", "0.05"),
            "select": manifest_value(settings, "extractor_select", "top_k"),
        },
        "inputs": {
            "input_tsv": str(input_tsv),
            "input_label": "AD Knowledge Portal merged differential-expression summary table",
            "source_repository": "AMP-AD Knowledge Portal",
            "source_dataset": "released merged differential-expression summary table",
            "study_fields": CONTRAST_COLUMNS,
            "comparison_fields": CONTRAST_COLUMNS,
            "organism": "human",
            "genome_build": manifest_value(settings, "genome_build", "hg19"),
        },
        "naming": {
            "signature_name": manifest_value(settings, "signature_name", "AMP_AD"),
            "comparison_style": "Study__Tissue__Model__Comparison__Sex",
            "gene_set_pattern": "AMP_AD_<comparison>_up|dn",
            "direction_labels": ["up", "dn"],
        },
    }
    write_text(extractor_out / "geneset.model.json", json.dumps(root_payload, indent=2, sort_keys=True) + "\n")
    for row in rows:
        comparison = str(row.get("comparison", "")).strip()
        comparison_human = comparison_human_from_id(comparison)
        comparison_gmt = comparison_gmt_from_id(comparison)
        description = render_description(template, model_id=model_id, comparison_label=comparison_human)
        gmt_path = extractor_out / str(row.get("path", "")).strip() / "genesets.gmt"
        meta_rel = str(row.get("meta_path", "")).strip()
        if not meta_rel:
            continue
        payload = dict(root_payload)
        payload["naming"] = {
            **root_payload["naming"],
            "comparison_label": comparison_gmt,
            "comparison_label_human": comparison_human,
        }
        meta_path = extractor_out / meta_rel
        write_text(meta_path.with_name("geneset.model.json"), json.dumps(payload, indent=2, sort_keys=True) + "\n")
        patch_metadata_description(meta_path, description)
        rewrite_gmt_descriptions(gmt_path, description)
    rewrite_gmt_descriptions(extractor_out / "genesets.gmt", "AMP-AD bulk brain RNA differential-expression gene set library")


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
    log_path = model_out / "run.log"

    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        input_tsv=input_tsv,
        workflow_out=workflow_out,
    )
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        prepared_tsv=prepared_tsv,
        extractor_out=extractor_out,
        settings=settings,
    )
    add_mirror_flags(workflow_cmd, args)
    add_mirror_flags(extractor_cmd, args)
    write_model_commands(model_out, workflow_cmd, extractor_cmd, dig_dir)

    template_path = Path(args.model_manifest).resolve().parent / "model_description_templates.tsv"
    if args.write_model_only:
        write_model_sidecars(extractor_out, args.model_id, settings, input_tsv=input_tsv, template_path=template_path)
        scrub_publish_paths(
            model_out,
            local_prefix=args.provenance_mirror_local_prefix,
            remote_prefix=args.provenance_mirror_remote_prefix,
        )
        return 0
    if args.write_commands_only:
        return 0

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{dig_dir / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    run_command(workflow_cmd, log_path, env)
    run_command(extractor_cmd, log_path, env)
    write_model_sidecars(extractor_out, args.model_id, settings, input_tsv=input_tsv, template_path=template_path)
    scrub_publish_paths(
        model_out,
        local_prefix=args.provenance_mirror_local_prefix,
        remote_prefix=args.provenance_mirror_remote_prefix,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
