import os
import argparse

from run_eaggl import run_eaggl, run_pigean, save_results

DEFAULT_BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/runs/gtex_all_models/genesets"
DEFAULT_OUT_FOLDER = "../../data/gtex/output.tissue"


def parse_gmt_file(gmt_file):
    gene_sets = []
    with open(gmt_file, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            gene_set_name = parts[0]
            gene_set_genes = parts[2:]
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


def run_validation(folder_path, out_file, model=None, method="eaggl"):
    print("Running validation for folder:", folder_path)
    gmt_file = get_gmt_file(folder_path)
    if gmt_file is None:
        print("No GMT file found for folder:", folder_path)
        return
    gene_sets = parse_gmt_file(gmt_file)
    print("Parsed {} gene sets from {}".format(len(gene_sets), gmt_file))
    with open(out_file, 'a') as out_f:
        for gene_set in gene_sets:
            gene_set_name = f"{model}__{gene_set['gene_set']}" if model else gene_set['gene_set']
            print("Gene set:", gene_set_name, "Number of genes:", len(gene_set['genes']))
            if method == "eaggl":
                results = run_eaggl(gene_set['genes'])
            else:
                results = run_pigean(gene_set['genes'])
            save_results(out_f, gene_set_name, len(gene_set['genes']), results)


def validate_tissue(tissue, base_folder, out_file_template, method="eaggl", force_rewrite=False):
    tissue_path = os.path.join(base_folder, tissue, "models")
    if not os.path.isdir(tissue_path):
        print(f"Tissue folder not found: {tissue_path}")
        return
    out_file = out_file_template.format(tissue)
    if not force_rewrite and os.path.exists(out_file):
        print(f"Skipping validation for tissue {tissue} as output file already exists.")
        return
    for folder in os.listdir(tissue_path):
        folder_path = os.path.join(tissue_path, folder)
        if os.path.isdir(folder_path):
            try:
                run_validation(folder_path, out_file, model=folder, method=method)
            except Exception as e:
                print(f"Error validating folder {folder_path}: {e}")


def validate_single_file(file_path, output_folder, method="eaggl", force_rewrite=False):
    """Validate gene sets from a single GMT file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    gene_sets = parse_gmt_file(file_path)
    print(f"Parsed {len(gene_sets)} gene sets from {file_path}")
    
    os.makedirs(output_folder, exist_ok=True)
    out_file = os.path.join(output_folder, f"validation_results_{method}.txt")
    
    # Clear output file if force-rewrite is enabled
    if force_rewrite and os.path.exists(out_file):
        os.remove(out_file)
    
    with open(out_file, 'a') as out_f:
        for gene_set in gene_sets:
            gene_set_name = gene_set['gene_set']
            print("Gene set:", gene_set_name, "Number of genes:", len(gene_set['genes']))
            if method == "eaggl":
                results = run_eaggl(gene_set['genes'])
            else:
                results = run_pigean(gene_set['genes'])
            save_results(out_f, gene_set_name, len(gene_set['genes']), results)


def main():
    parser = argparse.ArgumentParser(description="Validate gene sets using EAGGL/PIGEAN")
    parser.add_argument("-b", "--base-folder", required=False, help="Base folder for genesets")
    parser.add_argument("-f", "--file", required=False, help="Single GMT file to process")
    parser.add_argument("-o", "--output-folder", required=True, help="Output folder for results")
    parser.add_argument("-t", "--tissue", action="append", help="Tissue(s) to process (can be repeated)")
    parser.add_argument("-m", "--method", choices=["eaggl", "pigean"], default="eaggl", help="Enrichment method")
    parser.add_argument("--force-rewrite", action="store_true", help="Force rewrite of existing output files")
    args = parser.parse_args()
    
    # Validate that either -b or -f is provided
    if not args.base_folder and not args.file:
        parser.error("Either -b/--base-folder or -f/--file must be provided")
    
    if args.base_folder and args.file:
        parser.error("Cannot use both -b/--base-folder and -f/--file")
    
    # Handle single file mode
    if args.file:
        try:
            validate_single_file(args.file, args.output_folder, method=args.method, force_rewrite=args.force_rewrite)
        except FileNotFoundError as e:
            parser.error(str(e))
        return
    
    # Create output folder if it doesn't exist
    os.makedirs(args.output_folder, exist_ok=True)
    
    # Construct output file template based on method
    if args.method == "pigean":
        out_folder = args.output_folder.replace("output.tissue", "output.tissue.pigean")
    else:
        out_folder = args.output_folder
    
    out_file_template = os.path.join(out_folder, "{}_validation_results_{}.txt".format("{}", args.method))
    
    # Determine which tissues to process
    if args.tissue:
        tissues = args.tissue
    else:
        tissues = [d for d in os.listdir(args.base_folder) if os.path.isdir(os.path.join(args.base_folder, d))]
    
    for tissue in tissues:
        print(f"Processing tissue: {tissue} with method: {args.method}")
        validate_tissue(tissue, args.base_folder, out_file_template, method=args.method, force_rewrite=args.force_rewrite)


if __name__ == "__main__":
    main()
