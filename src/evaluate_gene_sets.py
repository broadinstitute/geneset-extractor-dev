#!/usr/bin/env python3
"""Run the vd-evaluation scorer for every generated GMT in one output tree."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path


def discover_gmt_files(local_output_root: Path) -> list[Path]:
    """Return all GMT files below *local_output_root* in stable path order."""
    return sorted(
        (path for path in local_output_root.rglob("*") if path.is_file() and path.suffix.lower() == ".gmt"),
        key=lambda path: path.relative_to(local_output_root).as_posix(),
    )


def evaluation_output_path(gmt_path: Path) -> Path:
    """Return the summary TSV paired with *gmt_path*."""
    return gmt_path.with_suffix(".evaluation.tsv")


def intermediate_output_path(gmt_path: Path, local_output_root: Path, intermediate_root: Path) -> Path:
    """Keep optional hit rows in a tree matching the corresponding GMT path."""
    return intermediate_root / gmt_path.relative_to(local_output_root).with_suffix(".evaluation.hits.tsv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate every GMT below a library output root using the vd-evaluation scorer"
    )
    parser.add_argument("--local_output_root", required=True, help="Completed library output directory to evaluate")
    parser.add_argument(
        "-r", "--reference", action="append", required=True,
        help="Reference GMT file or directory of GMT files (can be repeated)",
    )
    parser.add_argument(
        "-n", "--negative-controls",
        help="Precomputed negative-controls GMT file or directory; controls are generated if omitted or missing",
    )
    parser.add_argument("--seed", type=int, help="Random seed for generated negative controls")
    parser.add_argument("--p-value", type=float, default=0.05, help="Strict enrichment p-value cutoff")
    parser.add_argument("--max-gene-sets", type=int, default=50, help="Maximum enriched hits per input gene set")
    parser.add_argument(
        "--intermediate-results",
        help="Optional directory for per-hit TSVs, preserving the GMT directory structure",
    )
    parser.add_argument(
        "-O", "--force-rewrite", "--overwrite", action="store_true",
        help="Overwrite existing paired summary TSVs",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="Log per-gene-set scorer messages")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="Only log warnings and errors")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO)
    local_output_root = Path(args.local_output_root).expanduser().resolve()
    if not local_output_root.is_dir():
        raise SystemExit(f"Missing local output root: {local_output_root}")
    for reference in args.reference:
        if not Path(reference).exists():
            raise SystemExit(f"Reference path not found: {reference}")
    if not 0 < args.p_value <= 1:
        raise SystemExit("--p-value must be greater than 0 and at most 1")
    if args.max_gene_sets < 1:
        raise SystemExit("--max-gene-sets must be at least 1")
    gmt_files = discover_gmt_files(local_output_root)
    if not gmt_files:
        raise SystemExit(f"No .gmt files found below: {local_output_root}")
    intermediate_root = Path(args.intermediate_results).expanduser().resolve() if args.intermediate_results else None

    try:
        from gene_set_evaluation_score import build_evaluation_context, score_gmt_file
        context = build_evaluation_context(args.reference, args.negative_controls, args.seed)
        for gmt_path in gmt_files:
            output_path = evaluation_output_path(gmt_path)
            if output_path.exists() and not args.force_rewrite:
                raise FileExistsError(f"Summary file already exists: {output_path} (use --force-rewrite to overwrite)")
            hits_path = None
            if intermediate_root is not None:
                hits_path = intermediate_output_path(gmt_path, local_output_root, intermediate_root)
                hits_path.parent.mkdir(parents=True, exist_ok=True)
            scores = score_gmt_file(gmt_path, context, args.p_value, args.max_gene_sets, out_file=hits_path)
            from gene_set_evaluation_score import write_summary
            write_summary(output_path, scores, overwrite=args.force_rewrite)
            logging.info("Saved summary to %s", output_path)
            if hits_path is not None:
                logging.info("Saved intermediate results to %s", hits_path)
    except (ImportError, ValueError, FileExistsError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
