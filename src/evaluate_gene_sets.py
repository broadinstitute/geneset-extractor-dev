#!/usr/bin/env python3
"""Run the vd-evaluation scorer for every generated GMT in one output tree."""

from __future__ import annotations

import argparse
import csv
from contextlib import nullcontext
import logging
from pathlib import Path
import time


SUMMARY_COLUMNS = ["source_gmt", "gene_set_name", "negative_control_count", "n_hits", "evaluation_score"]


def discover_gmt_files(local_output_root: Path) -> list[Path]:
    """Return all GMT files below *local_output_root* in stable path order."""
    return sorted(
        (path for path in local_output_root.rglob("*") if path.is_file() and path.suffix.lower() == ".gmt"),
        key=lambda path: path.relative_to(local_output_root).as_posix(),
    )


def default_evaluation_output_path(local_output_root: Path) -> Path:
    """Return the default consolidated evaluation summary location."""
    return local_output_root / "evaluation" / "evaluation_summary.tsv"


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
    parser.add_argument("--batch-size", type=int, default=128, help="Gene sets evaluated per sparse batch (default: 128)")
    parser.add_argument(
        "--progress-every", type=int, default=100,
        help="Log gene-set progress every N gene sets (default: 100)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Consolidated summary TSV (default: <local_output_root>/evaluation/evaluation_summary.tsv)",
    )
    parser.add_argument(
        "--intermediate-results",
        help="Optional consolidated per-hit TSV; it is overwritten if it exists",
    )
    parser.add_argument(
        "-O", "--force-rewrite", "--overwrite", action="store_true",
        help="Overwrite an existing consolidated summary TSV",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="Log per-gene-set scorer messages")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="Only log warnings and errors")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(message)s",
    )
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
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")
    if args.progress_every < 1:
        raise SystemExit("--progress-every must be at least 1")
    gmt_files = discover_gmt_files(local_output_root)
    if not gmt_files:
        raise SystemExit(f"No .gmt files found below: {local_output_root}")
    output_path = Path(args.output).expanduser().resolve() if args.output else default_evaluation_output_path(local_output_root)
    intermediate_path = Path(args.intermediate_results).expanduser().resolve() if args.intermediate_results else None
    if output_path.exists() and not args.force_rewrite:
        raise SystemExit(f"Summary file already exists: {output_path} (use --force-rewrite to overwrite)")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if intermediate_path is not None:
        intermediate_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from gene_set_evaluation_score import build_evaluation_context, evaluate_gene_sets, read_gmt, summarize_hits
        context = build_evaluation_context(args.reference, args.negative_controls, args.seed)
        gmt_gene_sets = [(gmt_path, read_gmt(gmt_path)) for gmt_path in gmt_files]
        total_gene_sets = sum(len(gene_sets) for _, gene_sets in gmt_gene_sets)
        logging.info("Evaluating %d gene sets across %d GMT files", total_gene_sets, len(gmt_gene_sets))
        started = time.monotonic()
        completed_gene_sets = 0
        with output_path.open("w", newline="", encoding="utf-8") as summary_handle:
            summary_writer = csv.DictWriter(
                summary_handle,
                fieldnames=SUMMARY_COLUMNS,
                delimiter="\t",
                extrasaction="ignore",
            )
            summary_writer.writeheader()
            with (intermediate_path.open("w", newline="", encoding="utf-8") if intermediate_path else nullcontext()) as hits_handle:
                if hits_handle:
                    hits_writer = csv.writer(hits_handle, delimiter="\t")
                    hits_writer.writerow(["source_gmt", "gene_set_name", "gene_set_size", "rank", "hit_gene_set_name", "hit_gene_set_size", "p_value"])
                for gmt_index, (gmt_path, gene_sets) in enumerate(gmt_gene_sets, 1):
                    source_gmt = gmt_path.relative_to(local_output_root).as_posix()
                    logging.info("Evaluating GMT %d/%d: %s", gmt_index, len(gmt_gene_sets), source_gmt)
                    batch_hits = evaluate_gene_sets(
                        list(gene_sets.values()), context, args.p_value, args.max_gene_sets, args.batch_size
                    )
                    for (gene_set_name, genes), hits in zip(gene_sets.items(), batch_hits):
                        score = summarize_hits(gene_set_name, len(genes), hits)
                        summary_writer.writerow({"source_gmt": source_gmt, **score})
                        if hits_handle:
                            for rank, hit in enumerate(hits):
                                hits_writer.writerow([source_gmt, gene_set_name, len(genes), rank,
                                                      hit["gene_set"], hit["gene_set_size"], hit["p_value"]])
                        completed_gene_sets += 1
                        if completed_gene_sets % args.progress_every == 0 or completed_gene_sets == total_gene_sets:
                            elapsed_seconds = time.monotonic() - started
                            remaining_seconds = elapsed_seconds * (total_gene_sets - completed_gene_sets) / completed_gene_sets
                            logging.info(
                                "Evaluated gene sets %d/%d (elapsed %.1f seconds; estimated remaining %.1f seconds)",
                                completed_gene_sets,
                                total_gene_sets,
                                elapsed_seconds,
                                remaining_seconds,
                            )
        logging.info("Saved summary to %s", output_path)
        if intermediate_path is not None:
            logging.info("Saved intermediate results to %s", intermediate_path)
    except (ImportError, ValueError, FileExistsError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
