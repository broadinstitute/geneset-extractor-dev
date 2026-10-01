#!/usr/bin/env python3
"""Thin wrapper for the per-signature LINCS L1000 chemical-perturbation model."""
from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path, env: dict[str, str], log: Path) -> None:
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("$ " + " ".join(shlex.quote(part) for part in cmd) + "\n")
        result = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        handle.write(result.stdout)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--signature_manifest_tsv", required=True)
    parser.add_argument("--cache_dir")
    parser.add_argument("--top_n", type=int, default=250)
    parser.add_argument("--python_bin", default=sys.executable)
    parser.add_argument("--write_model_only", action="store_true")
    args = parser.parse_args()
    dig_dir = Path(args.dig_dir).resolve()
    manifest = Path(args.signature_manifest_tsv).resolve()
    if not manifest.is_file():
        raise SystemExit(f"Missing LINCS_CP_SIGNATURE_MANIFEST_TSV: {manifest}")
    model_out = Path(args.run_root).resolve() / "CP1"
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "extractor"
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)
    sidecar = {
        "schema_version": "1",
        "library": "LINCS_L1000",
        "model_id": "CP1",
        "model_group": "cd_signature_export",
        "model_label": "l1000_cp",
        "workflow_name": "lincs_l1000_cp",
        "extractor_name": "signed_term_gene",
        "parameters": {"sigcom_library_id": "54198d6e-fe17-5ef8-91ac-02b425761653", "top_n": args.top_n, "ranking": "CD-coefficient descending; symbol ascending", "term_suffixes": [" up", " down"], "gmt_description": ""},
        "inputs": {"organism": "human", "genome_build": "hg38", "signature_manifest": str(manifest)},
    }
    (extractor_out / "geneset.model.json").write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.write_model_only:
        return 0
    env = {**os.environ, "PYTHONPATH": str(dig_dir / "src") + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
    py = str(Path(args.python_bin).resolve())
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else workflow_out / "source_cache"
    workflow_cmd = [py, "-m", "geneset_extractors.cli", "workflows", "lincs_l1000_cp", "--signature_manifest_tsv", str(manifest), "--out_dir", str(workflow_out), "--cache_dir", str(cache_dir), "--top_n", str(args.top_n)]
    extractor_cmd = [py, "-m", "geneset_extractors.cli", "convert", "signed_term_gene", "--table_tsv", str(workflow_out / "lincs_l1000_cp_signed_term_gene.tsv"), "--out_dir", str(extractor_out), "--organism", "human", "--genome_build", "hg38", "--term_prefix", "", "--signature_name", "LINCS L1000 chemical perturbation Characteristic Direction signatures", "--gmt_name_separator", " ", "--gmt_signed_labels", "up_down", "--gmt_description", "", "--gmt_preserve_names", "--gmt_min_genes", str(args.top_n), "--gmt_require_symbol", "true"]
    provenance_cmd = [py, "-m", "geneset_extractors.cli", "provenance", "build", str(extractor_out / "geneset.meta.json"), "--out", str(extractor_out / "geneset.provenance.json"), "--upstream_provenance_graph_json", str(workflow_out / "lincs_l1000_cp_signed_term_gene.provenance_graph.json")]
    commands = "\n".join(["# Commands For CP1", "", "```bash", f"cd {shlex.quote(str(dig_dir))}", f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {' '.join(shlex.quote(x) for x in workflow_cmd)}", f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {' '.join(shlex.quote(x) for x in extractor_cmd)}", f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {' '.join(shlex.quote(x) for x in provenance_cmd)}", "```,".rstrip(","), ""])
    (model_out / "commands.md").write_text(commands, encoding="utf-8")
    log = model_out / "run.log"
    for command in (workflow_cmd, extractor_cmd, provenance_cmd):
        _run(command, dig_dir, env, log)
    with (extractor_out / "run_manifest.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump({"model_id": "CP1", "workflow_dir": str(workflow_out), "extractor_dir": str(extractor_out)}, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
