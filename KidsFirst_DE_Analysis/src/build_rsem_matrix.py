#!/usr/bin/env python3
"""
Build a gene x sample count matrix from RSEM *.rsem.genes.results.gz files.
Extracts expected_count (rounded to int) per gene per sample.

Usage:
  python build_rsem_matrix.py \
    --rsem_dir KidsFirst_KF_TALL/outputs/rsem_files \
    --manifest_tsv KidsFirst_KF_TALL/config/rsem_manifest.tsv \
    --out_tsv outputs/analysis/tall/rsem_counts.tsv
"""
import argparse
import csv
import gzip
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def _load_manifest(
    manifest_path: Path,
    filter_column: str | None = None,
    filter_value: str | None = None,
) -> dict[str, str]:
    """Returns {file_name: sample_id} mapping.

    If filter_column and filter_value are provided, only rows where
    row[filter_column] == filter_value are included.
    Used for CBTN where one manifest covers all diagnoses.
    """
    mapping = {}
    skipped = 0
    with open(manifest_path) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if filter_column and filter_value:
                if row.get(filter_column, "").strip() != filter_value:
                    skipped += 1
                    continue
            fname = (row.get("file_name") or "").strip()
            sid = (row.get("sample_id") or "").strip()
            if fname and sid:
                mapping[fname] = sid
    if filter_column and filter_value:
        print(
            f"  Manifest filter: {filter_column}=={filter_value!r} "
            f"→ {len(mapping)} kept, {skipped} skipped",
            file=sys.stderr,
        )
    return mapping


def _read_one_rsem(args: tuple[Path, str]) -> tuple[str, list[str], list[float]]:
    """Read a single RSEM file. Returns (sample_id, gene_ids, counts)."""
    path, sample_id = args
    gene_ids = []
    counts = []
    open_fn = gzip.open if path.suffix == ".gz" else open
    with open_fn(path, "rt") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            gene_ids.append(row["gene_id"])
            counts.append(float(row["expected_count"]))
    return sample_id, gene_ids, counts


def build_matrix(
    rsem_dir: Path,
    manifest_path: Path | None,
    out_path: Path,
    workers: int = 4,
    filter_column: str | None = None,
    filter_value: str | None = None,
) -> None:
    rsem_files = sorted(rsem_dir.glob("*.rsem.genes.results.gz"))
    if not rsem_files:
        print(f"ERROR: no .rsem.genes.results.gz files in {rsem_dir}", file=sys.stderr)
        sys.exit(1)

    file_to_sample: dict[str, str] = {}
    if manifest_path and manifest_path.exists():
        file_to_sample = _load_manifest(manifest_path, filter_column, filter_value)

    tasks = []
    for f in rsem_files:
        if file_to_sample and f.name not in file_to_sample:
            # When a filtered manifest is provided, skip files not in the filter
            continue
        sid = file_to_sample.get(f.name, f.name.split(".rsem.genes.results")[0])
        tasks.append((f, sid))

    print(f"Reading {len(tasks)} RSEM files with {workers} workers...", file=sys.stderr)

    results: dict[str, list[float]] = {}
    gene_ids: list[str] | None = None

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_read_one_rsem, t): t[1] for t in tasks}
        done = 0
        for future in as_completed(futures):
            sid, gids, counts = future.result()
            if gene_ids is None:
                gene_ids = gids
            results[sid] = counts
            done += 1
            if done % 100 == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)}", file=sys.stderr, end="\r")

    print(f"\n  {len(results)} samples, {len(gene_ids)} genes", file=sys.stderr)

    sample_ids = sorted(results.keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["gene_id"] + sample_ids)
        for i, gene_id in enumerate(gene_ids):
            row = [gene_id] + [str(int(round(results[sid][i]))) for sid in sample_ids]
            writer.writerow(row)

    print(f"Written: {out_path}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rsem_dir", required=True)
    p.add_argument("--manifest_tsv", default=None)
    p.add_argument("--out_tsv", required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--filter_column", default=None,
                   help="Manifest column to filter on (e.g. 'diagnosis_slug' for CBTN)")
    p.add_argument("--filter_value", default=None,
                   help="Value to keep (e.g. 'low_grade_glioma')")
    args = p.parse_args()

    build_matrix(
        rsem_dir=Path(args.rsem_dir),
        manifest_path=Path(args.manifest_tsv) if args.manifest_tsv else None,
        out_path=Path(args.out_tsv),
        workers=args.workers,
        filter_column=args.filter_column,
        filter_value=args.filter_value,
    )


if __name__ == "__main__":
    main()
