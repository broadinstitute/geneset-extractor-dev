#!/usr/bin/env python3
"""
Expand inputs/ensg_to_symbol.tsv with CBTN ENSG IDs via mygene.info.
Run from KidsFirst_non_CBTN project root.

Usage:
  python3 KidsFirst_DE_Analysis/src/expand_gene_map_cbtn.py
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

ANALYSIS_DIR = Path("outputs/analysis")
GENE_MAP_PATH = Path("inputs/ensg_to_symbol.tsv")
BATCH_SIZE = 1000

CBTN_SLUGS = [
    "low_grade_glioma",
    "malignant_glioma",
    "medulloblastoma",
    "ependymoma",
    "ganglioglioma",
    "craniopharyngioma",
    "atypical_teratoid_rhabdoid_tumor",
]


def load_gene_map(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with open(path) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            gid = row.get("gene_id", "").strip()
            sym = row.get("gene_symbol", "").strip()
            if gid and sym:
                mapping[gid] = sym
    return mapping


def collect_cbtn_ensg_ids() -> set[str]:
    ids: set[str] = set()
    for slug in CBTN_SLUGS:
        tsv = ANALYSIS_DIR / f"CBTN-{slug}" / "rsem_counts.tsv"
        if not tsv.exists():
            print(f"  [WARN] missing: {tsv}", file=sys.stderr)
            continue
        with open(tsv) as fh:
            reader = csv.reader(fh, delimiter="\t")
            next(reader)  # skip header
            for row in reader:
                if row:
                    gid = row[0].strip().split(".")[0]
                    if gid.startswith("ENSG"):
                        ids.add(gid)
        print(f"  read: {tsv.name} ({slug})", file=sys.stderr)
    return ids


def query_mygene_batch(ensg_ids: list[str]) -> dict[str, str]:
    data = urllib.parse.urlencode({
        "ids": ",".join(ensg_ids),
        "fields": "symbol",
        "species": "human",
    }).encode()
    req = urllib.request.Request(
        "https://mygene.info/v3/gene",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        results = json.loads(resp.read())

    mapping: dict[str, str] = {}
    for hit in results:
        if isinstance(hit, dict) and not hit.get("notfound") and "symbol" in hit:
            mapping[hit.get("query", "")] = hit["symbol"]
    return mapping


def main() -> None:
    print("Loading existing gene map...", file=sys.stderr)
    existing = load_gene_map(GENE_MAP_PATH)
    print(f"  {len(existing)} existing entries", file=sys.stderr)

    print("\nCollecting CBTN ENSG IDs...", file=sys.stderr)
    cbtn_ids = collect_cbtn_ensg_ids()
    print(f"  {len(cbtn_ids)} unique ENSG IDs from CBTN", file=sys.stderr)

    new_ids = sorted(gid for gid in cbtn_ids if gid not in existing)
    print(f"  {len(new_ids)} new IDs not in existing map", file=sys.stderr)

    if not new_ids:
        print("Nothing to add — gene map already covers CBTN IDs.", file=sys.stderr)
        return

    print(f"\nQuerying mygene.info ({len(new_ids)} IDs, batch={BATCH_SIZE})...", file=sys.stderr)
    new_mapping: dict[str, str] = {}
    for i in range(0, len(new_ids), BATCH_SIZE):
        batch = new_ids[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(new_ids) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  batch {batch_num}/{total_batches} ({len(batch)} IDs)...", file=sys.stderr)
        result = query_mygene_batch(batch)
        new_mapping.update(result)
        print(f"    → {len(result)} symbols found", file=sys.stderr)
        if i + BATCH_SIZE < len(new_ids):
            time.sleep(0.3)  # be polite to the API

    print(f"\n  Total new symbols: {len(new_mapping)} / {len(new_ids)} queried", file=sys.stderr)

    # Append new entries to gene map (preserve existing)
    with open(GENE_MAP_PATH, "a", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        for gid, sym in sorted(new_mapping.items()):
            writer.writerow([gid, sym])

    print(f"\nUpdated: {GENE_MAP_PATH}", file=sys.stderr)
    print(f"  Before: {len(existing)}", file=sys.stderr)
    print(f"  Added:  {len(new_mapping)}", file=sys.stderr)
    print(f"  After:  {len(existing) + len(new_mapping)}", file=sys.stderr)
    print("\nNext steps:", file=sys.stderr)
    print("  1. Delete CBTN de_inputs + de_results (see below)", file=sys.stderr)
    print("  2. sbatch KidsFirst_DE_Analysis/run/sbatch_02_cbtn.de.sh", file=sys.stderr)


if __name__ == "__main__":
    main()
