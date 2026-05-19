#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from build_tissue_inputs import (
    compact_age_comparison_label,
    derive_subject_id,
    normalize_age,
    normalize_sex,
    open_maybe_gzip,
    read_tsv,
    write_naming_reference,
    write_tsv,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts_gct", required=True)
    parser.add_argument("--sample_metadata_tsv", required=True)
    parser.add_argument("--subject_metadata_tsv", required=True)
    parser.add_argument("--tissue_label", required=True, help="Human-readable broad tissue label for summaries.")
    parser.add_argument("--metadata_group_column", default="SMTS")
    parser.add_argument("--metadata_group_value", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--sample_id_column", default="SAMPID")
    parser.add_argument("--subject_id_column_sample", default="SUBJID")
    parser.add_argument("--subject_id_column_subject", default="SUBJID")
    parser.add_argument("--age_column", default="AGE")
    parser.add_argument("--sex_column", default="SEX")
    parser.add_argument("--primary_tissue_column", default="SMTS")
    parser.add_argument("--detailed_tissue_column", default="SMTSD")
    parser.add_argument("--reference_age_bin", default="20-29")
    parser.add_argument("--age_bins", default="20-29,30-39,40-49,50-59,60-69,70-79")
    parser.add_argument("--min_samples_per_group", type=int, default=2)
    return parser


def parse_gct_header(path: Path) -> tuple[list[str], list[str]]:
    with open_maybe_gzip(path) as handle:
        _version = handle.readline()
        _dims = handle.readline()
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
    if len(header) < 3 or header[0] != "Name":
        raise ValueError("Expected GTEx GCT with Name, Description, and sample columns")
    sample_ids = [str(value).strip() for value in header[2:] if str(value).strip()]
    return header, sample_ids


def write_filtered_counts(
    *,
    counts_gct: Path,
    sample_columns: list[str],
    sample_index: list[int],
    out_path: Path,
) -> int:
    fieldnames = ["gene_id", "gene_symbol", *sample_columns]
    n_rows = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as out_handle:
        writer = csv.DictWriter(out_handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        with open_maybe_gzip(counts_gct) as in_handle:
            _version = in_handle.readline()
            _dims = in_handle.readline()
            reader = csv.reader(in_handle, delimiter="\t")
            _header = next(reader)
            for row in reader:
                out_row = {
                    "gene_id": str(row[0]).strip(),
                    "gene_symbol": str(row[1]).strip(),
                }
                for out_col, idx in zip(sample_columns, sample_index):
                    out_row[out_col] = row[idx + 2]
                writer.writerow(out_row)
                n_rows += 1
    return n_rows


def main() -> int:
    args = build_arg_parser().parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sample_rows = read_tsv(Path(args.sample_metadata_tsv))
    subject_rows = read_tsv(Path(args.subject_metadata_tsv))
    _header, gct_sample_ids = parse_gct_header(Path(args.counts_gct))

    subject_by_id = {
        str(row.get(args.subject_id_column_subject, "")).strip(): row
        for row in subject_rows
        if str(row.get(args.subject_id_column_subject, "")).strip()
    }

    gct_sample_id_set = set(gct_sample_ids)
    age_order = [token.strip() for token in str(args.age_bins).split(",") if token.strip()]
    metadata_group_value = str(args.metadata_group_value).strip()

    prepared_meta: list[dict[str, str]] = []
    retained_sample_ids: list[str] = []
    for row in sample_rows:
        sample_id = str(row.get(args.sample_id_column, "")).strip()
        if not sample_id or sample_id not in gct_sample_id_set:
            continue
        if str(row.get(args.metadata_group_column, "")).strip() != metadata_group_value:
            continue
        subject_id = str(row.get(args.subject_id_column_sample, "")).strip()
        if not subject_id:
            subject_id = derive_subject_id(sample_id)
        subject_row = subject_by_id.get(subject_id, {})
        age_bin = normalize_age(str(subject_row.get(args.age_column, "")))
        sex = normalize_sex(str(subject_row.get(args.sex_column, "")))
        if age_bin not in age_order:
            continue
        retained_sample_ids.append(sample_id)
        prepared_meta.append(
            {
                "sample_id": sample_id,
                "subject_id": subject_id,
                "age_bin": age_bin,
                "SEX": sex,
                "primary_tissue": str(row.get(args.primary_tissue_column, "")).strip(),
                "detailed_tissue": str(row.get(args.detailed_tissue_column, "")).strip(),
            }
        )

    retained_sample_id_set = set(retained_sample_ids)
    sample_index = [idx for idx, sample_id in enumerate(gct_sample_ids) if sample_id in retained_sample_id_set]
    sample_columns = [gct_sample_ids[idx] for idx in sample_index]
    n_genes_retained = write_filtered_counts(
        counts_gct=Path(args.counts_gct),
        sample_columns=sample_columns,
        sample_index=sample_index,
        out_path=out_dir / "tissue_counts.tsv",
    )

    write_tsv(
        out_dir / "sample_metadata.tsv",
        prepared_meta,
        ["sample_id", "subject_id", "age_bin", "SEX", "primary_tissue", "detailed_tissue"],
    )

    age_counts: dict[str, int] = {}
    for row in prepared_meta:
        age_counts[row["age_bin"]] = age_counts.get(row["age_bin"], 0) + 1

    comparisons: list[dict[str, str]] = []
    reference_age = str(args.reference_age_bin)
    for age_bin in age_order:
        if age_bin == reference_age:
            continue
        if age_counts.get(reference_age, 0) < int(args.min_samples_per_group):
            continue
        if age_counts.get(age_bin, 0) < int(args.min_samples_per_group):
            continue
        comparisons.append(
            {
                "comparison_id": compact_age_comparison_label(age_bin, reference_age),
                "comparison_kind": "condition_a_vs_b",
                "group_column": "age_bin",
                "group_a": age_bin,
                "group_b": reference_age,
            }
        )

    write_tsv(
        out_dir / "comparisons.tsv",
        comparisons,
        ["comparison_id", "comparison_kind", "group_column", "group_a", "group_b"],
    )

    summary = {
        "tissue_label": args.tissue_label,
        "metadata_group_column": args.metadata_group_column,
        "metadata_group_value": metadata_group_value,
        "counts_gct": str(Path(args.counts_gct).resolve()),
        "sample_metadata_tsv": str(Path(args.sample_metadata_tsv).resolve()),
        "subject_metadata_tsv": str(Path(args.subject_metadata_tsv).resolve()),
        "n_samples_retained": len(prepared_meta),
        "n_genes_retained": n_genes_retained,
        "reference_age_bin": reference_age,
        "age_bin_counts": {key: age_counts.get(key, 0) for key in age_order},
        "n_comparisons": len(comparisons),
        "comparison_ids": [row["comparison_id"] for row in comparisons],
    }
    (out_dir / "prepare_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_naming_reference(out_dir / "naming_reference.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
