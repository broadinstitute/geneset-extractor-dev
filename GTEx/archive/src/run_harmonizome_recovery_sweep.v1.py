#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
import subprocess
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_harmonizome_recovery_sweep_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared_inputs_tsv", required=True)
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--rscript_executable", default="Rscript")
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


def write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    LOGGER.info("wrote text: %s", path)


def read_gmt(path: Path) -> dict[str, list[str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    out: dict[str, list[str]] = {}
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            out[parts[0]] = [token for token in parts[1:] if token]
    LOGGER.info("loaded GMT path=%s n_sets=%d", path, len(out))
    return out


def ensure_r_packages(rscript_executable: str) -> None:
    cmd = [
        rscript_executable,
        "-e",
        "cat(requireNamespace('limma', quietly=TRUE), '\\n'); cat(requireNamespace('edgeR', quietly=TRUE), '\\n')",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    values = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if values != ["TRUE", "TRUE"]:
        raise RuntimeError("R packages limma and edgeR are required for this sweep.")


def write_r_script(path: Path) -> None:
    script = r"""
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 7) {
  stop("expected args: matrix_tsv metadata_tsv comparisons_tsv out_dir tissue_name filter_mode ebayes_mode")
}

suppressPackageStartupMessages(library(edgeR))
suppressPackageStartupMessages(library(limma))

matrix_tsv <- args[[1]]
metadata_tsv <- args[[2]]
comparisons_tsv <- args[[3]]
out_dir <- args[[4]]
tissue_name <- args[[5]]
filter_mode <- args[[6]]
ebayes_mode <- args[[7]]

dir.create(out_dir, recursive=TRUE, showWarnings=FALSE)

expr_df <- read.table(matrix_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)
metadata_df <- read.table(metadata_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)
comparisons_df <- read.table(comparisons_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)

sample_ids <- colnames(expr_df)[-1]
counts <- as.matrix(expr_df[, -1, drop=FALSE])
rownames(counts) <- expr_df$gene_symbol
storage.mode(counts) <- 'numeric'

for (i in seq_len(nrow(comparisons_df))) {
  comparison_id <- as.character(comparisons_df$comparison_id[i])
  group_a_ids <- unlist(strsplit(as.character(comparisons_df$group_a_sample_ids[i]), "\\|", fixed=FALSE))
  group_b_ids <- unlist(strsplit(as.character(comparisons_df$group_b_sample_ids[i]), "\\|", fixed=FALSE))
  selected_ids <- c(group_b_ids, group_a_ids)
  selected_ids <- selected_ids[selected_ids %in% colnames(counts)]
  if (length(selected_ids) < 6) {
    next
  }

  counts_sub <- counts[, selected_ids, drop=FALSE]
  group <- factor(c(rep("control", length(group_b_ids)), rep("case", length(group_a_ids))), levels=c("control", "case"))
  design <- model.matrix(~ group)

  dge <- DGEList(counts=counts_sub)
  if (filter_mode == "default") {
    keep <- filterByExpr(dge, design=design)
    dge <- dge[keep, , keep.lib.sizes=FALSE]
  } else if (filter_mode == "relaxed") {
    keep <- filterByExpr(dge, design=design, min.count=1, min.total.count=5)
    dge <- dge[keep, , keep.lib.sizes=FALSE]
  } else if (filter_mode == "none") {
    # no-op
  } else {
    stop(paste("unknown filter_mode", filter_mode))
  }

  dge <- calcNormFactors(dge)
  v <- voom(dge, design, plot=FALSE)
  fit <- lmFit(v, design)
  if (ebayes_mode == "default") {
    fit <- eBayes(fit)
  } else if (ebayes_mode == "trend_robust") {
    fit <- eBayes(fit, trend=TRUE, robust=TRUE)
  } else {
    stop(paste("unknown ebayes_mode", ebayes_mode))
  }

  tt <- topTable(fit, coef="groupcase", number=Inf, sort.by="none")
  tt$gene_symbol <- rownames(tt)
  tt$comparison_id <- comparison_id
  tt$group_a <- as.character(comparisons_df$group_a[i])
  tt$group_b <- as.character(comparisons_df$group_b[i])
  tt$n_group_a <- length(group_a_ids)
  tt$n_group_b <- length(group_b_ids)
  tt <- tt[, c("comparison_id", "gene_symbol", "logFC", "AveExpr", "t", "P.Value", "adj.P.Val", "B", "group_a", "group_b", "n_group_a", "n_group_b")]
  out_path <- file.path(out_dir, paste0(comparison_id, ".v1.tsv"))
  write.table(tt, file=out_path, sep='\t', row.names=FALSE, quote=FALSE)
}
"""
    write_text(script.strip() + "\n", path)


def config_rows() -> list[dict[str, object]]:
    return [
        {
            "config_name": "baseline_current",
            "filter_mode": "default",
            "ebayes_mode": "default",
            "adj_p_max": 0.05,
        },
        {
            "config_name": "no_filter",
            "filter_mode": "none",
            "ebayes_mode": "default",
            "adj_p_max": 0.05,
        },
        {
            "config_name": "relaxed_filter",
            "filter_mode": "relaxed",
            "ebayes_mode": "default",
            "adj_p_max": 0.05,
        },
        {
            "config_name": "current_trend_robust",
            "filter_mode": "default",
            "ebayes_mode": "trend_robust",
            "adj_p_max": 0.05,
        },
        {
            "config_name": "current_relaxed_sig",
            "filter_mode": "default",
            "ebayes_mode": "default",
            "adj_p_max": 0.10,
        },
    ]


def run_config(
    *,
    config_row: dict[str, object],
    prepared_df: pd.DataFrame,
    output_dir: Path,
    rscript_executable: str,
    r_script_path: Path,
) -> pd.DataFrame:
    config_name = str(config_row["config_name"])
    filter_mode = str(config_row["filter_mode"])
    ebayes_mode = str(config_row["ebayes_mode"])
    config_dir = output_dir / config_name
    deg_dir = config_dir / "deg_tissue"
    deg_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    for row in prepared_df.to_dict(orient="records"):
        tissue_name = str(row["tissue_name"])
        tissue_out_dir = deg_dir / tissue_name
        tissue_out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            rscript_executable,
            str(r_script_path),
            str(row["matrix_tsv"]),
            str(row["metadata_tsv"]),
            str(row["comparisons_tsv"]),
            str(tissue_out_dir),
            tissue_name,
            filter_mode,
            ebayes_mode,
        ]
        LOGGER.info("running config=%s tissue=%s", config_name, tissue_name)
        result = subprocess.run(cmd, capture_output=True, text=True)
        write_text(result.stdout, tissue_out_dir / "limma_voom.stdout.v1.log")
        write_text(result.stderr, tissue_out_dir / "limma_voom.stderr.v1.log")
        if result.returncode != 0:
            raise RuntimeError(f"config={config_name} failed for tissue={tissue_name}")
        manifest_rows.append(
            {
                "config_name": config_name,
                "tissue_name": tissue_name,
                "deg_out_dir": str(tissue_out_dir),
                "n_deg_tables": len(sorted(tissue_out_dir.glob("GTEx_*.v1.tsv"))),
            }
        )

    manifest_df = pd.DataFrame(manifest_rows).sort_values(["config_name", "tissue_name"]).reset_index(drop=True)
    LOGGER.info("config manifest shape=%s config=%s", manifest_df.shape, config_name)
    return manifest_df


def combine_deg_tables(config_dir: Path) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for path in sorted((config_dir / "deg_tissue").glob("*/*.v1.tsv")):
        df = pd.read_csv(path, sep="\t", dtype=str)
        rows.append(df)
    if not rows:
        raise ValueError(f"no DEG tables found for {config_dir}")
    combined_df = pd.concat(rows, ignore_index=True)
    combined_df = combined_df.rename(
        columns={
            "AveExpr": "ave_expr",
            "P.Value": "pvalue",
            "adj.P.Val": "adj_p_val",
            "B": "b_stat",
        }
    )
    LOGGER.info("combined DEG shape=%s config_dir=%s", combined_df.shape, config_dir)
    return combined_df


def build_gmt(combined_deg_df: pd.DataFrame, *, adj_p_max: float, min_genes: int = 5) -> tuple[pd.DataFrame, list[str]]:
    sig_df = combined_deg_df.copy()
    sig_df["adj_p_val"] = pd.to_numeric(sig_df["adj_p_val"], errors="coerce")
    sig_df["logFC"] = pd.to_numeric(sig_df["logFC"], errors="coerce")
    sig_df = sig_df.loc[sig_df["adj_p_val"].notna() & sig_df["logFC"].notna()].copy()
    sig_df = sig_df.loc[sig_df["adj_p_val"] < adj_p_max].copy()
    sig_df["direction"] = sig_df["logFC"].map(lambda value: "Up" if value > 0 else "Down")
    sig_df = sig_df.sort_values(["comparison_id", "direction", "adj_p_val", "gene_symbol"]).reset_index(drop=True)
    sig_df = sig_df.groupby(["comparison_id", "direction"], as_index=False, group_keys=False).head(250).reset_index(drop=True)
    LOGGER.info("postprocessed signature rows shape=%s adj_p_max=%.3f", sig_df.shape, adj_p_max)

    manifest_rows: list[dict[str, object]] = []
    gmt_rows: list[str] = []
    for (comparison_id, direction), group_df in sig_df.groupby(["comparison_id", "direction"], sort=True):
        genes = group_df["gene_symbol"].dropna().astype(str).tolist()
        if len(genes) < min_genes:
            continue
        set_name = f"{comparison_id}_{direction}"
        manifest_rows.append(
            {
                "set_name": set_name,
                "comparison_id": comparison_id,
                "direction": direction,
                "n_genes": len(genes),
            }
        )
        gmt_rows.append("\t".join([set_name, *genes]))

    manifest_df = pd.DataFrame(manifest_rows).sort_values("set_name").reset_index(drop=True)
    return manifest_df, gmt_rows


def compare_sets(reference_sets: dict[str, list[str]], generated_sets: dict[str, list[str]]) -> pd.DataFrame:
    shared_names = sorted(set(reference_sets) & set(generated_sets))
    rows: list[dict[str, object]] = []
    for set_name in shared_names:
        ref_genes = set(reference_sets[set_name])
        gen_genes = set(generated_sets[set_name])
        intersection = ref_genes & gen_genes
        union = ref_genes | gen_genes
        rows.append(
            {
                "set_name": set_name,
                "reference_n_genes": len(ref_genes),
                "generated_n_genes": len(gen_genes),
                "shared_n_genes": len(intersection),
                "jaccard": (len(intersection) / len(union)) if union else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["jaccard", "set_name"], ascending=[False, True]).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_harmonizome_recovery_sweep.v1.log")

    prepared_inputs_tsv = Path(args.prepared_inputs_tsv).resolve()
    reference_gmt_gz = Path(args.reference_gmt_gz).resolve()
    for path in [prepared_inputs_tsv, reference_gmt_gz]:
        if not path.exists():
            raise FileNotFoundError(path)

    ensure_r_packages(args.rscript_executable)

    prepared_df = pd.read_csv(prepared_inputs_tsv, sep="\t", dtype=str)
    LOGGER.info("prepared inputs shape=%s", prepared_df.shape)
    reference_sets = read_gmt(reference_gmt_gz)

    config_df = pd.DataFrame(config_rows())
    write_dataframe(config_df, output_dir / "config_manifest.v1.tsv")

    r_script_path = output_dir / "run_limma_voom_recovery_sweep.v1.R"
    write_r_script(r_script_path)

    config_summary_rows: list[dict[str, object]] = []
    all_comparison_rows: list[pd.DataFrame] = []
    generated_set_name_by_config: dict[str, set[str]] = {}
    baseline_missing_set_names: set[str] | None = None

    for config_row in config_rows():
        config_name = str(config_row["config_name"])
        adj_p_max = float(config_row["adj_p_max"])
        config_dir = output_dir / config_name
        manifest_df = run_config(
            config_row=config_row,
            prepared_df=prepared_df,
            output_dir=output_dir,
            rscript_executable=args.rscript_executable,
            r_script_path=r_script_path,
        )
        write_dataframe(manifest_df, config_dir / "deg_tissue_manifest.v1.tsv")

        combined_deg_df = combine_deg_tables(config_dir)
        write_dataframe(combined_deg_df, config_dir / "deg_long_combined.v1.tsv")

        gmt_manifest_df, gmt_rows = build_gmt(combined_deg_df, adj_p_max=adj_p_max, min_genes=5)
        write_dataframe(gmt_manifest_df, config_dir / "gtex_aging_signatures_legacy_format.v1.tsv")

        gmt_path = config_dir / "gtex_aging_signatures_legacy_format.v1.gmt"
        gmt_gz_path = config_dir / "gtex_aging_signatures_legacy_format.v1.gmt.gz"
        write_text("\n".join(gmt_rows) + "\n", gmt_path)
        with gzip.open(gmt_gz_path, "wt", encoding="utf-8") as handle:
            handle.write("\n".join(gmt_rows) + "\n")
        LOGGER.info("wrote config GMT sets=%d config=%s", len(gmt_rows), config_name)

        generated_sets = read_gmt(gmt_gz_path)
        generated_set_names = set(generated_sets)
        generated_set_name_by_config[config_name] = generated_set_names
        comparison_df = compare_sets(reference_sets, generated_sets)
        write_dataframe(comparison_df, config_dir / "comparison_to_reference.v1.tsv")

        shared_names = set(reference_sets) & generated_set_names
        missing_names = set(reference_sets) - generated_set_names
        extra_names = generated_set_names - set(reference_sets)
        mean_jaccard = float(comparison_df["jaccard"].mean()) if not comparison_df.empty else 0.0
        median_jaccard = float(comparison_df["jaccard"].median()) if not comparison_df.empty else 0.0

        if config_name == "baseline_current":
            baseline_missing_set_names = missing_names
        recovered_missing_vs_baseline = 0
        if baseline_missing_set_names is not None:
            recovered_missing_vs_baseline = len(baseline_missing_set_names & generated_set_names)

        config_summary_rows.append(
            {
                "config_name": config_name,
                "filter_mode": config_row["filter_mode"],
                "ebayes_mode": config_row["ebayes_mode"],
                "adj_p_max": adj_p_max,
                "n_generated_sets": len(generated_set_names),
                "n_shared_reference_sets": len(shared_names),
                "n_missing_reference_sets": len(missing_names),
                "n_extra_sets": len(extra_names),
                "mean_jaccard": mean_jaccard,
                "median_jaccard": median_jaccard,
                "n_recovered_missing_vs_baseline": recovered_missing_vs_baseline,
            }
        )

        missing_detail_df = pd.DataFrame({"set_name": sorted(missing_names)})
        write_dataframe(missing_detail_df, config_dir / "missing_reference_sets.v1.tsv")

        report_lines = [
            f"# Recovery Sweep Config {config_name}",
            "",
            f"- filter_mode: {config_row['filter_mode']}",
            f"- ebayes_mode: {config_row['ebayes_mode']}",
            f"- adj_p_max: {adj_p_max}",
            f"- generated sets: {len(generated_set_names)}",
            f"- shared reference sets: {len(shared_names)}",
            f"- missing reference sets: {len(missing_names)}",
            f"- extra sets: {len(extra_names)}",
            f"- mean jaccard: {mean_jaccard:.6f}",
            f"- median jaccard: {median_jaccard:.6f}",
            f"- recovered missing sets vs baseline_current: {recovered_missing_vs_baseline}",
            "",
        ]
        if not comparison_df.empty:
            report_lines.append("## Top Shared Jaccard Scores")
            report_lines.append("")
            for row in comparison_df.head(15).to_dict(orient="records"):
                report_lines.append(
                    f"- {row['set_name']}: jaccard={float(row['jaccard']):.6f} "
                    f"shared={int(row['shared_n_genes'])} generated={int(row['generated_n_genes'])} "
                    f"reference={int(row['reference_n_genes'])}"
                )
        write_text("\n".join(report_lines) + "\n", config_dir / "comparison_to_reference.v1.md")

        recovered_detail_df = None
        if baseline_missing_set_names is not None:
            recovered_set_names = sorted(baseline_missing_set_names & generated_set_names)
            recovered_detail_df = pd.DataFrame({"set_name": recovered_set_names})
            write_dataframe(recovered_detail_df, config_dir / "recovered_missing_sets_vs_baseline.v1.tsv")
        all_comparison_rows.append(comparison_df.assign(config_name=config_name))

    summary_df = pd.DataFrame(config_summary_rows).sort_values(
        ["n_recovered_missing_vs_baseline", "n_shared_reference_sets", "mean_jaccard", "config_name"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    write_dataframe(summary_df, output_dir / "recovery_sweep_summary.v1.tsv")

    combined_comparison_df = pd.concat(all_comparison_rows, ignore_index=True) if all_comparison_rows else pd.DataFrame()
    if not combined_comparison_df.empty:
        write_dataframe(combined_comparison_df, output_dir / "recovery_sweep_comparison_details.v1.tsv")

    lines = [
        "# Harmonizome Recovery Sweep v1",
        "",
        "## Take-Home Summary",
        "",
    ]
    for row in summary_df.to_dict(orient="records"):
        lines.append(
            f"- {row['config_name']}: recovered_missing_vs_baseline={int(row['n_recovered_missing_vs_baseline'])}, "
            f"shared_reference_sets={int(row['n_shared_reference_sets'])}, "
            f"generated_sets={int(row['n_generated_sets'])}, "
            f"mean_jaccard={float(row['mean_jaccard']):.6f}, "
            f"median_jaccard={float(row['median_jaccard']):.6f}"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This sweep reuses the prepared tissue inputs from the legacy-reproduction run and varies only the DE/filtering sensitivity.",
            "Recovery is measured as the number of legacy sets missing from `baseline_current` that appear under an alternative configuration.",
        ]
    )
    write_text("\n".join(lines) + "\n", output_dir / "findings.v1.md")


if __name__ == "__main__":
    main()
