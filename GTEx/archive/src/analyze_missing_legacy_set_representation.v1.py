#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("analyze_missing_legacy_set_representation_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--generated_gmt_gz", required=True)
    parser.add_argument("--comparison_manifest_tsv", required=True)
    parser.add_argument("--sample_metadata_tsv", required=True)
    parser.add_argument("--combined_deg_tsv", required=True)
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


def read_gmt_set_names(path: Path) -> set[str]:
    names: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if parts and parts[0]:
                names.add(parts[0])
    LOGGER.info("loaded GMT set names path=%s n=%d", path, len(names))
    return names


def parse_set_name(set_name: str) -> tuple[str, str]:
    comparison_id, direction = set_name.rsplit("_", 1)
    return comparison_id, direction


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "analyze_missing_legacy_set_representation.v1.log")

    reference_gmt_gz = Path(args.reference_gmt_gz).resolve()
    generated_gmt_gz = Path(args.generated_gmt_gz).resolve()
    comparison_manifest_tsv = Path(args.comparison_manifest_tsv).resolve()
    sample_metadata_tsv = Path(args.sample_metadata_tsv).resolve()
    combined_deg_tsv = Path(args.combined_deg_tsv).resolve()

    for path in [reference_gmt_gz, generated_gmt_gz, comparison_manifest_tsv, sample_metadata_tsv, combined_deg_tsv]:
        if not path.exists():
            raise FileNotFoundError(path)

    reference_set_names = read_gmt_set_names(reference_gmt_gz)
    generated_set_names = read_gmt_set_names(generated_gmt_gz)
    missing_set_names = sorted(reference_set_names - generated_set_names)
    LOGGER.info("missing set names n=%d", len(missing_set_names))

    comparison_df = pd.read_csv(comparison_manifest_tsv, sep="\t", dtype=str)
    sample_metadata_df = pd.read_csv(sample_metadata_tsv, sep="\t", dtype=str)
    combined_deg_df = pd.read_csv(combined_deg_tsv, sep="\t", dtype=str)
    LOGGER.info("comparison manifest shape=%s", comparison_df.shape)
    LOGGER.info("sample metadata shape=%s", sample_metadata_df.shape)
    LOGGER.info("combined DEG shape=%s", combined_deg_df.shape)

    comparison_df["n_group_a"] = pd.to_numeric(comparison_df["n_group_a"], errors="coerce")
    comparison_df["n_group_b"] = pd.to_numeric(comparison_df["n_group_b"], errors="coerce")
    combined_deg_df["adj_p_val"] = pd.to_numeric(combined_deg_df["adj_p_val"], errors="coerce")
    combined_deg_df["logFC"] = pd.to_numeric(combined_deg_df["logFC"], errors="coerce")

    comparison_lookup = {
        str(row["comparison_id"]): row for row in comparison_df.to_dict(orient="records")
    }

    deg_rows: list[dict[str, object]] = []
    for comparison_id, group_df in combined_deg_df.groupby("comparison_id", sort=False):
        sig_df = group_df.loc[group_df["adj_p_val"].notna() & (group_df["adj_p_val"] < 0.05)].copy()
        deg_rows.append(
            {
                "comparison_id": str(comparison_id),
                "n_deg_rows": int(group_df.shape[0]),
                "n_sig_rows": int(sig_df.shape[0]),
                "n_sig_up": int((sig_df["logFC"] > 0).sum()),
                "n_sig_down": int((sig_df["logFC"] < 0).sum()),
            }
        )
    deg_summary_df = pd.DataFrame(deg_rows)
    LOGGER.info("DEG summary shape=%s", deg_summary_df.shape)
    deg_lookup = {str(row["comparison_id"]): row for row in deg_summary_df.to_dict(orient="records")}

    raw_sample_counts_df = (
        sample_metadata_df.groupby(["tissue_name", "age_bin"], as_index=False)
        .size()
        .rename(columns={"size": "n_samples_raw"})
    )
    raw_sample_lookup = {
        (str(row["tissue_name"]), str(row["age_bin"])): int(row["n_samples_raw"])
        for row in raw_sample_counts_df.to_dict(orient="records")
    }
    LOGGER.info("raw sample count table shape=%s", raw_sample_counts_df.shape)

    rows: list[dict[str, object]] = []
    for set_name in missing_set_names:
        comparison_id, direction = parse_set_name(set_name)
        comparison_row = comparison_lookup.get(comparison_id)
        deg_row = deg_lookup.get(comparison_id)
        tissue_name = comparison_id.replace("GTEx_", "").split("_20-29_vs_")[0]
        older_age_bin = comparison_id.split("_vs_")[-1]
        raw_control_n = raw_sample_lookup.get((tissue_name, "20-29"), 0)
        raw_case_n = raw_sample_lookup.get((tissue_name, older_age_bin), 0)

        represented_in_input = comparison_row is not None
        n_group_a = int(comparison_row["n_group_a"]) if comparison_row is not None else None
        n_group_b = int(comparison_row["n_group_b"]) if comparison_row is not None else None
        n_deg_rows = int(deg_row["n_deg_rows"]) if deg_row is not None else 0
        n_sig_rows = int(deg_row["n_sig_rows"]) if deg_row is not None else 0
        n_sig_direction = 0
        if deg_row is not None:
            n_sig_direction = int(deg_row["n_sig_up"] if direction == "Up" else deg_row["n_sig_down"])

        if not represented_in_input:
            status = "comparison_absent_from_input"
        elif n_sig_direction == 0:
            status = "comparison_present_no_significant_genes_in_direction"
        elif n_sig_direction < 5:
            status = "comparison_present_but_fewer_than_5_significant_genes_in_direction"
        else:
            status = "comparison_present_unexpected_missing_set"

        rows.append(
            {
                "set_name": set_name,
                "comparison_id": comparison_id,
                "direction": direction,
                "tissue_name": tissue_name,
                "older_age_bin": older_age_bin,
                "represented_in_input": represented_in_input,
                "status": status,
                "raw_n_20_29": raw_control_n,
                "raw_n_older_age_bin": raw_case_n,
                "n_group_a_balanced": n_group_a,
                "n_group_b_balanced": n_group_b,
                "n_deg_rows": n_deg_rows,
                "n_sig_rows": n_sig_rows,
                "n_sig_direction": n_sig_direction,
            }
        )

    missing_df = pd.DataFrame(rows).sort_values(["status", "set_name"]).reset_index(drop=True)
    summary_df = (
        missing_df.groupby(["status", "represented_in_input"], as_index=False)
        .size()
        .rename(columns={"size": "n_missing_sets"})
        .sort_values(["n_missing_sets", "status"], ascending=[False, True])
        .reset_index(drop=True)
    )
    tissue_summary_df = (
        missing_df.groupby(["tissue_name", "status"], as_index=False)
        .size()
        .rename(columns={"size": "n_missing_sets"})
        .sort_values(["n_missing_sets", "tissue_name", "status"], ascending=[False, True, True])
        .reset_index(drop=True)
    )

    write_dataframe(missing_df, output_dir / "missing_set_representation.v1.tsv")
    write_dataframe(summary_df, output_dir / "missing_set_representation_summary.v1.tsv")
    write_dataframe(tissue_summary_df, output_dir / "missing_set_representation_by_tissue.v1.tsv")

    represented_n = int(missing_df["represented_in_input"].sum())
    absent_n = int((~missing_df["represented_in_input"]).sum())
    no_sig_n = int((missing_df["status"] == "comparison_present_no_significant_genes_in_direction").sum())
    too_few_n = int((missing_df["status"] == "comparison_present_but_fewer_than_5_significant_genes_in_direction").sum())
    unexpected_n = int((missing_df["status"] == "comparison_present_unexpected_missing_set").sum())

    lines = [
        "# Missing Legacy Set Representation v1",
        "",
        "## Take-Home Summary",
        "",
        f"- missing legacy sets examined: {missing_df.shape[0]}",
        f"- represented in prepared reproduction input: {represented_n}",
        f"- absent from prepared reproduction input: {absent_n}",
        f"- present in input but with zero significant genes in the missing direction: {no_sig_n}",
        f"- present in input but with only 1-4 significant genes in the missing direction: {too_few_n}",
        f"- present in input with >=5 significant genes in the missing direction but still absent from GMT: {unexpected_n}",
        "",
        "## Interpretation",
        "",
        "This analysis asks whether the missing legacy GMT sets were even represented as tissue/age comparisons in the reproduction input.",
        "A set is counted as represented when its comparison_id appears in the prepared comparison manifest, meaning the GTEx input had enough samples to define that contrast.",
        "If a comparison was represented but the set is still missing, the missing direction usually failed downstream because there were either no significant genes or fewer than 5 significant genes after `adj.P.Val < 0.05` filtering.",
        "",
        "## Top Missing-Set Status Counts",
        "",
    ]
    for row in summary_df.to_dict(orient="records"):
        lines.append(
            f"- {row['status']}: {int(row['n_missing_sets'])} missing sets "
            f"(represented_in_input={str(bool(row['represented_in_input'])).lower()})"
        )

    lines.extend(
        [
            "",
            "## Most Affected Tissues",
            "",
        ]
    )
    for row in tissue_summary_df.head(15).to_dict(orient="records"):
        lines.append(f"- {row['tissue_name']} / {row['status']}: {int(row['n_missing_sets'])}")

    write_text("\n".join(lines) + "\n", output_dir / "missing_set_representation.v1.md")


if __name__ == "__main__":
    main()
