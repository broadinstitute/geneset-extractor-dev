#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("analyze_one_missing_legacy_set_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set_name", default="GTEx_Blood_20-29_vs_30-39_Up")
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--reproduced_gmt_gz", required=True)
    parser.add_argument("--missing_set_representation_tsv", required=True)
    parser.add_argument("--comparison_manifest_tsv", required=True)
    parser.add_argument("--deg_tsv", required=True)
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


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "analyze_one_missing_legacy_set.v1.log")

    reference_sets = read_gmt(Path(args.reference_gmt_gz).resolve())
    reproduced_sets = read_gmt(Path(args.reproduced_gmt_gz).resolve())
    set_name = args.set_name
    if set_name not in reference_sets:
        raise ValueError(f"set not found in reference GMT: {set_name}")
    if set_name in reproduced_sets:
        raise ValueError(f"set is present in reproduced GMT, expected missing: {set_name}")

    comparison_id, direction = set_name.rsplit("_", 1)
    legacy_genes = reference_sets[set_name]
    legacy_gene_set = set(legacy_genes)
    LOGGER.info("selected set=%s comparison_id=%s direction=%s n_legacy_genes=%d", set_name, comparison_id, direction, len(legacy_genes))

    missing_df = pd.read_csv(args.missing_set_representation_tsv, sep="\t")
    comparison_df = pd.read_csv(args.comparison_manifest_tsv, sep="\t")
    deg_df = pd.read_csv(args.deg_tsv, sep="\t")
    LOGGER.info("missing representation shape=%s", missing_df.shape)
    LOGGER.info("comparison manifest shape=%s", comparison_df.shape)
    LOGGER.info("DEG table shape=%s", deg_df.shape)

    missing_row = missing_df.loc[missing_df["set_name"] == set_name].copy()
    if missing_row.empty:
        raise ValueError(f"set not found in missing representation table: {set_name}")
    comparison_row = comparison_df.loc[comparison_df["comparison_id"] == comparison_id].copy()
    if comparison_row.empty:
        raise ValueError(f"comparison not found in manifest: {comparison_id}")

    comparison_deg_df = deg_df.loc[deg_df["comparison_id"] == comparison_id].copy()
    if comparison_deg_df.empty:
        raise ValueError(f"comparison not found in DEG table: {comparison_id}")
    comparison_deg_df["adj_p_val"] = pd.to_numeric(comparison_deg_df["adj_p_val"], errors="coerce")
    comparison_deg_df["pvalue"] = pd.to_numeric(comparison_deg_df["pvalue"], errors="coerce")
    comparison_deg_df["logFC"] = pd.to_numeric(comparison_deg_df["logFC"], errors="coerce")
    comparison_deg_df["legacy_member"] = comparison_deg_df["gene_symbol"].isin(legacy_gene_set)
    comparison_deg_df["rank_by_adj_p_val"] = comparison_deg_df["adj_p_val"].rank(method="first", ascending=True).astype("Int64")

    direction_mask = comparison_deg_df["logFC"] > 0 if direction == "Up" else comparison_deg_df["logFC"] < 0
    significant_mask = comparison_deg_df["adj_p_val"] < 0.05
    significant_direction_df = comparison_deg_df.loc[significant_mask & direction_mask].copy()
    significant_any_df = comparison_deg_df.loc[significant_mask].copy()
    legacy_in_deg_df = comparison_deg_df.loc[comparison_deg_df["legacy_member"]].copy()
    legacy_in_direction_df = legacy_in_deg_df.loc[direction_mask].copy()
    legacy_sig_df = legacy_in_deg_df.loc[significant_mask].copy()

    top_deg_df = comparison_deg_df.sort_values(["adj_p_val", "gene_symbol"]).head(25).copy()
    top_legacy_df = legacy_in_deg_df.sort_values(["adj_p_val", "gene_symbol"]).head(25).copy()
    top_direction_df = comparison_deg_df.loc[direction_mask].sort_values(["adj_p_val", "gene_symbol"]).head(25).copy()

    selected_columns = [
        "comparison_id",
        "gene_symbol",
        "logFC",
        "pvalue",
        "adj_p_val",
        "rank_by_adj_p_val",
        "legacy_member",
    ]
    write_dataframe(top_deg_df.loc[:, selected_columns], output_dir / "top_reproduction_genes_by_adj_p_val.v1.tsv")
    write_dataframe(top_legacy_df.loc[:, selected_columns], output_dir / "legacy_genes_in_reproduction_by_adj_p_val.v1.tsv")
    write_dataframe(top_direction_df.loc[:, selected_columns], output_dir / "top_reproduction_genes_in_missing_direction.v1.tsv")

    legacy_status_df = pd.DataFrame(
        {
            "gene_symbol": legacy_genes,
            "present_in_reproduction_deg": [gene in set(comparison_deg_df["gene_symbol"]) for gene in legacy_genes],
        }
    )
    legacy_status_df = legacy_status_df.merge(
        comparison_deg_df.loc[:, ["gene_symbol", "logFC", "pvalue", "adj_p_val", "rank_by_adj_p_val"]],
        on="gene_symbol",
        how="left",
    )
    legacy_status_df["same_direction_as_missing_set"] = legacy_status_df["logFC"] > 0 if direction == "Up" else legacy_status_df["logFC"] < 0
    legacy_status_df["significant_in_reproduction"] = legacy_status_df["adj_p_val"] < 0.05
    write_dataframe(legacy_status_df, output_dir / "legacy_gene_status_in_reproduction.v1.tsv")

    summary_rows = [
        {"metric": "set_name", "value": set_name},
        {"metric": "comparison_id", "value": comparison_id},
        {"metric": "direction", "value": direction},
        {"metric": "legacy_gene_count", "value": len(legacy_genes)},
        {"metric": "comparison_represented_in_input", "value": bool(missing_row.iloc[0]["represented_in_input"])},
        {"metric": "missing_status", "value": str(missing_row.iloc[0]["status"])},
        {"metric": "raw_n_20_29", "value": int(missing_row.iloc[0]["raw_n_20_29"])},
        {"metric": "raw_n_older_age_bin", "value": int(missing_row.iloc[0]["raw_n_older_age_bin"])},
        {"metric": "balanced_n_20_29", "value": int(missing_row.iloc[0]["n_group_b_balanced"])},
        {"metric": "balanced_n_older_age_bin", "value": int(missing_row.iloc[0]["n_group_a_balanced"])},
        {"metric": "n_reproduction_deg_rows", "value": int(comparison_deg_df.shape[0])},
        {"metric": "n_reproduction_significant_any_direction", "value": int(significant_any_df.shape[0])},
        {"metric": "n_reproduction_significant_missing_direction", "value": int(significant_direction_df.shape[0])},
        {"metric": "n_legacy_genes_present_in_reproduction_deg", "value": int(legacy_in_deg_df.shape[0])},
        {"metric": "n_legacy_genes_same_direction_in_reproduction", "value": int(legacy_in_direction_df.shape[0])},
        {"metric": "n_legacy_genes_significant_in_reproduction", "value": int(legacy_sig_df.shape[0])},
        {"metric": "min_reproduction_adj_p_val", "value": float(comparison_deg_df["adj_p_val"].min())},
        {"metric": "min_legacy_gene_adj_p_val_in_reproduction", "value": float(legacy_in_deg_df["adj_p_val"].min()) if not legacy_in_deg_df.empty else ""},
    ]
    summary_df = pd.DataFrame(summary_rows)
    write_dataframe(summary_df, output_dir / "selected_missing_set_summary.v1.tsv")

    c_row = comparison_row.iloc[0]
    m_row = missing_row.iloc[0]
    lines = [
        "# One Missing Legacy Gene Set Analysis v1",
        "",
        "## Take-Home Summary",
        "",
        f"The selected set is `{set_name}`. It appears in the legacy GMT with {len(legacy_genes)} genes but does not appear in the reproduction GMT.",
        f"The underlying comparison `{comparison_id}` is represented in the reproduction input: Blood has {int(m_row['raw_n_20_29'])} raw `20-29` samples and {int(m_row['raw_n_older_age_bin'])} raw `30-39` samples, which were balanced to {int(m_row['n_group_b_balanced'])} and {int(m_row['n_group_a_balanced'])} samples respectively.",
        f"The reason the set is missing is downstream DE filtering: the reproduction DE table contains {comparison_deg_df.shape[0]} tested genes for this comparison, but {significant_any_df.shape[0]} genes pass `adj_p_val < 0.05` in any direction and {significant_direction_df.shape[0]} pass in the missing `{direction}` direction.",
        "Because the GMT builder emits only direction-specific groups with at least 5 significant genes, this set cannot be emitted from the reproduced DE results.",
        "",
        "## Input Representation",
        "",
        f"- tissue_name: `{c_row['tissue_name']}`",
        f"- older age bin: `{m_row['older_age_bin']}`",
        f"- raw `20-29` sample count: {int(m_row['raw_n_20_29'])}",
        f"- raw older-bin sample count: {int(m_row['raw_n_older_age_bin'])}",
        f"- balanced `20-29` sample count used for DE: {int(c_row['n_group_b'])}",
        f"- balanced older-bin sample count used for DE: {int(c_row['n_group_a'])}",
        "",
        "## DE Evidence",
        "",
        f"- reproduced DEG rows for this comparison: {comparison_deg_df.shape[0]}",
        f"- reproduced genes with `adj_p_val < 0.05`: {significant_any_df.shape[0]}",
        f"- reproduced genes with `adj_p_val < 0.05` and `{direction}` logFC sign: {significant_direction_df.shape[0]}",
        f"- minimum reproduced adjusted p-value: {comparison_deg_df['adj_p_val'].min():.6g}",
        f"- legacy genes present in reproduced DEG table: {legacy_in_deg_df.shape[0]} of {len(legacy_genes)}",
        f"- legacy genes with same reproduced logFC direction: {legacy_in_direction_df.shape[0]} of {len(legacy_genes)}",
        f"- legacy genes significant in reproduced DEG table: {legacy_sig_df.shape[0]} of {len(legacy_genes)}",
        "",
        "## Interpretation",
        "",
        "This is not an input-coverage problem. The Blood `20-29` versus `30-39` comparison exists and was tested in the reproduction.",
        "It is missing because the reproduced limma/voom results do not contain enough adjusted-significant genes in the `Up` direction to pass the GMT emission rule.",
        "The legacy GMT therefore appears to have been generated under DE, filtering, mapping, or significance behavior that produced a much stronger signal for this comparison than the current reproduction.",
        "",
        "## Output Files",
        "",
        "- `selected_missing_set_summary.v1.tsv`",
        "- `legacy_gene_status_in_reproduction.v1.tsv`",
        "- `legacy_genes_in_reproduction_by_adj_p_val.v1.tsv`",
        "- `top_reproduction_genes_by_adj_p_val.v1.tsv`",
        "- `top_reproduction_genes_in_missing_direction.v1.tsv`",
    ]
    write_text("\n".join(lines) + "\n", output_dir / "one_missing_legacy_set_analysis.v1.md")


if __name__ == "__main__":
    main()
