#!/usr/bin/env python3
"""Materialize one IMPC HZ1 model directory and refresh its submission metadata."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return "sha256:" + h.hexdigest()

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--assertions", required=True, type=Path); p.add_argument("--symbol-mapping", required=True, type=Path); p.add_argument("--run-root", required=True, type=Path); p.add_argument("--dig-repo", required=True, type=Path); p.add_argument("--overwrite", action="store_true"); args = p.parse_args()
    root = Path(__file__).resolve().parents[1]; model = args.run_root.resolve() / "HZ1"; extractor = model / "extractor"
    if model.exists():
        if not args.overwrite: raise SystemExit(f"output exists: {model}; pass --overwrite")
        shutil.rmtree(model)
    command = [sys.executable, str(root / "src/build_impc_hz1.py"), "--assertions", str(args.assertions.resolve()), "--symbol-mapping", str(args.symbol_mapping.resolve()), "--out-gmt", str(extractor / "genesets.gmt"), "--diagnostics", str(extractor / "reconstruction_diagnostics.json")]
    print("$ " + " ".join(command), flush=True); subprocess.run(command, check=True)
    diag = json.loads((extractor / "reconstruction_diagnostics.json").read_text())
    geneset_id = "impc_hz1_" + hashlib.sha256((digest(args.assertions) + digest(args.symbol_mapping)).encode()).hexdigest()[:16]
    metadata = {"converter": {"name": "impc_hz1", "version": "1"}, "geneset_id": geneset_id, "provenance": {"focus_node_id": geneset_id}, "gene_set": {"id": geneset_id, "name": "IMPC_HZ1_Mouse_Phenotypes", "description": "IMPC Data Release 18 direct genotype-phenotype assertions normalized with Harmonizome mappingFile_2017.", "organism": "human", "genome_build": "hg38", "assay": "mouse_knockout_phenotype", "data_type": "phenotype_association", "n_genes": diag["unique_genes_retained"]}, "input": {"organism": "human", "genome_build": "hg38", "files": [{"role": "impc_dr18_assertions", "path": str(args.assertions.resolve()), "sha256": digest(args.assertions)}, {"role": "harmonizome_mappingfile_2017", "path": str(args.symbol_mapping.resolve()), "sha256": digest(args.symbol_mapping)}]}, "output": {"files": [{"path": "genesets.gmt", "role": "gmt_library"}, {"path": "reconstruction_diagnostics.json", "role": "reconstruction_diagnostics"}, {"path": "geneset.meta.json", "role": "metadata_json"}]}, "gmt": {"path": "genesets.gmt", "written": True, "min_genes": 5, "prefer_symbol": True}, "parameters": {"model_id": "HZ1", "algorithm": "direct assertions; case-normalized Harmonizome 2017 symbol mapping; deduplicate term-gene memberships; min_genes=5"}}
    extractor.mkdir(parents=True, exist_ok=True); (extractor / "geneset.meta.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    sidecar = {"schema_version": "1", "library": "IMPC", "model_id": "HZ1", "model_group": "HZ", "model_label": "historical Harmonizome reconstruction", "workflow_name": "impc_dr18_direct_assertions", "extractor_name": "impc_hz1", "parameters": {"min_genes": 5, "mapping": "Harmonizome mappingFile_2017"}, "inputs": {"organism": "human", "genome_build": "hg38", "impc_release": "18.0"}, "naming": {"gene_set_pattern": "<Mouse Phenotype term> (MP:identifier)"}}
    (extractor / "geneset.model.json").write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n")
    refresh = ["bash", str(root.parent / "run/refresh_model_metadata_and_provenance.sh"), "--model_id", "HZ1", "--model_dir", str(model), "--description_template_tsv", str(root / "config/model_description_templates.tsv"), "--python_bin", sys.executable]
    print("$ " + " ".join(refresh), flush=True); subprocess.run(refresh, check=True, env={**os.environ, "DIG_DIR": str(args.dig_repo.resolve())})
    return 0
if __name__ == "__main__": raise SystemExit(main())
