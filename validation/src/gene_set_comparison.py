import os

from collections import defaultdict
from run_validation import parse_gmt_file

BASE_FOLDER = "/humgen/diabetes2/users/ryank/geneset_extractors/GTEx/outputs/genesets/adipose_subcutaneous/models"
BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/gtex/genesets/adipose_tissue/models"
OUT_FILE = "../../data/gtex/output.tissue/adipose_tissue_{}_comparison.tsv"

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
            print("Loading gene sets for model:", folder)
            gmt_file = folder_path + "/extractor/genesets.gmt"
            if os.path.exists(gmt_file):
                for gene_set in parse_gmt_file(gmt_file):
                    gene_set_name = gene_set['gene_set']
                    if gene_set_name.startswith("A"):
                        gene_set_name = gene_set_name.split("__", 1)[1] if "__" in gene_set_name else gene_set_name
                    genesets[gene_set_name][model_name(folder)] = gene_set['genes']
            else:
                print("No GMT file found for model:", folder)
    return genesets


def gene_set_overlap(geneset1, geneset2):
    set1 = set(geneset1)
    set2 = set(geneset2)
    overlap = set1.intersection(set2)
    left_only = set1 - set2
    right_only = set2 - set1
    return len(left_only), len(overlap), len(right_only)


def compare_gene_sets(gene_set_name, genesets, base_gene_sets):
    results = []
    for base_name, base_gene_set in base_gene_sets.items():
        genesets[base_name] = base_gene_set
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
    base_gene_sets = {}
    dcc_gene_sets = read_gmt_file("../../GTEx/VD/inputs/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt")
    base_gene_sets['DCC'] = set(dcc_gene_sets["GTEx AdiposeTissue 20-29 vs 70-79 Down"])
    harmonizome_gene_sets = read_gmt_file("../../GTEx/VD/inputs/harmonizome_gtex_aging.gmt")
    base_gene_sets['Harmo'] = set(harmonizome_gene_sets["GTEx AdiposeTissue 20-29 vs 70-79 Down"])
    gene_set_name = "age70_20__neg"
    comparison_results = compare_gene_sets(gene_set_name, genesets[gene_set_name], base_gene_sets) 

def read_gmt_file(gmt_path):
    """
    Read GMT file and return a dictionary of gene sets.
    
    Args:
        gmt_path (str): Path to GMT file
        
    Returns:
        dict: Dictionary with gene set names as keys and lists of genes as values
    """
    gene_sets = {}
    
    with open(gmt_path, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                gene_set_name = parts[0]
                # Skip the description (parts[1])
                genes = parts[2:]
                gene_sets[gene_set_name] = genes
    
    return gene_sets



if __name__ == "__main__":
    main()