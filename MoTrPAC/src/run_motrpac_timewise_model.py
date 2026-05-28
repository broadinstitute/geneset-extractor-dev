#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from motrpac_selection_io import default_model_manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one MoTrPAC timewise model and emit notebook-style signature outputs."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--tissue_id", required=True)
    parser.add_argument("--prepared_dir", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--organism", default="human", choices=["human", "mouse"])
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--write_commands_only", action="store_true")
    return parser.parse_args()


def load_model_settings(manifest_path: Path) -> dict[str, dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    settings: dict[str, dict[str, str]] = {}
    for row in rows:
        model_id = str(row.get("model_id", "")).strip()
        if model_id:
            settings[model_id] = {str(key): str(value) for key, value in row.items()}
    if not settings:
        raise SystemExit(f"No model settings found in {manifest_path}")
    return settings


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def resolve_rscript_bin(rscript_bin: str) -> str:
    resolved = shutil.which(rscript_bin) if not Path(rscript_bin).is_absolute() else rscript_bin
    if not resolved or not Path(resolved).exists():
        raise SystemExit(f"Rscript not found: {rscript_bin}")
    return resolved


def check_r_packages(rscript_bin: str) -> None:
    cmd = [
        rscript_bin,
        "--vanilla",
        "-e",
        "quit(status=if (requireNamespace('edgeR', quietly=TRUE) && requireNamespace('limma', quietly=TRUE)) 0 else 1)",
    ]
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            "R packages 'edgeR' and 'limma' are required for the MoTrPAC timewise workflow and were not found for "
            f"{rscript_bin}."
        )


def read_sample_metadata(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_workflow_script(
    *,
    script_path: Path,
    counts_tsv: Path,
    metadata_tsv: Path,
    workflow_dir: Path,
    min_samples_per_group: int,
) -> None:
    script = f'''suppressPackageStartupMessages({{
  library(edgeR)
  library(limma)
}})

counts <- read.delim("{counts_tsv}", check.names=FALSE)
meta <- read.delim("{metadata_tsv}", check.names=FALSE)
count_cols <- setdiff(colnames(counts), c("gene_id", "gene_symbol"))
count_mat <- as.matrix(counts[, count_cols, drop=FALSE])
storage.mode(count_mat) <- "numeric"
rownames(count_mat) <- counts$gene_id
gene_ids <- counts$gene_id
gene_symbols <- as.character(counts$gene_symbol)

meta$sample_id <- as.character(meta$sample_id)
meta$sex_label <- tolower(as.character(meta$sex_label))
meta$intervention <- factor(as.character(meta$intervention), levels=c("control", "training"))
meta$timepoint_label <- as.character(meta$timepoint_label)
meta$tissue_code_no <- tolower(as.character(meta$tissue_code_no))
meta$tissue_slug <- gsub("[^a-z0-9]+", "-", tolower(as.character(meta$tissue)))

dir.create(file.path("{workflow_dir}", "comparisons"), showWarnings=FALSE, recursive=TRUE)
all_results <- list()
summary_rows <- list()
strata <- unique(meta[, c("sex_label", "timepoint_label", "tissue_code_no", "tissue_slug"), drop=FALSE])

for (i in seq_len(nrow(strata))) {{
  sex_label <- as.character(strata$sex_label[i])
  timepoint_label <- as.character(strata$timepoint_label[i])
  tissue_code_no <- as.character(strata$tissue_code_no[i])
  tissue_slug <- as.character(strata$tissue_slug[i])
  comparison_id <- paste0(tissue_code_no, "-", tissue_slug, "_", sex_label, "_", timepoint_label)
  submeta <- meta[meta$sex_label == sex_label & meta$timepoint_label == timepoint_label, , drop=FALSE]
  n_control <- sum(submeta$intervention == "control")
  n_training <- sum(submeta$intervention == "training")
  summary_rows[[length(summary_rows) + 1]] <- data.frame(
    comparison_id=comparison_id,
    sex_label=sex_label,
    timepoint_label=timepoint_label,
    n_control=n_control,
    n_training=n_training,
    stringsAsFactors=FALSE
  )
  if (n_control < {min_samples_per_group} || n_training < {min_samples_per_group}) {{
    next
  }}
  subset_mat <- count_mat[, submeta$sample_id, drop=FALSE]
  y <- DGEList(counts=subset_mat)
  design <- model.matrix(~ intervention, data=submeta)
  keep_genes <- filterByExpr(y, design=design)
  y <- y[keep_genes, , keep.lib.sizes=FALSE]
  kept_gene_ids <- gene_ids[keep_genes]
  kept_gene_symbols <- gene_symbols[keep_genes]
  y <- calcNormFactors(y)
  v <- voom(y, design, plot=FALSE)
  fit <- lmFit(v, design)
  fit <- eBayes(fit)
  tt <- topTable(fit, coef="interventiontraining", number=Inf, sort.by="none")
  tt$comparison_id <- comparison_id
  tt$gene_id <- kept_gene_ids
  tt$gene_symbol <- kept_gene_symbols
  tt$group_a <- "training"
  tt$group_b <- "control"
  tt$stratum <- paste0("sex=", sex_label, ";timepoint=", timepoint_label)
  tt$backend <- "r_limma_voom_motrpac_timewise"
  tt$n_group_a <- n_training
  tt$n_group_b <- n_control
  tt$mean_expr <- tt$AveExpr
  tt$model_formula <- "intervention"
  keep_cols <- c("comparison_id", "gene_id", "gene_symbol", "logFC", "t", "P.Value", "adj.P.Val", "group_a", "group_b", "stratum", "backend", "n_group_a", "n_group_b", "mean_expr", "model_formula")
  tt <- tt[, keep_cols, drop=FALSE]
  colnames(tt)[colnames(tt) == "t"] <- "stat"
  colnames(tt)[colnames(tt) == "P.Value"] <- "pvalue"
  colnames(tt)[colnames(tt) == "adj.P.Val"] <- "padj"
  out_path <- file.path("{workflow_dir}", "comparisons", paste0(comparison_id, ".tsv"))
  write.table(tt, file=out_path, sep="\\t", row.names=FALSE, quote=FALSE)
  all_results[[length(all_results) + 1]] <- tt
}}

summary_df <- do.call(rbind, summary_rows)
write.table(summary_df, file=file.path("{workflow_dir}", "comparison_summary.tsv"), sep="\\t", row.names=FALSE, quote=FALSE)
if (length(all_results) > 0) {{
  deg_long <- do.call(rbind, all_results)
  write.table(deg_long, file=file.path("{workflow_dir}", "deg_long.tsv"), sep="\\t", row.names=FALSE, quote=FALSE)
}}
'''
    write_text(script_path, script)


def build_extractor_cmd(
    *,
    python_bin: str,
    deg_tsv: Path,
    extractor_out: Path,
    organism: str,
    genome_build: str,
    signature_name: str,
    settings: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg",
        "--deg_tsv",
        str(deg_tsv),
        "--out_dir",
        str(extractor_out),
        "--organism",
        organism,
        "--genome_build",
        genome_build,
        "--signature_name",
        signature_name,
        "--postprocess_mode",
        settings["extractor_postprocess_mode"],
        "--score_mode",
        settings["extractor_score_mode"],
        "--select",
        settings["extractor_select"],
        "--normalize",
        "within_set_l1",
        "--emit_full",
        "true",
        "--emit_gmt",
        "true",
        "--gmt_split_signed",
        "true",
        "--gmt_require_symbol",
        settings["extractor_gmt_require_symbol"],
        "--emit_small_gene_sets",
        settings["extractor_emit_small_gene_sets"],
    ]
    if settings["extractor_disable_default_excludes"] == "true":
        cmd.append("--disable_default_excludes")
    for flag_name, key in [
        ("--padj_max", "extractor_padj_max"),
        ("--pvalue_max", "extractor_pvalue_max"),
        ("--min_abs_logfc", "extractor_min_abs_logfc"),
        ("--top_k", "extractor_top_k"),
        ("--min_score", "extractor_min_score"),
        ("--gmt_source", "extractor_gmt_source"),
        ("--gmt_topk_list", "extractor_gmt_topk_list"),
        ("--gmt_min_genes", "extractor_gmt_min_genes"),
        ("--gmt_max_genes", "extractor_gmt_max_genes"),
    ]:
        value = settings[key]
        if value != "NA":
            cmd.extend([flag_name, value])
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


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


def write_model_commands(
    *,
    model_out: Path,
    model_id: str,
    workflow_cmd: list[str],
    dig_dir: Path,
    extractor_cmds: list[list[str]],
) -> None:
    lines = [
        f"# Commands For {model_id}",
        "",
        "## Workflow",
        "",
        "```bash",
        shell_join(workflow_cmd),
        "```",
        "",
        "## Extractors",
        "",
    ]
    for cmd in extractor_cmds:
        lines.extend([
            "```bash",
            f"cd {shlex.quote(str(dig_dir))}",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {shell_join(cmd)}",
            "```",
            "",
        ])
    write_text(model_out / "commands.md", "\n".join(lines))


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]

    prepared_dir = Path(args.prepared_dir).resolve()
    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "tissue_extractor"
    comparisons_out = extractor_out / "comparisons"
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    comparisons_out.mkdir(parents=True, exist_ok=True)

    rscript_bin = resolve_rscript_bin(args.rscript_bin)
    check_r_packages(rscript_bin)

    min_samples_per_group = int(settings.get("workflow_min_samples_per_group", "2") or "2")
    workflow_script = workflow_out / "run_motrpac_timewise_limma_voom.R"
    workflow_cmd = [rscript_bin, str(workflow_script)]
    write_workflow_script(
        script_path=workflow_script,
        counts_tsv=prepared_dir / "tissue_counts.tsv",
        metadata_tsv=prepared_dir / "sample_metadata.tsv",
        workflow_dir=workflow_out,
        min_samples_per_group=min_samples_per_group,
    )

    metadata_rows = read_sample_metadata(prepared_dir / "sample_metadata.tsv")
    comparison_ids = sorted(
        {
            f"{str(row.get('tissue_code_no', '')).strip().lower()}-{ '-'.join(part for part in ''.join(ch.lower() if ch.isalnum() else ' ' for ch in str(row.get('tissue', '')).strip()).split() if part) }_{str(row.get('sex_label', '')).strip().lower()}_{str(row.get('timepoint_label', '')).strip()}"
            for row in metadata_rows
            if row.get("tissue_code_no") and row.get("sex_label") and row.get("timepoint_label")
        }
    )
    extractor_cmds = [
        build_extractor_cmd(
            python_bin=str(Path(args.python_bin).resolve()),
            deg_tsv=workflow_out / "comparisons" / f"{comparison_id}.tsv",
            extractor_out=comparisons_out / comparison_id,
            organism=args.organism,
            genome_build=args.genome_build,
            signature_name=comparison_id,
            settings=settings,
            provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
            provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
        )
        for comparison_id in comparison_ids
    ]
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        dig_dir=dig_dir,
        extractor_cmds=extractor_cmds,
    )
    if args.write_commands_only:
        return 0

    env = dict(os.environ)
    env["PYTHONPATH"] = str(dig_dir / "src")
    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=model_out, env=env, log_path=model_log)

    comparison_summary_path = workflow_out / "comparison_summary.tsv"
    if not comparison_summary_path.exists():
        raise SystemExit(f"Expected comparison summary after workflow: {comparison_summary_path}")
    with comparison_summary_path.open("r", encoding="utf-8", newline="") as handle:
        summary_rows = list(csv.DictReader(handle, delimiter="\t"))
    runnable_comparisons = [
        row["comparison_id"]
        for row in summary_rows
        if int(row.get("n_control", "0")) >= min_samples_per_group
        and int(row.get("n_training", "0")) >= min_samples_per_group
        and (workflow_out / "comparisons" / f"{row['comparison_id']}.tsv").exists()
    ]
    if not runnable_comparisons:
        raise SystemExit("No runnable timewise comparisons were produced for this tissue.")

    gmt_lines: list[str] = []
    summary_out_rows: list[dict[str, str]] = []
    for comparison_id in runnable_comparisons:
        deg_tsv = workflow_out / "comparisons" / f"{comparison_id}.tsv"
        comparison_extractor_out = comparisons_out / comparison_id
        cmd = build_extractor_cmd(
            python_bin=str(Path(args.python_bin).resolve()),
            deg_tsv=deg_tsv,
            extractor_out=comparison_extractor_out,
            organism=args.organism,
            genome_build=args.genome_build,
            signature_name=comparison_id,
            settings=settings,
            provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
            provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
        )
        run_command(cmd, cwd=dig_dir, env=env, log_path=model_log)
        gmt_path = comparison_extractor_out / "genesets.gmt"
        if gmt_path.exists():
            lines = [line.rstrip("\n") for line in gmt_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            gmt_lines.extend(lines)
            summary_out_rows.append(
                {
                    "comparison_id": comparison_id,
                    "extractor_out_dir": str(comparison_extractor_out),
                    "n_gmt_sets": str(len(lines)),
                }
            )

    write_text(extractor_out / "genesets.gmt", "\n".join(gmt_lines) + ("\n" if gmt_lines else ""))
    write_tsv(
        extractor_out / "signature_summary.tsv",
        summary_out_rows,
        ["comparison_id", "extractor_out_dir", "n_gmt_sets"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
