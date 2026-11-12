#!/usr/bin/env python3
"""Evaluate leaf GMT files in independently schedulable chunks."""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path


def leaf_gmts(root: Path, progress_every: int = 10_000) -> list[Path]:
    """Discover leaf biological GMTs without quadratic parent comparisons."""
    candidates: list[Path] = []
    directories_seen = 0
    for directory, _subdirectories, filenames in os.walk(root):
        directories_seen += 1
        if "genesets.gmt" in filenames:
            candidates.append(Path(directory) / "genesets.gmt")
        if directories_seen % progress_every == 0:
            print(f"discovery directories={directories_seen} gmt_candidates={len(candidates)}", flush=True)
    ancestor_directories: set[Path] = set()
    leaves: list[Path] = []
    for gmt in sorted(candidates, key=lambda path: (len(path.parts), path.as_posix()), reverse=True):
        if gmt.parent in ancestor_directories:
            continue
        leaves.append(gmt)
        ancestor_directories.update(gmt.parent.parents)
    print(f"discovery complete directories={directories_seen} leaf_gmts={len(leaves)}", flush=True)
    return sorted(leaves)


def write_worklist(root: Path, worklist: Path, chunk_size: int, progress_every: int) -> int:
    gmts = leaf_gmts(root, progress_every)
    worklist.parent.mkdir(parents=True, exist_ok=True)
    with worklist.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["chunk_index", "gmt_path"], delimiter="\t")
        writer.writeheader()
        for index, gmt in enumerate(gmts):
            writer.writerow({"chunk_index": index // chunk_size + 1, "gmt_path": str(gmt)})
            if (index + 1) % progress_every == 0:
                print(f"worklist rows={index + 1} chunks={index // chunk_size + 1}", flush=True)
    return (len(gmts) + chunk_size - 1) // chunk_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-output-root", required=True)
    parser.add_argument("--dig-dir", required=True)
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument("--worklist", required=True)
    parser.add_argument("--chunk-size", type=int, default=25)
    parser.add_argument("--progress-every", type=int, default=10_000,
                        help="report discovery and worklist progress every N items")
    parser.add_argument("--task-index", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = Path(args.local_output_root).resolve()
    dig_dir = Path(args.dig_dir).resolve()
    worklist = Path(args.worklist).resolve()
    if args.chunk_size < 1 or args.progress_every < 1:
        raise SystemExit("--chunk-size and --progress-every must be at least 1")
    if not root.is_dir() or not (dig_dir / "src/geneset_extractors").is_dir():
        raise SystemExit("--local-output-root and --dig-dir must be existing directories")
    if args.task_index is None:
        chunks = write_worklist(root, worklist, args.chunk_size, args.progress_every)
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
