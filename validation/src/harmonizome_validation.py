import os
import argparse

from run_eaggl import run_eaggl, run_pigean, save_results
from gene_set_comparison import read_gmt_file

DEFAULT_GENE_SET_FOLDER = "../../data/gtex/input"
DEFAULT_OUT_FOLDER = "../../data/gtex/output.tissue"


def validate_gene_sets(gene_set_name, genes, out_f, method="eaggl"):
    print(f"Gene set: {gene_set_name}, Number of genes: {len(genes)}")
    if method == "eaggl":
        results = run_eaggl(genes)
    elif method == "pigean":
        results = run_pigean(genes)
    save_results(out_f, gene_set_name, len(genes), results)


def main():
    parser = argparse.ArgumentParser(description="Validate harmonizome gene sets")
    parser.add_argument("-i", "--input-folder", default=DEFAULT_GENE_SET_FOLDER, help="Input folder with GMT files")
    parser.add_argument("-o", "--output-folder", default=DEFAULT_OUT_FOLDER, help="Output folder for results")
    parser.add_argument("-s", "--source", choices=["harmonizome", "data_matrix"], default="harmonizome", help="Gene set source")
    parser.add_argument("-m", "--method", choices=["eaggl", "pigean"], default="eaggl", help="Enrichment method")
    args = parser.parse_args()
    
    # Determine output file and sources
    if args.method == "pigean":
        out_folder = args.output_folder.replace("output.tissue", "output.tissue.pigean")
    else:
        out_folder = args.output_folder
    
    if args.source == "harmonizome":
        out_file = os.path.join(out_folder, f"harmonizome_validation_{args.method}.txt")
        sources = ["harmonizome_gtex_aging.gmt"]
    else:
        out_file = os.path.join(out_folder, f"data_matrix_validation_{args.method}.txt")
        sources = ["GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt"]
    
    with open(out_file, 'w') as out_f:
        for source_file in sources:
            gmt_file = os.path.join(args.input_folder, source_file)
            gene_sets = read_gmt_file(gmt_file)
            print(f"Parsed {len(gene_sets)} gene sets from {gmt_file}")
            for gene_set_name, genes in gene_sets.items():
                validate_gene_sets(gene_set_name, genes, out_f, method=args.method)            


if __name__ == "__main__":
    main()
    # main("data_matrix")
    # main("data_matrix_pigean")
    main("harmonizome_pigean")
