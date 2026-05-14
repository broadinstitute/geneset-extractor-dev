import os

from run_eaggl import run_eaggl, save_results

BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/gtex_outputs/genesets/lung/models"
OUT_FILE = "../../data/gtex/output/lung_validation_results.txt"


def parse_gmt_file(gmt_file):
    gene_sets = []
    with open(gmt_file, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            gene_set_name = parts[0]
            gene_set_genes = parts[1].split(' ')
            gene_sets.append({
                "gene_set": gene_set_name,
                "genes": gene_set_genes
            })
    return gene_sets


def get_gmt_file(folder_path):
    gmt_file = folder_path + "/extractor/genesets.gmt"
    if os.path.exists(gmt_file):
        return gmt_file
    gmt_file = folder_path + "/tissue_extractor/genesets.gmt"
    if os.path.exists(gmt_file):
        return gmt_file
    return None


def run_validation(folder_path):
    print("Running validation for folder:", folder_path)
    gmt_file = get_gmt_file(folder_path)
    if gmt_file is None:
        print("No GMT file found for folder:", folder_path)
        return
    genesets = parse_gmt_file(gmt_file)
    print("Parsed {} gene sets from {}".format(len(genesets), gmt_file))
    with open(OUT_FILE, 'a') as out_f:
        for gene_set in genesets:
            print("Gene set:", gene_set['gene_set'], "Number of genes:", len(gene_set['genes']))
            genesets = run_eaggl(gene_set['genes'])
            save_results(out_f, gene_set['gene_set'], len(gene_set['genes']), genesets)


def main():
    for folder in os.listdir(BASE_FOLDER):
        folder_path = os.path.join(BASE_FOLDER, folder)
        if os.path.isdir(folder_path):
            run_validation(folder_path)


if __name__ == "__main__":
    main()
