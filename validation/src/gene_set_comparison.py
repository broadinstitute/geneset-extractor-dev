import os
import argparse

from collections import defaultdict
from run_validation import parse_gmt_file
from validation_summary import key, parse_gtex_gene_set_name_suffix, parse_drc_gene_set_name_suffix

DEFAULT_BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/runs/gtex_all_models/genesets"
DEFAULT_OUT_FOLDER = "../../data/gtex/output.tissue"

MODELS = [ "DM", "HZ1", "Harmo", 
    "AB1", "AB2", "AB3", "AB4", "AB5", "AB6", "AB7", "AB8", "AB9", "AB10",
    "AB11", "AB12", "AB13", "AB14", "AB15", "AB16", "AB17", "AB18", "AB19", "AB20", "AB21", "AB22", "CFDE1"
]

def model_name(folder):
    if folder.startswith("AB") or folder.startswith("AC") :
        if len(folder) == 2:
            model_name = folder[0]+"0"+folder[1]
        else:            
            model_name = folder
    else:
        model_name = folder
    return model_name


def load_genesets_for_tissue(tissue_folder):
    genesets = defaultdict(dict)
    for folder in os.listdir(tissue_folder):
        folder_path = os.path.join(tissue_folder, folder)
        if os.path.isdir(folder_path):
            print("Loading gene sets for model:", folder)
            gmt_file = folder_path + "/extractor/genesets.gmt"
            if not os.path.exists(gmt_file):
                gmt_file = folder_path + "/tissue_extractor/genesets.gmt"
            if os.path.exists(gmt_file):
                for gene_set in parse_gmt_file(gmt_file):
                    gene_set_name = gene_set['gene_set']
                    genesets[gene_set_name][model_name(folder)] = gene_set['genes']
            else:
                print("No GMT file found for model:", folder)
    print("Total gene sets loaded for tissue {}: {}".format(tissue_folder, len(genesets)))
    return genesets


def load_genesets(base_folder=None):
    if base_folder is None:
        base_folder = DEFAULT_BASE_FOLDER
    tissue_genesets = defaultdict(dict)
    for tissue in os.listdir(base_folder):
        tissue_folder = os.path.join(base_folder, tissue)
        if os.path.isdir(tissue_folder):
            print("Loading gene sets for tissue:", tissue)
            path = os.path.join(tissue_folder, "models")
            for gene_set_name, gene_set in load_genesets_for_tissue(path).items():
                gene_set_key = key(*parse_gtex_gene_set_name_suffix(tissue, gene_set_name))
                tissue_genesets[gene_set_key].update(gene_set)
    count = sum(len(gene_sets) for gene_sets in tissue_genesets.values())
    print("Loaded {} gene sets across all tissues".format(count))
    return tissue_genesets


def gene_set_overlap(geneset1, geneset2):
    set1 = set(geneset1)
    set2 = set(geneset2)
    overlap = set1.intersection(set2)
    left_only = set1 - set2
    right_only = set2 - set1
    return len(left_only), len(overlap), len(right_only)


def compare_gene_sets_matrix(gene_set_name, genesets, base_gene_sets):
    results = []
    for base_name, base_gene_set in base_gene_sets.items():
        genesets[base_name] = base_gene_set
    with open(OUT_FILE.format(gene_set_name), 'w') as out_f:
        out_f.write("\t" + "\t".join(MODELS) + "\n")
        for model1 in MODELS:
            row = [model1]
            for model2 in MODELS:
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



def compare_gene_sets(gene_set_name, genesets, out_f):
    row = [gene_set_name]
    if 'DM' not in genesets:
        base_gene_set = set()
    else:
        base_gene_set = set(genesets['DM'])
    for model2 in MODELS:
        if model2 not in genesets:
            row.append("")
        else:
            left_only, overlap, right_only = gene_set_overlap(base_gene_set, genesets[model2])
            row.append("{}|{}|{}".format(left_only, overlap, right_only))
    if len("".join(row[1:])) > 1:
        out_f.write("\t".join(row) + "\n")


def main_matrix():
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


def main_DM_vs_AB_models():
    genesets = load_genesets()
    harmonizome_gene_sets = read_gmt_file("../../GTEx/VD/inputs/harmonizome_gtex_aging.gmt")
    for gene_set_name, gene_set in harmonizome_gene_sets.items():
        # print("Adding harmonizome gene set:", gene_set_name, "with key", key(*parse_drc_gene_set_name_suffix(gene_set_name)))
        genesets[key(*parse_drc_gene_set_name_suffix(gene_set_name))]['Harmo'] = gene_set
    dcc_gene_sets = read_gmt_file("../../GTEx/VD/inputs/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt")
    for gene_set_name, gene_set in dcc_gene_sets.items():
        # print("Comparing gene set:", gene_set_name, "with key", key(*parse_drc_gene_set_name_suffix(gene_set_name)))
        genesets[key(*parse_drc_gene_set_name_suffix(gene_set_name))]['DM'] = gene_set
    with open(DCC_COMP_OUT_FILE, 'w') as out_f:
        out_f.write("key\t" + "\t".join(MODELS) + "\n")
        for gene_set_name in sorted(genesets.keys()):
            print("Comparing gene set:", gene_set_name)
            compare_gene_sets(gene_set_name, genesets[gene_set_name], out_f)

def main_DM_vs_DM():
    genesets = read_gmt_file("../../GTEx/VD/inputs/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt")
    with open(DM_VS_DM_COMP_OUT_FILE, 'w') as out_f:
        out_f.write("key1\ttissue1\tkey2\ttissue2\tleft_only\toverlap\tright_only\n")
        for gene_set_name1 in sorted(genesets.keys()):
            print("Comparing gene set:", gene_set_name1)
            tissue1, _, _, _ = parse_drc_gene_set_name_suffix(gene_set_name1)
            for gene_set_name2 in sorted(genesets.keys()):
                tissue2, _, _, _ = parse_drc_gene_set_name_suffix(gene_set_name2)
                gene_set1 = genesets[gene_set_name1]
                gene_set2 = genesets[gene_set_name2]
                left_only, overlap, right_only = gene_set_overlap(gene_set1, gene_set2)
                out_f.write(f"{gene_set_name1}\t{tissue1}\t{gene_set_name2}\t{tissue2}\t{left_only}\t{overlap}\t{right_only}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare gene sets across models")
    parser.add_argument("-b", "--base-folder", default=DEFAULT_BASE_FOLDER, help="Base folder for genesets")
    parser.add_argument("-o", "--output-folder", default=DEFAULT_OUT_FOLDER, help="Output folder for results")
    parser.add_argument("--dm-comparison", action="store_true", help="Run DM vs AB models comparison")
    parser.add_argument("--dm-vs-dm", action="store_true", help="Run DM vs DM comparison")
    args = parser.parse_args()
    
    if args.dm_comparison:
        main_DM_vs_AB_models()
    elif args.dm_vs_dm:
        main_DM_vs_DM()
    else:
        print("Please specify --dm-comparison or --dm-vs-dm")
