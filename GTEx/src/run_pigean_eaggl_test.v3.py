#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import itertools
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_pigean_eaggl_test_v3")

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
    parser.add_argument("--pigean_repo", required=True)
    parser.add_argument("--python_executable", default=sys.executable)
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


def format_command_multiline(cmd: list[str]) -> str:
    return " \\\n".join(shlex.quote(part) for part in cmd)


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


def choose_shared_adipose_set(source_to_sets: dict[str, dict[str, list[str]]]) -> str:
    source_names = list(source_to_sets.keys())
    common_names = set(source_to_sets[source_names[0]].keys())
    for source_name in source_names[1:]:
        common_names &= set(source_to_sets[source_name].keys())
    common_adipose = sorted(name for name in common_names if name.startswith("GTEx_AdiposeTissue_"))
    if not common_adipose:
        raise ValueError("no shared adipose tissue gene set found across all 3 GMTs")
    common_up = [name for name in common_adipose if name.endswith("_Up")]
    selected = common_up[0] if common_up else common_adipose[0]
    LOGGER.info("selected shared adipose set: %s n_candidates=%d", selected, len(common_adipose))
    return selected


def build_overlap_tables(selected_set_name: str, selected_sets: dict[str, list[str]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_rows: list[dict[str, object]] = []
    pairwise_rows: list[dict[str, object]] = []
    membership_rows: list[dict[str, object]] = []

    source_names = list(selected_sets.keys())
    source_gene_sets = {source_name: set(genes) for source_name, genes in selected_sets.items()}
    for source_name, genes in selected_sets.items():
        source_rows.append(
            {
                "selected_set_name": selected_set_name,
                "source_name": source_name,
                "n_genes": len(genes),
            }
        )

    for source_a, source_b in itertools.combinations(source_names, 2):
        genes_a = source_gene_sets[source_a]
        genes_b = source_gene_sets[source_b]
        intersection = genes_a & genes_b
        union = genes_a | genes_b
        pairwise_rows.append(
            {
                "selected_set_name": selected_set_name,
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

    all_genes = sorted(set().union(*source_gene_sets.values()))
    for gene in all_genes:
        flags = {source_name: gene in source_gene_sets[source_name] for source_name in source_names}
        membership_rows.append(
            {
                "gene": gene,
                "selected_set_name": selected_set_name,
                **{f"in_{source_name}": int(flags[source_name]) for source_name in source_names},
                "membership_pattern": "|".join(source_name for source_name in source_names if flags[source_name]) or "none",
            }
        )

    source_df = pd.DataFrame(source_rows).sort_values("source_name")
    pairwise_df = pd.DataFrame(pairwise_rows).sort_values(["source_a", "source_b"])
    membership_df = pd.DataFrame(membership_rows)
    LOGGER.info(
        "built overlap tables source_shape=%s pairwise_shape=%s membership_shape=%s",
        source_df.shape,
        pairwise_df.shape,
        membership_df.shape,
    )
    return source_df, pairwise_df, membership_df


def build_membership_pattern_counts(membership_df: pd.DataFrame) -> pd.DataFrame:
    pattern_df = (
        membership_df.groupby("membership_pattern", dropna=False)
        .size()
        .reset_index(name="n_genes")
        .sort_values(["n_genes", "membership_pattern"], ascending=[False, True])
        .reset_index(drop=True)
    )
    LOGGER.info("built membership pattern counts shape=%s", pattern_df.shape)
    return pattern_df


def write_plot_data_md(plot_stem: Path, title: str, tsv_path: Path) -> None:
    md_path = plot_stem.with_suffix(".md")
    lines = [
        f"# {title}",
        "",
        f"- data_tsv: `{tsv_path.name}`",
        f"- pdf_plot: `{plot_stem.name}.pdf`",
        f"- png_plot: `{plot_stem.name}.png`",
        "",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote plot documentation: %s", md_path)


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

draw_plot <- function(device_fn) {
  device_fn()
  par(mar=c(8, 5, 4, 1) + 0.1)
  if (plot_type == "sizes") {
    values <- df$n_genes
    names(values) <- df$source_name
    barplot(values, las=2, col="#4C78A8", main=title, ylab="Genes")
  } else if (plot_type == "jaccard") {
    labels <- paste(df$source_a, "vs", df$source_b)
    values <- df$jaccard
    names(values) <- labels
    barplot(values, las=2, col="#F58518", main=title, ylab="Jaccard")
  } else if (plot_type == "membership") {
    values <- df$n_genes
    names(values) <- df$membership_pattern
    barplot(values, las=2, col="#54A24B", main=title, ylab="Genes")
  } else {
    stop("unknown plot_type")
  }
  invisible(dev.off())
}

draw_plot(function() pdf(pdf_path, width=9, height=6))
draw_plot(function() png(png_path, width=900, height=600))
"""
    cmd = [rscript_executable, "-e", plot_code, plot_type, str(input_tsv), str(pdf_path), str(png_path), title]
    LOGGER.info("running R plot step plot_type=%s input=%s", plot_type, input_tsv)
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"R plotting failed for {plot_type}; see {log_path}")
    LOGGER.info("completed R plot step plot_type=%s returncode=%d", plot_type, proc.returncode)


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


def summarize_factor_table(source_name: str, factors_path: Path) -> dict[str, object]:
    factors_df = pd.read_csv(factors_path, sep="\t")
    top_df = factors_df.sort_values(["any_relevance", "lambda"], ascending=[False, False]).reset_index(drop=True)
    top_labels = top_df["label"].head(5).tolist()
    top_genes = []
    for value in top_df["top_genes"].head(5):
        top_genes.extend([gene for gene in str(value).split(",") if gene])
    unique_top_genes = list(dict.fromkeys(top_genes))
    summary = {
        "source_name": source_name,
        "n_factors": int(factors_df.shape[0]),
        "max_any_relevance": float(top_df["any_relevance"].max()),
        "median_any_relevance": float(top_df["any_relevance"].median()),
        "top_factor_label": str(top_df.iloc[0]["label"]),
        "top_factor_any_relevance": float(top_df.iloc[0]["any_relevance"]),
        "top_factor_lambda": float(top_df.iloc[0]["lambda"]),
        "top5_labels": ", ".join(top_labels),
        "top5_unique_genes": ", ".join(unique_top_genes[:10]),
    }
    LOGGER.info("summarized factors for source=%s summary=%s", source_name, summary)
    return summary


def build_similarity_tables(factor_summary_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    records = factor_summary_df.to_dict("records")
    for row_a, row_b in itertools.combinations(records, 2):
        labels_a = {item.strip() for item in str(row_a["top5_labels"]).split(",") if item.strip()}
        labels_b = {item.strip() for item in str(row_b["top5_labels"]).split(",") if item.strip()}
        genes_a = {item.strip() for item in str(row_a["top5_unique_genes"]).split(",") if item.strip()}
        genes_b = {item.strip() for item in str(row_b["top5_unique_genes"]).split(",") if item.strip()}
        rows.append(
            {
                "source_a": row_a["source_name"],
                "source_b": row_b["source_name"],
                "top5_label_overlap_n": len(labels_a & labels_b),
                "top5_label_jaccard": len(labels_a & labels_b) / len(labels_a | labels_b) if labels_a | labels_b else 0.0,
                "top_gene_overlap_n": len(genes_a & genes_b),
                "top_gene_jaccard": len(genes_a & genes_b) / len(genes_a | genes_b) if genes_a | genes_b else 0.0,
            }
        )
    similarity_df = pd.DataFrame(rows).sort_values(["source_a", "source_b"]).reset_index(drop=True)
    LOGGER.info("built factor similarity table shape=%s", similarity_df.shape)
    return similarity_df


def write_report(
    output_dir: Path,
    *,
    selected_set_name: str,
    source_overlap_df: pd.DataFrame,
    pairwise_overlap_df: pd.DataFrame,
    membership_pattern_df: pd.DataFrame,
    run_summary_df: pd.DataFrame,
    factor_summary_df: pd.DataFrame,
    factor_similarity_df: pd.DataFrame,
) -> Path:
    report_path = output_dir / "pigean_eaggl_test.v3.md"
    full_overlap_n = int(membership_pattern_df.loc[membership_pattern_df["membership_pattern"].str.count("\\|") == 2, "n_genes"].sum())
    lines = [
        "# PIGEAN EAGGL Test v3",
        "",
        f"- selected_set_name: `{selected_set_name}`",
        f"- n_sources: {int(source_overlap_df.shape[0])}",
        f"- n_shared_across_all_three: {full_overlap_n}",
        "",
        "## Gene-set overlap",
        "",
    ]
    for _, row in source_overlap_df.iterrows():
        lines.append(f"- {row['source_name']}: n_genes={int(row['n_genes'])}")
    lines.append("")
    for _, row in pairwise_overlap_df.iterrows():
        lines.append(
            f"- {row['source_a']} vs {row['source_b']}: intersection={int(row['n_intersection'])}, "
            f"union={int(row['n_union'])}, jaccard={row['jaccard']:.3f}, overlap_coefficient={row['overlap_coefficient']:.3f}"
        )
    lines.extend(["", "## EAGGL Take-home Messages", ""])
    for _, row in factor_summary_df.iterrows():
        lines.append(
            f"- {row['source_name']}: top factor `{row['top_factor_label']}` "
            f"(any_relevance={row['top_factor_any_relevance']:.3f}, lambda={row['top_factor_lambda']:.4f}); "
            f"top programs were {row['top5_labels']}; recurring top genes included {row['top5_unique_genes']}."
        )
    lines.extend(["", "## Cross-run comparison", ""])
    for _, row in factor_similarity_df.iterrows():
        lines.append(
            f"- {row['source_a']} vs {row['source_b']}: top5_label_overlap_n={int(row['top5_label_overlap_n'])}, "
            f"top5_label_jaccard={row['top5_label_jaccard']:.3f}, top_gene_overlap_n={int(row['top_gene_overlap_n'])}, "
            f"top_gene_jaccard={row['top_gene_jaccard']:.3f}"
        )
    lines.extend(["", "## Run outputs", ""])
    for _, row in run_summary_df.iterrows():
        lines.append(
            f"- {row['source_name']}: pigean_bundle=`{Path(row['pigean_bundle_out']).name}`, "
            f"eaggl_factors=`{Path(row['eaggl_factors_out']).name}`, n_input_genes={int(row['n_input_genes'])}"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote report: %s", report_path)
    return report_path


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_pigean_eaggl_test.v3.log")

    pigean_repo = Path(args.pigean_repo).resolve()
    if not pigean_repo.exists():
        raise FileNotFoundError(f"pigean repo not found: {pigean_repo}")

    bundle_data_dir = pigean_repo / "bundles" / "model_small-2026.02.22" / "data"
    x_in_path = bundle_data_dir / "gene_set_list_msigdb_nohp.txt"
    gene_map_path = bundle_data_dir / "portal_gencode.gene.map"
    gene_loc_path = bundle_data_dir / "NCBI37.3.plink.gene.loc"
    required_paths = [x_in_path, gene_map_path, gene_loc_path]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        raise FileNotFoundError("missing bundled PIGEAN inputs: " + ", ".join(missing_paths))

    source_to_sets: dict[str, dict[str, list[str]]] = {}
    source_manifest_rows: list[dict[str, object]] = []
    for source_spec in SOURCE_SPECS:
        source_name = str(source_spec["source_name"])
        gmt_path = (repo_root / str(source_spec["gmt_gz"])).resolve()
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

    selected_set_name = choose_shared_adipose_set(source_to_sets)
    selected_sets = {source_name: source_to_sets[source_name][selected_set_name] for source_name in source_to_sets}

    selected_rows = [
        {
            "source_name": source_name,
            "selected_set_name": selected_set_name,
            "n_genes": len(genes),
            "source_gmt_gz": str((repo_root / next(spec["gmt_gz"] for spec in SOURCE_SPECS if spec["source_name"] == source_name)).resolve()),
        }
        for source_name, genes in selected_sets.items()
    ]
    selected_df = pd.DataFrame(selected_rows).sort_values("source_name")
    write_dataframe(selected_df, output_dir / "selected_gene_sets.v1.tsv")

    source_overlap_df, pairwise_overlap_df, membership_df = build_overlap_tables(selected_set_name, selected_sets)
    membership_pattern_df = build_membership_pattern_counts(membership_df)
    write_dataframe(source_overlap_df, output_dir / "gene_set_sizes.v1.tsv")
    write_dataframe(pairwise_overlap_df, output_dir / "pairwise_gene_overlap.v1.tsv")
    write_dataframe(membership_df, output_dir / "gene_membership.v1.tsv")
    write_dataframe(membership_pattern_df, output_dir / "gene_membership_patterns.v1.tsv")

    plot_specs = [
        ("sizes", output_dir / "gene_set_sizes_plot.v1", output_dir / "gene_set_sizes.v1.tsv", "Shared Adipose Set Gene Counts"),
        ("jaccard", output_dir / "pairwise_gene_overlap_plot.v1", output_dir / "pairwise_gene_overlap.v1.tsv", "Pairwise Gene-set Jaccard"),
        ("membership", output_dir / "gene_membership_patterns_plot.v1", output_dir / "gene_membership_patterns.v1.tsv", "Gene Membership Patterns"),
    ]
    for plot_type, plot_stem, input_tsv, title in plot_specs:
        run_r_plot(
            rscript_executable=args.rscript_executable,
            plot_type=plot_type,
            input_tsv=input_tsv,
            pdf_path=plot_stem.with_suffix(".pdf"),
            png_path=plot_stem.with_suffix(".png"),
            title=title,
            log_path=plot_stem.with_suffix(".log"),
        )
        write_plot_data_md(plot_stem, title, input_tsv)

    env = os.environ.copy()
    src_root = str(pigean_repo / "src")
    env["PYTHONPATH"] = src_root if not env.get("PYTHONPATH") else src_root + os.pathsep + env["PYTHONPATH"]
    env["PYTHONHASHSEED"] = "0"

    run_rows: list[dict[str, object]] = []
    factor_summary_rows: list[dict[str, object]] = []
    for source_name, genes in selected_sets.items():
        source_out_dir = output_dir / source_name
        source_out_dir.mkdir(parents=True, exist_ok=True)
        gene_list_path = source_out_dir / "selected_gene_list.v1.txt"
        gene_list_path.write_text("\n".join(genes) + "\n", encoding="utf-8")
        LOGGER.info("wrote gene list source=%s path=%s n_genes=%d", source_name, gene_list_path, len(genes))

        pigean_gene_stats = source_out_dir / "pigean.gene_stats.v1.tsv"
        pigean_gene_set_stats = source_out_dir / "pigean.gene_set_stats.v1.tsv"
        pigean_params = source_out_dir / "pigean.params.v1.tsv"
        pigean_bundle = source_out_dir / "pigean_to_eaggl.v1.tar.gz"
        pigean_cmd = build_pigean_cmd(
            python_executable=args.python_executable,
            x_in_path=x_in_path,
            gene_map_path=gene_map_path,
            gene_loc_path=gene_loc_path,
            gene_list_path=gene_list_path,
            gene_stats_out=pigean_gene_stats,
            gene_set_stats_out=pigean_gene_set_stats,
            params_out=pigean_params,
            bundle_out=pigean_bundle,
        )
        run_command(
            step_name=f"pigean_beta_tildes[{source_name}]",
            cmd=pigean_cmd,
            cwd=pigean_repo,
            env=env,
            stdout_path=source_out_dir / "pigean.stdout.v1.log",
            stderr_path=source_out_dir / "pigean.stderr.v1.log",
        )

        eaggl_factors = source_out_dir / "eaggl.factors.v1.tsv"
        eaggl_gene_set_clusters = source_out_dir / "eaggl.gene_set_clusters.v1.tsv"
        eaggl_gene_clusters = source_out_dir / "eaggl.gene_clusters.v1.tsv"
        eaggl_params = source_out_dir / "eaggl.params.v1.tsv"
        eaggl_cmd = build_eaggl_cmd(
            python_executable=args.python_executable,
            bundle_in=pigean_bundle,
            factors_out=eaggl_factors,
            gene_set_clusters_out=eaggl_gene_set_clusters,
            gene_clusters_out=eaggl_gene_clusters,
            params_out=eaggl_params,
        )
        run_command(
            step_name=f"eaggl_factor[{source_name}]",
            cmd=eaggl_cmd,
            cwd=pigean_repo,
            env=env,
            stdout_path=source_out_dir / "eaggl.stdout.v1.log",
            stderr_path=source_out_dir / "eaggl.stderr.v1.log",
        )
        run_rows.append(
            {
                "source_name": source_name,
                "selected_set_name": selected_set_name,
                "n_input_genes": len(genes),
                "gene_list_path": str(gene_list_path),
                "pigean_bundle_out": str(pigean_bundle),
                "pigean_gene_stats_out": str(pigean_gene_stats),
                "pigean_gene_set_stats_out": str(pigean_gene_set_stats),
                "pigean_params_out": str(pigean_params),
                "eaggl_factors_out": str(eaggl_factors),
                "eaggl_gene_set_clusters_out": str(eaggl_gene_set_clusters),
                "eaggl_gene_clusters_out": str(eaggl_gene_clusters),
                "eaggl_params_out": str(eaggl_params),
                "pigean_command": shlex.join(pigean_cmd),
                "eaggl_command": shlex.join(eaggl_cmd),
            }
        )
        factor_summary_rows.append(summarize_factor_table(source_name, eaggl_factors))

    run_summary_df = pd.DataFrame(run_rows).sort_values("source_name")
    factor_summary_df = pd.DataFrame(factor_summary_rows).sort_values("source_name")
    factor_similarity_df = build_similarity_tables(factor_summary_df)
    write_dataframe(run_summary_df, output_dir / "run_summary.v1.tsv")
    write_dataframe(factor_summary_df, output_dir / "factor_summary.v1.tsv")
    write_dataframe(factor_similarity_df, output_dir / "factor_similarity.v1.tsv")

    write_report(
        output_dir,
        selected_set_name=selected_set_name,
        source_overlap_df=source_overlap_df,
        pairwise_overlap_df=pairwise_overlap_df,
        membership_pattern_df=membership_pattern_df,
        run_summary_df=run_summary_df,
        factor_summary_df=factor_summary_df,
        factor_similarity_df=factor_similarity_df,
    )


if __name__ == "__main__":
    main()
