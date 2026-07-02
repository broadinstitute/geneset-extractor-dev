#!/usr/bin/env python3
"""Master loop for the NCI_GDC_TCGA_RNAseq library.

Publishable pattern: the DIG workflow `rnaseq_counts_assemble` builds the counts matrix
from the TRUE initial GDC inputs (per-sample STAR-Counts files + sample sheet) and emits a
provenance graph rooted at those inputs. Per (tumor_type x model) we then dispatch to the
family runner, which chains that assemble graph through rna_de_prepare -> rna_deg_multi so
final provenance begins from the true inputs. geneset-extractor-dev stays a thin wrapper.

- tumor_vs_rest (TR*): assemble ONCE pan-cancer (Primary Tumor), shared across projects.
- tumor_vs_normal (TN*): assemble per focal project (Primary Tumor + Solid Tissue Normal).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tcga_rnaseq_selection_io import (
    default_model_list_path, default_model_manifest_path, default_out_root,
    default_tumor_type_list_path, load_model_rows, load_tumor_type_rows,
    model_group_for, relative_or_absolute_path, repo_root, resolve_requested_ids, row_map,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build TCGA RNA-seq tumor-type gene sets (true-input provenance).")
    p.add_argument("--models", default="all")
    p.add_argument("--models_file")
    p.add_argument("--tumor_types", default="all")
    p.add_argument("--tumor_types_file")
    p.add_argument("--model_list", default=str(default_model_list_path()))
    p.add_argument("--tumor_type_list", default=str(default_tumor_type_list_path()))
    p.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    p.add_argument("--python_bin", default=sys.executable or "python3")
    p.add_argument("--counts_dir", required=True, help="Directory of GDC per-sample STAR-Counts *.tsv (TRUE inputs).")
    p.add_argument("--sample_sheet_tsv", required=True, help="GDC sample sheet (TRUE input).")
    p.add_argument("--gtf", help="GTF for biotype filtering (required if any model sets require_gtf).")
    p.add_argument("--provenance_mirror_local_prefix")
    p.add_argument("--provenance_mirror_remote_prefix")
    p.add_argument("--dig_dir", required=True)
    p.add_argument("--out_root", default=str(default_out_root()))
    p.add_argument("--overwrite", action="store_true")
    return p


def run_command(command: list[str], env=None) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def dir_nonempty(path: Path) -> bool:
    return path.exists() and path.is_dir() and any(path.iterdir())


def model_requires_gtf(row: dict[str, str]) -> bool:
    return str(row.get("require_gtf", "")).strip().lower() in {"true", "1", "yes"}


def require_existing_file(path_text: str, label: str) -> Path:
    path = relative_or_absolute_path(path_text)
    if not path.exists() or not path.is_file():
        raise SystemExit(f"Missing {label}: {path}")
    return path


def run_assemble(*, python_bin, dig_dir, counts_dir, sample_sheet, out_dir, keep_sample_types, keep_projects):
    """Invoke the DIG rnaseq_counts_assemble workflow; return (counts_tsv, sample_metadata_tsv, graph)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy(); env["PYTHONPATH"] = str(dig_dir / "src")
    cmd = [python_bin, "-m", "geneset_extractors.cli", "workflows", "rnaseq_counts_assemble",
           "--counts_dir", str(counts_dir), "--sample_sheet_tsv", str(sample_sheet),
           "--keep_sample_types", keep_sample_types, "--out_dir", str(out_dir),
           "--organism", "human", "--genome_build", "hg38"]
    if keep_projects:
        cmd += ["--keep_projects", keep_projects]
    run_command(cmd, env=env)
    return (out_dir / "counts.tsv", out_dir / "sample_metadata.tsv", out_dir / "counts_assemble.provenance_graph.json")


def main() -> int:
    args = build_parser().parse_args()
    model_rows = load_model_rows(Path(args.model_list))
    tumor_rows = load_tumor_type_rows(Path(args.tumor_type_list))
    selected_models = resolve_requested_ids(csv_text=args.models, file_path=args.models_file, rows=model_rows, key_field="model_id")
    selected_tumor_types = resolve_requested_ids(csv_text=args.tumor_types, file_path=args.tumor_types_file, rows=tumor_rows, key_field="tumor_type_id")
    tumor_by_id = row_map(tumor_rows, "tumor_type_id")
    model_by_id = row_map(model_rows, "model_id")

    out_root = Path(args.out_root).resolve()
    outputs_root = out_root / "genesets"
    assemble_root = out_root / "assemble"
    src_root = repo_root() / "geneset-extractor-dev" / "NCI_GDC_TCGA_RNAseq" / "src"

    counts_dir = require_existing_file(args.counts_dir, "counts dir") if Path(relative_or_absolute_path(args.counts_dir)).is_file() else relative_or_absolute_path(args.counts_dir)
    if not counts_dir.is_dir():
        raise SystemExit(f"--counts_dir must be a directory of GDC per-sample files: {counts_dir}")
    sample_sheet = require_existing_file(args.sample_sheet_tsv, "sample sheet")
    dig_dir = relative_or_absolute_path(args.dig_dir).resolve()
    if not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    tr_models = [m for m in selected_models if model_group_for(m) == "tumor_vs_rest"]
    tn_models = [m for m in selected_models if model_group_for(m) == "tumor_vs_normal"]
    runner_for = {"tumor_vs_rest": "run_tumor_vs_rest_model.py", "tumor_vs_normal": "run_tumor_vs_normal_model.py"}

    model_list_gtf_required = [str(r["model_id"]).strip() for r in model_rows if model_requires_gtf(r)]
    resolved_gtf = require_existing_file(args.gtf, "GTF") if args.gtf else None
    if model_list_gtf_required and resolved_gtf is None:
        raise SystemExit("model_list has models requiring --gtf but none provided: " + ", ".join(model_list_gtf_required))
    model_manifest = require_existing_file(args.model_manifest, "model manifest")

    def has_normal(row):
        return str(row.get("has_solid_tissue_normal", "")).strip().lower() in {"true", "1", "yes"}

    # tumor_vs_rest: assemble the pan-cancer Primary Tumor matrix ONCE (shared).
    tr_inputs = None
    if tr_models:
        tr_inputs = run_assemble(python_bin=args.python_bin, dig_dir=dig_dir, counts_dir=counts_dir,
                                 sample_sheet=sample_sheet, out_dir=assemble_root / "tumor_vs_rest",
                                 keep_sample_types="Primary Tumor", keep_projects="")

    def dispatch(model_id, tumor_type_id, row, counts_tsv, sample_metadata_tsv, upstream_graph):
        models_root = outputs_root / tumor_type_id / "models"
        if args.overwrite and (models_root / model_id).exists():
            shutil.rmtree(models_root / model_id)
        family = model_group_for(model_id)
        cmd = [str(Path(args.python_bin).resolve()), str(src_root / runner_for[family]),
               "--model_id", model_id, "--tumor_type_id", tumor_type_id,
               "--tumor_type_label", str(row.get("tumor_type_label", "")).strip(),
               "--project_id", str(row.get("project_id", "")).strip(),
               "--counts_tsv", str(counts_tsv), "--sample_metadata_tsv", str(sample_metadata_tsv),
               "--upstream_provenance_graph_json", str(upstream_graph),
               "--run_root", str(models_root), "--python_bin", str(Path(args.python_bin).resolve()),
               "--dig_dir", str(dig_dir), "--model_manifest", str(model_manifest)]
        if resolved_gtf is not None and model_requires_gtf(model_by_id[model_id]):
            cmd += ["--gtf", str(resolved_gtf)]
        if args.provenance_mirror_local_prefix:
            cmd += ["--provenance_mirror_local_prefix", args.provenance_mirror_local_prefix]
        if args.provenance_mirror_remote_prefix:
            cmd += ["--provenance_mirror_remote_prefix", args.provenance_mirror_remote_prefix]
        run_command(cmd)

    for tumor_type_id in selected_tumor_types:
        row = tumor_by_id[tumor_type_id]
        # tumor_vs_rest models: shared pan-cancer PT assemble
        for model_id in tr_models:
            dispatch(model_id, tumor_type_id, row, tr_inputs[0], tr_inputs[1], tr_inputs[2])
        # tumor_vs_normal models: per-project PT+STN assemble (only if normals exist)
        if tn_models:
            if not has_normal(row):
                for m in tn_models:
                    print(f"  skip {tumor_type_id}/{m}: no matched solid tissue normal", flush=True)
                continue
            proj = str(row.get("project_id", "")).strip()
            tn_inputs = run_assemble(python_bin=args.python_bin, dig_dir=dig_dir, counts_dir=counts_dir,
                                     sample_sheet=sample_sheet, out_dir=assemble_root / tumor_type_id,
                                     keep_sample_types="Primary Tumor,Solid Tissue Normal", keep_projects=proj)
            for model_id in tn_models:
                dispatch(model_id, tumor_type_id, row, tn_inputs[0], tn_inputs[1], tn_inputs[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
