import csv
import os
import pandas as pd
import matplotlib.pyplot as plt

from gene_set_comparison import model_name


BASE_FOLDER = "/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/gtex/genesets"
IN_FILE = "../../data/gtex/output.tissue/{}_validation_results.txt"


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


def summarize_tissue(tissue):
    #check if input file exists
    if not os.path.exists(IN_FILE.format(tissue)):
        print(f"Input file {IN_FILE.format(tissue)} not found. Skipping tissue {tissue}.")
        return None
    df = pd.read_csv(IN_FILE.format(tissue), sep='\t', header=None, names=['model','gene_set_name_suffix','gene_set_name', 'gene_set_size', 'rank', 'enriched_gene_sets_name', 'enriched_gene_set_size', 'enriched_gene_set_p_value'])
    df['tissue'] = tissue
    # Extract model prefix from gene_set_name (everything before first "__")
    # df['model'] = df['gene_set_name'].str.split('__').str[0]
    # Extract model index (remove "M" and convert to integer)
    # df['model_index'] = df['model'].str.replace('M', '').astype(int)
    # gene_set_name_suffix = df['gene_set_name'].str.split('__', n=1).str[1]
    # df['gene_set_name_suffix'] = gene_set_name_suffix
    # print(df.head())
    
    # Create top enriched gene set dataframe
    top_df = create_top_enriched_df(df)
    print("\nTop enriched gene sets by model and gene_set_name_suffix:")
    print(top_df.head(10))
    
    return top_df
    # Save to TSV file
    # output_path = "../../data/gtex/output-test/{}_top_gene_sets.tsv".format(tissue)
    # top_df.to_csv(output_path, sep='\t', index=False)
    # print(f"\nSaved top gene sets to {output_path}")


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
    ab_df = df[df['model'].str.startswith('AB')].copy()
    ac_df = df[df['model'].str.startswith('AC')].copy()
    
    # Create pivot tables
    ab_pivot = ab_df.pivot_table(
        index=['tissue', 'gene_set_name_suffix'],
        columns='model',
        values='negative_control_count',
        aggfunc='first'
    )
    
    ac_pivot = ac_df.pivot_table(
        index=['tissue', 'gene_set_name_suffix'],
        columns='model',
        values='negative_control_count',
        aggfunc='first'
    )
    
    return ab_pivot, ac_pivot


def main():
    output_path = "../../data/gtex/output.tissue/top_gene_sets.tsv"
    pivot_ab_output_path = "../../data/gtex/output.tissue/negative_control_counts_AB.tsv"
    pivot_ac_output_path = "../../data/gtex/output.tissue/negative_control_counts_AC.tsv"
    df = None
    for tissue in sorted(os.listdir(BASE_FOLDER)):
        tissue_path = os.path.join(BASE_FOLDER, tissue)
        if os.path.isdir(tissue_path):
            if df is None:
                df = summarize_tissue(tissue)
            else:                
                tissue_df = summarize_tissue(tissue)
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

if __name__ == "__main__":
    main()