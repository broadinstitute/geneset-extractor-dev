import random

import requests
import csv
import sys


OUT_FILE = "../../data/gtex/output/random_genes_validation_results.txt"


def read_all_loc_genes():
    gene_locations_file = '/humgen/diabetes2/users/lthakur/lap_test/ldsc/raw/NCBI37.3.plink.gene.loc'
    all_loc_genes = set()
    with open(gene_locations_file, 'r') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            symbol = row[5]
            all_loc_genes.add(symbol)
    # for gene in sorted(all_loc_genes):
    #     print(gene, file=sys.stdout)
    print("Total genes in gene locations file:", len(all_loc_genes), file=sys.stderr)
    return all_loc_genes


def save_results(out_f, gene_set_name, gene_set_size, genesets):
    # Extract model from gene_set_name (prefix before first "__")
    model = gene_set_name.split("__")[0] if "__" in gene_set_name else gene_set_name
    gene_set_name_suffix = gene_set_name.split("__", 1)[1] if "__" in gene_set_name else ""
    
    for i, gene_set in enumerate(genesets):
        enriched_gene_sets_name = gene_set['gene_set']
        enriched_gene_set_size = gene_set['gene_set_size']
        enriched_gene_set_p_value = gene_set['p_value']
        out_f.write("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(model, gene_set_name_suffix, gene_set_name, gene_set_size, i, enriched_gene_sets_name, enriched_gene_set_size, enriched_gene_set_p_value))
        out_f.flush()


def run_client(genes, enrichment_analysis="hypergeometric"):
    URL = "http://chembio-dev-03:8082/pigean"
    payload = {
        "p_value": "0.05",
        "max_number_gene_sets": 50,
        "gene_sets": "default",
        "enrichment_analysis": enrichment_analysis,
        "factorization_weight": "-logpvalue/sqrt_size",
        "exclude_controls": False,
        "factorization_phi": 0.1,
        "genes": genes
    }
    response = requests.post(URL, json=payload)
    print(response.status_code)
    if response.status_code != 200:
        print("Error: {}".format(response.text))
        return
    response_json = response.json()
    for entry in response_json['logs']:
        print(entry)
    print("\nEnriched gene sets:")
    for i, gene_set in enumerate(response_json['gene_sets']):
        if i >= 10:
            break
        print(gene_set['gene_set'], gene_set['gene_set_size'], gene_set['p_value'])
    return response_json['gene_sets']


def run_eaggl(genes):
    return run_client(genes, enrichment_analysis="hypergeometric")


def run_pigean(genes):
    return run_client(genes, enrichment_analysis="naive_priors")


def main():
    all_loc_genes = read_all_loc_genes()
    print("loaded {} genes".format(len(all_loc_genes)))
    n_simulations = 100
    n_random_genes = 250
    with open(OUT_FILE, 'a') as out_f:
        for i in range(n_simulations):
            random_genes = sorted(random.sample(all_loc_genes, n_random_genes))
            print("\nSimulation {}: Running EAGGL with {} random genes".format(i+1, n_random_genes))
            genesets = run_eaggl(random_genes)
            save_results(out_f, "random_genes", n_random_genes, genesets)


if __name__ == '__main__':
    main()