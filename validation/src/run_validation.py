import os

from run_eaggl import run_eaggl, run_pigean, save_results

BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/gtex/genesets"
OUT_FILE = "../../data/gtex/output.tissue/{}_validation_results.txt"
OUT_FILE_PIGEAN = "../../data/gtex/output.tissue.pigean/{}_validation_results_pigean.txt"


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


def run_validation(folder_path, out_file):
    print("Running validation for folder:", folder_path)
    gmt_file = get_gmt_file(folder_path)
    if gmt_file is None:
        print("No GMT file found for folder:", folder_path)
        return
    genesets = parse_gmt_file(gmt_file)
    print("Parsed {} gene sets from {}".format(len(genesets), gmt_file))
    with open(out_file, 'a') as out_f:
        for gene_set in genesets:
            print("Gene set:", gene_set['gene_set'], "Number of genes:", len(gene_set['genes']))
            # genesets = run_eaggl(gene_set['genes'])
            genesets = run_pigean(gene_set['genes'])
            save_results(out_f, gene_set['gene_set'], len(gene_set['genes']), genesets)


def validate_tissue(tissue):
    base_folder = os.path.join(BASE_FOLDER, tissue, "models")
    for folder in os.listdir(base_folder):
        folder_path = os.path.join(base_folder, folder)
        if os.path.isdir(folder_path):
            try:
                run_validation(folder_path, OUT_FILE_PIGEAN.format(tissue))
            except Exception as e:
                print(f"Error validating folder {folder_path}: {e}")


def main():
    for tissue in os.listdir(BASE_FOLDER):
        tissue_path = os.path.join(BASE_FOLDER, tissue)
        if os.path.isdir(tissue_path):
            validate_tissue(tissue)

if __name__ == "__main__":
    main()
