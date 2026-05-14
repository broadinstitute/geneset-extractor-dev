import csv
import pandas as pd
import matplotlib.pyplot as plt

from gene_set_comparison import model_name

IN_FILE = "../../data/gtex/output/lung_validation_results.txt"



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
    result_df = top_df[['model', 'gene_set_name_suffix', 'gene_set_size', 'enriched_gene_sets_name', 'enriched_gene_set_size', 'enriched_gene_set_p_value']].rename(
        columns={'enriched_gene_sets_name': 'top_enriched_gene_set'}
    )
    result_df['model'] = result_df['model'].apply(model_name)
    # Sort by gene_set_name_suffix and then by model
    result_df = result_df.sort_values(['gene_set_name_suffix', 'model']).reset_index(drop=True)
    
    return result_df


def main():
    df = pd.read_csv(IN_FILE, sep='\t', header=None, names=['gene_set_name', 'gene_set_size', 'rank', 'enriched_gene_sets_name', 'enriched_gene_set_size', 'enriched_gene_set_p_value'])
    # Extract model prefix from gene_set_name (everything before first "__")
    df['model'] = df['gene_set_name'].str.split('__').str[0]
    # Extract model index (remove "M" and convert to integer)
    # df['model_index'] = df['model'].str.replace('M', '').astype(int)
    gene_set_name_suffix = df['gene_set_name'].str.split('__', n=1).str[1]
    df['gene_set_name_suffix'] = gene_set_name_suffix
    print(df.head())
    
    # Create top enriched gene set dataframe
    top_df = create_top_enriched_df(df)
    print("\nTop enriched gene sets by model and gene_set_name_suffix:")
    print(top_df.head(10))
    
    # Save to TSV file
    output_path = "../../data/gtex/output/lung_top_gene_sets.tsv"
    top_df.to_csv(output_path, sep='\t', index=False)
    print(f"\nSaved top gene sets to {output_path}")

if __name__ == "__main__":
    main()