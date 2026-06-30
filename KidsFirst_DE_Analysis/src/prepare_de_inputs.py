#!/usr/bin/env python3
"""
Merge a KidsFirst tumor count matrix with a GTEx normal count matrix.
Aligns gene IDs (stripping Ensembl version suffixes), then outputs:
  - combined_counts.tsv  (gene_id x all_samples)
  - sample_metadata.tsv  (sample_id, condition, source, diagnosis)

These files are the direct inputs to:
  geneset-extractors workflows rna_de_prepare \
    --counts_tsv combined_counts.tsv \
    --sample_metadata_tsv sample_metadata.tsv \
    --group_column condition \
    --condition_a tumor --condition_b normal

Usage:
  python prepare_de_inputs.py \
    --tumor_counts outputs/analysis/tall/rsem_counts.tsv \
    --normal_counts outputs/analysis/gtex_whole_blood_counts.tsv \
    --tumor_metadata KidsFirst_KF_TALL/config/sample_metadata.tsv \
    --study_id KF-TALL \
    --out_dir outputs/analysis/tall_vs_whole_blood
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def _strip_version(gene_id: str) -> str:
    """ENSG00000000003.15 → ENSG00000000003"""
    return gene_id.split(".")[0] if "." in gene_id else gene_id


def _read_matrix(path: Path) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """Returns (gene_ids_stripped, sample_ids, {gene_id_stripped: [count_str, ...]})"""
    gene_ids = []
    sample_ids = []
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


def _read_tumor_metadata(path: Path, study_id: str) -> dict[str, str]:
    """Returns {sample_id: diagnosis_slug}."""
    mapping: dict[str, str] = {}
    with open(path) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            sid = (row.get("Sample ID") or row.get("sample_id") or "").strip()
            diag = (row.get("Diagnosis (Source Text)") or row.get("diagnosis") or "").strip()
            if sid:
                mapping[sid] = diag or study_id
    return mapping


def _load_gene_map(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    import csv as _csv
    mapping: dict[str, str] = {}
    with open(path) as fh:
        reader = _csv.DictReader(fh, delimiter="\t")
        for row in reader:
            gid = row.get("gene_id", "").strip()
            sym = row.get("gene_symbol", "").strip()
            if gid and sym:
                mapping[gid] = sym
    return mapping


def merge(
    tumor_counts_path: Path,
    normal_counts_path: Path,
    tumor_metadata_path: Path | None,
    study_id: str,
    out_dir: Path,
    gene_map_path: Path | None = None,
) -> None:
    gene_map = _load_gene_map(gene_map_path)
    if gene_map:
        print(f"  Gene symbol map: {len(gene_map)} entries loaded", file=sys.stderr)

    print("Reading tumor counts...", file=sys.stderr)
    tumor_genes, tumor_samples, tumor_data = _read_matrix(tumor_counts_path)
    print(f"  {len(tumor_samples)} tumor samples, {len(tumor_genes)} genes", file=sys.stderr)

    print("Reading normal counts...", file=sys.stderr)
    normal_genes, normal_samples, normal_data = _read_matrix(normal_counts_path)
    print(f"  {len(normal_samples)} normal samples, {len(normal_genes)} genes", file=sys.stderr)

    # Intersect gene IDs (preserve tumor order)
    normal_gene_set = set(normal_genes)
    shared_genes = [g for g in tumor_genes if g in normal_gene_set]
    print(f"  {len(shared_genes)} shared genes after intersection", file=sys.stderr)
    if len(shared_genes) < 10000:
        print("WARNING: fewer than 10k shared genes — check gene ID format", file=sys.stderr)

    # Load tumor sample → diagnosis mapping
    tumor_diag: dict[str, str] = {}
    if tumor_metadata_path and tumor_metadata_path.exists():
        tumor_diag = _read_tumor_metadata(tumor_metadata_path, study_id)

    all_samples = list(tumor_samples) + list(normal_samples)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write combined counts
    counts_path = out_dir / "combined_counts.tsv"
    print(f"Writing {counts_path}...", file=sys.stderr)
    has_symbols = bool(gene_map)
    header = ["gene_id"] + (["gene_symbol"] if has_symbols else []) + all_samples
    with open(counts_path, "w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(header)
        for gene_id in shared_genes:
            tumor_row = tumor_data.get(gene_id, ["0"] * len(tumor_samples))
            normal_row = normal_data.get(gene_id, ["0"] * len(normal_samples))
            sym_cols = [gene_map.get(gene_id, "")] if has_symbols else []
            writer.writerow([gene_id] + sym_cols + tumor_row + normal_row)

    # Write sample metadata
    meta_path = out_dir / "sample_metadata.tsv"
    print(f"Writing {meta_path}...", file=sys.stderr)
    with open(meta_path, "w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            delimiter="\t",
            fieldnames=["sample_id", "condition", "source", "diagnosis"],
            lineterminator="\n",
        )
        writer.writeheader()
        for sid in tumor_samples:
            writer.writerow({
                "sample_id": sid,
                "condition": "tumor",
                "source": study_id,
                "diagnosis": tumor_diag.get(sid, study_id),
            })
        for sid in normal_samples:
            writer.writerow({
                "sample_id": sid,
                "condition": "normal",
                "source": "GTEx",
                "diagnosis": "normal",
            })

    print(f"Done. Outputs in: {out_dir}", file=sys.stderr)
    print(f"  combined_counts.tsv : {len(all_samples)} samples x {len(shared_genes)} genes", file=sys.stderr)
    print(f"  sample_metadata.tsv : {len(tumor_samples)} tumor + {len(normal_samples)} normal", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tumor_counts", required=True)
    p.add_argument("--normal_counts", required=True)
    p.add_argument("--tumor_metadata", default=None)
    p.add_argument("--study_id", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--gene_map_tsv", default=None, help="TSV with gene_id and gene_symbol columns")
    args = p.parse_args()

    merge(
        tumor_counts_path=Path(args.tumor_counts),
        normal_counts_path=Path(args.normal_counts),
        tumor_metadata_path=Path(args.tumor_metadata) if args.tumor_metadata else None,
        study_id=args.study_id,
        out_dir=Path(args.out_dir),
        gene_map_path=Path(args.gene_map_tsv) if args.gene_map_tsv else None,
    )


if __name__ == "__main__":
    main()
