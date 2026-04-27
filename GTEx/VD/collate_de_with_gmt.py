#!/usr/bin/env python3
"""
Script to collate differential expression results with GMT gene set membership.

This script:
1. Takes a comparison parameter in format: '<tissue> <age_group1> vs <age_group2>'
2. Reads the GMT file to get Up and Down gene sets
3. Reads de_genes_all.tsv from the corresponding folder
4. Adds a column indicating which genes are in the Up/Down gene sets
5. Saves to de_genes_with_gmt.tsv

Usage:
    python collate_de_with_gmt.py "Thyroid 20-29 vs 40-49"
    python collate_de_with_gmt.py "Blood 20-29 vs 60-69"
"""

import sys
import os
import pandas as pd
from pathlib import Path


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


def get_gmt_membership(gene_sets, comparison_param):
    """
    Extract Up and Down gene sets for the given comparison.
    
    Args:
        gene_sets (dict): Dictionary of gene sets
        comparison_param (str): Comparison parameter (e.g., "Thyroid 20-29 vs 40-49")
        
    Returns:
        tuple: (up_genes set, down_genes set)
    """
    up_key = f"GTEx {comparison_param} Up"
    down_key = f"GTEx {comparison_param} Down"
    
    up_genes = set(gene_sets.get(up_key, []))
    down_genes = set(gene_sets.get(down_key, []))
    
    if not up_genes and not down_genes:
        raise ValueError(
            f"Could not find gene sets for comparison: '{comparison_param}'\n"
            f"  Looking for: '{up_key}' and '{down_key}'"
        )
    
    if not up_genes:
        print(f"Warning: Could not find Up gene set: {up_key}")
    if not down_genes:
        print(f"Warning: Could not find Down gene set: {down_key}")
    
    return up_genes, down_genes


def get_folder_name(comparison_param):
    """
    Convert comparison parameter to folder name.
    
    Args:
        comparison_param (str): Comparison parameter (e.g., "Thyroid 20-29 vs 40-49")
        
    Returns:
        str: Folder name (e.g., "Thyroid_20-29_vs_40-49")
    """
    return comparison_param.replace(" ", "_").replace("-", "-")


def add_gmt_column(df, up_genes, down_genes):
    """
    Add a column indicating GMT membership.
    
    Args:
        df (pd.DataFrame): DataFrame with gene symbols
        up_genes (set): Set of up-regulated genes
        down_genes (set): Set of down-regulated genes
        
    Returns:
        pd.DataFrame: DataFrame with added 'GMT_category' column
    """
    def categorize_gene(symbol):
        in_up = symbol in up_genes
        in_down = symbol in down_genes
        
        if in_up and in_down:
            return "Both Up and Down"
        elif in_up:
            return "Up"
        elif in_down:
            return "Down"
        else:
            return ""
    
    df['GMT_category'] = df['gene_symbol'].apply(categorize_gene)
    return df


def main():
    """Main function to collate DE results with GMT membership."""
    
    # Parse command-line arguments
    if len(sys.argv) != 2:
        print("Usage: python collate_de_with_gmt.py '<tissue> <age_group1> vs <age_group2>'")
        print("Example: python collate_de_with_gmt.py 'Thyroid 20-29 vs 40-49'")
        sys.exit(1)
    
    comparison_param = sys.argv[1]
    
    # Get current directory and file paths
    current_dir = Path.cwd()
    gmt_path = current_dir / "inputs" / "GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt"
    gmt_path = current_dir / "inputs" / "harmonizome_gtex_aging.gmt"
    folder_name = get_folder_name(comparison_param)
    de_folder = current_dir / "outputs" / folder_name
    de_file = de_folder / "de_genes_all.tsv"
    output_file = de_folder / "de_genes_with_gmt.tsv"
    
    # Validate files exist
    if not gmt_path.exists():
        print(f"Error: GMT file not found: {gmt_path}")
        sys.exit(1)
    
    if not de_folder.exists():
        print(f"Error: Results folder not found: {de_folder}")
        sys.exit(1)
    
    if not de_file.exists():
        print(f"Error: DE results file not found: {de_file}")
        sys.exit(1)
    
    print(f"Processing comparison: {comparison_param}")
    print(f"  GMT file: {gmt_path}")
    print(f"  DE file: {de_file}")
    print(f"  Output: {output_file}")
    
    # Read GMT file
    print("\nReading GMT file...")
    gene_sets = read_gmt_file(gmt_path)
    print(f"  Found {len(gene_sets)} gene sets")
    
    # Get Up and Down genes
    print(f"\nExtracting gene sets for: {comparison_param}")
    up_genes, down_genes = get_gmt_membership(gene_sets, comparison_param)
    print(f"  Up genes: {len(up_genes)}")
    print(f"  Down genes: {len(down_genes)}")
    
    # Read DE results
    print(f"\nReading DE results...")
    df = pd.read_csv(de_file, sep='\t')
    print(f"  Total genes: {len(df)}")
    
    # Add GMT category column
    print(f"\nAdding GMT membership column...")
    df = add_gmt_column(df, up_genes, down_genes)
    
    # Show summary
    print("\nGMT membership summary:")
    print(df['GMT_category'].value_counts())
    
    # Save results
    print(f"\nSaving results to: {output_file}")
    df.to_csv(output_file, sep='\t', index=False)
    print("✓ Done!")


if __name__ == "__main__":
    main()
