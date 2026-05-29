import csv
import os
import pandas as pd
import matplotlib.pyplot as plt

from gene_set_comparison import model_name


BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/gtex/genesets"
IN_FILE = "../../data/gtex/output.tissue/{}_validation_results.txt"
HARMONIZOME_FILE = "../../data/gtex/output.tissue/harmonizome_validation.txt"
DATA_MATRIX_FILE = "../../data/gtex/output.tissue/data_matrix_validation.txt"

def plot_gene_set_by_model(df, gene_set_name_suffix):
    """
    Plot rank vs model for a given gene_set_name_suffix.
    X-axis: model indices (1-22)
    Y-axis: rank
    Lines: connected by enriched_gene_sets_name
    """
    # Filter data for the given gene_set_name_suffix
    filtered_df = df[df['gene_set_name_suffix'] == gene_set_name_suffix].copy()
    
    if filtered_df.empty:
        print(f"No data found for gene_set_name_suffix: {gene_set_name_suffix}")
        return
    
    # Create figure
    plt.figure(figsize=(12, 6))
    
    # Group by enriched_gene_sets_name and plot each line
    for gene_set, group in filtered_df.groupby('enriched_gene_sets_name'):
        # Sort by model_index for proper line connection
        group = group.sort_values('model_index')
        plt.plot(group['model_index'], group['rank'], marker='o', label=gene_set, alpha=0.7)
    
    plt.xlabel('Model', fontsize=12)
    plt.ylabel('Rank', fontsize=12)
    plt.title(f'Rank by Model for {gene_set_name_suffix}', fontsize=14)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def create_top_enriched_df(df):
    """
    Create a dataframe with columns: model, gene_set_name_suffix, top_enriched_gene_set
    For each model-gene_set_name_suffix combination, get the top enriched gene set (lowest rank)
    Sorted by gene_set_name_suffix and then by model
    """
    # Group by model and gene_set_name_suffix, then get the row with the minimum rank
    top_df = df.loc[df.groupby(['model', 'gene_set_name_suffix'])['rank'].idxmin()]
    
    # Select only the columns we need
    result_df = top_df[['model', 'tissue', 'gene_set_name_suffix', 'gene_set_size', 'enriched_gene_sets_name', 'enriched_gene_set_size', 'enriched_gene_set_p_value']].rename(
        columns={'enriched_gene_sets_name': 'top_enriched_gene_set'}
    )
    result_df['model'] = result_df['model'].apply(model_name)
    
    # Count negative controls for each gene_set_name_suffix
    negative_control_counts = df[df['enriched_gene_sets_name'].str.startswith('negative_control_')].groupby(['model', 'gene_set_name_suffix']).size()
    result_df['negative_control_count'] = result_df.set_index(['model', 'gene_set_name_suffix']).index.map(negative_control_counts).fillna(0).astype(int)
    
    # Sort by gene_set_name_suffix and then by model
    result_df = result_df.sort_values(['gene_set_name_suffix', 'model']).reset_index(drop=True)
    
    return result_df


def parse_drc_gene_set_name_suffix(gene_set_name):
    """ parse gene set name into tissue, age group 1 and age group 2, direction (up/down) 
        for example, "GTEx AdiposeTissue 20-29 vs 70-79 Down" would be parsed into:
        tissue: "AdiposeTissue"
        age group 1: "20"
        age group 2: "70"
        direction: "down"
    """
    parts = gene_set_name.split()
    tissue = parts[1].lower()
    age_group_1 = parts[2].split('-')[0]
    age_group_2 = parts[4].split('-')[0]
    direction = parts[5].lower()  # "Down" -> "down", "Up" -> "up"
    return tissue, age_group_1, age_group_2, direction


def parse_gtex_gene_set_name_suffix(tissue, gene_set_name):
    """ parse gene set name into tissue, age group 1 and age group 2, direction (up/down) 
        for example, "adipose_tissue" and "age70_20__neg" would be parsed into:
        tissue: "adiposetissue"
        age group 1: "70"
        age group 2: "20"
        direction: "down"
    """
    tissue = tissue.replace("_", "").lower()
    age_group_1 = "0"
    age_group_2 = "0"
    direction = ""
    parts = gene_set_name.split("__")
    if "age" in parts[0]:
        age_group_1 = parts[0][3:5]  # "age70" -> "70"
        age_group_2 = parts[0][6:8]  # "age20" -> "20"
    if len(parts) > 1:
        direction = "down" if parts[1] == "neg" else "up"
    return tissue, age_group_2, age_group_1, direction


def key(tissue, age_group_1, age_group_2, direction):
    return f"{tissue}_{age_group_1}_{age_group_2}_{direction}" 


def add_key_column_gtex(df):
    df['key'] = df.apply(lambda row: key(*parse_gtex_gene_set_name_suffix(row['tissue'], row['gene_set_name_suffix'])), axis=1)
    return df


def add_key_column_drc(df):
    df['key'] = df.apply(lambda row: key(*parse_drc_gene_set_name_suffix(row['gene_set_name_suffix'])), axis=1)
    return df


def summarize_tissue(tissue):
    #check if input file exists
    if not os.path.exists(IN_FILE.format(tissue)):
        print(f"Input file {IN_FILE.format(tissue)} not found. Skipping tissue {tissue}.")
        return None
    df = pd.read_csv(IN_FILE.format(tissue), sep='\t', header=None, names=['model','gene_set_name_suffix','gene_set_name', 'gene_set_size', 'rank', 'enriched_gene_sets_name', 'enriched_gene_set_size', 'enriched_gene_set_p_value'])
    df['tissue'] = tissue
    
    # Create top enriched gene set dataframe
    top_df = create_top_enriched_df(df)
    print("\nTop enriched gene sets by model and gene_set_name_suffix:")
    print(top_df.head(10))
    
    return top_df


def mainx():
    tissue = "adrenal_gland"
    tissue = "whole_blood"
    summarize_tissue(tissue)

def create_pivot_tables(df):
    """
    Create two pivot tables:
    1. For AB models (AB1-AB22): tissue and gene_set_name_suffix as rows, model as columns
    2. For AC models (AC1-AC10): tissue and gene_set_name_suffix as rows, model as columns
    Values: negative_control_count
    """
    # Separate dataframes by model prefix
    ab_df = df[~df['model'].str.startswith('AC')].copy()
    ac_df = df[df['model'].str.startswith('AC')].copy()
    
    # Create pivot tables
    ab_pivot = ab_df.pivot_table(
        # index=['tissue', 'gene_set_name_suffix'],
        index=['key'],
        columns='model',
        values='negative_control_count',
        aggfunc='first'
    )
    
    ac_pivot = ac_df.pivot_table(
        # index=['tissue', 'gene_set_name_suffix'],
        index=['key'],
        columns='model',
        values='negative_control_count',
        aggfunc='first'
    )
    
    return ab_pivot, ac_pivot


def main():
    output_path = "../../data/gtex/output.tissue/test_top_gene_sets.tsv"
    pivot_ab_output_path = "../../data/gtex/output.tissue/test_negative_control_counts_AB.tsv"
    pivot_ac_output_path = "../../data/gtex/output.tissue/test_negative_control_counts_AC.tsv"
    df = None
    # process harmonizome file
    if os.path.exists(HARMONIZOME_FILE):
        harmonizome_df = pd.read_csv(HARMONIZOME_FILE, sep='\t', names=['gene_set_name_suffix','model','gene_set_name', 'gene_set_size', 'rank', 'enriched_gene_sets_name', 'enriched_gene_set_size', 'enriched_gene_set_p_value'])
        # select only rows where gene_set_name_suffix starts with "GTEx"
        harmonizome_df = harmonizome_df[harmonizome_df['gene_set_name_suffix'].str.startswith("GTEx")]
        
        harmonizome_df['model'] = 'HAR'
        harmonizome_df['tissue'] = 'harmonizome'
        print(f"Processed harmonizome file with {len(harmonizome_df)} rows.")
        # print(harmonizome_df.head())
        summarize_harmonizome_df = create_top_enriched_df(harmonizome_df)
        summarize_harmonizome_df = add_key_column_drc(summarize_harmonizome_df)
        print("\nTop enriched gene sets for harmonizome:")
        print(summarize_harmonizome_df.head(10))
        df = summarize_harmonizome_df
    else:
        print(f"Harmonizome file {HARMONIZOME_FILE} not found. Skipping.")
    # process data matrix file
    if os.path.exists(DATA_MATRIX_FILE):
        data_matrix_df = pd.read_csv(DATA_MATRIX_FILE, sep='\t', names=['gene_set_name_suffix','model','gene_set_name', 'gene_set_size', 'rank', 'enriched_gene_sets_name', 'enriched_gene_set_size', 'enriched_gene_set_p_value'])
        # select only rows where gene_set_name_suffix starts with "GTEx"
        data_matrix_df = data_matrix_df[data_matrix_df['gene_set_name_suffix'].str.startswith("GTEx")]

        data_matrix_df['model'] = 'DTMX'
        data_matrix_df['tissue'] = 'data_matrix'
        print(f"Processed data matrix file with {len(data_matrix_df)} rows.")
        # print(data_matrix_df.head())
        summarize_data_matrix_df = create_top_enriched_df(data_matrix_df)
        summarize_data_matrix_df = add_key_column_drc(summarize_data_matrix_df)
        print("\nTop enriched gene sets for data matrix:")
        print(summarize_data_matrix_df.head(10))
        if df is not None:
            df = pd.concat([df, summarize_data_matrix_df], ignore_index=True)
        else:
            df = summarize_data_matrix_df
    else:
        print(f"Data matrix file {DATA_MATRIX_FILE} not found. Skipping.")

    # Process each tissue file and concatenate results
    for tissue in sorted(os.listdir(BASE_FOLDER)):
        tissue_path = os.path.join(BASE_FOLDER, tissue)
        if os.path.isdir(tissue_path):
            tissue_df = summarize_tissue(tissue)
            if tissue_df is not None:
                tissue_df = add_key_column_gtex(tissue_df)
            if df is None:
                df = tissue_df
            else: 
                if tissue_df is not None:
                    df = pd.concat([df, tissue_df], ignore_index=True)
    df.to_csv(output_path, sep='\t', index=False)
    print(f"\nSaved top gene sets to {output_path}")
    
    # Create and save pivot tables
    ab_pivot, ac_pivot = create_pivot_tables(df)
    ab_pivot.to_csv(pivot_ab_output_path, sep='\t')
    print(f"Saved AB models pivot table to {pivot_ab_output_path}")
    ac_pivot.to_csv(pivot_ac_output_path, sep='\t')
    print(f"Saved AC models pivot table to {pivot_ac_output_path}")

    # evaluate model performance
    # count across all tissues, use 25 for missing values
    # filer out rows where key ends with "_"
    ab_pivot = ab_pivot[~ab_pivot.index.str.endswith("_")]
    ac_pivot = ac_pivot[~ac_pivot.index.str.endswith("_")]
    pivot_ab_filled = ab_pivot.fillna(25)
    pivot_ac_filled = ac_pivot.fillna(25)
    # calculate average negative control count for each model    
    ab_model_performance = pivot_ab_filled.sum().sort_values()
    ac_model_performance = pivot_ac_filled.sum().sort_values()
    print("\nAverage negative control count for AB models:")    
    print(ab_model_performance)
    print("\nAverage negative control count for AC models:")
    print(ac_model_performance)


if __name__ == "__main__":
    main()