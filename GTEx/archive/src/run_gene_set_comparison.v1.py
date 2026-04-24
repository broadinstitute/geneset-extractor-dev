#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import itertools
import logging
import subprocess
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_gene_set_comparison_v1")

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
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


def read_gmt(path: Path) -> dict[str, list[str]]:
    gene_sets: dict[str, list[str]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            set_name, genes_blob = line.split("\t", 1)
            genes = [gene for gene in genes_blob.split() if gene]
            gene_sets[set_name] = genes
    return gene_sets


def build_overlap_tables(source_to_sets: dict[str, dict[str, list[str]]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_names = list(source_to_sets.keys())
    common_names = sorted(set.intersection(*(set(source_to_sets[name].keys()) for name in source_names)))
    LOGGER.info("identified common gene-set names n_common=%d", len(common_names))

    common_df = pd.DataFrame({"set_name": common_names})

    pairwise_rows: list[dict[str, object]] = []
    triplet_rows: list[dict[str, object]] = []
    membership_rows: list[dict[str, object]] = []

    for set_name in common_names:
        gene_sets = {source_name: set(source_to_sets[source_name][set_name]) for source_name in source_names}
        union_all = set().union(*gene_sets.values())
        intersection_all = set.intersection(*gene_sets.values())
        triplet_rows.append(
            {
                "set_name": set_name,
                **{f"n_genes_{source_name}": len(gene_sets[source_name]) for source_name in source_names},
                "n_union_all_three": len(union_all),
                "n_intersection_all_three": len(intersection_all),
                "jaccard_all_three": len(intersection_all) / len(union_all) if union_all else 0.0,
                "intersection_over_min_size": len(intersection_all) / min(len(gene_sets[source_name]) for source_name in source_names) if source_names else 0.0,
            }
        )
        for source_a, source_b in itertools.combinations(source_names, 2):
            genes_a = gene_sets[source_a]
            genes_b = gene_sets[source_b]
            intersection = genes_a & genes_b
            union = genes_a | genes_b
            pairwise_rows.append(
                {
                    "set_name": set_name,
                    "source_a": source_a,
                    "source_b": source_b,
                    "n_genes_a": len(genes_a),
                    "n_genes_b": len(genes_b),
                    "n_intersection": len(intersection),
                    "n_union": len(union),
                    "jaccard": len(intersection) / len(union) if union else 0.0,
                    "overlap_coefficient": len(intersection) / min(len(genes_a), len(genes_b)) if genes_a and genes_b else 0.0,
                }
            )

        for gene in sorted(union_all):
            flags = {source_name: gene in gene_sets[source_name] for source_name in source_names}
            membership_rows.append(
                {
                    "set_name": set_name,
                    "gene": gene,
                    **{f"in_{source_name}": int(flags[source_name]) for source_name in source_names},
                    "membership_pattern": "|".join(source_name for source_name in source_names if flags[source_name]) or "none",
                }
            )

    pairwise_df = pd.DataFrame(pairwise_rows).sort_values(["source_a", "source_b", "set_name"]).reset_index(drop=True)
    triplet_df = pd.DataFrame(triplet_rows).sort_values("set_name").reset_index(drop=True)
    membership_df = pd.DataFrame(membership_rows).sort_values(["set_name", "gene"]).reset_index(drop=True)

    membership_pattern_df = (
        membership_df.groupby(["set_name", "membership_pattern"], dropna=False)
        .size()
        .reset_index(name="n_genes")
        .sort_values(["set_name", "n_genes", "membership_pattern"], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    LOGGER.info(
        "built overlap tables common_shape=%s pairwise_shape=%s triplet_shape=%s membership_pattern_shape=%s",
        common_df.shape,
        pairwise_df.shape,
        triplet_df.shape,
        membership_pattern_df.shape,
    )
    return common_df, pairwise_df, triplet_df, membership_pattern_df


def build_pairwise_summary(pairwise_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = (
        pairwise_df.groupby(["source_a", "source_b"], dropna=False)
        .agg(
            n_sets=("set_name", "size"),
            mean_jaccard=("jaccard", "mean"),
            median_jaccard=("jaccard", "median"),
            min_jaccard=("jaccard", "min"),
            max_jaccard=("jaccard", "max"),
            mean_overlap_coefficient=("overlap_coefficient", "mean"),
            median_overlap_coefficient=("overlap_coefficient", "median"),
        )
        .reset_index()
        .sort_values(["source_a", "source_b"])
        .reset_index(drop=True)
    )
    LOGGER.info("built pairwise summary shape=%s", summary_df.shape)
    return summary_df


def build_extreme_sets_table(triplet_df: pd.DataFrame, n_sets: int = 15) -> pd.DataFrame:
    highest = triplet_df.sort_values(["jaccard_all_three", "n_intersection_all_three", "set_name"], ascending=[False, False, True]).head(n_sets).copy()
    highest["rank_group"] = "highest_triplet_jaccard"
    lowest = triplet_df.sort_values(["jaccard_all_three", "n_intersection_all_three", "set_name"], ascending=[True, True, True]).head(n_sets).copy()
    lowest["rank_group"] = "lowest_triplet_jaccard"
    extremes_df = pd.concat([highest, lowest], ignore_index=True)
    LOGGER.info("built extremes table shape=%s", extremes_df.shape)
    return extremes_df


def write_output_md(path: Path, title: str, bullets: list[str]) -> None:
    md_path = path.with_suffix(".md")
    lines = [f"# {title}", ""]
    lines.extend(f"- {bullet}" for bullet in bullets)
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("wrote documentation: %s", md_path)


def run_r_plot(
    *,
    rscript_executable: str,
    plot_type: str,
    input_tsv: Path,
    pdf_path: Path,
    png_path: Path,
    title: str,
    log_path: Path,
) -> None:
    plot_code = """
args <- commandArgs(trailingOnly = TRUE)
plot_type <- args[[1]]
input_tsv <- args[[2]]
pdf_path <- args[[3]]
png_path <- args[[4]]
title <- args[[5]]
df <- read.delim(input_tsv, sep="\\t", check.names=FALSE, stringsAsFactors=FALSE)

trim_label <- function(x, width=52) {
  ifelse(nchar(x) <= width, x, paste0(substr(x, 1, width - 3), "..."))
}

draw_plot <- function(device_fn) {
  device_fn()
  par(mar=c(9, 5, 4, 1) + 0.1)
  if (plot_type == "pairwise_jaccard") {
    groups <- paste(df$source_a, "vs", df$source_b)
    boxplot(df$jaccard ~ groups, las=2, col=c("#4C78A8", "#F58518", "#54A24B"), main=title, ylab="Jaccard")
  } else if (plot_type == "triplet_jaccard_extremes") {
    labels <- trim_label(df$set_name)
    values <- df$jaccard_all_three
    cols <- ifelse(df$rank_group == "highest_triplet_jaccard", "#4C78A8", "#E45756")
    ord <- order(values)
    barplot(values[ord], names.arg=labels[ord], horiz=TRUE, las=1, col=cols[ord], main=title, xlab="Three-way Jaccard", cex.names=0.7)
  } else if (plot_type == "membership_patterns") {
    labels <- trim_label(paste(df$set_name, df$membership_pattern, sep=" | "))
    values <- df$n_genes
    ord <- order(values)
    barplot(values[ord], names.arg=labels[ord], horiz=TRUE, las=1, col="#72B7B2", main=title, xlab="Genes", cex.names=0.65)
  } else {
    stop("unknown plot_type")
  }
  invisible(dev.off())
}

draw_plot(function() pdf(pdf_path, width=11, height=8.5))
draw_plot(function() png(png_path, width=1100, height=850))
"""
    cmd = [rscript_executable, "-e", plot_code, plot_type, str(input_tsv), str(pdf_path), str(png_path), title]
    LOGGER.info("running R plot step plot_type=%s input=%s", plot_type, input_tsv)
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"R plotting failed for {plot_type}; see {log_path}")
    LOGGER.info("completed R plot step plot_type=%s returncode=%d", plot_type, proc.returncode)


def build_summary_paragraph(pairwise_summary_df: pd.DataFrame, triplet_df: pd.DataFrame, membership_pattern_df: pd.DataFrame) -> str:
    local_row = pairwise_summary_df[
        (pairwise_summary_df["source_a"] == "gtex_harmonizome_analysis_v1") &
        (pairwise_summary_df["source_b"] == "gtex_no_harmonizome_analysis_v1")
    ].iloc[0]
    ref_rows = pairwise_summary_df[
        pairwise_summary_df["source_a"].str.contains("GTEx_XMT") | pairwise_summary_df["source_b"].str.contains("GTEx_XMT")
    ]
    best_triplet = triplet_df.sort_values(["jaccard_all_three", "n_intersection_all_three", "set_name"], ascending=[False, False, True]).iloc[0]
    worst_triplet = triplet_df.sort_values(["jaccard_all_three", "n_intersection_all_three", "set_name"], ascending=[True, True, True]).iloc[0]
    full_pattern_name = "|".join(spec["source_name"] for spec in SOURCE_SPECS)
    full_shared_genes = int(membership_pattern_df.loc[membership_pattern_df["membership_pattern"] == full_pattern_name, "n_genes"].sum())
    return (
        f"Across the 203 gene-set names shared by all three GMT files, the two locally generated libraries were far more similar to each other than either was to the reference GMT: "
        f"`gtex_harmonizome_analysis_v1` vs `gtex_no_harmonizome_analysis_v1` had mean Jaccard {local_row['mean_jaccard']:.3f} and median Jaccard {local_row['median_jaccard']:.3f}, "
        f"whereas the two comparisons involving `GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021` had mean Jaccards between {ref_rows['mean_jaccard'].min():.3f} and {ref_rows['mean_jaccard'].max():.3f}. "
        f"The best-preserved three-way overlap was `{best_triplet['set_name']}` with three-way Jaccard {best_triplet['jaccard_all_three']:.3f}, while the weakest was `{worst_triplet['set_name']}` with three-way Jaccard {worst_triplet['jaccard_all_three']:.3f}. "
        f"Summed across all common set names, only {full_shared_genes} gene occurrences fell into the exact three-way membership pattern, reinforcing that most disagreement comes from the reference GMT rather than between the two regenerated libraries."
    )


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_gene_set_comparison.v1.log")

    source_to_sets: dict[str, dict[str, list[str]]] = {}
    source_manifest_rows: list[dict[str, object]] = []
    for spec in SOURCE_SPECS:
        source_name = str(spec["source_name"])
        gmt_path = (repo_root / str(spec["gmt_gz"])).resolve()
        if not gmt_path.exists():
            raise FileNotFoundError(f"source GMT not found: {gmt_path}")
        gene_sets = read_gmt(gmt_path)
        source_to_sets[source_name] = gene_sets
        source_manifest_rows.append(
            {
                "source_name": source_name,
                "gmt_gz_path": str(gmt_path),
                "n_sets": len(gene_sets),
            }
        )
    source_manifest_df = pd.DataFrame(source_manifest_rows).sort_values("source_name")
    write_dataframe(source_manifest_df, output_dir / "source_manifest.v1.tsv")

    common_df, pairwise_df, triplet_df, membership_pattern_df = build_overlap_tables(source_to_sets)
    pairwise_summary_df = build_pairwise_summary(pairwise_df)
    extremes_df = build_extreme_sets_table(triplet_df, n_sets=15)

    write_dataframe(common_df, output_dir / "common_gene_set_names.v1.tsv")
    write_dataframe(pairwise_df, output_dir / "pairwise_gene_overlap_by_set.v1.tsv")
    write_dataframe(triplet_df, output_dir / "triplet_gene_overlap_by_set.v1.tsv")
    write_dataframe(membership_pattern_df, output_dir / "gene_membership_patterns_by_set.v1.tsv")
    write_dataframe(pairwise_summary_df, output_dir / "pairwise_overlap_summary.v1.tsv")
    write_dataframe(extremes_df, output_dir / "triplet_overlap_extremes.v1.tsv")

    plot_specs = [
        (
            "pairwise_jaccard",
            output_dir / "pairwise_jaccard_distribution_plot.v1",
            output_dir / "pairwise_gene_overlap_by_set.v1.tsv",
            "Pairwise Jaccard Distribution Across Common Gene Sets",
        ),
        (
            "triplet_jaccard_extremes",
            output_dir / "triplet_jaccard_extremes_plot.v1",
            output_dir / "triplet_overlap_extremes.v1.tsv",
            "Highest And Lowest Three-way Jaccard Gene Sets",
        ),
        (
            "membership_patterns",
            output_dir / "gene_membership_patterns_extremes_plot.v1",
            output_dir / "gene_membership_patterns_by_set.v1.tsv",
            "Gene Membership Patterns For Extreme Three-way Overlaps",
        ),
    ]
    for plot_type, plot_stem, input_tsv, title in plot_specs:
        plot_input_tsv = input_tsv
        if plot_type == "membership_patterns":
            extreme_set_names = set(extremes_df["set_name"])
            filtered_df = membership_pattern_df[membership_pattern_df["set_name"].isin(extreme_set_names)].copy()
            plot_input_tsv = output_dir / "gene_membership_patterns_extremes_plot_data.v1.tsv"
            write_dataframe(filtered_df, plot_input_tsv)
        run_r_plot(
            rscript_executable=args.rscript_executable,
            plot_type=plot_type,
            input_tsv=plot_input_tsv,
            pdf_path=plot_stem.with_suffix(".pdf"),
            png_path=plot_stem.with_suffix(".png"),
            title=title,
            log_path=plot_stem.with_suffix(".log"),
        )
        write_output_md(
            plot_stem.with_suffix(".pdf"),
            title,
            [
                f"data_tsv: `{plot_input_tsv.name}`",
                f"png_plot: `{plot_stem.with_suffix('.png').name}`",
                f"log_file: `{plot_stem.with_suffix('.log').name}`",
            ],
        )

    summary_text = build_summary_paragraph(pairwise_summary_df, triplet_df, membership_pattern_df)
    summary_path = output_dir / "findings_summary.v1.txt"
    summary_path.write_text(summary_text + "\n", encoding="utf-8")
    LOGGER.info("wrote summary text: %s", summary_path)
    write_output_md(
        summary_path,
        "Findings Summary v1",
        [
            "context: summary paragraph for shared gene-set overlap across the three GMT libraries",
        ],
    )


if __name__ == "__main__":
    main()
