#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_pigean_eaggl_test_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--pigean_repo", required=True)
    parser.add_argument("--source_gmt_gz", required=True)
    parser.add_argument("--python_executable", default=sys.executable)
    parser.add_argument("--log_level", default="INFO")
    return parser.parse_args()


def configure_logging(level: str, log_path: Path) -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(resolved_level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(resolved_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)
    LOGGER.info("wrote table: %s shape=%s", path, df.shape)


def format_command_multiline(cmd: list[str]) -> str:
    return " \\\n".join(shlex.quote(part) for part in cmd)


def read_first_adipose_set(path: Path) -> tuple[str, list[str]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            set_name, genes_blob = line.rstrip("\n").split("\t", 1)
            if set_name.startswith("GTEx_AdiposeTissue_"):
                genes = [gene for gene in genes_blob.split() if gene]
                LOGGER.info("selected adipose set: %s n_genes=%d", set_name, len(genes))
                return set_name, genes
    raise ValueError(f"no adipose gene set found in {path}")


def run_command(
    *,
    step_name: str,
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> int:
    LOGGER.info("running step=%s cwd=%s", step_name, cwd)
    LOGGER.info("command:\n%s", format_command_multiline(cmd))
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    LOGGER.info("completed step=%s returncode=%d", step_name, proc.returncode)
    if proc.returncode != 0:
        raise RuntimeError(f"{step_name} failed with returncode={proc.returncode}; see {stderr_path}")
    return proc.returncode


def write_output_doc(output_dir: Path, set_name: str, selected_set_path: Path, run_summary_path: Path) -> Path:
    doc_path = output_dir / "pigean_eaggl_test.v1.md"
    lines = [
        "# PIGEAN EAGGL Test v1",
        "",
        f"- selected_set_name: `{set_name}`",
        f"- selected_set_tsv: `{selected_set_path}`",
        f"- run_summary_tsv: `{run_summary_path}`",
        "- source_gmt_choice: first Adipose tissue set from the no-harmonizome GTEx aging signature GMT",
        "- pigean_mode: `beta_tildes`",
        "- eaggl_mode: `factor` from `--eaggl-bundle-in`",
        "",
    ]
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote documentation: %s", doc_path)
    return doc_path


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    configure_logging(args.log_level, output_dir / "run_pigean_eaggl_test.v1.log")

    pigean_repo = Path(args.pigean_repo).resolve()
    source_gmt_gz = Path(args.source_gmt_gz).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pigean_repo.exists():
        raise FileNotFoundError(f"pigean repo not found: {pigean_repo}")
    if not source_gmt_gz.exists():
        raise FileNotFoundError(f"source GMT not found: {source_gmt_gz}")

    set_name, genes = read_first_adipose_set(source_gmt_gz)

    selected_set_path = output_dir / "selected_gene_set.v1.tsv"
    selected_genes_path = output_dir / "selected_gene_list.v1.txt"
    write_dataframe(
        pd.DataFrame(
            [{"set_name": set_name, "source_gmt_gz": str(source_gmt_gz), "n_genes": len(genes)}]
        ),
        selected_set_path,
    )
    selected_genes_path.write_text("\n".join(genes) + "\n", encoding="utf-8")
    LOGGER.info("wrote selected gene list: %s n_genes=%d", selected_genes_path, len(genes))

    bundle_data_dir = pigean_repo / "bundles" / "model_small-2026.02.22" / "data"
    x_in_path = bundle_data_dir / "gene_set_list_msigdb_nohp.txt"
    gene_map_path = bundle_data_dir / "portal_gencode.gene.map"
    gene_loc_path = bundle_data_dir / "NCBI37.3.plink.gene.loc"
    required_paths = [x_in_path, gene_map_path, gene_loc_path]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        raise FileNotFoundError("missing bundled PIGEAN inputs: " + ", ".join(missing_paths))

    pigean_out_dir = output_dir / "pigean.v1"
    eaggl_out_dir = output_dir / "eaggl.v1"
    pigean_out_dir.mkdir(parents=True, exist_ok=True)
    eaggl_out_dir.mkdir(parents=True, exist_ok=True)

    pigean_gene_stats = pigean_out_dir / "pigean.gene_stats.v1.tsv"
    pigean_gene_set_stats = pigean_out_dir / "pigean.gene_set_stats.v1.tsv"
    pigean_params = pigean_out_dir / "pigean.params.v1.tsv"
    pigean_bundle = pigean_out_dir / "pigean_to_eaggl.v1.tar.gz"

    env = os.environ.copy()
    src_root = str(pigean_repo / "src")
    env["PYTHONPATH"] = src_root if not env.get("PYTHONPATH") else src_root + os.pathsep + env["PYTHONPATH"]
    env["PYTHONHASHSEED"] = "0"

    pigean_cmd = [
        args.python_executable,
        "-m",
        "pigean",
        "beta_tildes",
        "--X-in",
        str(x_in_path),
        "--gene-map-in",
        str(gene_map_path),
        "--gene-loc-file",
        str(gene_loc_path),
        "--gene-list-in",
        str(selected_genes_path),
        "--gene-list-no-header",
        "--gene-list-all-in",
        str(gene_loc_path),
        "--gene-list-all-id-col",
        "6",
        "--gene-list-all-no-header",
        "--hide-opts",
        "--deterministic",
        "--min-gene-set-size",
        "1",
        "--filter-gene-set-p",
        "1",
        "--max-gene-set-read-p",
        "1",
        "--no-filter-negative",
        "--max-num-gene-sets-initial",
        "200",
        "--max-num-gene-sets-hyper",
        "200",
        "--max-num-gene-sets",
        "200",
        "--max-num-burn-in",
        "5",
        "--max-num-iter-betas",
        "20",
        "--min-num-iter-betas",
        "5",
        "--num-chains-betas",
        "2",
        "--gene-stats-out",
        str(pigean_gene_stats),
        "--gene-set-stats-out",
        str(pigean_gene_set_stats),
        "--params-out",
        str(pigean_params),
        "--eaggl-bundle-out",
        str(pigean_bundle),
    ]
    run_command(
        step_name="pigean_beta_tildes",
        cmd=pigean_cmd,
        cwd=pigean_repo,
        env=env,
        stdout_path=pigean_out_dir / "pigean.stdout.v1.log",
        stderr_path=pigean_out_dir / "pigean.stderr.v1.log",
    )

    eaggl_cmd = [
        args.python_executable,
        "-m",
        "eaggl",
        "factor",
        "--eaggl-bundle-in",
        str(pigean_bundle),
        "--factors-out",
        str(eaggl_out_dir / "factors.v1.tsv"),
        "--gene-set-clusters-out",
        str(eaggl_out_dir / "gene_set_clusters.v1.tsv"),
        "--gene-clusters-out",
        str(eaggl_out_dir / "gene_clusters.v1.tsv"),
        "--params-out",
        str(eaggl_out_dir / "params.v1.tsv"),
    ]
    run_command(
        step_name="eaggl_factor",
        cmd=eaggl_cmd,
        cwd=pigean_repo,
        env=env,
        stdout_path=eaggl_out_dir / "eaggl.stdout.v1.log",
        stderr_path=eaggl_out_dir / "eaggl.stderr.v1.log",
    )

    run_summary_path = output_dir / "run_summary.v1.tsv"
    write_dataframe(
        pd.DataFrame(
            [
                {
                    "step_name": "pigean_beta_tildes",
                    "workdir": str(pigean_repo),
                    "command": shlex.join(pigean_cmd),
                    "stdout_log": str(pigean_out_dir / "pigean.stdout.v1.log"),
                    "stderr_log": str(pigean_out_dir / "pigean.stderr.v1.log"),
                    "primary_output": str(pigean_bundle),
                },
                {
                    "step_name": "eaggl_factor",
                    "workdir": str(pigean_repo),
                    "command": shlex.join(eaggl_cmd),
                    "stdout_log": str(eaggl_out_dir / "eaggl.stdout.v1.log"),
                    "stderr_log": str(eaggl_out_dir / "eaggl.stderr.v1.log"),
                    "primary_output": str(eaggl_out_dir / "params.v1.tsv"),
                },
            ]
        ),
        run_summary_path,
    )
    write_output_doc(output_dir, set_name, selected_set_path, run_summary_path)


if __name__ == "__main__":
    main()
