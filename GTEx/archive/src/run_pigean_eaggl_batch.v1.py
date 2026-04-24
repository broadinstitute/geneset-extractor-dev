#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_pigean_eaggl_batch_v1")

SOURCE_SPECS = [
    {
        "source_name": "gtex_harmonizome_analysis_v1",
        "gmt_gz": "outputs/gtex_harmonizome_analysis_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz",
    },
    {
        "source_name": "gtex_no_harmonizome_analysis_v1",
        "gmt_gz": "outputs/gtex_no_harmonizome_analysis_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz",
    },
    {
        "source_name": "GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021",
        "gmt_gz": "GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz",
    },
]

PIGEAN_NO_ENRICHMENT_TEXT = "No gene sets passed the standalone gene-list enrichment filter"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--pigean_repo", required=True)
    parser.add_argument("--python_executable", default=sys.executable)
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--dry_run", action="store_true")
    return parser.parse_args()


def configure_logging(level: str, log_path: Path | None = None) -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(resolved_level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(resolved_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(resolved_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def append_command(
    command_rows: list[dict[str, object]],
    *,
    step: str,
    workdir: Path,
    cmd: list[str],
    metadata: dict[str, object] | None = None,
) -> None:
    command_one_line = shlex.join(cmd)
    command_multiline = " \\\n".join(shlex.quote(part) for part in cmd)
    row: dict[str, object] = {
        "step": step,
        "workdir": str(workdir),
        "command": command_one_line,
        "command_multiline": command_multiline,
    }
    if metadata:
        row.update(metadata)
    command_rows.append(row)


def safe_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return sanitized or "set"


def read_gmt_sets(path: Path) -> list[tuple[str, list[str]]]:
    sets: list[tuple[str, list[str]]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            set_name = parts[0]
            genes = [gene for gene in parts[1].split() if gene]
            sets.append((set_name, genes))
    return sets


def write_gene_list(path: Path, genes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(genes) + "\n", encoding="utf-8")


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)
    LOGGER.info("wrote table: %s shape=%s", path, df.shape)


def build_pigean_cmd(
    *,
    python_executable: str,
    x_in_path: Path,
    gene_map_path: Path,
    gene_loc_path: Path,
    gene_list_path: Path,
    gene_stats_out: Path,
    gene_set_stats_out: Path,
    params_out: Path,
    bundle_out: Path,
) -> list[str]:
    return [
        python_executable,
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
        str(gene_list_path),
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
        str(gene_stats_out),
        "--gene-set-stats-out",
        str(gene_set_stats_out),
        "--params-out",
        str(params_out),
        "--eaggl-bundle-out",
        str(bundle_out),
    ]


def build_eaggl_cmd(
    *,
    python_executable: str,
    bundle_in: Path,
    factors_out: Path,
    gene_set_clusters_out: Path,
    gene_clusters_out: Path,
    params_out: Path,
) -> list[str]:
    return [
        python_executable,
        "-m",
        "eaggl",
        "factor",
        "--eaggl-bundle-in",
        str(bundle_in),
        "--gene-set-stats-id-col",
        "Gene_Set",
        "--gene-set-stats-beta-tilde-col",
        "beta_tilde",
        "--gene-stats-id-col",
        "Gene",
        "--gene-stats-log-bf-col",
        "log_bf",
        "--factors-out",
        str(factors_out),
        "--gene-set-clusters-out",
        str(gene_set_clusters_out),
        "--gene-clusters-out",
        str(gene_clusters_out),
        "--params-out",
        str(params_out),
    ]


def run_logged_command(
    *,
    step_name: str,
    cmd: list[str],
    workdir: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[int, str, str]:
    LOGGER.info("running step=%s", step_name)
    proc = subprocess.run(
        cmd,
        cwd=workdir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    stdout_text = proc.stdout or ""
    stderr_text = proc.stderr or ""
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    LOGGER.info("completed step=%s returncode=%d", step_name, proc.returncode)
    return proc.returncode, stdout_text, stderr_text


def classify_pigean_status(returncode: int, stdout_text: str, stderr_text: str, bundle_out: Path) -> str:
    if returncode != 0:
        return "error"
    combined = "\n".join([stdout_text, stderr_text])
    if PIGEAN_NO_ENRICHMENT_TEXT in combined:
        return "no_enrichment"
    if bundle_out.exists() and bundle_out.stat().st_size > 0:
        return "success"
    return "no_outputs"


def classify_eaggl_status(returncode: int, stdout_text: str, stderr_text: str, factors_out: Path) -> str:
    if returncode != 0:
        return "error"
    combined = "\n".join([stdout_text, stderr_text])
    if PIGEAN_NO_ENRICHMENT_TEXT in combined:
        return "no_enrichment"
    if factors_out.exists() and factors_out.stat().st_size > 0:
        return "success"
    return "no_outputs"


def run_single_gene_list(
    *,
    pigean_repo: Path,
    python_executable: str,
    x_in_path: Path,
    gene_map_path: Path,
    gene_loc_path: Path,
    set_name: str,
    genes: list[str],
    output_dir: Path,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    gene_list_path = output_dir / "input_gene_list.v1.txt"
    write_gene_list(gene_list_path, genes)

    pigean_gene_stats = output_dir / "pigean.gene_stats.v1.tsv"
    pigean_gene_set_stats = output_dir / "pigean.gene_set_stats.v1.tsv"
    pigean_params = output_dir / "pigean.params.v1.tsv"
    pigean_bundle = output_dir / "pigean_to_eaggl.v1.tar.gz"
    pigean_stdout = output_dir / "pigean.stdout.v1.log"
    pigean_stderr = output_dir / "pigean.stderr.v1.log"

    eaggl_factors = output_dir / "eaggl.factors.v1.tsv"
    eaggl_gene_set_clusters = output_dir / "eaggl.gene_set_clusters.v1.tsv"
    eaggl_gene_clusters = output_dir / "eaggl.gene_clusters.v1.tsv"
    eaggl_params = output_dir / "eaggl.params.v1.tsv"
    eaggl_stdout = output_dir / "eaggl.stdout.v1.log"
    eaggl_stderr = output_dir / "eaggl.stderr.v1.log"

    env = os.environ.copy()
    src_root = str(pigean_repo / "src")
    env["PYTHONPATH"] = src_root if not env.get("PYTHONPATH") else src_root + os.pathsep + env["PYTHONPATH"]
    env["PYTHONHASHSEED"] = "0"

    pigean_cmd = build_pigean_cmd(
        python_executable=python_executable,
        x_in_path=x_in_path,
        gene_map_path=gene_map_path,
        gene_loc_path=gene_loc_path,
        gene_list_path=gene_list_path,
        gene_stats_out=pigean_gene_stats,
        gene_set_stats_out=pigean_gene_set_stats,
        params_out=pigean_params,
        bundle_out=pigean_bundle,
    )
    pigean_returncode, pigean_stdout_text, pigean_stderr_text = run_logged_command(
        step_name="pigean_beta_tildes",
        cmd=pigean_cmd,
        workdir=pigean_repo,
        env=env,
        stdout_path=pigean_stdout,
        stderr_path=pigean_stderr,
    )
    pigean_status = classify_pigean_status(
        pigean_returncode,
        pigean_stdout_text,
        pigean_stderr_text,
        pigean_bundle,
    )

    eaggl_cmd: list[str] = []
    eaggl_returncode: int | None = None
    eaggl_stdout_text = ""
    eaggl_stderr_text = ""
    eaggl_status = "skipped"

    if pigean_status == "success":
        eaggl_cmd = build_eaggl_cmd(
            python_executable=python_executable,
            bundle_in=pigean_bundle,
            factors_out=eaggl_factors,
            gene_set_clusters_out=eaggl_gene_set_clusters,
            gene_clusters_out=eaggl_gene_clusters,
            params_out=eaggl_params,
        )
        eaggl_returncode, eaggl_stdout_text, eaggl_stderr_text = run_logged_command(
            step_name="eaggl_factor",
            cmd=eaggl_cmd,
            workdir=pigean_repo,
            env=env,
            stdout_path=eaggl_stdout,
            stderr_path=eaggl_stderr,
        )
        eaggl_status = classify_eaggl_status(
            eaggl_returncode,
            eaggl_stdout_text,
            eaggl_stderr_text,
            eaggl_factors,
        )

    LOGGER.info(
        "completed set=%s pigean_status=%s eaggl_status=%s n_input_genes=%d",
        set_name,
        pigean_status,
        eaggl_status,
        len(genes),
    )
    return {
        "set_name": set_name,
        "n_input_genes": len(genes),
        "gene_list_path": str(gene_list_path),
        "pigean_status": pigean_status,
        "pigean_returncode": pigean_returncode,
        "pigean_gene_stats_out": str(pigean_gene_stats) if pigean_gene_stats.exists() else "",
        "pigean_gene_set_stats_out": str(pigean_gene_set_stats) if pigean_gene_set_stats.exists() else "",
        "pigean_params_out": str(pigean_params) if pigean_params.exists() else "",
        "pigean_bundle_out": str(pigean_bundle) if pigean_bundle.exists() else "",
        "pigean_stdout_log": str(pigean_stdout),
        "pigean_stderr_log": str(pigean_stderr),
        "eaggl_status": eaggl_status,
        "eaggl_returncode": "" if eaggl_returncode is None else eaggl_returncode,
        "eaggl_factors_out": str(eaggl_factors) if eaggl_factors.exists() else "",
        "eaggl_gene_set_clusters_out": str(eaggl_gene_set_clusters) if eaggl_gene_set_clusters.exists() else "",
        "eaggl_gene_clusters_out": str(eaggl_gene_clusters) if eaggl_gene_clusters.exists() else "",
        "eaggl_params_out": str(eaggl_params) if eaggl_params.exists() else "",
        "eaggl_stdout_log": str(eaggl_stdout) if eaggl_stdout.exists() else "",
        "eaggl_stderr_log": str(eaggl_stderr) if eaggl_stderr.exists() else "",
        "pigean_command": shlex.join(pigean_cmd),
        "eaggl_command": "" if not eaggl_cmd else shlex.join(eaggl_cmd),
    }


def write_report(summary_df: pd.DataFrame, report_path: Path) -> None:
    pigean_counts = summary_df["pigean_status"].value_counts().to_dict()
    eaggl_counts = summary_df["eaggl_status"].value_counts().to_dict()
    lines = [
        "# PIGEAN EAGGL Batch v1",
        "",
        f"- total_sets: {int(summary_df.shape[0])}",
        f"- pigean_success: {int(pigean_counts.get('success', 0))}",
        f"- pigean_no_enrichment: {int(pigean_counts.get('no_enrichment', 0))}",
        f"- pigean_no_outputs: {int(pigean_counts.get('no_outputs', 0))}",
        f"- pigean_error: {int(pigean_counts.get('error', 0))}",
        f"- eaggl_success: {int(eaggl_counts.get('success', 0))}",
        f"- eaggl_no_enrichment: {int(eaggl_counts.get('no_enrichment', 0))}",
        f"- eaggl_no_outputs: {int(eaggl_counts.get('no_outputs', 0))}",
        f"- eaggl_error: {int(eaggl_counts.get('error', 0))}",
        f"- eaggl_skipped: {int(eaggl_counts.get('skipped', 0))}",
        "",
        "## By source",
        "",
    ]
    by_source = (
        summary_df.groupby("source_name", dropna=False)
        .agg(
            n_sets=("set_name", "size"),
            pigean_success=("pigean_status", lambda s: int((s == "success").sum())),
            pigean_no_enrichment=("pigean_status", lambda s: int((s == "no_enrichment").sum())),
            pigean_no_outputs=("pigean_status", lambda s: int((s == "no_outputs").sum())),
            pigean_error=("pigean_status", lambda s: int((s == "error").sum())),
            eaggl_success=("eaggl_status", lambda s: int((s == "success").sum())),
            eaggl_no_enrichment=("eaggl_status", lambda s: int((s == "no_enrichment").sum())),
            eaggl_no_outputs=("eaggl_status", lambda s: int((s == "no_outputs").sum())),
            eaggl_error=("eaggl_status", lambda s: int((s == "error").sum())),
            eaggl_skipped=("eaggl_status", lambda s: int((s == "skipped").sum())),
        )
        .reset_index()
    )
    for _, row in by_source.iterrows():
        lines.append(
            "- {source_name}: n_sets={n_sets}, pigean_success={pigean_success}, "
            "pigean_no_enrichment={pigean_no_enrichment}, pigean_no_outputs={pigean_no_outputs}, "
            "pigean_error={pigean_error}, eaggl_success={eaggl_success}, "
            "eaggl_no_enrichment={eaggl_no_enrichment}, eaggl_no_outputs={eaggl_no_outputs}, "
            "eaggl_error={eaggl_error}, eaggl_skipped={eaggl_skipped}".format(**row.to_dict())
        )
    lines.extend(["", "## Example EAGGL successes", ""])
    success_df = summary_df[summary_df["eaggl_status"] == "success"].head(20)
    for _, row in success_df.iterrows():
        lines.append(f"- {row['source_name']} | {row['set_name']} | n_input_genes={int(row['n_input_genes'])}")
    lines.extend(["", "## Example skipped after PIGEAN", ""])
    skipped_df = summary_df[summary_df["eaggl_status"] == "skipped"].head(20)
    for _, row in skipped_df.iterrows():
        lines.append(
            f"- {row['source_name']} | {row['set_name']} | n_input_genes={int(row['n_input_genes'])} | pigean_status={row['pigean_status']}"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote report: %s", report_path)


def write_dry_run_outputs(command_rows: list[dict[str, object]], output_dir: Path) -> tuple[Path, Path]:
    commands_df = pd.DataFrame(command_rows)
    if commands_df.empty:
        commands_df = pd.DataFrame(columns=["step", "workdir", "command", "command_multiline"])
    commands_path = output_dir / "dry_run_commands.v1.tsv"
    write_dataframe(commands_df, commands_path)

    report_path = output_dir / "dry_run_commands.v1.md"
    lines = [
        "# PIGEAN EAGGL Batch Dry Run v1",
        "",
        f"- total_commands: {int(commands_df.shape[0])}",
        "",
        "These are the exact external commands the script would run.",
        "",
        "## Commands",
        "",
    ]
    for _, row in commands_df.iterrows():
        lines.append(f"### {row['step']}")
        lines.append("")
        lines.append(f"- workdir: `{row['workdir']}`")
        if "source_name" in row and pd.notna(row["source_name"]):
            lines.append(f"- source_name: `{row['source_name']}`")
        if "set_index" in row and pd.notna(row["set_index"]):
            lines.append(f"- set_index: `{int(row['set_index'])}`")
        if "set_name" in row and pd.notna(row["set_name"]):
            lines.append(f"- set_name: `{row['set_name']}`")
        if "n_input_genes" in row and pd.notna(row["n_input_genes"]):
            lines.append(f"- n_input_genes: `{int(row['n_input_genes'])}`")
        lines.append("")
        lines.append("```bash")
        lines.append(str(row["command_multiline"]))
        lines.append("```")
        lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote dry-run report: %s", report_path)
    return commands_path, report_path


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_pigean_eaggl_batch.v1.log")

    pigean_repo = Path(args.pigean_repo).resolve()
    bundle_data_dir = pigean_repo / "bundles" / "model_small-2026.02.22" / "data"
    x_in_path = bundle_data_dir / "gene_set_list_msigdb_nohp.txt"
    gene_map_path = bundle_data_dir / "portal_gencode.gene.map"
    gene_loc_path = bundle_data_dir / "NCBI37.3.plink.gene.loc"
    required_paths = [x_in_path, gene_map_path, gene_loc_path]
    if not pigean_repo.exists():
        raise FileNotFoundError(f"pigean repo not found: {pigean_repo}")
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        raise FileNotFoundError("missing bundled PIGEAN inputs: " + ", ".join(missing_paths))
    LOGGER.info("using bundled inputs: x_in=%s gene_map=%s gene_loc=%s", x_in_path, gene_map_path, gene_loc_path)

    source_manifest_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    command_rows: list[dict[str, object]] = []

    for source_spec in SOURCE_SPECS:
        source_name = str(source_spec["source_name"])
        gmt_gz_path = (repo_root / str(source_spec["gmt_gz"])).resolve()
        if not gmt_gz_path.exists():
            raise FileNotFoundError(f"source GMT not found: {gmt_gz_path}")
        sets = read_gmt_sets(gmt_gz_path)
        LOGGER.info("loaded source=%s n_sets=%d", source_name, len(sets))
        source_manifest_rows.append(
            {
                "source_name": source_name,
                "gmt_gz_path": str(gmt_gz_path),
                "n_sets": len(sets),
            }
        )

        for set_index, (set_name, genes) in enumerate(sets, start=1):
            set_output_dir = output_dir / source_name / f"{set_index:04d}_{safe_name(set_name)}"
            gene_list_path = set_output_dir / "input_gene_list.v1.txt"
            pigean_cmd = build_pigean_cmd(
                python_executable=args.python_executable,
                x_in_path=x_in_path,
                gene_map_path=gene_map_path,
                gene_loc_path=gene_loc_path,
                gene_list_path=gene_list_path,
                gene_stats_out=set_output_dir / "pigean.gene_stats.v1.tsv",
                gene_set_stats_out=set_output_dir / "pigean.gene_set_stats.v1.tsv",
                params_out=set_output_dir / "pigean.params.v1.tsv",
                bundle_out=set_output_dir / "pigean_to_eaggl.v1.tar.gz",
            )
            eaggl_cmd = build_eaggl_cmd(
                python_executable=args.python_executable,
                bundle_in=set_output_dir / "pigean_to_eaggl.v1.tar.gz",
                factors_out=set_output_dir / "eaggl.factors.v1.tsv",
                gene_set_clusters_out=set_output_dir / "eaggl.gene_set_clusters.v1.tsv",
                gene_clusters_out=set_output_dir / "eaggl.gene_clusters.v1.tsv",
                params_out=set_output_dir / "eaggl.params.v1.tsv",
            )
            if args.dry_run:
                metadata = {
                    "source_name": source_name,
                    "set_index": set_index,
                    "set_name": set_name,
                    "n_input_genes": len(genes),
                }
                append_command(command_rows, step="pigean_beta_tildes", workdir=pigean_repo, cmd=pigean_cmd, metadata=metadata)
                append_command(command_rows, step="eaggl_factor", workdir=pigean_repo, cmd=eaggl_cmd, metadata=metadata)
                continue

            result = run_single_gene_list(
                pigean_repo=pigean_repo,
                python_executable=args.python_executable,
                x_in_path=x_in_path,
                gene_map_path=gene_map_path,
                gene_loc_path=gene_loc_path,
                set_name=set_name,
                genes=genes,
                output_dir=set_output_dir,
            )
            result["source_name"] = source_name
            result["set_index"] = set_index
            result["set_output_dir"] = str(set_output_dir)
            summary_rows.append(result)

    source_manifest_df = pd.DataFrame(source_manifest_rows).sort_values("source_name")
    write_dataframe(source_manifest_df, output_dir / "source_manifest.v1.tsv")
    if args.dry_run:
        write_dry_run_outputs(command_rows, output_dir)
        return

    summary_df = pd.DataFrame(summary_rows).sort_values(["source_name", "set_index"])
    write_dataframe(summary_df, output_dir / "pigean_eaggl_run_summary.v1.tsv")
    write_report(summary_df, output_dir / "pigean_eaggl_run_summary.v1.md")


if __name__ == "__main__":
    main()
