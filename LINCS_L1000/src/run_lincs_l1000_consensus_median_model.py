#!/usr/bin/env python3
"""Thin wrapper for the LINCS L1000 consensus-median HZ3 model."""
from __future__ import annotations

import argparse
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
    parser.add_argument("--gctx_path", required=True)
    parser.add_argument("--min_signatures", type=int, default=10)
    parser.add_argument("--top_n", type=int, default=200)
    parser.add_argument("--partition_index", type=int, default=0)
    parser.add_argument("--partition_count", type=int, default=1)
    parser.add_argument("--python_bin", default=sys.executable)
    parser.add_argument("--write_model_only", action="store_true")
    args = parser.parse_args()
    dig_dir, gctx_path = Path(args.dig_dir).resolve(), Path(args.gctx_path).resolve()
    if not gctx_path.is_file():
        raise SystemExit(f"Missing LINCS_CP_COEFF_GCTX: {gctx_path}")
    model_out = Path(args.run_root).resolve() / "HZ3"
    workflow_out, extractor_out = model_out / "workflow", model_out / "extractor"
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)
    sidecar = {"schema_version": "1", "library": "LINCS_L1000", "model_id": "HZ3", "model_group": "consensus_median", "model_label": "consensus_median_signatures", "workflow_name": "lincs_l1000_consensus_median", "extractor_name": "lincs_l1000_cp_gmt", "parameters": {"public_gctx_url": "https://lincs-dcic.s3.amazonaws.com/LINCS-sigs-2021/gctx/cd-coefficient/cp_coeff_mat.gctx", "sigcom_library_uuid": "54198d6e-fe17-5ef8-91ac-02b425761653", "sigcom_metadata_api": "https://maayanlab.cloud/sigcom-lincs/metadata-api", "grouping_key": "pert_name", "consensus_operation": "coordinate_wise_median", "min_signatures": args.min_signatures, "top_n": args.top_n, "partition_index": args.partition_index, "partition_count": args.partition_count, "term_suffixes": [" up", " down"], "gmt_description": "LINCS L1000 chemical perturbation consensus median signature"}, "inputs": {"organism": "human", "genome_build": "hg38", "gctx_path": str(gctx_path), "required_datasets": ["0/DATA/0/matrix", "0/META/ROW/id", "0/META/COL/pert_name"]}}
    (extractor_out / "geneset.model.json").write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.write_model_only:
        return 0
    env = {**os.environ, "PYTHONPATH": str(dig_dir / "src") + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
    py = str(Path(args.python_bin).resolve())
    workflow_cmd = [py, "-m", "geneset_extractors.cli", "workflows", "lincs_l1000_consensus_median", "--gctx_path", str(gctx_path), "--out_dir", str(workflow_out), "--min_signatures", str(args.min_signatures), "--top_n", str(args.top_n), "--partition_index", str(args.partition_index), "--partition_count", str(args.partition_count)]
    finalizer_cmd = [py, "-m", "geneset_extractors.cli", "convert", "lincs_l1000_cp_gmt", "--gmt", str(workflow_out / "lincs_l1000_consensus_median.gmt"), "--out_dir", str(extractor_out), "--signature_name", "LINCS L1000 chemical perturbation consensus median signatures", "--gmt_description", "LINCS L1000 chemical perturbation consensus median signature", "--genes_per_set", str(args.top_n), "--upstream_provenance_graph_json", str(workflow_out / "lincs_l1000_consensus_median.provenance_graph.json")]
    provenance_cmd = [py, "-m", "geneset_extractors.cli", "provenance", "build", str(extractor_out / "geneset.meta.json"), "--out", str(extractor_out / "geneset.provenance.json"), "--upstream_provenance_graph_json", str(workflow_out / "lincs_l1000_consensus_median.provenance_graph.json")]
    commands = "\n".join(["# Commands For HZ3", "", "## Workflow", "", "```bash", f"cd {shlex.quote(str(dig_dir))}", f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {' '.join(shlex.quote(x) for x in workflow_cmd)}", "```", "", "## Streaming finalizer", "", "```bash", f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {' '.join(shlex.quote(x) for x in finalizer_cmd)}", "```", "", "## Provenance", "", "```bash", f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {' '.join(shlex.quote(x) for x in provenance_cmd)}", "```", ""])
    (model_out / "commands.md").write_text(commands, encoding="utf-8")
    log = model_out / "run.log"
    for command in (workflow_cmd, finalizer_cmd, provenance_cmd):
        _run(command, dig_dir, env, log)
    (extractor_out / "run_manifest.json").write_text(json.dumps({"model_id": "HZ3", "workflow_dir": str(workflow_out), "extractor_dir": str(extractor_out), "partition_index": args.partition_index, "partition_count": args.partition_count}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
