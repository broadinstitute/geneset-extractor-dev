from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
from typing import Iterable


AGE_CODE_MAP = {
    "1": "20-29",
    "2": "30-39",
    "3": "40-49",
    "4": "50-59",
    "5": "60-69",
    "6": "70-79",
}

SEX_CODE_MAP = {
    "1": "M",
    "2": "F",
}


def open_maybe_gzip(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with open_maybe_gzip(path) as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def normalize_age(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if value in AGE_CODE_MAP:
        return AGE_CODE_MAP[value]
    if value in AGE_CODE_MAP.values():
        return value
    compact = value.replace(" ", "")
    if compact in AGE_CODE_MAP.values():
        return compact
    return value


def normalize_sex(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    return SEX_CODE_MAP.get(value, value)


def derive_subject_id(sample_id: str) -> str:
    value = str(sample_id or "").strip()
    if not value:
        return ""
    parts = value.split("-")
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return ""


def compact_age_comparison_label(age_bin: str, reference_age_bin: str) -> str:
    left = str(age_bin or "").strip()
    right = str(reference_age_bin or "").strip()
    if not left or not right:
        raise ValueError("age_bin and reference_age_bin must be non-empty")
    left_decade = left.split("-", 1)[0]
    right_decade = right.split("-", 1)[0]
    return f"age{left_decade}_{right_decade}"


def write_naming_reference(path: Path) -> None:
    text = """# Naming Reference

This prepared GTEx bundle uses compact age-bin comparison names.

## Comparison Labels

- `age30_20` means `30-39` vs `20-29`
- `age40_20` means `40-49` vs `20-29`
- `age50_20` means `50-59` vs `20-29`
- `age60_20` means `60-69` vs `20-29`
- `age70_20` means `70-79` vs `20-29`

The suffix `_20` always refers to the reference age bin `20-29`.

## Gene Set Labels

Downstream GTEx model runs emit compact gene-set names using:

`<model_id>__<comparison>__<sign>`

Examples:

- `AB1__age50_20__pos`
- `AB1__age50_20__neg`
"""
    path.write_text(text, encoding="utf-8")


def write_tsv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_gct(path: Path) -> tuple[list[str], list[list[str]]]:
    with open_maybe_gzip(path) as handle:
        _version = handle.readline()
        _dims = handle.readline()
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        rows = [row for row in reader]
    return header, rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts_gct", required=True)
    parser.add_argument("--sample_metadata_tsv", required=True)
    parser.add_argument("--subject_metadata_tsv", required=True)
    parser.add_argument("--tissue_label", required=True, help="Human-readable tissue label for summaries only.")
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


def main() -> int:
    args = build_arg_parser().parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sample_rows = read_tsv(Path(args.sample_metadata_tsv))
    subject_rows = read_tsv(Path(args.subject_metadata_tsv))
    header, gct_rows = parse_gct(Path(args.counts_gct))

    if len(header) < 3 or header[0] != "Name":
        raise ValueError("Expected GTEx GCT with Name, Description, and sample columns")

    subject_by_id = {
        str(row.get(args.subject_id_column_subject, "")).strip(): row
        for row in subject_rows
        if str(row.get(args.subject_id_column_subject, "")).strip()
    }

    gct_sample_ids = [str(value).strip() for value in header[2:] if str(value).strip()]
    gct_sample_id_set = set(gct_sample_ids)
    age_order = [token.strip() for token in str(args.age_bins).split(",") if token.strip()]

    prepared_meta: list[dict[str, str]] = []
    retained_sample_ids: list[str] = []
    for row in sample_rows:
        sample_id = str(row.get(args.sample_id_column, "")).strip()
        if not sample_id or sample_id not in gct_sample_id_set:
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

    counts_rows: list[dict[str, str]] = []
    for row in gct_rows:
        gene_id = str(row[0]).strip()
        gene_symbol = str(row[1]).strip()
        out_row = {"gene_id": gene_id, "gene_symbol": gene_symbol}
        for out_col, idx in zip(sample_columns, sample_index):
            out_row[out_col] = row[idx + 2]
        counts_rows.append(out_row)

    counts_fieldnames = ["gene_id", "gene_symbol", *sample_columns]
    write_tsv(out_dir / "tissue_counts.tsv", counts_rows, counts_fieldnames)
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
        "counts_gct": str(Path(args.counts_gct).resolve()),
        "sample_metadata_tsv": str(Path(args.sample_metadata_tsv).resolve()),
        "subject_metadata_tsv": str(Path(args.subject_metadata_tsv).resolve()),
        "n_samples_retained": len(prepared_meta),
        "n_genes_retained": len(counts_rows),
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
