#!/usr/bin/env python3
"""Run one scRNA cNMF (dataset, model) pair as a wrapper around DIG workflows and rna_sc_programs.

Pipeline stages:
  1. geneset-extractors workflows scrna_cnmf_prepare  -- data prep + script generation
  2. bash run_cnmf.sh                                 -- cNMF CLI: prepare/factorize/combine/k_plot
  3. bash run_cnmf_consensus_auto_k.sh                -- cnmf_select_k + cnmf consensus
  4. bash run_geneset_extractors_from_cnmf.sh         -- rna_sc_programs extractor
  5. copy extractor outputs to standard extractor/    -- standard layout
  6. write geneset.model.json                         -- model sidecar
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from glob import glob
from pathlib import Path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run one scRNA cNMF model as a wrapper around DIG workflows."
    )
    p.add_argument("--model_id", required=True, help="Model ID from model_list.tsv (e.g. GP1).")
    p.add_argument("--dataset_id", required=True, help="Dataset ID from dataset_list.tsv.")
    p.add_argument("--run_root", required=True,
                   help="Root under which genesets/<dataset>/models/<model_id>/ is created.")
    p.add_argument("--matrix_tsv", required=True, help="Local path to the cell-by-gene matrix TSV.")
    p.add_argument("--meta_tsv", required=True, help="Local path to the cell metadata TSV.")
    p.add_argument("--python_bin", default=sys.executable or "python3")
    p.add_argument("--dig_dir", required=True,
                   help="Root of dig-gene-set-extractors checkout (contains src/).")
    p.add_argument("--model_manifest", help="Path to model_manifest.tsv. Default: same dir as this script.")
    p.add_argument("--dataset_list", help="Path to dataset_list.tsv. Default: same dir as this script.")
    p.add_argument("--provenance_mirror_local_prefix")
    p.add_argument("--provenance_mirror_remote_prefix")
    p.add_argument("--local_input_source_map_tsv")
    p.add_argument("--write_model_only", action="store_true",
                   help="Only write geneset.model.json; skip all workflow steps.")
    p.add_argument("--write_commands_only", action="store_true",
                   help="Only write commands.md; skip execution.")
    p.add_argument("--overwrite", action="store_true",
                   help="Re-run even if extractor/ already exists.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------

def _load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def load_model_settings(manifest_path: Path, model_id: str) -> dict[str, str]:
    rows = _load_tsv(manifest_path)
    for row in rows:
        if row.get("model_id", "").strip() == model_id:
            return {k: v for k, v in row.items()}
    raise SystemExit(f"Model ID '{model_id}' not found in {manifest_path}")


def load_dataset_settings(dataset_path: Path, dataset_id: str) -> dict[str, str]:
    rows = _load_tsv(dataset_path)
    for row in rows:
        if row.get("dataset_id", "").strip() == dataset_id:
            return {k: v for k, v in row.items()}
    raise SystemExit(f"Dataset ID '{dataset_id}' not found in {dataset_path}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def default_manifest_path() -> Path:
    return _CONFIG_DIR / "model_manifest.tsv"


def default_dataset_list_path() -> Path:
    return _CONFIG_DIR / "dataset_list.tsv"


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text.rstrip("\n") + "\n")


def manifest_value(settings: dict[str, str], key: str, default: str) -> str:
    v = str(settings.get(key, "")).strip()
    return default if (not v or v == "NA") else v


def require_existing_file(path_text: str, label: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_file():
        raise SystemExit(f"Expected {label} to be a file: {path}")
    return path


def run_command(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
) -> None:
    log_line(log_path, f"$ {shell_join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.stdout:
        log_line(log_path, proc.stdout.rstrip("\n"))
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)


# ---------------------------------------------------------------------------
# geneset.model.json
# ---------------------------------------------------------------------------

def write_model_sidecar(
    *,
    path: Path,
    model_id: str,
    dataset_id: str,
    model_settings: dict[str, str],
    dataset_settings: dict[str, str],
) -> None:
    payload = {
        "schema_version": "1",
        "library": "scRNA_cNMF",
        "model_id": model_id,
        "dataset_id": dataset_id,
        "model_group": "cnmf_programs",
        "model_label": "standard_top_program",
        "workflow_name": "scrna_cnmf_prepare",
        "extractor_name": "rna_sc_programs",
        "parameters": {
            "cnmf_k_list": manifest_value(model_settings, "workflow_cnmf_k_list", "auto"),
            "cnmf_k": manifest_value(model_settings, "workflow_cnmf_k", "auto"),
            "cnmf_n_iter": manifest_value(model_settings, "workflow_cnmf_n_iter", "100"),
            "cnmf_numgenes": manifest_value(model_settings, "workflow_cnmf_numgenes", "2000"),
            "cnmf_export_kind": manifest_value(model_settings, "workflow_cnmf_export_kind", "score"),
            "cnmf_select_strategy": manifest_value(model_settings, "workflow_cnmf_select_strategy", "largest_stable"),
            "top_k": manifest_value(model_settings, "workflow_top_k", "100"),
            "min_genes": manifest_value(model_settings, "workflow_min_genes", "5"),
            "max_cells_total": manifest_value(model_settings, "workflow_max_cells_total", "20000"),
            "seed": manifest_value(model_settings, "workflow_seed", "1"),
        },
        "inputs": {
            "organism": dataset_settings.get("organism", "human"),
            "genome_build": dataset_settings.get("genome_build", "hg38"),
            "cell_id_column": dataset_settings.get("cell_id_column", ""),
            "cell_type_column": dataset_settings.get("cell_type_column", ""),
            "donor_column": dataset_settings.get("donor_column", ""),
            "value_type": dataset_settings.get("value_type", "counts"),
            "funding": dataset_settings.get("funding", ""),
            "access": dataset_settings.get("access", ""),
            "matrix_url": dataset_settings.get("matrix_url", ""),
            "meta_url": dataset_settings.get("meta_url", ""),
            "dataset_label": dataset_settings.get("dataset_label", dataset_id),
            "dataset_source": dataset_settings.get("dataset_source", ""),
        },
        "naming": {
            "comparison_style": "cnmf_program",
            "dataset_label": dataset_settings.get("dataset_label", dataset_id),
            "gene_set_pattern": "scRNA_cNMF_{dataset_label}_Program<k>_up|dn",
            "direction_labels": {"pos": "up", "neg": "dn"},
        },
    }
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# commands.md
# ---------------------------------------------------------------------------

def write_commands_doc(
    *,
    model_out: Path,
    model_id: str,
    dataset_id: str,
    prepare_cmd: list[str],
    dig_dir: Path,
    subset_dir_rel: str,
) -> None:
    text = "\n".join([
        f"# Commands For {dataset_id} / {model_id}",
        "",
        "## Stage 1: scrna_cnmf_prepare (DIG workflow)",
        "",
        "Generates filtered counts and cNMF run scripts under `workflow/subsets/`.",
        "",
        "```bash",
        f"cd {shlex.quote(str(dig_dir))}",
        f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {shell_join(prepare_cmd)}",
        "```",
        "",
        "## Stage 2: cNMF factorize (cnmf CLI)",
        "",
        "Runs cNMF prepare / factorize / combine / k-selection-plot via generated script.",
        "",
        "```bash",
        f"cd {subset_dir_rel}",
        "bash run_cnmf.sh",
        "```",
        "",
        "## Stage 3: cNMF consensus (DIG cnmf_select_k + cnmf consensus)",
        "",
        "Selects K by stability and runs cnmf consensus via generated script.",
        "",
        "```bash",
        f"cd {subset_dir_rel}",
        "bash run_cnmf_consensus_auto_k.sh",
        "```",
        "",
        "## Stage 4: rna_sc_programs extractor (DIG convert)",
        "",
        "Converts gene spectra scores to standard genesets via generated script.",
        "",
        "```bash",
        f"cd {subset_dir_rel}",
        "bash run_geneset_extractors_from_cnmf.sh",
        "```",
        "",
        "## Notes",
        "",
        "- Extractor outputs are copied to `extractor/` after stage 4.",
        "- `geneset.model.json` is written as the final step.",
        "- Refresh: run `refresh_model_metadata_and_provenance.sh` to patch descriptions and rewrite provenance.",
        "",
    ])
    write_text(model_out / "commands.md", text)


# ---------------------------------------------------------------------------
# build_prepare_cmd
# ---------------------------------------------------------------------------

def build_prepare_cmd(
    *,
    python_bin: str,
    dig_dir: Path,
    matrix_tsv: Path,
    meta_tsv: Path,
    model_settings: dict[str, str],
    dataset_settings: dict[str, str],
    workflow_out: Path,
) -> list[str]:
    organism = dataset_settings.get("organism", "human")
    genome_build = dataset_settings.get("genome_build", "hg38")
    cell_id_col = dataset_settings.get("cell_id_column", "cell_id")
    cell_type_col = dataset_settings.get("cell_type_column", "")
    donor_col = dataset_settings.get("donor_column", "")
    value_type = dataset_settings.get("value_type", "counts")

    cmd = [
        python_bin, "-m", "geneset_extractors.cli",
        "workflows", "scrna_cnmf_prepare",
        "--matrix_tsv", str(matrix_tsv),
        "--meta_tsv", str(meta_tsv),
        "--meta_cell_id_column", cell_id_col,
        "--matrix_value_type", value_type,
        "--organism", organism,
        "--genome_build", genome_build,
        "--split_by_cell_type", "false",
        "--max_cells_total", manifest_value(model_settings, "workflow_max_cells_total", "20000"),
        "--seed", manifest_value(model_settings, "workflow_seed", "1"),
        "--cnmf_k_list", manifest_value(model_settings, "workflow_cnmf_k_list", "auto"),
        "--cnmf_k", manifest_value(model_settings, "workflow_cnmf_k", "auto"),
        "--cnmf_n_iter", manifest_value(model_settings, "workflow_cnmf_n_iter", "100"),
        "--cnmf_numgenes", manifest_value(model_settings, "workflow_cnmf_numgenes", "2000"),
        "--cnmf_export_kind", manifest_value(model_settings, "workflow_cnmf_export_kind", "score"),
        "--cnmf_select_strategy", manifest_value(model_settings, "workflow_cnmf_select_strategy", "largest_stable"),
        "--out_dir", str(workflow_out),
    ]
    if cell_type_col:
        cmd.extend(["--cell_type_column", cell_type_col])
    if donor_col:
        cmd.extend(["--donor_column", donor_col])
    return cmd


# ---------------------------------------------------------------------------
# find extractor output
# ---------------------------------------------------------------------------

def find_extractor_src(subset_dir: Path, export_kind: str) -> Path:
    """Find the rna_sc_programs output dir inside cnmf_out/."""
    cnmf_out = subset_dir / "cnmf_out"
    pattern = str(cnmf_out / f"geneset_extractors_programs_k_*_{export_kind}")
    matches = sorted(glob(pattern))
    if not matches:
        # Also try without export_kind suffix (older DIG versions)
        matches = sorted(glob(str(cnmf_out / "geneset_extractors_programs_k_*")))
    if not matches:
        raise SystemExit(
            f"No rna_sc_programs output found matching "
            f"geneset_extractors_programs_k_*_{export_kind} under {cnmf_out}"
        )
    if len(matches) > 1:
        print(f"warning: multiple extractor output dirs found; using most recent: {matches[-1]}", file=sys.stderr)
    return Path(matches[-1])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    manifest_path = Path(args.model_manifest) if args.model_manifest else default_manifest_path()
    dataset_path = Path(args.dataset_list) if args.dataset_list else default_dataset_list_path()

    model_settings = load_model_settings(manifest_path, args.model_id)
    dataset_settings = load_dataset_settings(dataset_path, args.dataset_id)

    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.dataset_id / "models" / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "extractor"

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    # Always update model sidecar
    write_model_sidecar(
        path=extractor_out / "geneset.model.json",
        model_id=args.model_id,
        dataset_id=args.dataset_id,
        model_settings=model_settings,
        dataset_settings=dataset_settings,
    )
    if args.write_model_only:
        print(f"wrote geneset.model.json for {args.dataset_id}/{args.model_id}", file=sys.stderr)
        return 0

    matrix_tsv = require_existing_file(args.matrix_tsv, "matrix TSV")
    meta_tsv = require_existing_file(args.meta_tsv, "meta TSV")

    export_kind = manifest_value(model_settings, "workflow_cnmf_export_kind", "score")

    prepare_cmd = build_prepare_cmd(
        python_bin=args.python_bin,
        dig_dir=dig_dir,
        matrix_tsv=matrix_tsv,
        meta_tsv=meta_tsv,
        model_settings=model_settings,
        dataset_settings=dataset_settings,
        workflow_out=workflow_out,
    )

    # The single global subset is always named "all" when split_by_cell_type=false
    subset_dir = workflow_out / "subsets" / "all"

    write_commands_doc(
        model_out=model_out,
        model_id=args.model_id,
        dataset_id=args.dataset_id,
        prepare_cmd=prepare_cmd,
        dig_dir=dig_dir,
        subset_dir_rel=str(subset_dir),
    )
    if args.write_commands_only:
        return 0

    # Skip if already completed (unless --overwrite)
    if (extractor_out / "genesets.gmt").exists() and not args.overwrite:
        print(
            f"extractor output already exists for {args.dataset_id}/{args.model_id}; "
            "use --overwrite to re-run",
            file=sys.stderr,
        )
        return 0

    env = dict(os.environ)
    env["PYTHONPATH"] = str(dig_dir / "src")

    # Create a shim for `geneset-extractors` if not installed as a console script.
    # DIG-generated bash scripts call it as a bare command; gsx310 only has it as
    # `python -m geneset_extractors.cli`.
    _shim_dir = None
    if not shutil.which("geneset-extractors", path=env.get("PATH", "")):
        _shim_dir = Path(tempfile.mkdtemp(prefix="ge_shim_"))
        shim = _shim_dir / "geneset-extractors"
        shim.write_text(
            f"#!/usr/bin/env bash\nexec {args.python_bin} -m geneset_extractors.cli \"$@\"\n"
        )
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        env["PATH"] = f"{_shim_dir}:{env.get('PATH', '')}"

    model_log = model_out / "run.log"

    # Stage 1: scrna_cnmf_prepare
    run_command(prepare_cmd, cwd=dig_dir, env=env, log_path=model_log)

    # Stage 2: cNMF factorize
    if not subset_dir.is_dir():
        raise SystemExit(
            f"scrna_cnmf_prepare did not produce expected subset dir: {subset_dir}\n"
            "Check run.log for details."
        )
    run_command(["bash", "run_cnmf.sh"], cwd=subset_dir, env=env, log_path=model_log)

    # Stage 3: cNMF consensus (cnmf_select_k + cnmf consensus)
    run_command(
        ["bash", "run_cnmf_consensus_auto_k.sh"],
        cwd=subset_dir, env=env, log_path=model_log,
    )

    # Stage 4: rna_sc_programs extractor
    run_command(
        ["bash", "run_geneset_extractors_from_cnmf.sh"],
        cwd=subset_dir, env=env, log_path=model_log,
    )

    # Stage 5: copy extractor outputs to standard extractor/ location
    extractor_src = find_extractor_src(subset_dir, export_kind)
    for item in extractor_src.iterdir():
        dest = extractor_out / item.name
        if item.is_file():
            shutil.copy2(str(item), str(dest))
        elif item.is_dir():
            if dest.exists():
                shutil.rmtree(str(dest))
            shutil.copytree(str(item), str(dest))

    # geneset.model.json was already written above; re-write to ensure final state
    write_model_sidecar(
        path=extractor_out / "geneset.model.json",
        model_id=args.model_id,
        dataset_id=args.dataset_id,
        model_settings=model_settings,
        dataset_settings=dataset_settings,
    )

    print(
        f"[done] {args.dataset_id}/{args.model_id} "
        f"extractor={extractor_out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
