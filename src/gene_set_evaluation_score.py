
"""Local validation scoring of gene sets against reference sets and negative controls.

Purpose
    For each input gene set (one GMT line), run hypergeometric enrichment against reference gene sets plus
    size-matched random negative controls, keep the top hits, and score how many hits are negative controls.
    The enrichment math matches the service (dcc/compute_utils.py: compute_enrichment, hypergeometric path only).

Pipeline (all in-process, no files written except the requested outputs)
    build_evaluation_context(reference_paths, negative_controls_path, seed)
        reference GMTs -> gene universe (sorted union of reference genes) + genes x sets sparse matrix
        negative controls: loaded from GMT if given and found, else generated in memory (names start with
        NEGATIVE_CONTROL_PREFIX; each control has the size of its source set; seed makes them reproducible)
    score_gmt_file(gmt_file, context, ...) -> score_gene_sets -> per input gene set:
        evaluate_gene_set: genes_to_vector -> compute_enrichment -> rank_enriched_gene_sets
            (p < p_value_cutoff, ascending p-value, at most max_gene_sets hits)
        summarize_hits: negative_control_count, n_hits, evaluation_score = 1 - 2 * controls / hits (0 if no hits)

Outputs
    Summary TSV (-o): columns in SUMMARY_COLUMNS, one row per input gene set in input order.
        Never overwritten unless -O/--force-rewrite is given.
    Optional intermediate file (--intermediate-results): one line per hit, tab-delimited:
        gene_set_name, gene_set_name, gene_set_size, rank (0 = smallest p), hit name, hit size, p-value. Always overwritten.

CLI example
    python3 gene_set_evaluation_score.py -f input.gmt -r ref_dir_or_file.gmt [-r more] [-n controls_dir_or_file]
        --seed 1 -o out/summary.tsv [-O] [--intermediate-results out/hits.txt] [-v | -q]
    -v also logs per gene set messages (debug level); -q logs warnings/errors only.

Notes
    - Input and reference paths can be files or folders (a folder contributes all its .gmt files, sorted by name).
    - Input genes not in the reference universe are dropped (logged only with -v); the universe size affects p-values.
    - Controls loaded from file are only counted if their names start with NEGATIVE_CONTROL_PREFIX.
    - Runtime is dominated by one hypergeometric test over all gene sets per input gene set (a run against a
      reference + controls matrix of ~46k gene sets took about 5 minutes).
"""
import argparse
import csv
import os
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sparse
from scipy.stats import hypergeom

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEFAULT_P_VALUE_CUTOFF = 0.05
DEFAULT_MAX_GENE_SETS = 50
NEGATIVE_CONTROL_PREFIX = "negative_control_"
SUMMARY_COLUMNS = ["gene_set_name", "negative_control_count", "n_hits", "evaluation_score"]

def compute_enrichment(gene_list, gene_sets):
    """
    Compute enrichment p-values using the Hypergeometric Distribution.
    """
    logger.debug("Calculating enrichment p-values")

    n_all_genes = gene_sets.shape[0]
    intersections = sparse.csc_matrix(gene_list) @ (gene_sets)
    intersections = intersections.toarray()[0,:]
    gene_set_sizes = gene_sets.sum(axis=0).A1
    gene_list_size = sum(sum(gene_list))

    # Calculate the p-value using the hypergeometric test
    #     # Sizes for the hypergeometric test
    #     M = n_all_genes  # Total number of genes
    #     N = len(gene_set_genes)  # Size of the gene set
    #     n = len(gene_list)  # Size of the input gene list
    #     K = len(set(gene_list) & set(gene_set_genes))  # Overlap between gene list and gene set
    #     # Compute the p-value using the survival function (sf)
    #     p_value = hypergeom.sf(K - 1, M, N, n)
    pvalues = hypergeom.sf(intersections-1, n_all_genes, gene_list_size, gene_set_sizes)
    logger.debug("Enrichment p-values calculated for %d gene sets." % len(pvalues))
    return pvalues, gene_set_sizes


@dataclass
class EvaluationContext:
    gene_index: dict
    matrix: sparse.csc_matrix
    gene_set_names: list


def read_gmt(gmt_file):
    """Read a GMT file into an ordered {gene_set_name: [genes]} dict."""
    gene_sets = {}
    with open(gmt_file, 'r') as f:
        for line in f:
            parts = line.rstrip("\r\n").split("\t")
            if not parts[0]:
                continue
            gene_sets[parts[0]] = [gene for gene in parts[2:] if gene]
    return gene_sets


def expand_gmt_paths(paths):
    """Expand files and folders into a list of GMT files; a folder contributes all its .gmt files (sorted)."""
    if isinstance(paths, str):
        paths = [paths]
    gmt_files = []
    for path in paths:
        if os.path.isdir(path):
            gmt_files.extend(os.path.join(path, name) for name in sorted(os.listdir(path)) if name.lower().endswith(".gmt"))
        else:
            gmt_files.append(path)
    return gmt_files


def _read_named_gene_sets(gmt_files):
    named_gene_sets = []
    for gmt_file in gmt_files:
        named_gene_sets.extend(read_gmt(gmt_file).items())
    return named_gene_sets


def _build_matrix(named_gene_sets, gene_index):
    """Build a genes x gene-sets 0/1 CSC matrix; genes missing from gene_index are dropped."""
    rows, cols = [], []
    n_dropped = 0
    for col, (_, genes) in enumerate(named_gene_sets):
        for gene in set(genes):
            if gene in gene_index:
                rows.append(gene_index[gene])
                cols.append(col)
            else:
                n_dropped += 1
    if n_dropped:
        logger.warning("Dropped %d gene memberships not in the gene universe.", n_dropped)
    data = np.ones(len(rows), dtype=np.int64)
    return sparse.csc_matrix((data, (rows, cols)), shape=(len(gene_index), len(named_gene_sets)))


def build_reference_matrix(gmt_files):
    """Build the gene universe, gene index and reference gene set matrix from a list of GMT files."""
    named_gene_sets = _read_named_gene_sets(gmt_files)
    universe = sorted({gene for _, genes in named_gene_sets for gene in genes})
    gene_index = {gene: i for i, gene in enumerate(universe)}
    matrix = _build_matrix(named_gene_sets, gene_index)
    names = [name for name, _ in named_gene_sets]
    logger.info("Built reference matrix with %d genes and %d gene sets.", matrix.shape[0], matrix.shape[1])
    return gene_index, matrix, names


def generate_negative_controls(matrix, suffix=0, seed=None):
    """Generate random negative-control gene sets, each the same size as its source gene set."""
    rng = np.random.default_rng(seed)
    n_genes, n_sets = matrix.shape
    sizes = matrix.getnnz(axis=0)
    if n_sets == 0:
        return sparse.csc_matrix((n_genes, 0), dtype=np.int64), []
    rows = np.concatenate([rng.choice(n_genes, size=int(size), replace=False) for size in sizes])
    cols = np.repeat(np.arange(n_sets), sizes)
    data = np.ones(len(rows), dtype=np.int64)
    controls = sparse.csc_matrix((data, (rows, cols)), shape=(n_genes, n_sets))
    names = ["%s%d_%s" % (NEGATIVE_CONTROL_PREFIX, i, suffix) for i in range(n_sets)]
    logger.info("Generated %d negative control gene sets.", len(names))
    return controls, names


def load_or_create_negative_controls(reference_matrix, gene_index, control_files=None, seed=None, suffix=0):
    """Load negative controls from a list of GMT files if given, otherwise generate them in memory."""
    if control_files:
        named_gene_sets = _read_named_gene_sets(control_files)
        names = [name for name, _ in named_gene_sets]
        if not all(name.startswith(NEGATIVE_CONTROL_PREFIX) for name in names):
            logger.warning("Some loaded negative control names do not start with '%s'; they will not be counted.",
                           NEGATIVE_CONTROL_PREFIX)
        logger.info("Loaded %d negative control gene sets from %d file(s).", len(names), len(control_files))
        return _build_matrix(named_gene_sets, gene_index), names
    return generate_negative_controls(reference_matrix, suffix=suffix, seed=seed)


def build_evaluation_context(reference_paths, negative_controls_path=None, seed=None):
    """Build the reference + negative control gene set matrix used to evaluate input gene lists.

    reference_paths and negative_controls_path accept GMT files or folders (all .gmt files in the folder are used).
    Negative controls are generated in memory when the path is None, missing, or has no .gmt files.
    """
    reference_files = expand_gmt_paths(reference_paths)
    if not reference_files:
        raise ValueError("No GMT files found in reference path(s): %s" % reference_paths)
    control_files = []
    if negative_controls_path:
        if os.path.exists(negative_controls_path):
            control_files = expand_gmt_paths(negative_controls_path)
        if not control_files:
            logger.info("No negative controls GMT found at %s; generating controls.", negative_controls_path)
    gene_index, reference_matrix, reference_names = build_reference_matrix(reference_files)
    control_matrix, control_names = load_or_create_negative_controls(
        reference_matrix, gene_index, control_files=control_files, seed=seed)
    matrix = sparse.hstack([reference_matrix, control_matrix], format="csc")
    return EvaluationContext(gene_index=gene_index, matrix=matrix, gene_set_names=reference_names + control_names)


def genes_to_vector(genes, gene_index):
    """Convert a gene list to a dense 1 x n_genes 0/1 vector; unknown genes are dropped."""
    unique_genes = set(genes)
    indices = [gene_index[gene] for gene in unique_genes if gene in gene_index]
    if len(indices) < len(unique_genes):
        logger.debug("%d of %d input genes are not in the gene universe.", len(unique_genes) - len(indices), len(unique_genes))
    vector = np.zeros((1, len(gene_index)))
    vector[0, indices] = 1
    return vector


def rank_enriched_gene_sets(pvalues, gene_set_sizes, gene_set_names,
                            p_value_cutoff=DEFAULT_P_VALUE_CUTOFF, max_gene_sets=DEFAULT_MAX_GENE_SETS):
    """Return up to max_gene_sets hits with p < cutoff, sorted by ascending p-value."""
    passing = np.flatnonzero(pvalues < p_value_cutoff)
    order = passing[np.lexsort((passing, pvalues[passing]))][:max_gene_sets]
    return [{"gene_set": gene_set_names[i], "gene_set_size": int(gene_set_sizes[i]), "p_value": float(pvalues[i])}
            for i in order]


def evaluate_gene_set(genes, context, p_value_cutoff=DEFAULT_P_VALUE_CUTOFF, max_gene_sets=DEFAULT_MAX_GENE_SETS):
    """Local replacement for run_eaggl(): enriched gene sets for a gene list."""
    vector = genes_to_vector(genes, context.gene_index)
    pvalues, gene_set_sizes = compute_enrichment(vector, context.matrix)
    return rank_enriched_gene_sets(pvalues, gene_set_sizes, context.gene_set_names, p_value_cutoff, max_gene_sets)


def summarize_hits(gene_set_name, gene_set_size, hits):
    """Validation score for one input gene set: top hit and number of negative controls among the hits."""
    top = hits[0] if hits else None
    negative_control_count = sum(hit["gene_set"].startswith(NEGATIVE_CONTROL_PREFIX) for hit in hits)
    return {
        "gene_set_name": gene_set_name,
        "gene_set_size": gene_set_size,
        "top_enriched_gene_set": top["gene_set"] if top else "",
        "enriched_gene_set_size": top["gene_set_size"] if top else "",
        "enriched_gene_set_p_value": top["p_value"] if top else "",
        "negative_control_count": negative_control_count,
        "n_hits": len(hits),
        "evaluation_score": 1 - 2 * negative_control_count / len(hits) if hits else 0
    }


def write_validation_results(out_f, gene_set_name, gene_set_size, hits):
    """Write hits in the 7-column format produced by run_eaggl.save_results."""
    for rank, hit in enumerate(hits):
        out_f.write("{}\t{}\t{}\t{}\t{}\t{}\n".format(
            gene_set_name, gene_set_size, rank, hit["gene_set"], hit["gene_set_size"], hit["p_value"]))


def write_summary(summary_file, scores, overwrite=False):
    """Write score dicts to a tab-delimited summary in the given order; refuses to overwrite unless asked."""
    with open(summary_file, 'w' if overwrite else 'x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(scores)


def score_gene_sets(gene_sets, context, p_value_cutoff=DEFAULT_P_VALUE_CUTOFF,
                    max_gene_sets=DEFAULT_MAX_GENE_SETS, out_f=None):
    """Score each {name: genes} gene set; optionally write per-hit results to the open file out_f."""
    scores = []
    for gene_set_name, genes in gene_sets.items():
        hits = evaluate_gene_set(genes, context, p_value_cutoff, max_gene_sets)
        if out_f is not None:
            write_validation_results(out_f, gene_set_name, len(genes), hits)
        scores.append(summarize_hits(gene_set_name, len(genes), hits))
    return scores


def score_gmt_file(gmt_file, context, p_value_cutoff=DEFAULT_P_VALUE_CUTOFF,
                   max_gene_sets=DEFAULT_MAX_GENE_SETS, out_file=None):
    """Score every gene set in a GMT file; optionally write per-hit results to out_file."""
    gene_sets = read_gmt(gmt_file)
    logger.info("Parsed %d gene sets from %s", len(gene_sets), gmt_file)
    if out_file is None:
        return score_gene_sets(gene_sets, context, p_value_cutoff, max_gene_sets)
    with open(out_file, 'w') as out_f:
        return score_gene_sets(gene_sets, context, p_value_cutoff, max_gene_sets, out_f=out_f)


def main():
    parser = argparse.ArgumentParser(description="Compute gene set validation scores locally (hypergeometric enrichment)")
    parser.add_argument("-f", "--file", required=True, help="GMT file with the gene sets to score")
    parser.add_argument("-r", "--reference", action="append", required=True, help="Reference GMT file or folder of GMT files (can be repeated)")
    parser.add_argument("-n", "--negative-controls", help="Precomputed negative controls GMT file or folder of GMT files; generated in memory if omitted or missing")
    parser.add_argument("--seed", type=int, help="Random seed for generated negative controls")
    parser.add_argument("--p-value", type=float, default=DEFAULT_P_VALUE_CUTOFF, help="P-value cutoff for enriched gene sets")
    parser.add_argument("--max-gene-sets", type=int, default=DEFAULT_MAX_GENE_SETS, help="Maximum enriched gene sets kept per input gene set")
    parser.add_argument("-o", "--output", required=True, help="Summary output file (must not already exist unless -O is given)")
    parser.add_argument("-O", "--force-rewrite", action="store_true", help="Overwrite the summary file if it exists")
    parser.add_argument("--intermediate-results", help="Optional file for per-hit results; overwritten if it exists")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="Also log per gene set processing messages")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="Only log warnings and errors")
    args = parser.parse_args()

    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO)

    for path in [args.file] + args.reference:
        if not os.path.exists(path):
            parser.error("File not found: %s" % path)

    for path in (args.output, args.intermediate_results):
        if path and os.path.isdir(path):
            parser.error("Output path must be a file, but is a folder: %s" % path)

    if os.path.exists(args.output) and not args.force_rewrite:
        parser.error("Summary file already exists: %s (use -O/--force-rewrite to overwrite)" % args.output)
    for path in (args.output, args.intermediate_results):
        if path and os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        context = build_evaluation_context(args.reference, negative_controls_path=args.negative_controls, seed=args.seed)
    except ValueError as e:
        parser.error(str(e))
    scores = score_gmt_file(args.file, context, args.p_value, args.max_gene_sets, out_file=args.intermediate_results)
    write_summary(args.output, scores, overwrite=args.force_rewrite)
    logger.info("Saved summary to %s", args.output)
    if args.intermediate_results:
        logger.info("Saved intermediate results to %s", args.intermediate_results)


if __name__ == "__main__":
    main()


