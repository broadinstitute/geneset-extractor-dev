import os
import argparse
from collections import defaultdict
import sys

from run_validation import parse_gmt_file
from validation_summary import key, parse_gtex_gene_set_name_suffix
from gene_set_comparison import load_genesets
from run_eaggl import run_eaggl, run_pigean, save_results

DEFAULT_BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/runs/gtex_all_models/genesets"
DEFAULT_OUT_FOLDER = "../../data/gtex/output.tissue"
MIN_GENES_FOR_CONSENSUS = 4

def consensus_counts(gene_sets):
    """
    Takes a collection of gene sets (dict of {source: [genes]} or iterable of gene lists)
    and returns an ordered list of (gene, count) tuples sorted from most to least frequent.
    """
    counts = defaultdict(int)
    sources = gene_sets.values() if isinstance(gene_sets, dict) else gene_sets
    for genes in sources:
        for gene in genes:
            counts[gene] += 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)


def consensus_thresholds(gene_sets, thresholds=(0.90, 0.75, 0.50, 0.25)):
    """
    Takes a collection of gene sets and returns a dict mapping each threshold
    to the list of genes that appear in at least that fraction of the gene sets.
    Genes within each threshold list are ordered from most to least frequent.
    """
    sources = list(gene_sets.values()) if isinstance(gene_sets, dict) else list(gene_sets)
    n = len(sources)
    if n < MIN_GENES_FOR_CONSENSUS:
        return {"AA{}".format(int(threshold*100)): [] for threshold in thresholds}  # Not enough gene sets to apply thresholds meaningfully
    ranked = consensus_counts(gene_sets)
    result = {}
    for threshold in thresholds:
        min_count = threshold * n
        result["AA{}".format(int(threshold*100))] = [gene for gene, count in ranked if count >= min_count]
    return result


def analyze_consensus(gene_set_name, gene_set, out_f, method="eaggl"):
    thresholds = consensus_thresholds(gene_set)
    for threshold, genes in thresholds.items():
        print("Genes in at least {}% of gene sets:".format(int(threshold[2:])), len(genes))
        if method == "eaggl":
            results = run_eaggl(genes)
        else:
            results = run_pigean(genes)
        save_results(out_f, f"{threshold}__{gene_set_name}", len(genes), results)


def filter_genesets(gene_sets, min_genes=10, prefix=""):
    """
    Filters out gene sets that have fewer than min_genes genes.
    """
    filtered = {}
    for gene_set_name, gene_set in gene_sets.items():
        if len(gene_set) >= min_genes:
            filtered[gene_set_name] = {model: genes for model, genes in gene_set.items() if model.startswith(prefix)}
            if len(filtered[gene_set_name]) < min_genes:
                del filtered[gene_set_name]
    return filtered


def main():
    parser = argparse.ArgumentParser(description="Analyze consensus gene sets")
    parser.add_argument("-b", "--base-folder", default=DEFAULT_BASE_FOLDER, help="Base folder for genesets")
    parser.add_argument("-o", "--output-folder", default=DEFAULT_OUT_FOLDER, help="Output folder for results")
    parser.add_argument("-m", "--method", choices=["eaggl", "pigean"], default="eaggl", help="Enrichment method")
    parser.add_argument("--min-genes", type=int, default=MIN_GENES_FOR_CONSENSUS, help="Minimum genes for consensus")
    parser.add_argument("--prefix", default="AB", help="Model prefix filter (e.g., AB, AC, CFDE1)")
    args = parser.parse_args()
    
    # Construct output file path
    if args.method == "pigean":
        out_folder = args.output_folder.replace("output.tissue", "output.tissue.pigean")
    else:
        out_folder = args.output_folder
    consensus_file = os.path.join(out_folder, f"consensus_analysis_{args.method}.txt")
    
    # Load and filter genesets
    genesets = load_genesets(args.base_folder)
    filtered_genesets = filter_genesets(genesets, min_genes=args.min_genes, prefix=args.prefix)
    
    for gene_set_name, gene_set in filtered_genesets.items():
        print(f"Gene set: {gene_set_name}, Number of source gene sets: {len(gene_set)}")
    
    with open(consensus_file, 'w') as out_f:
        for gene_set_name, gene_set in filtered_genesets.items():
            print(f"Analyzing consensus for gene set: {gene_set_name}")
            analyze_consensus(gene_set_name, gene_set, out_f, method=args.method)


if __name__ == "__main__":
    main()
