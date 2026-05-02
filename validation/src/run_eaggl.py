import requests
import csv
import sys


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


def run_eaggl(genes):
    URL = "http://chembio-dev-03:8082/pigean"
    payload = {
        "p_value": "0.05",
        "max_number_gene_sets": 50,
        "gene_sets": "default",
        "enrichment_analysis": "hypergeometric",
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
    for i,gene_set in enumerate(response_json['gene_sets']):
        if i >= 10:
            break
        print(gene_set['gene_set'], gene_set['gene_set_size'], gene_set['p_value'])
    return response_json['gene_sets']

def main():
    all_loc_genes = read_all_loc_genes()
    print("loaded {} genes".format(len(all_loc_genes)))

    random_genes = [
        "WDR25",
        "RECQL",
        "RGPD3",
        "WNT16",
        "HOXA7"
    ]
    run_eaggl(random_genes)


if __name__ == '__main__':
    main()