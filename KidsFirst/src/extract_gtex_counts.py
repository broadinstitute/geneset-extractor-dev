#!/usr/bin/env python3
"""
Extract a tissue-specific count matrix from a GTEx GCT file.
Output format matches build_rsem_matrix.py: gene_id x sample TSV.

Usage:
  python extract_gtex_counts.py \
    --gct inputs/GTEx/v10/gene_reads_v10_whole_blood.gct.gz \
    --sample_attrs inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt \
    --tissue "Whole Blood" \
    --out_tsv outputs/analysis/gtex_whole_blood_counts.tsv

Tissue values (SMTSD column in SampleAttributes):
  "Whole Blood"          whole_blood GCT
  "Adrenal Gland"        adrenal_gland GCT
  "Muscle - Skeletal"    muscle_skeletal GCT
  "Brain - Cortex"       brain_cortex GCT
"""
import argparse
import csv
import gzip
import sys
from pathlib import Path


def _open(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _get_tissue_sample_ids(sample_attrs_path: Path, tissue: str) -> set[str]:
    """Return sample IDs where SMTSD matches tissue."""
    ids: set[str] = set()
    with open(sample_attrs_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if row.get("SMTSD", "").strip() == tissue:
                sid = row.get("SAMPID", "").strip()
                if sid:
                    ids.add(sid)
    return ids


def extract(gct_path: Path, sample_attrs_path: Path, tissue: str, out_path: Path) -> None:
    tissue_ids = _get_tissue_sample_ids(sample_attrs_path, tissue)
    if not tissue_ids:
        print(f"ERROR: no samples found for tissue '{tissue}'", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(tissue_ids)} samples in SampleAttributes for '{tissue}'", file=sys.stderr)

    # Read GCT header to find which columns to keep
    with _open(gct_path) as fh:
        fh.readline()  # #1.2
        fh.readline()  # dims
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader)  # Name Description sample1 sample2 ...

    all_sample_ids = header[2:]
    keep_idx = [i for i, sid in enumerate(all_sample_ids) if sid in tissue_ids]
    keep_ids = [all_sample_ids[i] for i in keep_idx]

    if not keep_ids:
        print(f"ERROR: none of the {len(tissue_ids)} tissue samples found in GCT header", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(keep_ids)} samples found in GCT", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_genes = 0

    with _open(gct_path) as fh, open(out_path, "w", newline="") as out_fh:
        fh.readline()
        fh.readline()
        reader = csv.reader(fh, delimiter="\t")
        next(reader)  # skip header
        writer = csv.writer(out_fh, delimiter="\t")
        writer.writerow(["gene_id"] + keep_ids)
        for row in reader:
            if not row:
                continue
            gene_id = row[0].strip()
            # GTEx: row[0]=Name (Ensembl ID), row[1]=Description (symbol), row[2+]=counts
            counts = [row[2 + i] for i in keep_idx]
            writer.writerow([gene_id] + counts)
            n_genes += 1

    print(f"  {n_genes} genes written", file=sys.stderr)
    print(f"Written: {out_path}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gct", required=True, help="GTEx GCT .gz file")
    p.add_argument("--sample_attrs", required=True, help="GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt")
    p.add_argument("--tissue", required=True, help="SMTSD value, e.g. 'Whole Blood'")
    p.add_argument("--out_tsv", required=True)
    args = p.parse_args()

    extract(
        gct_path=Path(args.gct),
        sample_attrs_path=Path(args.sample_attrs),
        tissue=args.tissue,
        out_path=Path(args.out_tsv),
    )


if __name__ == "__main__":
    main()
