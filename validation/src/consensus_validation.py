import os
from collections import defaultdict
import sys

from run_validation import parse_gmt_file
from validation_summary import key, parse_gtex_gene_set_name_suffix
from gene_set_comparison import load_genesets
from run_eaggl import run_eaggl, run_pigean, save_results

CLIENT = "eaggl"
MIN_GENES_FOR_CONSENSUS = 4

BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/runs/gtex_all_models/genesets"
CONSENSUS_OUT_FILE = "../../data/gtex/output.tissue/consensus_analysis.txt"
CONSENSUS_PIGEAN_OUT_FILE = "../../data/gtex/output.tissue.pigean/consensus_analysis_pigean.txt"

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


def analyze_consensus(gene_set_name,gene_set, out_f):
    thresholds = consensus_thresholds(gene_set)
    for threshold, genes in thresholds.items():
        print("Genes in at least {}% of gene sets:".format(int(threshold[2:])), len(genes))
        if CLIENT == "eaggl":
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
    genesets = load_genesets()
    consensus_file = CONSENSUS_PIGEAN_OUT_FILE if CLIENT == "pigean" else CONSENSUS_OUT_FILE
    filtered_genesets = filter_genesets(genesets, min_genes=MIN_GENES_FOR_CONSENSUS, prefix="AB")
    for gene_set_name, gene_set in filtered_genesets.items():
        print(f"Gene set: {gene_set_name}, Number of source gene sets: {len(gene_set)}")
    with open(consensus_file, 'w') as out_f:
        for gene_set_name, gene_set in filtered_genesets.items():
            print(f"Analyzing consensus for gene set: {gene_set_name}")
            analyze_consensus(gene_set_name, gene_set, out_f)


if __name__ == "__main__":
    main()
