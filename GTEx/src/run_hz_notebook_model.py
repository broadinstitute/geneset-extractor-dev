#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the HZ1 notebook-style GTEx aging-signature model by delegating "
            "the notebook-equivalent biology and dig-style outputs to "
            "dig-gene-set-extractors."
        )
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--tissue_id", required=True)
    parser.add_argument("--tissue_label", required=True)
    parser.add_argument("--expression_gct", required=True)
    parser.add_argument("--sample_attributes_tsv", required=True)
    parser.add_argument("--subject_phenotypes_tsv", required=True)
    parser.add_argument("--human_gene_info", required=True)
    parser.add_argument("--prepared_dir")
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--organism", default="human", choices=["human"])
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--write_commands_only", action="store_true")
    parser.add_argument("--reference_age_group", default="20-29")
    parser.add_argument("--comparison_age_groups", default="30-39,40-49,50-59,60-69,70-79")
    parser.add_argument("--random_state", type=int, default=1)
    parser.add_argument("--min_samples_per_group", type=int, default=3)
    parser.add_argument("--filter_mode", choices=["none", "tissue"], default="none")
    parser.add_argument("--chunksize", type=int, default=1000)
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def shell_join(cmd: list[str]) -> str:
    import shlex

    return " ".join(shlex.quote(part) for part in cmd)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> None:
    log_line(log_path, f"$ {shell_join(cmd)}")
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.stdout:
        log_line(log_path, completed.stdout.rstrip("\n"))
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)


def read_summary(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_provenance_rebuild_cmd(
    *,
    python_bin: str,
    metadata_json: Path,
    upstream_provenance_graph_json: Path,
    provenance_out: Path,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "provenance",
        "build",
        "--metadata_json",
        str(metadata_json),
        "--provenance_out",
        str(provenance_out),
        "--upstream_provenance_graph_json",
        str(upstream_provenance_graph_json),
    ]
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def write_model_commands(
    *,
    model_out: Path,
    model_id: str,
    workflow_cmd: list[str],
    extractor_cmd: list[str] | None,
    provenance_cmd: list[str] | None,
    invocation_cmd: list[str],
) -> None:
    lines = [
        f"# Commands For {model_id}",
        "",
        "## Invocation",
        "",
        "```bash",
        shell_join(invocation_cmd),
        "```",
        "",
        "## `dig` Workflow",
        "",
        "```bash",
        shell_join(workflow_cmd),
        "```",
        "",
    ]
    if extractor_cmd is not None:
        lines.extend(
            [
                "## `dig` Converter",
                "",
                "```bash",
                shell_join(extractor_cmd),
                "```",
                "",
            ]
        )
    if provenance_cmd is not None:
        lines.extend(
            [
                "## Provenance Rebuild",
                "",
                "```bash",
                shell_join(provenance_cmd),
                "```",
                "",
            ]
        )
    write_text(model_out / "commands.md", "\n".join(lines))


def write_empty_extractor_outputs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    write_text(path / "genesets.gmt", "")
    write_text(path / "manifest.tsv", "comparison\tgeneset_id\tlabel\tpath\tmeta_path\tprovenance_path\tfocus_node_id\n")


def require_existing_file(path_text: str, label: str) -> Path:
    path = Path(path_text).resolve()
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")
    if not path.is_file():
        raise SystemExit(f"Expected {label} to be a file: {path}")
    return path


def main() -> int:
    args = parse_args()
    repo = repo_root()
    model_out = Path(args.run_root).resolve() / args.model_id
    workflow_dir = model_out / "workflow"
    extractor_dir = model_out / "extractor"
    model_log = model_out / "run.log"
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists() or not dig_dir.is_dir():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    expression_gct = require_existing_file(args.expression_gct, "expression GCT")
    sample_attributes_tsv = require_existing_file(args.sample_attributes_tsv, "sample attributes TSV")
    subject_phenotypes_tsv = require_existing_file(args.subject_phenotypes_tsv, "subject phenotypes TSV")
    human_gene_info = require_existing_file(args.human_gene_info, "human_gene_info")

    model_out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    dig_pythonpath = str(dig_dir / "src")
    env["PYTHONPATH"] = dig_pythonpath if not existing_pythonpath else f"{dig_pythonpath}{os.pathsep}{existing_pythonpath}"

    workflow_cmd = [
        str(Path(args.python_bin).resolve()),
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "gtex_aging_signatures",
        "--expression_gct",
        str(expression_gct),
        "--sample_attributes_tsv",
        str(sample_attributes_tsv),
        "--subject_phenotypes_tsv",
        str(subject_phenotypes_tsv),
        "--human_gene_info",
        str(human_gene_info),
        "--out_dir",
        str(workflow_dir),
        "--organism",
        args.organism,
        "--genome_build",
        args.genome_build,
        "--rscript_bin",
        args.rscript_bin,
        "--tissue_column",
        "SMTS",
        "--tissue_value",
        args.tissue_label,
        "--tissue_label",
        args.tissue_label,
        "--tissue_id",
        args.tissue_id,
        "--reference_age_group",
        args.reference_age_group,
        "--comparison_age_groups",
        args.comparison_age_groups,
        "--random_state",
        str(args.random_state),
        "--min_samples_per_group",
        str(args.min_samples_per_group),
        "--filter_mode",
        args.filter_mode,
        "--chunksize",
        str(args.chunksize),
    ]
    if args.provenance_mirror_local_prefix:
        workflow_cmd.extend(["--provenance_mirror_local_prefix", args.provenance_mirror_local_prefix])
    if args.provenance_mirror_remote_prefix:
        workflow_cmd.extend(["--provenance_mirror_remote_prefix", args.provenance_mirror_remote_prefix])

    extractor_cmd = [
        str(Path(args.python_bin).resolve()),
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg_multi",
        "--deg_tsv",
        str(workflow_dir / "deg_long.tsv"),
        "--comparison_column",
        "comparison_id",
        "--comparison_name_column",
        "aging_signature",
        "--out_dir",
        str(extractor_dir),
        "--organism",
        args.organism,
        "--genome_build",
        args.genome_build,
        "--signature_name",
        "__comparison_only__",
        "--postprocess_mode",
        "legacy",
        "--score_mode",
        "auto",
        "--select",
        "none",
        "--normalize",
        "none",
        "--emit_full",
        "true",
        "--emit_gmt",
        "true",
        "--gmt_mode",
        "top_per_direction",
        "--gmt_top_n_per_direction",
        "250",
        "--gmt_sort_by",
        "logFC_abs",
        "--gmt_split_signed",
        "true",
        "--gmt_name_separator",
        "_",
        "--gmt_signed_labels",
        "up_dn",
        "--gmt_require_symbol",
        "true",
        "--gmt_min_genes",
        "5",
        "--gmt_max_genes",
        "500",
        "--emit_small_gene_sets",
        "false",
    ]
    if args.provenance_mirror_local_prefix:
        extractor_cmd.extend(["--provenance_mirror_local_prefix", args.provenance_mirror_local_prefix])
    if args.provenance_mirror_remote_prefix:
        extractor_cmd.extend(["--provenance_mirror_remote_prefix", args.provenance_mirror_remote_prefix])
    provenance_cmd = build_provenance_rebuild_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        metadata_json=extractor_dir / "geneset.meta.json",
        upstream_provenance_graph_json=workflow_dir / "deg_long.provenance_graph.json",
        provenance_out=extractor_dir / "geneset.provenance.json",
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )

    invocation_cmd = [
        str(repo / "geneset-extractor-dev" / "GTEx" / "run" / "build_genesets.sh"),
        "--tissues",
        args.tissue_id,
        "--models",
        args.model_id,
    ]
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        extractor_cmd=extractor_cmd,
        provenance_cmd=provenance_cmd,
        invocation_cmd=invocation_cmd,
    )
    if args.write_commands_only:
        return 0

    log_line(model_log, f"[run_hz_notebook_model] model_id={args.model_id}")
    log_line(model_log, f"[run_hz_notebook_model] tissue_id={args.tissue_id}")
    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)

    workflow_summary = read_summary(workflow_dir / "prepare_summary.json")
    if int(workflow_summary.get("n_comparisons_emitted", 0) or 0) <= 0:
        write_empty_extractor_outputs(extractor_dir)
        log_line(model_log, "[run_hz_notebook_model] no emitted comparisons; wrote empty extractor outputs")
        return 0

    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(provenance_cmd, cwd=dig_dir, env=env, log_path=model_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
