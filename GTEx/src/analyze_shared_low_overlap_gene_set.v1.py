#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("analyze_shared_low_overlap_gene_set_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set_name", default="GTEx_Skin_20-29_vs_60-69_Up")
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--reproduced_gmt_gz", required=True)
    parser.add_argument("--comparison_to_reference_tsv", required=True)
    parser.add_argument("--deg_tsv", required=True)
    parser.add_argument("--comparison_manifest_tsv", required=True)
    parser.add_argument("--processed_matrix_tsv", default="")
    parser.add_argument("--output_dir", required=True)
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
    out: dict[str, list[str]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                out[parts[0]] = [gene for gene in parts[1:] if gene]
    LOGGER.info("loaded GMT path=%s n_sets=%d", path, len(out))
    return out


def classify_legacy_gene(row: pd.Series) -> str:
    if not bool(row["present_in_reproduction_deg"]):
        return "absent_from_reproduced_deg_table"
    if not bool(row["same_direction_as_set"]):
        return "present_but_wrong_logfc_direction"
    if not bool(row["significant_in_reproduction"]):
        return "present_same_direction_but_not_adj_p_significant"
    if pd.isna(row["rank_within_reproduced_sig_direction"]) or int(row["rank_within_reproduced_sig_direction"]) > 250:
        return "present_significant_same_direction_but_ranked_below_top_250"
    return "present_and_would_have_been_in_reproduced_set"


def calculate_overlap_metrics(candidate_genes: list[str], legacy_gene_set: set[str]) -> dict[str, object]:
    candidate_gene_set = set(candidate_genes)
    shared_n = len(candidate_gene_set & legacy_gene_set)
    union_n = len(candidate_gene_set | legacy_gene_set)
    return {
        "candidate_n_genes": len(candidate_genes),
        "shared_n_genes": shared_n,
        "legacy_n_genes": len(legacy_gene_set),
        "jaccard": (shared_n / union_n) if union_n else 0.0,
        "legacy_recall": (shared_n / len(legacy_gene_set)) if legacy_gene_set else 0.0,
        "candidate_precision": (shared_n / len(candidate_genes)) if candidate_genes else 0.0,
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "analyze_shared_low_overlap_gene_set.v1.log")

    reference_sets = read_gmt(Path(args.reference_gmt_gz).resolve())
    reproduced_sets = read_gmt(Path(args.reproduced_gmt_gz).resolve())
    set_name = args.set_name
    if set_name not in reference_sets:
        raise ValueError(f"set not found in reference GMT: {set_name}")
    if set_name not in reproduced_sets:
        raise ValueError(f"set not found in reproduced GMT: {set_name}")

    comparison_id, direction = set_name.rsplit("_", 1)
    legacy_genes = reference_sets[set_name]
    reproduced_genes = reproduced_sets[set_name]
    legacy_gene_set = set(legacy_genes)
    reproduced_gene_set = set(reproduced_genes)
    shared_gene_set = legacy_gene_set & reproduced_gene_set
    legacy_only_genes = [gene for gene in legacy_genes if gene not in reproduced_gene_set]
    reproduced_only_genes = [gene for gene in reproduced_genes if gene not in legacy_gene_set]
    LOGGER.info(
        "selected set=%s legacy=%d reproduced=%d shared=%d",
        set_name,
        len(legacy_genes),
        len(reproduced_genes),
        len(shared_gene_set),
    )

    comparison_df = pd.read_csv(args.comparison_to_reference_tsv, sep="\t", dtype=str)
    manifest_df = pd.read_csv(args.comparison_manifest_tsv, sep="\t", dtype=str)
    deg_df = pd.read_csv(args.deg_tsv, sep="\t", dtype=str)
    LOGGER.info("comparison-to-reference shape=%s", comparison_df.shape)
    LOGGER.info("comparison manifest shape=%s", manifest_df.shape)
    LOGGER.info("DEG table shape=%s", deg_df.shape)

    overlap_row = comparison_df.loc[comparison_df["set_name"] == set_name].copy()
    if overlap_row.empty:
        raise ValueError(f"set not found in comparison table: {set_name}")
    manifest_row = manifest_df.loc[manifest_df["comparison_id"] == comparison_id].copy()
    if manifest_row.empty:
        raise ValueError(f"comparison not found in comparison manifest: {comparison_id}")

    processed_matrix_summary: dict[str, object] = {}
    if args.processed_matrix_tsv:
        processed_matrix_tsv = Path(args.processed_matrix_tsv).resolve()
        matrix_gene_df = pd.read_csv(processed_matrix_tsv, sep="\t", usecols=["gene_symbol"], dtype=str)
        matrix_gene_symbols = matrix_gene_df["gene_symbol"].dropna().astype(str)
        processed_matrix_summary = {
            "processed_matrix_tsv": str(processed_matrix_tsv),
            "processed_matrix_rows": int(matrix_gene_symbols.shape[0]),
            "processed_matrix_unique_gene_symbols": int(matrix_gene_symbols.nunique()),
            "processed_matrix_duplicate_gene_symbol_rows": int(matrix_gene_symbols.shape[0] - matrix_gene_symbols.nunique()),
            "processed_matrix_numeric_gene_symbols": int(matrix_gene_symbols.str.fullmatch(r"\d+").sum()),
        }
        write_dataframe(pd.DataFrame([processed_matrix_summary]), output_dir / "processed_matrix_identifier_summary.v1.tsv")

    comparison_deg_df = deg_df.loc[deg_df["comparison_id"] == comparison_id].copy()
    if comparison_deg_df.empty:
        raise ValueError(f"comparison not found in DEG table: {comparison_id}")
    comparison_deg_df["logFC"] = pd.to_numeric(comparison_deg_df["logFC"], errors="coerce")
    comparison_deg_df["pvalue"] = pd.to_numeric(comparison_deg_df["pvalue"], errors="coerce")
    comparison_deg_df["adj_p_val"] = pd.to_numeric(comparison_deg_df["adj_p_val"], errors="coerce")
    comparison_deg_df["in_legacy_gmt"] = comparison_deg_df["gene_symbol"].isin(legacy_gene_set)
    comparison_deg_df["in_reproduced_gmt"] = comparison_deg_df["gene_symbol"].isin(reproduced_gene_set)
    comparison_deg_df["same_direction_as_set"] = comparison_deg_df["logFC"] > 0 if direction == "Up" else comparison_deg_df["logFC"] < 0
    comparison_deg_df["significant_in_reproduction"] = comparison_deg_df["adj_p_val"] < 0.05

    sig_direction_df = comparison_deg_df.loc[
        comparison_deg_df["same_direction_as_set"] & comparison_deg_df["significant_in_reproduction"]
    ].copy()
    sig_direction_df = sig_direction_df.sort_values(["adj_p_val", "gene_symbol"]).reset_index(drop=True)
    sig_direction_df["rank_within_reproduced_sig_direction"] = range(1, sig_direction_df.shape[0] + 1)
    comparison_deg_df = comparison_deg_df.merge(
        sig_direction_df.loc[:, ["gene_symbol", "rank_within_reproduced_sig_direction"]],
        on="gene_symbol",
        how="left",
    )

    legacy_status_df = pd.DataFrame(
        {
            "gene_symbol": legacy_genes,
            "legacy_order": range(1, len(legacy_genes) + 1),
            "in_legacy_gmt": True,
            "in_reproduced_gmt": [gene in reproduced_gene_set for gene in legacy_genes],
        }
    )
    legacy_status_df = legacy_status_df.merge(
        comparison_deg_df.loc[
            :,
            [
                "gene_symbol",
                "logFC",
                "pvalue",
                "adj_p_val",
                "same_direction_as_set",
                "significant_in_reproduction",
                "rank_within_reproduced_sig_direction",
            ],
        ],
        on="gene_symbol",
        how="left",
    )
    legacy_status_df["present_in_reproduction_deg"] = legacy_status_df["logFC"].notna()
    legacy_status_df["exclusion_reason_from_reproduced_set"] = legacy_status_df.apply(classify_legacy_gene, axis=1)

    reproduced_status_df = pd.DataFrame(
        {
            "gene_symbol": reproduced_genes,
            "reproduced_order": range(1, len(reproduced_genes) + 1),
            "in_reproduced_gmt": True,
            "in_legacy_gmt": [gene in legacy_gene_set for gene in reproduced_genes],
        }
    )
    reproduced_status_df = reproduced_status_df.merge(
        comparison_deg_df.loc[
            :,
            [
                "gene_symbol",
                "logFC",
                "pvalue",
                "adj_p_val",
                "same_direction_as_set",
                "significant_in_reproduction",
                "rank_within_reproduced_sig_direction",
            ],
        ],
        on="gene_symbol",
        how="left",
    )
    reproduced_status_df["inclusion_reason_in_reproduced_set"] = "adj_p_val_lt_0.05_same_direction_ranked_top_250"

    legacy_reason_summary_df = (
        legacy_status_df.groupby("exclusion_reason_from_reproduced_set", as_index=False)
        .size()
        .rename(columns={"size": "n_legacy_genes"})
        .sort_values(["n_legacy_genes", "exclusion_reason_from_reproduced_set"], ascending=[False, True])
        .reset_index(drop=True)
    )

    reproduced_inclusion_summary_df = pd.DataFrame(
        [
            {
                "inclusion_reason_in_reproduced_set": "adj_p_val_lt_0.05_same_direction_ranked_top_250",
                "n_reproduced_genes": len(reproduced_genes),
            }
        ]
    )

    sweep_rows: list[dict[str, object]] = []
    same_direction_df = comparison_deg_df.loc[comparison_deg_df["same_direction_as_set"]].copy()
    threshold_configs = [
        ("adj_p_val", cutoff, 0.0)
        for cutoff in [0.001, 0.005, 0.01, 0.025, 0.05, 0.10, 0.25, 0.50, 1.00]
    ]
    threshold_configs.extend(
        [
            ("pvalue", cutoff, 0.0)
            for cutoff in [1e-6, 1e-5, 1e-4, 0.001, 0.005, 0.01, 0.025, 0.05, 0.10, 0.25, 0.50, 1.00]
        ]
    )
    threshold_configs.extend(
        [
            ("adj_p_val", cutoff, abs_logfc_min)
            for cutoff in [0.05, 0.10, 0.25, 0.50, 1.00]
            for abs_logfc_min in [0.1, 0.25, 0.5, 1.0]
        ]
    )
    top_k_values: list[int | None] = [50, 100, 250, 500, 1000, 2500, None]
    for score_metric, cutoff, abs_logfc_min in threshold_configs:
        filtered_df = same_direction_df.loc[
            same_direction_df[score_metric].notna()
            & (same_direction_df[score_metric] <= cutoff)
            & (same_direction_df["logFC"].abs() >= abs_logfc_min)
        ].copy()
        filtered_df = filtered_df.sort_values([score_metric, "gene_symbol"]).reset_index(drop=True)
        for top_k in top_k_values:
            candidate_df = filtered_df if top_k is None else filtered_df.head(top_k)
            candidate_genes = candidate_df["gene_symbol"].dropna().astype(str).tolist()
            metrics = calculate_overlap_metrics(candidate_genes, legacy_gene_set)
            sweep_rows.append(
                {
                    "score_metric": score_metric,
                    "score_cutoff": cutoff,
                    "abs_logfc_min": abs_logfc_min,
                    "top_k": "all" if top_k is None else top_k,
                    "eligible_same_direction_genes": int(filtered_df.shape[0]),
                    **metrics,
                }
            )
    threshold_sweep_df = pd.DataFrame(sweep_rows).sort_values(
        ["jaccard", "shared_n_genes", "candidate_n_genes", "score_metric", "score_cutoff", "abs_logfc_min", "top_k"],
        ascending=[False, False, True, True, True, True, True],
    ).reset_index(drop=True)

    legacy_threshold_summary_rows: list[dict[str, object]] = []
    legacy_present_same_direction_df = legacy_status_df.loc[
        legacy_status_df["present_in_reproduction_deg"] & legacy_status_df["same_direction_as_set"].fillna(False)
    ].copy()
    for metric in ["adj_p_val", "pvalue"]:
        metric_values = legacy_present_same_direction_df[metric].dropna()
        if metric_values.empty:
            continue
        for quantile in [0.25, 0.50, 0.75, 0.90, 1.00]:
            cutoff = float(metric_values.quantile(quantile))
            same_direction_at_cutoff_df = same_direction_df.loc[same_direction_df[metric] <= cutoff].copy()
            legacy_at_cutoff_n = int(
                legacy_present_same_direction_df.loc[legacy_present_same_direction_df[metric] <= cutoff].shape[0]
            )
            legacy_threshold_summary_rows.append(
                {
                    "threshold_type": f"legacy_{metric}_quantile",
                    "quantile": quantile,
                    "score_metric": metric,
                    "score_cutoff": cutoff,
                    "legacy_same_direction_recovered": legacy_at_cutoff_n,
                    "eligible_same_direction_genes": int(same_direction_at_cutoff_df.shape[0]),
                    "candidate_set_size_if_threshold_only": int(same_direction_at_cutoff_df.shape[0]),
                }
            )
    legacy_threshold_summary_df = pd.DataFrame(legacy_threshold_summary_rows)

    selected_columns = [
        "gene_symbol",
        "logFC",
        "pvalue",
        "adj_p_val",
        "same_direction_as_set",
        "significant_in_reproduction",
        "rank_within_reproduced_sig_direction",
        "in_legacy_gmt",
        "in_reproduced_gmt",
    ]
    top_reproduced_de_df = comparison_deg_df.sort_values(["adj_p_val", "gene_symbol"]).head(50).copy()
    top_legacy_excluded_df = legacy_status_df.sort_values(["adj_p_val", "gene_symbol"], na_position="last").head(50).copy()
    top_reproduced_only_df = reproduced_status_df.loc[~reproduced_status_df["in_legacy_gmt"]].head(50).copy()

    write_dataframe(legacy_status_df, output_dir / "legacy_gene_status_in_reproduction.v1.tsv")
    write_dataframe(reproduced_status_df, output_dir / "reproduced_gene_status.v1.tsv")
    write_dataframe(legacy_reason_summary_df, output_dir / "legacy_exclusion_reason_summary.v1.tsv")
    write_dataframe(reproduced_inclusion_summary_df, output_dir / "reproduced_inclusion_reason_summary.v1.tsv")
    write_dataframe(threshold_sweep_df, output_dir / "threshold_sweep_legacy_recovery.v1.tsv")
    write_dataframe(legacy_threshold_summary_df, output_dir / "legacy_recovery_threshold_summary.v1.tsv")
    write_dataframe(top_reproduced_de_df.loc[:, selected_columns], output_dir / "top_reproduction_de_genes.v1.tsv")
    write_dataframe(top_legacy_excluded_df, output_dir / "top_legacy_genes_by_reproduction_adj_p_val.v1.tsv")
    write_dataframe(top_reproduced_only_df, output_dir / "top_reproduced_only_genes.v1.tsv")

    shared_df = pd.DataFrame({"gene_symbol": sorted(shared_gene_set)})
    legacy_only_df = pd.DataFrame({"gene_symbol": legacy_only_genes})
    reproduced_only_df = pd.DataFrame({"gene_symbol": reproduced_only_genes})
    write_dataframe(shared_df, output_dir / "shared_genes.v1.tsv")
    write_dataframe(legacy_only_df, output_dir / "legacy_only_genes.v1.tsv")
    write_dataframe(reproduced_only_df, output_dir / "reproduced_only_genes.v1.tsv")

    overlap = overlap_row.iloc[0]
    manifest = manifest_row.iloc[0]
    n_sig_same_direction = int(sig_direction_df.shape[0])
    n_legacy_present = int(legacy_status_df["present_in_reproduction_deg"].sum())
    n_legacy_same_direction = int(legacy_status_df["same_direction_as_set"].fillna(False).sum())
    n_legacy_significant = int(legacy_status_df["significant_in_reproduction"].fillna(False).sum())
    n_legacy_would_include = int(
        (legacy_status_df["exclusion_reason_from_reproduced_set"] == "present_and_would_have_been_in_reproduced_set").sum()
    )

    summary_rows = [
        {"metric": "set_name", "value": set_name},
        {"metric": "comparison_id", "value": comparison_id},
        {"metric": "direction", "value": direction},
        {"metric": "reference_n_genes", "value": int(overlap["reference_n_genes"])},
        {"metric": "reproduced_n_genes", "value": int(overlap["generated_n_genes"])},
        {"metric": "shared_n_genes", "value": int(overlap["shared_n_genes"])},
        {"metric": "jaccard", "value": float(overlap["jaccard"])},
        {"metric": "balanced_group_a_n_older", "value": int(manifest["n_group_a"])},
        {"metric": "balanced_group_b_n_20_29", "value": int(manifest["n_group_b"])},
        {"metric": "reproduction_deg_rows", "value": int(comparison_deg_df.shape[0])},
        {"metric": "reproduction_sig_same_direction_rows", "value": n_sig_same_direction},
        {"metric": "legacy_genes_present_in_reproduction_deg", "value": n_legacy_present},
        {"metric": "legacy_genes_same_direction_in_reproduction", "value": n_legacy_same_direction},
        {"metric": "legacy_genes_significant_in_reproduction", "value": n_legacy_significant},
        {"metric": "legacy_genes_that_would_be_in_reproduced_set", "value": n_legacy_would_include},
    ]
    for key, value in processed_matrix_summary.items():
        summary_rows.append({"metric": key, "value": value})
    write_dataframe(pd.DataFrame(summary_rows), output_dir / "selected_low_overlap_set_summary.v1.tsv")

    reason_lines = [
        f"- {row['exclusion_reason_from_reproduced_set']}: {int(row['n_legacy_genes'])}"
        for row in legacy_reason_summary_df.to_dict(orient="records")
    ]
    example_reproduced = ", ".join(reproduced_genes[:10])
    example_legacy = ", ".join(legacy_genes[:10])
    top_excluded_examples = legacy_status_df.loc[
        legacy_status_df["exclusion_reason_from_reproduced_set"] != "present_and_would_have_been_in_reproduced_set",
        ["gene_symbol", "exclusion_reason_from_reproduced_set", "logFC", "adj_p_val"],
    ].head(10)
    top_excluded_lines = [
        f"- {row['gene_symbol']}: {row['exclusion_reason_from_reproduced_set']}, "
        f"logFC={row['logFC'] if pd.notna(row['logFC']) else 'NA'}, "
        f"adj_p_val={row['adj_p_val'] if pd.notna(row['adj_p_val']) else 'NA'}"
        for row in top_excluded_examples.to_dict(orient="records")
    ]
    top_included_lines = [
        f"- {row['gene_symbol']}: rank={int(row['rank_within_reproduced_sig_direction'])}, "
        f"logFC={float(row['logFC']):.6g}, adj_p_val={float(row['adj_p_val']):.6g}"
        for row in reproduced_status_df.head(10).to_dict(orient="records")
    ]
    best_threshold_rows = threshold_sweep_df.head(10).copy()
    best_threshold_lines = [
        f"- score={row['score_metric']} <= {float(row['score_cutoff']):.6g}, "
        f"abs_logfc_min={float(row['abs_logfc_min']):.3g}, top_k={row['top_k']}: "
        f"candidate_genes={int(row['candidate_n_genes'])}, shared={int(row['shared_n_genes'])}, "
        f"Jaccard={float(row['jaccard']):.6f}, legacy_recall={float(row['legacy_recall']):.3f}, "
        f"precision={float(row['candidate_precision']):.3f}"
        for row in best_threshold_rows.to_dict(orient="records")
    ]
    best_250_row = threshold_sweep_df.loc[threshold_sweep_df["candidate_n_genes"] == len(legacy_genes)].head(1)
    if best_250_row.empty:
        threshold_takeaway = "No swept threshold produced a candidate set with the same size as the legacy set."
    else:
        row = best_250_row.iloc[0]
        threshold_takeaway = (
            f"The best same-size candidate in this sweep used score={row['score_metric']} <= {float(row['score_cutoff']):.6g}, "
            f"abs_logfc_min={float(row['abs_logfc_min']):.3g}, top_k={row['top_k']}; it recovered "
            f"{int(row['shared_n_genes'])} of {len(legacy_genes)} legacy genes "
            f"(Jaccard={float(row['jaccard']):.6f})."
        )
    if not legacy_threshold_summary_df.empty:
        hardest_recovery_row = legacy_threshold_summary_df.sort_values(
            ["legacy_same_direction_recovered", "candidate_set_size_if_threshold_only"],
            ascending=[False, True],
        ).iloc[0]
        threshold_takeaway += (
            f" Recovering all same-direction legacy genes present in the reproduced DEG table would require "
            f"{hardest_recovery_row['score_metric']} <= {float(hardest_recovery_row['score_cutoff']):.6g}, "
            f"which admits {int(hardest_recovery_row['candidate_set_size_if_threshold_only'])} same-direction genes before any top-k cap."
        )
    if len(shared_gene_set) == 0:
        overlap_text = "the two versions have no shared genes"
    else:
        overlap_text = f"the two versions have low overlap with {len(shared_gene_set)} shared genes"
    if n_legacy_would_include == 0:
        inclusion_text = "none of the legacy genes satisfy the reproduced inclusion rule for this set"
    else:
        inclusion_text = f"{n_legacy_would_include} legacy genes satisfy the reproduced inclusion rule for this set"

    identifier_lines: list[str]
    interpretation_lines = [
        "This is not a set-name or comparison-coverage issue: the same set name and comparison exist in both outputs.",
        "The difference is caused by the reproduced DE ranking and significance results. The reproduced GMT is built from genes that are adjusted-significant in the positive direction and ranked within the top 250 for that comparison.",
        "The legacy GMT must therefore reflect different upstream DE statistics, filtering, mapping, or final membership logic for this comparison, because most of its 250 genes do not survive the reproduced inclusion rule.",
    ]
    if processed_matrix_summary:
        duplicate_rows = int(processed_matrix_summary["processed_matrix_duplicate_gene_symbol_rows"])
        numeric_rows = int(processed_matrix_summary["processed_matrix_numeric_gene_symbols"])
        identifier_lines = [
            f"- processed matrix rows: {processed_matrix_summary['processed_matrix_rows']}",
            f"- unique processed matrix gene symbols: {processed_matrix_summary['processed_matrix_unique_gene_symbols']}",
            f"- duplicate processed matrix gene-symbol rows: {duplicate_rows}",
            f"- numeric gene symbols in processed matrix: {numeric_rows}",
        ]
        if duplicate_rows == 0 and numeric_rows == 0:
            identifier_lines.append("- processed matrix identifiers are valid for this comparison.")
            interpretation_lines.insert(
                1,
                "After the identifier-preservation patch, this is no longer explained by numeric row IDs in the reproduced GMT.",
            )
        else:
            identifier_lines.append("- processed matrix identifiers are still malformed for this comparison.")
            interpretation_lines.insert(
                1,
                "Identifier problems remain a likely contributor because the processed matrix still has duplicate or numeric gene symbols.",
            )
    else:
        identifier_lines = ["- processed matrix diagnostics were not requested."]

    lines = [
        "# Shared Low-Overlap Gene Set Analysis v1",
        "",
        "## Take-Home Summary",
        "",
        f"The selected set is `{set_name}`. It appears in both GMT files, but {overlap_text}: legacy has {len(legacy_genes)} genes, the reproduction has {len(reproduced_genes)} genes, shared genes={len(shared_gene_set)}, Jaccard={float(overlap['jaccard']):.6f}.",
        f"The comparison itself is represented in the reproduction and was run with {int(manifest['n_group_b'])} `20-29` samples versus {int(manifest['n_group_a'])} `60-69` samples.",
        f"The reproduced set consists of the top 250 genes with `adj_p_val < 0.05` and positive logFC among {n_sig_same_direction} significant positive genes in the reproduced DE table.",
        f"The legacy genes are mostly excluded from the reproduced set because {inclusion_text}; {n_legacy_present} of 250 legacy genes are present in the reproduced DEG table, {n_legacy_same_direction} have positive reproduced logFC, {n_legacy_significant} are adjusted-significant, and {n_legacy_would_include} would rank into the reproduced top 250.",
        threshold_takeaway,
        "",
        "## Identifier Diagnostics",
        "",
        *identifier_lines,
    ]
    lines.extend(
        [
            "",
        "## Membership Examples",
        "",
        f"- first 10 legacy genes: {example_legacy}",
        f"- first 10 reproduced genes: {example_reproduced}",
        "",
        "## Legacy Gene Exclusion Reasons In The Reproduction",
        "",
        *reason_lines,
        "",
        "## Example Legacy Genes And Why They Are Excluded",
        "",
        *top_excluded_lines,
        "",
        "## Example Reproduced Genes And Why They Are Included",
        "",
        *top_included_lines,
        "",
        "## Threshold Sweep",
        "",
        "The sweep varied score metric, score cutoff, minimum absolute logFC, and top-k cap using the reproduced DEG table for the same comparison and direction.",
        "These thresholds can only recover legacy genes that are present in the reproduced DEG table with the same logFC direction; they cannot recover genes absent from the reproduced DEG table.",
        "",
        "Top threshold configurations by Jaccard against the legacy set:",
        "",
        *best_threshold_lines,
        "",
        "## Interpretation",
        "",
        *interpretation_lines,
        "",
        "## Output Files",
        "",
        "- `selected_low_overlap_set_summary.v1.tsv`",
        "- `legacy_gene_status_in_reproduction.v1.tsv`",
        "- `reproduced_gene_status.v1.tsv`",
        "- `legacy_exclusion_reason_summary.v1.tsv`",
        "- `threshold_sweep_legacy_recovery.v1.tsv`",
        "- `legacy_recovery_threshold_summary.v1.tsv`",
        "- `top_legacy_genes_by_reproduction_adj_p_val.v1.tsv`",
        "- `top_reproduced_only_genes.v1.tsv`",
        "- `processed_matrix_identifier_summary.v1.tsv`",
        ]
    )
    write_text("\n".join(lines) + "\n", output_dir / "shared_low_overlap_gene_set_analysis.v1.md")


if __name__ == "__main__":
    main()
