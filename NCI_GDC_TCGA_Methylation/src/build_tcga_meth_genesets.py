#!/usr/bin/env python3
"""Master loop for NCI_GDC_TCGA_Methylation (true-input provenance).

Per normal-bearing tumor type, the DIG workflow `methylation_beta_assemble` builds the
project's Primary Tumor + Solid Tissue Normal beta matrix from the TRUE GDC inputs (per-sample
Methylation Beta Value files + sample sheet) and emits a provenance graph rooted at them.
The runner then chains that graph through methylation_diff_prepare -> methylation_cpg_diff ->
provenance build, so final provenance begins from the true inputs. Thin wrapper; DIG owns logic.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from meth_selection_io import (
    default_model_list_path, default_model_manifest_path, default_out_root,
    default_tumor_type_list_path, load_model_rows, load_tumor_type_rows,
    model_group_for, relative_or_absolute_path, repo_root, resolve_requested_ids, row_map,
)


def build_parser():
    p = argparse.ArgumentParser(description="Build TCGA methylation tumor-vs-normal gene sets (true-input provenance).")
    p.add_argument("--models", default="all"); p.add_argument("--models_file")
    p.add_argument("--tumor_types", default="all"); p.add_argument("--tumor_types_file")
    p.add_argument("--model_list", default=str(default_model_list_path()))
    p.add_argument("--tumor_type_list", default=str(default_tumor_type_list_path()))
    p.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    p.add_argument("--python_bin", default=sys.executable or "python3")
    p.add_argument("--beta_dir", required=True, help="Directory of GDC per-sample Methylation Beta Value *.txt (TRUE inputs).")
    p.add_argument("--sample_sheet_tsv", required=True, help="GDC sample sheet (TRUE input).")
    p.add_argument("--gtf", required=True); p.add_argument("--probe_manifest_tsv")
    p.add_argument("--dig_dir", required=True); p.add_argument("--out_root", default=str(default_out_root()))
    p.add_argument("--overwrite", action="store_true")
    return p


def run_command(c, env=None): print("$ "+" ".join(c), flush=True); subprocess.run(c, check=True, env=env)
def require_file(t,l):
    p=relative_or_absolute_path(t)
    if not p.exists() or not p.is_file(): raise SystemExit(f"Missing {l}: {p}")
    return p
def has_normal(row): return str(row.get("has_solid_tissue_normal","")).strip().lower() in {"true","1","yes"}


def run_assemble(*, python_bin, dig_dir, beta_dir, sample_sheet, out_dir, keep_projects):
    out_dir.mkdir(parents=True, exist_ok=True)
    env=os.environ.copy(); env["PYTHONPATH"]=str(dig_dir/"src")
    run_command([python_bin,"-m","geneset_extractors.cli","workflows","methylation_beta_assemble",
        "--beta_dir",str(beta_dir),"--sample_sheet_tsv",str(sample_sheet),
        "--keep_sample_types","Primary Tumor,Solid Tissue Normal","--keep_projects",keep_projects,
        "--out_dir",str(out_dir),"--organism","human","--genome_build","hg38"], env=env)
    return (out_dir/"beta_matrix.tsv", out_dir/"sample_metadata.tsv", out_dir/"beta_assemble.provenance_graph.json")


def main()->int:
    a=build_parser().parse_args()
    model_rows=load_model_rows(Path(a.model_list)); tumor_rows=load_tumor_type_rows(Path(a.tumor_type_list))
    sel_models=resolve_requested_ids(csv_text=a.models,file_path=a.models_file,rows=model_rows,key_field="model_id")
    sel_types=resolve_requested_ids(csv_text=a.tumor_types,file_path=a.tumor_types_file,rows=tumor_rows,key_field="tumor_type_id")
    tumor_by_id=row_map(tumor_rows,"tumor_type_id")
    out_root=Path(a.out_root).resolve(); outputs_root=out_root/"genesets"; assemble_root=out_root/"assemble"
    src_root=repo_root()/"geneset-extractor-dev"/"NCI_GDC_TCGA_Methylation"/"src"
    beta_dir=relative_or_absolute_path(a.beta_dir).resolve()
    if not beta_dir.is_dir(): raise SystemExit(f"--beta_dir must be a directory: {beta_dir}")
    sample_sheet=require_file(a.sample_sheet_tsv,"sample sheet"); gtf=require_file(a.gtf,"GTF")
    manifest=require_file(a.probe_manifest_tsv,"probe manifest") if a.probe_manifest_tsv else None
    dig_dir=relative_or_absolute_path(a.dig_dir).resolve()
    if not dig_dir.is_dir(): raise SystemExit(f"Missing dig dir: {dig_dir}")
    model_manifest=require_file(a.model_manifest,"model manifest")
    meth_models=[m for m in sel_models if model_group_for(m)=="methylation_diff"]
    for tt in sel_types:
        row=tumor_by_id[tt]
        if not has_normal(row):
            for m in meth_models: print(f"  skip {tt}/{m}: no matched solid tissue normal",flush=True)
            continue
        proj=str(row.get("project_id","")).strip(); label=str(row.get("tumor_type_label","")).strip()
        beta_m, sample_m, graph = run_assemble(python_bin=a.python_bin,dig_dir=dig_dir,beta_dir=beta_dir,
            sample_sheet=sample_sheet,out_dir=assemble_root/tt,keep_projects=proj)
        models_root=outputs_root/tt/"models"
        for m in meth_models:
            if a.overwrite and (models_root/m).exists(): shutil.rmtree(models_root/m)
            cmd=[str(Path(a.python_bin).resolve()), str(src_root/"run_methylation_diff_model.py"),
                "--model_id",m,"--tumor_type_id",tt,"--tumor_type_label",label,"--project_id",proj,
                "--beta_matrix_tsv",str(beta_m),"--sample_metadata_tsv",str(sample_m),
                "--upstream_provenance_graph_json",str(graph),"--gtf",str(gtf),
                "--run_root",str(models_root),"--python_bin",str(Path(a.python_bin).resolve()),
                "--dig_dir",str(dig_dir),"--model_manifest",str(model_manifest)]
            if manifest is not None: cmd+=["--probe_manifest_tsv",str(manifest)]
            run_command(cmd)
    return 0

if __name__=="__main__": raise SystemExit(main())
