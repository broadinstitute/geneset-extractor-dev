#!/usr/bin/env python3
from __future__ import annotations
"""
Merge multiple KidsFirst count matrices (tumor studies) into one combined matrix.
Used to build category-level gene sets (e.g., all blood cancers, all solid tumors).

Genes: intersection of all input matrices (strips Ensembl version suffix).
Sample IDs: all columns from all inputs (must be unique across studies).

Usage:
  python merge_study_matrices.py \
    --inputs KF-TALL/rsem_counts.tsv KF-MMC/rsem_counts.tsv \
    --out_tsv outputs/analysis/KF-BLOOD/merged_tumor_counts.tsv \
    --study_ids KF-TALL KF-MMC          # optional: for metadata output
    --out_metadata_tsv outputs/analysis/KF-BLOOD/study_membership.tsv
"""
import argparse
import csv
import sys
from pathlib import Path


def _strip_version(gid: str) -> str:
    return gid.split(".")[0] if "." in gid else gid


def _read_matrix(path: Path) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """Returns (gene_ids_stripped, sample_ids, {gene_id: [count_str ...]})"""
    gene_ids: list[str] = []
    sample_ids: list[str] = []
    data: dict[str, list[str]] = {}
    with open(path) as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader)
        sample_ids = header[1:]
        for row in reader:
            if not row:
                continue
            gid = _strip_version(row[0].strip())
            gene_ids.append(gid)
            data[gid] = row[1:]
    return gene_ids, sample_ids, data


def merge(input_paths: list[Path], study_ids: list[str], out_matrix: Path, out_metadata: Path | None) -> None:
    print(f"Merging {len(input_paths)} matrices...", file=sys.stderr)

    all_gene_sets: list[set[str]] = []
    per_matrix: list[tuple[list[str], list[str], dict[str, list[str]]]] = []

    for path in input_paths:
        gene_ids, sample_ids, data = _read_matrix(path)
        per_matrix.append((gene_ids, sample_ids, data))
        all_gene_sets.append(set(gene_ids))
        print(f"  {path.name}: {len(sample_ids)} samples, {len(gene_ids)} genes", file=sys.stderr)

    # Intersection of gene IDs across all matrices
    shared_genes_set = all_gene_sets[0]
    for s in all_gene_sets[1:]:
        shared_genes_set = shared_genes_set & s
    # Preserve order from first matrix
    shared_genes = [g for g in per_matrix[0][0] if g in shared_genes_set]
    print(f"  Shared genes: {len(shared_genes)}", file=sys.stderr)

    # Collect all sample IDs in order, check uniqueness
    all_sample_ids: list[str] = []
    for gene_ids, sample_ids, _ in per_matrix:
        for sid in sample_ids:
            if sid in all_sample_ids:
                print(f"WARNING: duplicate sample_id '{sid}' across studies — skipping", file=sys.stderr)
            else:
                all_sample_ids.append(sid)

    # Write merged matrix
    out_matrix.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing merged matrix: {len(all_sample_ids)} samples x {len(shared_genes)} genes", file=sys.stderr)
    with open(out_matrix, "w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["gene_id"] + all_sample_ids)
        for gid in shared_genes:
            row = [gid]
            for _, sample_ids, data in per_matrix:
                counts = data.get(gid, ["0"] * len(sample_ids))
                row.extend(counts)
            writer.writerow(row)

    # Write study membership metadata
    if out_metadata:
        study_id_list = study_ids if len(study_ids) == len(input_paths) else [p.stem for p in input_paths]
        with open(out_metadata, "w", newline="") as fh:
            writer = csv.DictWriter(fh, delimiter="\t", fieldnames=["sample_id", "source_study"], lineterminator="\n")
            writer.writeheader()
            for (_, sample_ids, _), sid in zip(per_matrix, study_id_list):
                for s in sample_ids:
                    writer.writerow({"sample_id": s, "source_study": sid})

    print(f"Done: {out_matrix}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", nargs="+", required=True, help="List of count matrix TSVs to merge")
    p.add_argument("--out_tsv", required=True)
    p.add_argument("--study_ids", nargs="+", default=[])
    p.add_argument("--out_metadata_tsv", default=None)
    args = p.parse_args()

    merge(
        input_paths=[Path(x) for x in args.inputs],
        study_ids=args.study_ids,
        out_matrix=Path(args.out_tsv),
        out_metadata=Path(args.out_metadata_tsv) if args.out_metadata_tsv else None,
    )


if __name__ == "__main__":
    main()
