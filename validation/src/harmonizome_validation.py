import os

from run_eaggl import run_eaggl, run_pigean, save_results
from gene_set_comparison import read_gmt_file


GENE_SET_FOLDER = "../../data/gtex/input"
HARMONIZOME_FILE = "../../data/gtex/output.tissue/harmonizome_validation.txt"
DATA_MATRIX_FILE = "../../data/gtex/output.tissue/data_matrix_validation.txt"
DATA_MATRIX_PIGEAN_FILE = "../../data/gtex/output.tissue/data_matrix_pigean_validation.txt"


def validate_gene_sets(gene_set_name, genes, out_f, client="eaggl"):
    print(f"Gene set: {gene_set_name}, Number of genes: {len(genes)}")
    if client == "eaggl":
        results = run_eaggl(genes)
    elif client == "pigean":
        results = run_pigean(genes)
    save_results(out_f, gene_set_name, len(genes), results)
    # print(f"Results for gene set {gene_set}: {results}")


def main(source):
    client = "eaggl"
    if source == "harmonizome":
        out_file = HARMONIZOME_FILE
        sources = ["harmonizome_gtex_aging.gmt"]
    elif source == "data_matrix":
        out_file = DATA_MATRIX_FILE
        sources = ["GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt"]
    elif source == "data_matrix_pigean":
        out_file = DATA_MATRIX_PIGEAN_FILE
        sources = ["GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt"]
        client = "pigean"
    with open(out_file, 'w') as out_f:
        for source in sources:
            gmt_file = os.path.join(GENE_SET_FOLDER, source)
            gene_sets = read_gmt_file(gmt_file)
            print(f"Parsed {len(gene_sets)} gene sets from {gmt_file}")
            for gene_set_name, genes in gene_sets.items():
                validate_gene_sets(gene_set_name, genes, out_f, client=client)            


if __name__ == "__main__":
    # main("harmonizome")
    # main("data_matrix")
    main("data_matrix_pigean")
