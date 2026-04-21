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


LOGGER = logging.getLogger("run_eaggl_gene_list_batch_v1")

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

NO_ENRICHMENT_TEXT = "No gene sets passed the standalone gene-list enrichment filter"


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


def format_pretty_example_command(cmd: list[str]) -> str:
    repo_root = Path.cwd().resolve()

    def _render_token(token: str) -> str:
        try:
            token_path = Path(token)
            if token_path.is_absolute():
                resolved = token_path.resolve()
                try:
                    return shlex.quote(str(resolved.relative_to(repo_root)))
                except ValueError:
                    return shlex.quote(str(token))
        except Exception:
            pass
        return shlex.quote(str(token))

    if not cmd:
        return ""

    first_option_index = next((index for index, token in enumerate(cmd) if token.startswith("--")), len(cmd))
    head_tokens = cmd[:first_option_index]
    tail_tokens = cmd[first_option_index:]
    lines: list[str] = []

    head_line = " ".join(_render_token(token) for token in head_tokens)
    if tail_tokens:
        lines.append(f"{head_line} \\")
    else:
        lines.append(head_line)

    index = 0
    while index < len(tail_tokens):
        token = tail_tokens[index]
        if token.startswith("--"):
            if index + 1 < len(tail_tokens) and not tail_tokens[index + 1].startswith("--"):
                line = f"  {shlex.quote(token)} {_render_token(tail_tokens[index + 1])}"
                index += 2
            else:
                line = f"  {shlex.quote(token)}"
                index += 1
        else:
            line = f"  {_render_token(token)}"
            index += 1
        if index < len(tail_tokens):
            line += " \\"
        lines.append(line)
    return "\n".join(lines)


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


def classify_run(returncode: int, stdout_text: str, stderr_text: str, factors_out: Path) -> str:
    if returncode != 0:
        return "error"
    combined = "\n".join([stdout_text, stderr_text])
    if NO_ENRICHMENT_TEXT in combined:
        return "no_enrichment"
    if factors_out.exists() and factors_out.stat().st_size > 0:
        return "success"
    return "no_outputs"


def run_single_gene_list(
    *,
    pigean_repo: Path,
    python_executable: str,
    x_in_path: Path,
    set_name: str,
    genes: list[str],
    output_dir: Path,
) -> dict[str, object]:
    gene_list_path = output_dir / "input_gene_list.v1.txt"
    stdout_path = output_dir / "eaggl.stdout.v1.log"
    stderr_path = output_dir / "eaggl.stderr.v1.log"
    factors_out = output_dir / "factors.v1.tsv"
    gene_set_clusters_out = output_dir / "gene_set_clusters.v1.tsv"
    gene_clusters_out = output_dir / "gene_clusters.v1.tsv"
    params_out = output_dir / "params.v1.tsv"

    write_gene_list(gene_list_path, genes)
    cmd = [
        python_executable,
        "-m",
        "eaggl",
        "factor",
        "--X-in",
        str(x_in_path),
        "--gene-list-in",
        str(gene_list_path),
        "--gene-list-no-header",
        "--factors-out",
        str(factors_out),
        "--gene-set-clusters-out",
        str(gene_set_clusters_out),
        "--gene-clusters-out",
        str(gene_clusters_out),
        "--params-out",
        str(params_out),
    ]
    LOGGER.info("running EAGGL for set=%s n_genes=%d", set_name, len(genes))
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    proc = subprocess.run(
        cmd,
        cwd=pigean_repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    status = classify_run(proc.returncode, proc.stdout or "", proc.stderr or "", factors_out)
    LOGGER.info(
        "completed set=%s status=%s returncode=%d factors_exists=%s",
        set_name,
        status,
        proc.returncode,
        factors_out.exists(),
    )
    return {
        "set_name": set_name,
        "n_input_genes": len(genes),
        "status": status,
        "returncode": proc.returncode,
        "gene_list_path": str(gene_list_path),
        "factors_out": str(factors_out) if factors_out.exists() else "",
        "gene_set_clusters_out": str(gene_set_clusters_out) if gene_set_clusters_out.exists() else "",
        "gene_clusters_out": str(gene_clusters_out) if gene_clusters_out.exists() else "",
        "params_out": str(params_out) if params_out.exists() else "",
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)
    LOGGER.info("wrote table: %s shape=%s", path, df.shape)


def write_report(summary_df: pd.DataFrame, report_path: Path) -> None:
    counts = summary_df["status"].value_counts().to_dict()
    lines = [
        "# EAGGL Gene-list Batch v1",
        "",
        f"- total_sets: {int(summary_df.shape[0])}",
        f"- success: {int(counts.get('success', 0))}",
        f"- no_enrichment: {int(counts.get('no_enrichment', 0))}",
        f"- no_outputs: {int(counts.get('no_outputs', 0))}",
        f"- error: {int(counts.get('error', 0))}",
        "",
        "## By source",
        "",
    ]
    by_source = (
        summary_df.groupby(["source_name", "status"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for _, row in by_source.iterrows():
        parts = [f"{col}={int(row[col])}" for col in by_source.columns if col != "source_name"]
        lines.append(f"- {row['source_name']}: " + ", ".join(parts))
    lines.extend(["", "## Example successes", ""])
    success_df = summary_df[summary_df["status"] == "success"].head(20)
    for _, row in success_df.iterrows():
        lines.append(f"- {row['source_name']} | {row['set_name']} | n_input_genes={int(row['n_input_genes'])}")
    lines.extend(["", "## Example no_enrichment", ""])
    no_enrichment_df = summary_df[summary_df["status"] == "no_enrichment"].head(20)
    for _, row in no_enrichment_df.iterrows():
        lines.append(f"- {row['source_name']} | {row['set_name']} | n_input_genes={int(row['n_input_genes'])}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote report: %s", report_path)


def write_dry_run_outputs(command_rows: list[dict[str, object]], output_dir: Path) -> tuple[Path, Path]:
    example_rows: list[dict[str, object]] = []
    seen_steps: set[str] = set()
    for row in command_rows:
        step = str(row.get("step", ""))
        if step in seen_steps:
            continue
        seen_steps.add(step)
        example_rows.append(row)

    report_path = output_dir / "dry_run_examples.v2.md"
    lines = [
        "# EAGGL Gene-list Batch Dry Run v1",
        "",
        f"- total_examples: {len(example_rows)}",
        "",
        "This workflow runs one `eaggl factor` command per input gene set across the configured GMT sources.",
        "The example below shows the first such command in the order the script would run it.",
        "",
        "## Example Commands",
        "",
    ]
    for order_index, row in enumerate(example_rows, start=1):
        lines.append(f"### {order_index}. {row['step']}")
        lines.append("")
        lines.append("- explanation: Example set-level EAGGL factoring command. The real run repeats this same structure for every gene set in every source GMT.")
        lines.append(f"- workdir: `{row['workdir']}`")
        if "source_name" in row and pd.notna(row["source_name"]):
            lines.append(f"- example_source: `{row['source_name']}`")
        if "set_index" in row and pd.notna(row["set_index"]):
            lines.append(f"- example_set_index: `{int(row['set_index'])}`")
        if "set_name" in row and pd.notna(row["set_name"]):
            lines.append(f"- example_set_name: `{row['set_name']}`")
        if "n_input_genes" in row and pd.notna(row["n_input_genes"]):
            lines.append(f"- example_input_genes: `{int(row['n_input_genes'])}`")
        lines.append("")
        lines.append("```bash")
        lines.append(format_pretty_example_command(shlex.split(str(row["command"]))))
        lines.append("```")
        lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote dry-run report: %s", report_path)
    return report_path


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    output_dir = Path(args.output_dir).resolve()
    configure_logging(args.log_level, output_dir / "run_eaggl_gene_list_batch.v1.log")
    pigean_repo = Path(args.pigean_repo).resolve()
    x_in_path = pigean_repo / "bundles" / "model_small-2026.02.22" / "data" / "gene_set_list_msigdb_nohp.txt"
    if not pigean_repo.exists():
        raise FileNotFoundError(f"pigean repo not found: {pigean_repo}")
    if not x_in_path.exists():
        raise FileNotFoundError(f"EAGGL X input not found: {x_in_path}")
    LOGGER.info("using EAGGL X input: %s", x_in_path)

    output_dir.mkdir(parents=True, exist_ok=True)
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
            factors_out = set_output_dir / "factors.v1.tsv"
            gene_set_clusters_out = set_output_dir / "gene_set_clusters.v1.tsv"
            gene_clusters_out = set_output_dir / "gene_clusters.v1.tsv"
            params_out = set_output_dir / "params.v1.tsv"
            cmd = [
                args.python_executable,
                "-m",
                "eaggl",
                "factor",
                "--X-in",
                str(x_in_path),
                "--gene-list-in",
                str(gene_list_path),
                "--gene-list-no-header",
                "--factors-out",
                str(factors_out),
                "--gene-set-clusters-out",
                str(gene_set_clusters_out),
                "--gene-clusters-out",
                str(gene_clusters_out),
                "--params-out",
                str(params_out),
            ]
            if args.dry_run:
                append_command(
                    command_rows,
                    step="eaggl_factor",
                    workdir=pigean_repo,
                    cmd=cmd,
                    metadata={
                        "source_name": source_name,
                        "set_index": set_index,
                        "set_name": set_name,
                        "n_input_genes": len(genes),
                    },
                )
                continue
            result = run_single_gene_list(
                pigean_repo=pigean_repo,
                python_executable=args.python_executable,
                x_in_path=x_in_path,
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
    write_dataframe(summary_df, output_dir / "eaggl_run_summary.v1.tsv")
    write_report(summary_df, output_dir / "eaggl_run_summary.v1.md")


if __name__ == "__main__":
    main()
