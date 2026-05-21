import os

BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/gtex_outputs/genesets"
OUT_FILE = "../../data/gtex/counts.txt"

MODELS = ["AB1", "AB2", "AB3", "AB4", "AB5", "AB6", "AB7", "AB8", "AB9", "AB10", 
          "AB11", "AB12", "AB13", "AB14", "AB15", "AB16", "AB17", "AB18", "AB19", "AB20", "AB21", "AB22",
          "AC1", "AC2", "AC3", "AC4", "AC5", "AC6", "AC7", "AC8", "AC9", "AC10"]

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


def run_validation_count(folder_path):
    print("Running validation for folder:", folder_path)
    gmt_file = get_gmt_file(folder_path)
    if gmt_file is None:
        print("No GMT file found for folder:", folder_path)
        return 0
    genesets = parse_gmt_file(gmt_file)
    print("Parsed {} gene sets from {}".format(len(genesets), gmt_file))
    return len(genesets)


def validate_tissue(tissue, out_f):
    counts = {model: 0 for model in MODELS}
    base_folder = os.path.join(BASE_FOLDER, tissue, "models")
    for folder in os.listdir(base_folder):
        folder_path = os.path.join(base_folder, folder)
        if os.path.isdir(folder_path):
            count = run_validation_count(folder_path)
            if folder in MODELS:
                counts[folder] = count
                print(f"Model {folder}: {count} gene sets")
            else:
                print(f"Warning: Model {folder} not in MODELS list")
    out_f.write(f"{tissue}\t" + "\t".join(str(counts[model]) for model in MODELS) + "\n")


def main():
    with open(OUT_FILE, 'w') as out_f:
        out_f.write("Tissue\t" + "\t".join(MODELS) + "\n")
        for tissue in sorted(os.listdir(BASE_FOLDER)):
            tissue_path = os.path.join(BASE_FOLDER, tissue)
            if os.path.isdir(tissue_path):
                validate_tissue(tissue, out_f)


if __name__ == "__main__":
    main()
