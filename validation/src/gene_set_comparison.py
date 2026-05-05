import os

from collections import defaultdict
from run_validation import parse_gmt_file

BASE_FOLDER = "/humgen/diabetes2/users/ryank/geneset_extractors/GTEx/outputs/genesets/adipose_subcutaneous/models"
OUT_FILE = "../../data/gtex/output/adipose_subcutaneous_{}_comparison.txt"

def model_name(folder):
    if folder.startswith("M"):
        if len(folder) == 2:
            model_name = folder[0]+"0"+folder[1]
        else:            
            model_name = folder
    else:
        model_name = folder
    return model_name


def load_genesets():
    genesets = defaultdict(dict)
    for folder in os.listdir(BASE_FOLDER):
        folder_path = os.path.join(BASE_FOLDER, folder)
        if os.path.isdir(folder_path):
            print("Loading gene sets for folder:", folder_path)
            gmt_file = folder_path + "/extractor/genesets.gmt"
            for gene_set in parse_gmt_file(gmt_file):
                gene_set_name = gene_set['gene_set']
                if gene_set_name.startswith("M"):
                    gene_set_name = gene_set_name.split("__", 1)[1] if "__" in gene_set_name else gene_set_name
                genesets[gene_set_name][model_name(folder)] = gene_set['genes']
    return genesets


def gene_set_overlap(geneset1, geneset2):
    set1 = set(geneset1)
    set2 = set(geneset2)
    overlap = set1.intersection(set2)
    left_only = set1 - set2
    right_only = set2 - set1
    return len(left_only), len(overlap), len(right_only)


def compare_gene_sets(gene_set_name, genesets):
    results = []
    with open(OUT_FILE.format(gene_set_name), 'w') as out_f:
        models = sorted(genesets.keys())
        out_f.write("\t" + "\t".join(models) + "\n")
        for model1 in models:
            row = [model1]
            for model2 in models:
                left_only, overlap, right_only = gene_set_overlap(genesets[model1], genesets[model2])
                row.append("{}|{}|{}".format(left_only, overlap, right_only))
                results.append({
                    "model1": model1,
                    "model2": model2,
                    "left_only": left_only,
                    "overlap": overlap,
                    "right_only": right_only
                })
            out_f.write("\t".join(row) + "\n")
    return results


def main():
    genesets = load_genesets()
    comparison_results = compare_gene_sets('age70_20__neg', genesets['age70_20__neg'])
    

if __name__ == "__main__":
    main()