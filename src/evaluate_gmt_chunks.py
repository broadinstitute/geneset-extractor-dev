#!/usr/bin/env python3
"""Evaluate leaf GMT files in independently schedulable chunks."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def leaf_gmts(root: Path) -> list[Path]:
    gmts = sorted(root.rglob("genesets.gmt"))
    return [gmt for gmt in gmts if not any(gmt.parent in other.parent.parents for other in gmts if other != gmt)]


def write_worklist(root: Path, worklist: Path, chunk_size: int) -> int:
    gmts = leaf_gmts(root)
    worklist.parent.mkdir(parents=True, exist_ok=True)
    with worklist.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["chunk_index", "gmt_path"], delimiter="\t")
        writer.writeheader()
        for index, gmt in enumerate(gmts):
            writer.writerow({"chunk_index": index // chunk_size + 1, "gmt_path": str(gmt)})
    return (len(gmts) + chunk_size - 1) // chunk_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-output-root", required=True)
    parser.add_argument("--dig-dir", required=True)
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument("--worklist", required=True)
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--task-index", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = Path(args.local_output_root).resolve()
    dig_dir = Path(args.dig_dir).resolve()
    worklist = Path(args.worklist).resolve()
    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be at least 1")
    if not root.is_dir() or not (dig_dir / "src/geneset_extractors").is_dir():
        raise SystemExit("--local-output-root and --dig-dir must be existing directories")
    if args.task_index is None:
        chunks = write_worklist(root, worklist, args.chunk_size)
        print(f"worklist={worklist} chunks={chunks}")
        return 0
    sys.path.insert(0, str(dig_dir / "src"))
    from geneset_extractors.core.gene_set_evaluation import build_evaluation_context, score_gmt_file, write_summary
    with worklist.open(encoding="utf-8", newline="") as handle:
        gmts = [Path(row["gmt_path"]) for row in csv.DictReader(handle, delimiter="\t") if int(row["chunk_index"]) == args.task_index]
    if not gmts:
        raise SystemExit(f"No GMTs for task index {args.task_index}")
    context = build_evaluation_context(args.reference, seed=args.seed)
    for gmt in gmts:
        output = gmt.with_suffix(".eval")
        if output.exists() and not args.overwrite:
            print(f"skipped={output}")
            continue
        scores = score_gmt_file(gmt, context)
        write_summary(output, scores, overwrite=True)
        print(f"written={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
