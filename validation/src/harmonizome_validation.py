import os

from run_eaggl import run_eaggl, save_results
from gene_set_comparison import read_gmt_file


GENE_SET_FOLDER = "../../data/gtex/input"
OUT_FILE = "../../data/gtex/output/data_matrix_validation.txt"


def validate_gene_sets(gene_set_name, genes, out_f):
    print(f"Gene set: {gene_set_name}, Number of genes: {len(genes)}")
    results = run_eaggl(genes)
    save_results(out_f, gene_set_name, len(genes), results)
    # print(f"Results for gene set {gene_set}: {results}")


def main():
    sources = ["GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt", "GTEx_XMT_2023-03-10_GTEx_Tissues_V8_2023.gmt"]
    with open(OUT_FILE, 'w') as out_f:
        for source in sources:
            gmt_file = os.path.join(GENE_SET_FOLDER, source)
            gene_sets = read_gmt_file(gmt_file)
            print(f"Parsed {len(gene_sets)} gene sets from {gmt_file}")
            for gene_set_name, genes in gene_sets.items():
                validate_gene_sets(gene_set_name, genes, out_f)            


if __name__ == "__main__":
    main()