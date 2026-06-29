#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a MoTrPAC timepoint-stratified training-vs-control workflow that pools sexes "
            "within a tissue timepoint while adjusting for sex as a covariate."
        )
    )
    parser.add_argument("--counts_tsv", required=True)
    parser.add_argument("--sample_metadata_tsv", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--tissue_id", required=True)
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--min_samples_per_group", type=int, default=5)
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


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
            "R packages 'edgeR' and 'limma' are required for the MoTrPAC timepoint workflow and were not found for "
            f"{rscript_bin}."
        )


def slugify_tissue_id(tissue_id: str) -> str:
    return str(tissue_id).strip().lower().replace("_", "-")


def write_workflow_script(
    *,
    script_path: Path,
    counts_tsv: Path,
    metadata_tsv: Path,
    output_tsv: Path,
    tissue_slug: str,
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
meta$sex <- factor(as.character(meta$sex), levels=c("M", "F"))
meta$intervention <- factor(as.character(meta$intervention), levels=c("control", "training"))
meta$timepoint_label <- as.character(meta$timepoint_label)
meta$tissue_code_no <- as.character(meta$tissue_code_no)

all_results <- list()
all_summaries <- list()
timepoints <- unique(meta$timepoint_label)
for (tp in timepoints) {{
  meta_tp <- meta[meta$timepoint_label == tp, , drop=FALSE]
  n_training <- sum(meta_tp$intervention == "training")
  n_control <- sum(meta_tp$intervention == "control")
  comparison_id <- paste0(tolower(meta_tp$tissue_code_no[1]), "-{tissue_slug}_", tp)
  all_summaries[[length(all_summaries) + 1]] <- data.frame(
    comparison_id=comparison_id,
    timepoint_label=tp,
    n_control=n_control,
    n_training=n_training,
    stringsAsFactors=FALSE
  )
  if (n_training < {int(min_samples_per_group)} || n_control < {int(min_samples_per_group)}) {{
    next
  }}
  count_mat_tp <- count_mat[, meta_tp$sample_id, drop=FALSE]
  y <- DGEList(counts=count_mat_tp)
  design_formula <- if (length(unique(as.character(meta_tp$sex))) > 1) ~ intervention + sex else ~ intervention
  design <- model.matrix(design_formula, data=meta_tp)
  keep_genes <- filterByExpr(y, design=design)
  y <- y[keep_genes, , keep.lib.sizes=FALSE]
  gene_ids_tp <- gene_ids[keep_genes]
  gene_symbols_tp <- gene_symbols[keep_genes]
  y <- calcNormFactors(y)
  v <- voom(y, design, plot=FALSE)
  fit <- lmFit(v, design)
  fit <- eBayes(fit)
  tt <- topTable(fit, coef="interventiontraining", number=Inf, sort.by="none")
  tt$comparison_id <- comparison_id
  tt$gene_id <- gene_ids_tp
  tt$gene_symbol <- gene_symbols_tp
  tt$group_a <- "training"
  tt$group_b <- "control"
  tt$stratum <- paste("timepoint=", tp, sep="")
  tt$backend <- "r_limma_voom_motrpac_timepoint"
  tt$n_group_a <- n_training
  tt$n_group_b <- n_control
  tt$mean_expr <- tt$AveExpr
  tt$model_formula <- if (length(unique(as.character(meta_tp$sex))) > 1) "intervention + sex" else "intervention"
  keep_cols <- c("comparison_id", "gene_id", "gene_symbol", "logFC", "t", "P.Value", "adj.P.Val", "group_a", "group_b", "stratum", "backend", "n_group_a", "n_group_b", "mean_expr", "model_formula")
  tt <- tt[, keep_cols, drop=FALSE]
  colnames(tt)[colnames(tt) == "t"] <- "stat"
  colnames(tt)[colnames(tt) == "P.Value"] <- "pvalue"
  colnames(tt)[colnames(tt) == "adj.P.Val"] <- "padj"
  all_results[[length(all_results) + 1]] <- tt
}}

if (length(all_results) == 0) {{
  stop("No runnable MoTrPAC timepoint comparisons were identified from the prepared sample metadata.")
}}

result <- do.call(rbind, all_results)
summary_df <- do.call(rbind, all_summaries)
write.table(result, file="{output_tsv}", sep="\\t", row.names=FALSE, quote=FALSE)
write.table(summary_df, file="{script_path.parent / "comparison_summary.tsv"}", sep="\\t", row.names=FALSE, quote=FALSE)
'''
    write_text(script_path, script)


def main() -> int:
    args = parse_args()
    counts_tsv = Path(args.counts_tsv).resolve()
    metadata_tsv = Path(args.sample_metadata_tsv).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata_rows = read_tsv(metadata_tsv)
    if not metadata_rows:
        raise SystemExit(f"No sample metadata rows found in {metadata_tsv}")

    workflow_script = out_dir / "run_motrpac_timepoint_limma_voom.R"
    deg_tsv = out_dir / "deg_long.tsv"
    write_workflow_script(
        script_path=workflow_script,
        counts_tsv=counts_tsv,
        metadata_tsv=metadata_tsv,
        output_tsv=deg_tsv,
        tissue_slug=slugify_tissue_id(args.tissue_id),
        min_samples_per_group=int(args.min_samples_per_group),
    )

    rscript_bin = resolve_rscript_bin(args.rscript_bin)
    check_r_packages(rscript_bin)
    completed = subprocess.run(
        [rscript_bin, str(workflow_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stdout.strip() or f"Timepoint workflow failed with exit code {completed.returncode}")

    summary_rows = read_tsv(out_dir / "comparison_summary.tsv") if (out_dir / "comparison_summary.tsv").exists() else []
    payload = {
        "workflow": "motrpac_timepoint",
        "tissue_id": args.tissue_id,
        "counts_tsv": str(counts_tsv),
        "sample_metadata_tsv": str(metadata_tsv),
        "n_comparisons": len([row for row in summary_rows if int(str(row.get("n_control", "0")) or "0") >= int(args.min_samples_per_group) and int(str(row.get("n_training", "0")) or "0") >= int(args.min_samples_per_group)]),
    }
    write_text(out_dir / "prepare_summary.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
