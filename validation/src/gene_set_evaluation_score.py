
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
SUMMARY_COLUMNS = ["gene_set_name_suffix", "gene_set_size", "top_enriched_gene_set", "enriched_gene_set_size",
                   "enriched_gene_set_p_value", "negative_control_count", "n_hits"]

def compute_enrichment(gene_list, gene_sets):
    """
    Compute enrichment p-values using the Hypergeometric Distribution.
    """
    logger.info("Calculating enrichment p-values")

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
    logger.info("Enrichment p-values calculated for %d gene sets." % len(pvalues))
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
    """Build the gene universe, gene index and reference gene set matrix from GMT files."""
    named_gene_sets = []
    for gmt_file in gmt_files:
        named_gene_sets.extend(read_gmt(gmt_file).items())
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
    return controls, names


def load_or_create_negative_controls(reference_matrix, gene_index, path=None, seed=None, suffix=0):
    """Load negative controls from a GMT file if it exists, otherwise generate them in memory."""
    if path and os.path.exists(path):
        named_gene_sets = list(read_gmt(path).items())
        names = [name for name, _ in named_gene_sets]
        if not all(name.startswith(NEGATIVE_CONTROL_PREFIX) for name in names):
            logger.warning("Some negative control names in %s do not start with '%s'; they will not be counted.",
                           path, NEGATIVE_CONTROL_PREFIX)
        logger.info("Loaded %d negative control gene sets from %s.", len(names), path)
        return _build_matrix(named_gene_sets, gene_index), names
    if path:
        logger.info("Negative controls file %s not found; generating controls.", path)
    return generate_negative_controls(reference_matrix, suffix=suffix, seed=seed)


def build_evaluation_context(reference_gmt_files, negative_controls_file=None, seed=None):
    """Build the reference + negative control gene set matrix used to evaluate input gene lists."""
    gene_index, reference_matrix, reference_names = build_reference_matrix(reference_gmt_files)
    control_matrix, control_names = load_or_create_negative_controls(
        reference_matrix, gene_index, path=negative_controls_file, seed=seed)
    matrix = sparse.hstack([reference_matrix, control_matrix], format="csc")
    return EvaluationContext(gene_index=gene_index, matrix=matrix, gene_set_names=reference_names + control_names)


def genes_to_vector(genes, gene_index):
    """Convert a gene list to a dense 1 x n_genes 0/1 vector; unknown genes are dropped."""
    unique_genes = set(genes)
    indices = [gene_index[gene] for gene in unique_genes if gene in gene_index]
    if len(indices) < len(unique_genes):
        logger.warning("%d of %d input genes are not in the gene universe.", len(unique_genes) - len(indices), len(unique_genes))
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
    return {
        "gene_set_name_suffix": gene_set_name,
        "gene_set_size": gene_set_size,
        "top_enriched_gene_set": top["gene_set"] if top else "",
        "enriched_gene_set_size": top["gene_set_size"] if top else "",
        "enriched_gene_set_p_value": top["p_value"] if top else "",
        "negative_control_count": sum(hit["gene_set"].startswith(NEGATIVE_CONTROL_PREFIX) for hit in hits),
        "n_hits": len(hits),
    }


def write_validation_results(out_f, gene_set_name, gene_set_size, hits):
    """Write hits in the 8-column format produced by run_eaggl.save_results."""
    model, _, suffix = gene_set_name.partition("__")
    for rank, hit in enumerate(hits):
        out_f.write("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(
            model, suffix, gene_set_name, gene_set_size, rank, hit["gene_set"], hit["gene_set_size"], hit["p_value"]))


def write_summary(summary_file, scores):
    """Write score dicts to a tab-delimited summary sorted by gene set name."""
    with open(summary_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS, delimiter='\t')
        writer.writeheader()
        writer.writerows(sorted(scores, key=lambda score: score["gene_set_name_suffix"]))


def score_gene_sets(gene_sets, context, p_value_cutoff=DEFAULT_P_VALUE_CUTOFF,
                    max_gene_sets=DEFAULT_MAX_GENE_SETS, out_f=None):
    """Score each {name: genes} gene set; optionally write the 8-column results to the open file out_f."""
    scores = []
    for gene_set_name, genes in gene_sets.items():
        hits = evaluate_gene_set(genes, context, p_value_cutoff, max_gene_sets)
        if out_f is not None:
            write_validation_results(out_f, gene_set_name, len(genes), hits)
        scores.append(summarize_hits(gene_set_name, len(genes), hits))
    return scores


def score_gmt_file(gmt_file, context, p_value_cutoff=DEFAULT_P_VALUE_CUTOFF,
                   max_gene_sets=DEFAULT_MAX_GENE_SETS, out_file=None):
    """Score every gene set in a GMT file; optionally write the 8-column results to out_file."""
    gene_sets = read_gmt(gmt_file)
    logger.info("Parsed %d gene sets from %s", len(gene_sets), gmt_file)
    if out_file is None:
        return score_gene_sets(gene_sets, context, p_value_cutoff, max_gene_sets)
    with open(out_file, 'w') as out_f:
        return score_gene_sets(gene_sets, context, p_value_cutoff, max_gene_sets, out_f=out_f)


def main():
    parser = argparse.ArgumentParser(description="Compute gene set validation scores locally (hypergeometric enrichment)")
    parser.add_argument("-f", "--file", required=True, help="GMT file with the gene sets to score")
    parser.add_argument("-r", "--reference", action="append", required=True, help="Reference GMT file (can be repeated)")
    parser.add_argument("-n", "--negative-controls", help="Precomputed negative controls GMT; generated in memory if omitted or missing")
    parser.add_argument("--seed", type=int, help="Random seed for generated negative controls")
    parser.add_argument("--p-value", type=float, default=DEFAULT_P_VALUE_CUTOFF, help="P-value cutoff for enriched gene sets")
    parser.add_argument("--max-gene-sets", type=int, default=DEFAULT_MAX_GENE_SETS, help="Maximum enriched gene sets kept per input gene set")
    parser.add_argument("-o", "--output-folder", required=True, help="Output folder for results")
    parser.add_argument("--force-rewrite", action="store_true", help="Overwrite existing output files")
    args = parser.parse_args()

    for path in [args.file] + args.reference:
        if not os.path.exists(path):
            parser.error("File not found: %s" % path)

    os.makedirs(args.output_folder, exist_ok=True)
    results_file = os.path.join(args.output_folder, "validation_results_eaggl.txt")
    summary_file = os.path.join(args.output_folder, "summary_eaggl.tsv")
    if not args.force_rewrite and os.path.exists(results_file):
        logger.info("Skipping: %s already exists (use --force-rewrite to overwrite).", results_file)
        return

    context = build_evaluation_context(args.reference, negative_controls_file=args.negative_controls, seed=args.seed)
    scores = score_gmt_file(args.file, context, args.p_value, args.max_gene_sets, out_file=results_file)
    write_summary(summary_file, scores)
    logger.info("Saved results to %s and summary to %s", results_file, summary_file)


if __name__ == "__main__":
    main()


