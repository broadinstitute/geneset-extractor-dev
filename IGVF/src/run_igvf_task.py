"""Select IGVF task configuration and dispatch registered DIG contracts."""
from __future__ import annotations
import argparse, csv, os, subprocess, sys
from pathlib import Path

def rows(path):
    with path.open(encoding="utf-8", newline="") as handle: return list(csv.DictReader(handle, delimiter="\t"))
def env_for(root):
    env=os.environ.copy(); source=str(root.parents[1] / "dig-gene-set-extractors" / "src")
    env["PYTHONPATH"]=source+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else ""); return env
def add(cmd, flag, value):
    if value: cmd.extend([flag,value])
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("mode",choices=("smoke","full")); parser.add_argument("--task-id"); parser.add_argument("--out-root",required=True); args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]; selected=[r for r in rows(root/"config/task_manifest.tsv") if r["enabled"].lower()=="true"]
    if args.mode=="smoke": selected=[r for r in selected if r["task_id"]=="smoke_igvf"]
    if args.task_id: selected=[r for r in selected if r["task_id"]==args.task_id]
    if not selected: raise ValueError("No enabled IGVF tasks matched selection.")
    overlay=root/"config/provenance_overlay.json"
    for r in selected:
        base=Path(args.out_root).resolve()/r["output_relative_path"]; inp=(root/r["input_relative_path"]).resolve()
        cmd=[sys.executable,"-m","geneset_extractors.cli","workflows","igvf_perturbseq","--expression_tsv",str(inp),"--source_input_id",r["source_input_id"],"--out_dir",str(base/"workflow"),"--input_mode",r["input_mode"],"--term_column",r["term_column"],"--gene_symbol_column",r["gene_symbol_column"],"--gmt_name","gene_set_library_crisp.gmt","--min_gmt_size","5","--provenance_overlay_json",str(overlay)]
        for flag,key in (("--gene_id_column","gene_id_column"),("--effect_column","effect_column"),("--ratio_column","ratio_column"),("--score_column","score_column"),("--pvalue_column","pvalue_column"),("--pvalue_max","pvalue_max"),("--top_k_per_direction","top_k_per_direction")): add(cmd,flag,r[key])
        subprocess.run(cmd,check=True,env=env_for(root))
        cmd=[sys.executable,"-m","geneset_extractors.cli","convert","signed_term_gene","--table_tsv",str(base/"workflow/igvf_perturbseq_signed_term_gene.tsv"),"--out_dir",str(base/"extractor"),"--organism","human","--genome_build","hg38","--term_column","term","--term_prefix","IGVF_Perturb_Seq","--gene_id_column","gene_id","--gene_symbol_column","gene_symbol","--score_column","score","--sign_column","sign","--gmt_name_separator","_","--gmt_signed_labels","up_dn","--gmt_min_genes","5","--gmt_require_symbol","true","--emit_small_gene_sets","false","--provenance_overlay_json",str(overlay)]
        subprocess.run(cmd,check=True,env=env_for(root))
        cmd=[sys.executable,"-m","geneset_extractors.cli","provenance","build",str(base/"extractor/geneset.meta.json"),"--out",str(base/"extractor/geneset.provenance.json"),"--upstream_provenance_graph_json",str(base/"workflow/igvf_perturbseq_signed_term_gene.provenance_graph.json"),"--provenance_overlay_json",str(overlay)]
        subprocess.run(cmd,check=True,env=env_for(root))
    return 0
if __name__=="__main__": raise SystemExit(main())
