#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


AGE_ORDER = ["20-29", "30-39", "40-49", "50-59", "60-69", "70-79"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the CFDE notebook-style GTEx aging-signature workflow for one tissue/model "
            "from the prepared tissue bundle."
        )
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--tissue_id", required=True)
    parser.add_argument("--tissue_label", required=True)
    parser.add_argument("--prepared_dir", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--organism", default="human", choices=["human", "mouse"])
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--write_commands_only", action="store_true")
    parser.add_argument("--reference_age_bin", default="20-29")
    parser.add_argument("--min_samples_per_group", type=int, default=3)
    parser.add_argument("--padj_max", type=float, default=0.05)
    parser.add_argument("--top_n", type=int, default=250)
    parser.add_argument("--min_genes", type=int, default=5)
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


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


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
            "R packages 'edgeR' and 'limma' are required for CFDE notebook-style geneset building and were not found for "
            f"{rscript_bin}."
        )


def compact_age_comparison_label(age_bin: str, reference_age_bin: str) -> str:
    left_decade = str(age_bin).split("-", 1)[0]
    right_decade = str(reference_age_bin).split("-", 1)[0]
    return f"age{left_decade}_{right_decade}"


def parse_numeric_values(row: dict[str, str], sample_columns: list[str]) -> list[float]:
    return [float(row[column]) for column in sample_columns]


def row_variance(row: dict[str, str], sample_columns: list[str]) -> float:
    values = parse_numeric_values(row, sample_columns)
    if len(values) <= 1:
        return 0.0
    mean_value = sum(values) / len(values)
    return sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)


def prepare_notebook_counts(counts_path: Path, out_path: Path) -> tuple[list[str], int]:
    rows = read_tsv(counts_path)
    if not rows:
        raise SystemExit(f"No rows found in {counts_path}")
    fieldnames = list(rows[0].keys())
    sample_columns = [column for column in fieldnames if column not in {"gene_id", "gene_symbol"}]
    best_by_symbol: dict[str, tuple[float, dict[str, str]]] = {}
    symbol_order: list[str] = []
    for row in rows:
        gene_symbol = str(row.get("gene_symbol", "")).strip()
        if not gene_symbol:
            continue
        variance = row_variance(row, sample_columns)
        existing = best_by_symbol.get(gene_symbol)
        if existing is None or variance >= existing[0]:
            if existing is None:
                symbol_order.append(gene_symbol)
            best_by_symbol[gene_symbol] = (variance, row)
    kept_rows = [best_by_symbol[symbol][1] for symbol in symbol_order]
    write_tsv(out_path, kept_rows, ["gene_id", "gene_symbol", *sample_columns])
    return sample_columns, len(kept_rows)


def notebook_signature_name(tissue_label: str, age_bin: str, reference_age_bin: str) -> str:
    tissue_token = tissue_label.replace(" ", "").replace("-", "")
    return f"GTEx_{tissue_token}_{reference_age_bin}_vs_{age_bin}"


def select_comparisons(
    *,
    metadata_rows: list[dict[str, str]],
    reference_age_bin: str,
    min_samples_per_group: int,
    tissue_label: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    age_to_samples: dict[str, list[str]] = defaultdict(list)
    for row in metadata_rows:
        age_bin = str(row.get("age_bin", "")).strip()
        sample_id = str(row.get("sample_id", "")).strip()
        if age_bin and sample_id:
            age_to_samples[age_bin].append(sample_id)
    comparisons: list[dict[str, str]] = []
    selected_rows: list[dict[str, str]] = []
    if len(age_to_samples.get(reference_age_bin, [])) < min_samples_per_group:
        return comparisons, selected_rows
    for age_bin in AGE_ORDER:
        if age_bin == reference_age_bin:
            continue
        if len(age_to_samples.get(age_bin, [])) < min_samples_per_group:
            continue
        min_samp = min(len(age_to_samples[reference_age_bin]), len(age_to_samples[age_bin]))
        ctl_ids = random.Random(1).sample(age_to_samples[reference_age_bin], min_samp)
        pert_ids = random.Random(1).sample(age_to_samples[age_bin], min_samp)
        comparison_id = compact_age_comparison_label(age_bin, reference_age_bin)
        comparisons.append(
            {
                "comparison_id": comparison_id,
                "aging_signature": notebook_signature_name(tissue_label, age_bin, reference_age_bin),
                "reference_age_bin": reference_age_bin,
                "age_bin": age_bin,
                "n_control": str(len(ctl_ids)),
                "n_case": str(len(pert_ids)),
            }
        )
        for sample_id in ctl_ids:
            selected_rows.append(
                {"comparison_id": comparison_id, "role": "control", "sample_id": sample_id}
            )
        for sample_id in pert_ids:
            selected_rows.append(
                {"comparison_id": comparison_id, "role": "case", "sample_id": sample_id}
            )
    return comparisons, selected_rows


def write_r_script(
    *,
    script_path: Path,
    counts_tsv: Path,
    comparison_samples_tsv: Path,
    comparisons_tsv: Path,
    workflow_dir: Path,
) -> Path:
    script = f'''suppressPackageStartupMessages({{
  library(edgeR)
  library(limma)
}})

counts <- read.delim("{counts_tsv}", check.names=FALSE)
sample_map <- read.delim("{comparison_samples_tsv}", check.names=FALSE)
comparisons <- read.delim("{comparisons_tsv}", check.names=FALSE)
count_cols <- setdiff(colnames(counts), c("gene_id", "gene_symbol"))
count_mat <- as.matrix(counts[, count_cols, drop=FALSE])
storage.mode(count_mat) <- "numeric"
rownames(count_mat) <- counts$gene_id
gene_ids <- counts$gene_id
gene_symbols <- as.character(counts$gene_symbol)

y_all <- DGEList(counts=count_mat)
keep_genes <- filterByExpr(y_all)
count_mat <- count_mat[keep_genes, , drop=FALSE]
gene_ids <- gene_ids[keep_genes]
gene_symbols <- gene_symbols[keep_genes]

dir.create(file.path("{workflow_dir}", "comparisons"), showWarnings=FALSE, recursive=TRUE)
all_results <- list()

for (i in seq_len(nrow(comparisons))) {{
  cid <- as.character(comparisons$comparison_id[i])
  ctl_ids <- sample_map$sample_id[sample_map$comparison_id == cid & sample_map$role == "control"]
  case_ids <- sample_map$sample_id[sample_map$comparison_id == cid & sample_map$role == "case"]
  selected_ids <- c(ctl_ids, case_ids)
  subset_mat <- count_mat[, selected_ids, drop=FALSE]
  group <- factor(c(rep("control", length(ctl_ids)), rep("case", length(case_ids))), levels=c("control", "case"))
  y <- DGEList(counts=subset_mat)
  y <- calcNormFactors(y)
  design <- model.matrix(~ group)
  v <- voom(y, design, plot=FALSE)
  fit <- lmFit(v, design)
  fit <- eBayes(fit)
  tt <- topTable(fit, coef="groupcase", number=Inf, sort.by="none")
  tt$comparison_id <- cid
  tt$gene_id <- gene_ids
  tt$gene_symbol <- gene_symbols
  tt$group_a <- "older"
  tt$group_b <- "younger"
  tt$n_control <- length(ctl_ids)
  tt$n_case <- length(case_ids)
  out_path <- file.path("{workflow_dir}", "comparisons", paste0(cid, ".tsv"))
  write.table(tt, file=out_path, sep="\\t", quote=FALSE, row.names=FALSE)
  all_results[[length(all_results) + 1]] <- tt
}}

deg_long <- do.call(rbind, all_results)
write.table(deg_long, file=file.path("{workflow_dir}", "deg_long.tsv"), sep="\\t", quote=FALSE, row.names=FALSE)
'''
    write_text(script_path, script)
    return script_path


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


def safe_score(padj_text: str, sign: int) -> float:
    padj = max(float(padj_text), 1e-300)
    return (-math.log10(padj)) * float(sign)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_extractor_outputs(
    *,
    model_id: str,
    tissue_id: str,
    tissue_label: str,
    workflow_dir: Path,
    extractor_dir: Path,
    padj_max: float,
    top_n: int,
    min_genes: int,
    invocation_cmd: list[str],
) -> dict[str, Any]:
    rows = read_tsv(workflow_dir / "deg_long.tsv")
    by_comparison: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_comparison[str(row.get("comparison_id", "")).strip()].append(row)

    manifest_rows: list[dict[str, str]] = []
    top_level_gmt_lines: list[str] = []
    total_queries = 0

    for comparison_id in sorted(by_comparison):
        comparison_rows = [row for row in by_comparison[comparison_id] if str(row.get("gene_symbol", "")).strip()]
        significant_rows = [row for row in comparison_rows if float(row.get("adj.P.Val", "1")) < padj_max]
        significant_rows.sort(key=lambda row: (float(row.get("adj.P.Val", "1")), -abs(float(row.get("logFC", "0")))))
        pos_rows = [row for row in significant_rows if float(row.get("logFC", "0")) > 0][:top_n]
        neg_rows = [row for row in significant_rows if float(row.get("logFC", "0")) < 0][:top_n]

        comparison_dir = extractor_dir / comparison_id
        comparison_dir.mkdir(parents=True, exist_ok=True)
        full_rows: list[dict[str, Any]] = []
        selected_rows: list[dict[str, Any]] = []
        gmt_lines: list[str] = []

        for direction, sign, selected in [("pos", 1, pos_rows), ("neg", -1, neg_rows)]:
            query_name = f"{model_id}__{comparison_id}__{direction}"
            for row in selected:
                selected_rows.append(
                    {
                        "query_name": query_name,
                        "comparison_id": comparison_id,
                        "direction": direction,
                        "gene_symbol": row["gene_symbol"],
                        "gene_id": row.get("gene_id", ""),
                        "adj.P.Val": row.get("adj.P.Val", ""),
                        "P.Value": row.get("P.Value", ""),
                        "logFC": row.get("logFC", ""),
                        "score": f"{safe_score(str(row.get('adj.P.Val', '1')), sign):.6f}",
                    }
                )
            if len(selected) >= min_genes:
                genes = [row["gene_symbol"] for row in selected]
                gmt_lines.append("\t".join([query_name, *genes]))
                top_level_gmt_lines.append("\t".join([query_name, *genes]))
                total_queries += 1

        for row in significant_rows:
            sign = 1 if float(row.get("logFC", "0")) > 0 else -1
            direction = "pos" if sign > 0 else "neg"
            full_rows.append(
                {
                    "comparison_id": comparison_id,
                    "direction": direction,
                    "gene_symbol": row["gene_symbol"],
                    "gene_id": row.get("gene_id", ""),
                    "adj.P.Val": row.get("adj.P.Val", ""),
                    "P.Value": row.get("P.Value", ""),
                    "logFC": row.get("logFC", ""),
                    "score": f"{safe_score(str(row.get('adj.P.Val', '1')), sign):.6f}",
                }
            )

        write_tsv(
            comparison_dir / "geneset.tsv",
            selected_rows,
            ["query_name", "comparison_id", "direction", "gene_symbol", "gene_id", "adj.P.Val", "P.Value", "logFC", "score"],
        )
        write_tsv(
            comparison_dir / "geneset.full.tsv",
            full_rows,
            ["comparison_id", "direction", "gene_symbol", "gene_id", "adj.P.Val", "P.Value", "logFC", "score"],
        )
        write_text(comparison_dir / "genesets.gmt", "\n".join(gmt_lines) + ("\n" if gmt_lines else ""))
        meta_payload = {
            "model_id": model_id,
            "tissue_id": tissue_id,
            "tissue_label": tissue_label,
            "comparison_id": comparison_id,
            "padj_max": padj_max,
            "top_n": top_n,
            "min_genes": min_genes,
            "n_significant_rows": len(significant_rows),
            "n_pos_selected": len(pos_rows),
            "n_neg_selected": len(neg_rows),
        }
        write_json(comparison_dir / "geneset.meta.json", meta_payload)
        provenance_payload = {
            "type": "cfde_notebook_style_geneset",
            "model_id": model_id,
            "tissue_id": tissue_id,
            "comparison_id": comparison_id,
            "inputs": [
                str(workflow_dir / "deg_long.tsv"),
                str(workflow_dir / "comparisons" / f"{comparison_id}.tsv"),
            ],
            "outputs": [
                str(comparison_dir / "geneset.tsv"),
                str(comparison_dir / "geneset.full.tsv"),
                str(comparison_dir / "genesets.gmt"),
            ],
            "parameters": {
                "padj_max": padj_max,
                "top_n": top_n,
                "min_genes": min_genes,
                "selection": "adj.P.Val < padj_max, split by sign(logFC), top_n by ascending adj.P.Val",
            },
            "command_context": shell_join(invocation_cmd),
        }
        write_json(comparison_dir / "geneset.provenance.json", provenance_payload)
        run_summary = {
            "comparison_id": comparison_id,
            "n_significant_rows": len(significant_rows),
            "n_selected_rows": len(selected_rows),
            "n_queries_emitted": sum(1 for line in gmt_lines if line.strip()),
        }
        write_json(comparison_dir / "run_summary.json", run_summary)
        write_text(
            comparison_dir / "run_summary.txt",
            f"comparison={comparison_id}\tn_significant_rows={len(significant_rows)}\tn_selected_rows={len(selected_rows)}\n",
        )
        manifest_rows.append(
            {
                "comparison_id": comparison_id,
                "path": str(comparison_dir),
                "meta_path": str(comparison_dir / "geneset.meta.json"),
                "provenance_path": str(comparison_dir / "geneset.provenance.json"),
                "gmt_path": str(comparison_dir / "genesets.gmt"),
            }
        )

    write_text(extractor_dir / "genesets.gmt", "\n".join(top_level_gmt_lines) + ("\n" if top_level_gmt_lines else ""))
    write_tsv(extractor_dir / "manifest.tsv", manifest_rows, ["comparison_id", "path", "meta_path", "provenance_path", "gmt_path"])
    return {"n_queries": total_queries, "n_comparisons": len(manifest_rows)}


def write_model_commands(
    *,
    model_out: Path,
    model_id: str,
    workflow_cmd: list[str],
    invocation_cmd: list[str],
) -> None:
    text = "\n".join(
        [
            f"# Commands For {model_id}",
            "",
            "## CFDE Notebook-Style Workflow",
            "",
            "This model mirrors the GTExAgingSignatures notebook logic:",
            "- deduplicate by gene symbol using highest variance",
            "- require at least 3 samples per age group",
            "- balance each comparison by random subsampling with seed 1",
            "- run limma/voom per comparison",
            "- keep genes with adj.P.Val < 0.05",
            "- emit top 250 genes per sign into GMTs",
            "",
            "## Invocation",
            "",
            "```bash",
            shell_join(invocation_cmd),
            "```",
            "",
            "## Differential Expression Workflow",
            "",
            "```bash",
            shell_join(workflow_cmd),
            "```",
            "",
        ]
    )
    write_text(model_out / "commands.md", text)


def write_workflow_summary(
    *,
    path: Path,
    tissue_id: str,
    tissue_label: str,
    n_genes_after_dedup: int,
    comparisons: list[dict[str, str]],
) -> None:
    payload = {
        "tissue_id": tissue_id,
        "tissue_label": tissue_label,
        "n_genes_after_symbol_dedup": n_genes_after_dedup,
        "n_comparisons": len(comparisons),
        "comparison_ids": [row["comparison_id"] for row in comparisons],
        "aging_signatures": [row["aging_signature"] for row in comparisons],
    }
    write_json(path, payload)


def main() -> int:
    args = parse_args()
    repo = repo_root()
    prepared_dir = Path(args.prepared_dir).resolve()
    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_dir = model_out / "workflow"
    extractor_dir = model_out / "extractor"
    model_log = model_out / "run.log"
    rscript_bin = resolve_rscript_bin(args.rscript_bin)

    required = ["tissue_counts.tsv", "sample_metadata.tsv"]
    if not args.write_commands_only:
        missing = [name for name in required if not (prepared_dir / name).exists()]
        if missing:
            raise SystemExit("prepared_dir must contain tissue_counts.tsv and sample_metadata.tsv")
        check_r_packages(rscript_bin)

    model_out.mkdir(parents=True, exist_ok=True)
    notebook_counts_tsv = workflow_dir / "notebook_counts.tsv"
    comparison_samples_tsv = workflow_dir / "comparison_selected_samples.tsv"
    comparisons_tsv = workflow_dir / "comparisons.tsv"
    workflow_script = workflow_dir / "run_cfde_notebook_limma_voom.R"
    invocation_cmd = [
        str(repo / "geneset-extractor-dev" / "GTEx" / "run" / "build_genesets.sh"),
        "--tissues",
        args.tissue_id,
        "--models",
        args.model_id,
    ]

    metadata_rows = read_tsv(prepared_dir / "sample_metadata.tsv")
    _sample_columns, n_genes_after_dedup = prepare_notebook_counts(prepared_dir / "tissue_counts.tsv", notebook_counts_tsv)
    comparisons, selected_rows = select_comparisons(
        metadata_rows=metadata_rows,
        reference_age_bin=args.reference_age_bin,
        min_samples_per_group=args.min_samples_per_group,
        tissue_label=args.tissue_label,
    )
    write_tsv(
        comparison_samples_tsv,
        selected_rows,
        ["comparison_id", "role", "sample_id"],
    )
    write_tsv(
        comparisons_tsv,
        comparisons,
        ["comparison_id", "aging_signature", "reference_age_bin", "age_bin", "n_control", "n_case"],
    )
    write_workflow_summary(
        path=workflow_dir / "workflow_summary.json",
        tissue_id=args.tissue_id,
        tissue_label=args.tissue_label,
        n_genes_after_dedup=n_genes_after_dedup,
        comparisons=comparisons,
    )

    workflow_cmd = [rscript_bin, str(write_r_script(
        script_path=workflow_script,
        counts_tsv=notebook_counts_tsv,
        comparison_samples_tsv=comparison_samples_tsv,
        comparisons_tsv=comparisons_tsv,
        workflow_dir=workflow_dir,
    ))]
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        invocation_cmd=invocation_cmd,
    )

    if args.write_commands_only:
        return 0

    env = os.environ.copy()
    log_line(model_log, f"[run_cfde_notebook_model] model_id={args.model_id}")
    log_line(model_log, f"[run_cfde_notebook_model] tissue_id={args.tissue_id}")
    if comparisons:
        run_command(workflow_cmd, cwd=repo, env=env, log_path=model_log)
    else:
        write_tsv(
            workflow_dir / "deg_long.tsv",
            [],
            [
                "logFC",
                "AveExpr",
                "t",
                "P.Value",
                "adj.P.Val",
                "comparison_id",
                "gene_id",
                "gene_symbol",
                "group_a",
                "group_b",
                "n_control",
                "n_case",
            ],
        )
        log_line(model_log, "[run_cfde_notebook_model] no valid age comparisons; wrote empty deg_long.tsv")
    summary = build_extractor_outputs(
        model_id=args.model_id,
        tissue_id=args.tissue_id,
        tissue_label=args.tissue_label,
        workflow_dir=workflow_dir,
        extractor_dir=extractor_dir,
        padj_max=args.padj_max,
        top_n=args.top_n,
        min_genes=args.min_genes,
        invocation_cmd=invocation_cmd,
    )
    write_text(
        model_out / "run_summary.md",
        "\n".join(
            [
                f"# CFDE Notebook-Style Model Summary: {args.model_id}",
                "",
                f"- tissue_id: `{args.tissue_id}`",
                f"- tissue_label: `{args.tissue_label}`",
                f"- n_genes_after_symbol_dedup: `{n_genes_after_dedup}`",
                f"- n_comparisons: `{len(comparisons)}`",
                f"- n_queries_emitted: `{summary['n_queries']}`",
                "",
            ]
        )
        + "\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
