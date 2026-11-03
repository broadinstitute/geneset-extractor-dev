#!/usr/bin/env python3
"""Score every GMT below a completed library output root.

The command is intended to run after GMT generation and before publication.  It
uses the union of all GMT files below ``--local_output_root`` as the reference
collection, adds size-matched random negative controls, and writes a summary
next to every source GMT.  For example, ``model.gmt`` produces
``model.evaluation.tsv``.
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Iterable, Sequence


LOGGER = logging.getLogger(__name__)
NEGATIVE_CONTROL_PREFIX = "negative_control_"
SUMMARY_COLUMNS = ["gene_set_name", "negative_control_count", "n_hits", "evaluation_score"]


def discover_gmt_files(local_output_root: Path) -> list[Path]:
    """Return all GMT files below *local_output_root* in stable path order."""
    return sorted(
        (path for path in local_output_root.rglob("*") if path.is_file() and path.suffix.lower() == ".gmt"),
        key=lambda path: path.relative_to(local_output_root).as_posix(),
    )


def evaluation_output_path(gmt_path: Path) -> Path:
    """Return the sidecar evaluation TSV path for one GMT file."""
    return gmt_path.with_suffix(".evaluation.tsv")


def read_gmt(gmt_path: Path) -> list[tuple[str, list[str]]]:
    """Read the name and genes from each non-empty GMT line."""
    gene_sets: list[tuple[str, list[str]]] = []
    with gmt_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            fields = line.rstrip("\r\n").split("\t")
            if not fields or not fields[0]:
                continue
            if len(fields) < 3:
                raise ValueError(f"{gmt_path}:{line_number}: expected at least three GMT columns")
            gene_sets.append((fields[0], [gene for gene in fields[2:] if gene]))
    return gene_sets


def _build_matrix(named_gene_sets: Sequence[tuple[str, list[str]]], gene_index: dict[str, int]):
    import numpy as np
    import scipy.sparse as sparse

    rows: list[int] = []
    columns: list[int] = []
    for column, (_, genes) in enumerate(named_gene_sets):
        rows.extend(gene_index[gene] for gene in set(genes) if gene in gene_index)
        columns.extend([column] * sum(gene in gene_index for gene in set(genes)))
    return sparse.csc_matrix(
        (np.ones(len(rows), dtype=np.int8), (rows, columns)),
        shape=(len(gene_index), len(named_gene_sets)),
    )


def build_context(gmt_files: Iterable[Path], seed: int | None):
    """Build a reference-plus-negative-control matrix from all discovered GMTs."""
    import numpy as np
    import scipy.sparse as sparse

    named_gene_sets = [gene_set for gmt_path in gmt_files for gene_set in read_gmt(gmt_path)]
    if not named_gene_sets:
        raise ValueError("No gene sets were found in the discovered GMT files")
    universe = sorted({gene for _, genes in named_gene_sets for gene in genes})
    if not universe:
        raise ValueError("The discovered GMT files contain no genes")
    gene_index = {gene: index for index, gene in enumerate(universe)}
    reference_matrix = _build_matrix(named_gene_sets, gene_index)
    sizes = reference_matrix.getnnz(axis=0)
    rng = np.random.default_rng(seed)
    control_rows = np.concatenate(
        [rng.choice(len(gene_index), size=int(size), replace=False) for size in sizes]
    )
    control_columns = np.repeat(np.arange(len(sizes)), sizes)
    control_matrix = sparse.csc_matrix(
        (np.ones(len(control_rows), dtype=np.int8), (control_rows, control_columns)),
        shape=reference_matrix.shape,
    )
    names = [name for name, _ in named_gene_sets]
    control_names = [f"{NEGATIVE_CONTROL_PREFIX}{index}" for index in range(len(names))]
    return gene_index, sparse.hstack([reference_matrix, control_matrix], format="csc"), names + control_names


def score_gene_set(
    genes: Sequence[str],
    gene_index: dict[str, int],
    reference_matrix,
    reference_names: Sequence[str],
    p_value_cutoff: float,
    max_gene_sets: int,
) -> tuple[int, int, float]:
    import numpy as np
    import scipy.sparse as sparse
    from scipy.stats import hypergeom

    indices = [gene_index[gene] for gene in set(genes) if gene in gene_index]
    if not indices:
        return 0, 0, 0.0
    query = sparse.csc_matrix((np.ones(len(indices), dtype=np.int8), ([0] * len(indices), indices)),
                              shape=(1, len(gene_index)))
    overlaps = (query @ reference_matrix).toarray()[0]
    sizes = reference_matrix.getnnz(axis=0)
    p_values = hypergeom.sf(overlaps - 1, len(gene_index), len(indices), sizes)
    passing = np.flatnonzero(p_values < p_value_cutoff)
    selected = passing[np.lexsort((passing, p_values[passing]))][:max_gene_sets]
    negative_control_count = sum(reference_names[index].startswith(NEGATIVE_CONTROL_PREFIX) for index in selected)
    n_hits = len(selected)
    return negative_control_count, n_hits, 1 - 2 * negative_control_count / n_hits if n_hits else 0.0


def evaluate_gmt(
    gmt_path: Path,
    output_path: Path,
    gene_index: dict[str, int],
    reference_matrix,
    reference_names: Sequence[str],
    p_value_cutoff: float,
    max_gene_sets: int,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Evaluation output already exists: {output_path} (use --overwrite)")
    rows = []
    for gene_set_name, genes in read_gmt(gmt_path):
        negative_control_count, n_hits, evaluation_score = score_gene_set(
            genes, gene_index, reference_matrix, reference_names, p_value_cutoff, max_gene_sets
        )
        rows.append({
            "gene_set_name": gene_set_name,
            "negative_control_count": negative_control_count,
            "n_hits": n_hits,
            "evaluation_score": evaluation_score,
        })
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate every GMT below a library output root")
    parser.add_argument("--local_output_root", required=True, help="Completed library output directory")
    parser.add_argument("--seed", type=int, help="Random seed for generated negative controls")
    parser.add_argument("--p_value", type=float, default=0.05, help="Strict enrichment p-value cutoff")
    parser.add_argument("--max_gene_sets", type=int, default=50, help="Maximum retained hits per input gene set")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing *.evaluation.tsv sidecars")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = Path(args.local_output_root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Missing local output root: {root}")
    if not 0 < args.p_value <= 1:
        raise SystemExit("--p_value must be greater than 0 and at most 1")
    if args.max_gene_sets < 1:
        raise SystemExit("--max_gene_sets must be at least 1")
    gmt_files = discover_gmt_files(root)
    if not gmt_files:
        raise SystemExit(f"No .gmt files found below: {root}")
    try:
        gene_index, reference_matrix, reference_names = build_context(gmt_files, args.seed)
        for gmt_path in gmt_files:
            output_path = evaluation_output_path(gmt_path)
            evaluate_gmt(gmt_path, output_path, gene_index, reference_matrix, reference_names,
                         args.p_value, args.max_gene_sets, args.overwrite)
            LOGGER.info("wrote %s", output_path)
    except (ImportError, ValueError, FileExistsError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
