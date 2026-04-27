#!/usr/bin/env python3
"""
Batch process all DE comparisons with GMT membership and calculate Jaccard distances.

This script:
1. Reads all comparisons from comparisons.txt
2. Loops through each comparison and runs collate_de_with_gmt.py
3. For each comparison, calculates Jaccard distance between:
   - Top 250 genes (highest logFC - upregulated)
   - Bottom 250 genes (lowest logFC - downregulated)
   Based on their GMT membership patterns
4. Creates a summary TSV with results

Usage:
    python batch_process_de_gmt.py
"""

import subprocess
import sys
from pathlib import Path
import pandas as pd
from collections import Counter


def read_comparisons(comparisons_file):
    """Read comparisons from file."""
    comparisons = []
    with open(comparisons_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:  # Skip empty lines
                comparisons.append(line)
    return comparisons


def read_gmt_file_with_sizes(gmt_path):
    """
    Read GMT file and return dict with gene set names as keys and (genes_set, size) as values.
    """
    gene_sets = {}
    
    with open(gmt_path, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                gene_set_name = parts[0]
                genes = parts[2:]
                gene_sets[gene_set_name] = (set(genes), len(genes))
    
    return gene_sets


def run_collate_script(comparison):
    """Run the collate_de_with_gmt.py script for a comparison."""
    try:
        result = subprocess.run(
            [sys.executable, "collate_de_with_gmt.py", comparison],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Timeout processing {comparison}"
    except Exception as e:
        return False, "", str(e)


def calculate_jaccard_distance(set1, set2):
    """
    Calculate Jaccard distance between two sets.
    Jaccard distance = 1 - (|intersection| / |union|)
    """
    if len(set1) == 0 and len(set2) == 0:
        return 0.0  # Both empty, identical
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    if union == 0:
        return 0.0
    
    jaccard_similarity = intersection / union
    jaccard_distance = 1.0 - jaccard_similarity
    return jaccard_distance


def process_comparison(comparison, current_dir, up_gmt_genes, up_gmt_size, down_gmt_genes, down_gmt_size):
    """Process a single comparison and extract metrics for both Up and Down gene sets.
    
    Uses actual GMT gene set sizes and real genes from GMT files.
    Calculates Jaccard between how well top/bottom genes align with Up/Down predictions.
    """
    
    folder_name = comparison.replace(" ", "_").replace("-", "-")
    de_folder = current_dir / "outputs" / folder_name
    de_with_gmt_file = de_folder / "de_genes_with_gmt.tsv"
    
    # Check if file exists
    if not de_with_gmt_file.exists():
        return [{
            'comparison': comparison,
            'gmt_set': 'Up',
            'status': 'File not found',
            'total_genes': None,
            'gmt_set_size': up_gmt_size,
            'top_250_in_set': None,
            'bottom_250_in_set': None,
            'jaccard_distance': None,
            'error': f"File not found: {de_with_gmt_file}"
        }, {
            'comparison': comparison,
            'gmt_set': 'Down',
            'status': 'File not found',
            'total_genes': None,
            'gmt_set_size': down_gmt_size,
            'top_250_in_set': None,
            'bottom_250_in_set': None,
            'jaccard_distance': None,
            'error': f"File not found: {de_with_gmt_file}"
        }]
    
    try:
        # Read the data
        df = pd.read_csv(de_with_gmt_file, sep='\t')
        total_genes = len(df)
        
        # Get top 250 (highest logFC - upregulated)
        df_top_250 = df.head(250)
        
        # Get bottom 250 (lowest logFC - downregulated)
        df_bottom_250 = df.tail(250)
        
        # Count how many from each set are in the GMT gene sets
        top_genes_set = set(df_top_250['gene_symbol'])
        bottom_genes_set = set(df_bottom_250['gene_symbol'])
        
        top_in_up = len(top_genes_set & up_gmt_genes)
        bottom_in_up = len(bottom_genes_set & up_gmt_genes)
        top_in_down = len(top_genes_set & down_gmt_genes)
        bottom_in_down = len(bottom_genes_set & down_gmt_genes)
        
        # Calculate Jaccard distance:
        # For Up row: Jaccard between top 250 genes and Up GMT gene set
        # For Down row: Jaccard between bottom 250 genes and Down GMT gene set
        jaccard_up = calculate_jaccard_distance(
            top_genes_set,
            up_gmt_genes
        )
        
        # Down row: Jaccard between bottom 250 genes and Down GMT gene set
        jaccard_down = calculate_jaccard_distance(
            bottom_genes_set,
            down_gmt_genes
        )
        
        # Row 1: Up gene set analysis
        result_up = {
            'comparison': comparison,
            'gmt_set': 'Up',
            'status': 'Success',
            'total_genes': total_genes,
            'gmt_set_size': up_gmt_size,
            'top_250_in_set': top_in_up,
            'bottom_250_in_set': bottom_in_up,
            'jaccard_distance': round(jaccard_up, 4),
            'error': None
        }
        
        # Row 2: Down gene set analysis
        result_down = {
            'comparison': comparison,
            'gmt_set': 'Down',
            'status': 'Success',
            'total_genes': total_genes,
            'gmt_set_size': down_gmt_size,
            'top_250_in_set': top_in_down,
            'bottom_250_in_set': bottom_in_down,
            'jaccard_distance': round(jaccard_down, 4),
            'error': None
        }
        
        return [result_up, result_down]
        
    except Exception as e:
        return [{
            'comparison': comparison,
            'gmt_set': 'Up',
            'status': 'Error',
            'total_genes': None,
            'gmt_set_size': up_gmt_size,
            'top_250_in_set': None,
            'bottom_250_in_set': None,
            'jaccard_distance': None,
            'error': str(e)
        }, {
            'comparison': comparison,
            'gmt_set': 'Down',
            'status': 'Error',
            'total_genes': None,
            'gmt_set_size': down_gmt_size,
            'top_250_in_set': None,
            'bottom_250_in_set': None,
            'jaccard_distance': None,
            'error': str(e)
        }]


def main():
    """Main function."""
    
    current_dir = Path.cwd()
    comparisons_file = current_dir / "inputs" / "comparisons.txt"
    summary_file = current_dir / "outputs" / "gmt_analysis_summary.tsv"
    gmt_file = current_dir / "inputs" / "GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt"
    gmt_file = current_dir / "inputs" / "harmonizome_gtex_aging.gmt"
    
    if not comparisons_file.exists():
        print(f"Error: File not found: {comparisons_file}")
        sys.exit(1)
    
    if not gmt_file.exists():
        print(f"Error: File not found: {gmt_file}")
        sys.exit(1)
    
    # Read comparisons
    print(f"Reading comparisons from: {comparisons_file}")
    comparisons = read_comparisons(comparisons_file)
    print(f"  Found {len(comparisons)} comparisons\n")
    
    # Read GMT file with sizes
    print(f"Reading GMT file: {gmt_file}")
    gene_sets_with_sizes = read_gmt_file_with_sizes(gmt_file)
    print(f"  Found {len(gene_sets_with_sizes)} gene sets\n")
    
    results = []
    success_count = 0
    skip_count = 0
    
    for i, comparison in enumerate(comparisons, 1):
        print(f"[{i}/{len(comparisons)}] Processing: {comparison}")
        
        # Get GMT gene sets and sizes for this comparison
        up_key = f"GTEx {comparison} Up"
        down_key = f"GTEx {comparison} Down"
        
        if up_key not in gene_sets_with_sizes or down_key not in gene_sets_with_sizes:
            print(f"  ⊘ Skipped (GMT sets not found)")
            skip_count += 1
            continue
        
        up_gmt_genes, up_gmt_size = gene_sets_with_sizes[up_key]
        down_gmt_genes, down_gmt_size = gene_sets_with_sizes[down_key]
        
        # Run collate script
        success, stdout, stderr = run_collate_script(comparison)
        
        if success:
            print(f"  ✓ Collation successful")
            success_count += 1
        else:
            # Check if it's a "file not found" error (expected for non-analyzed comparisons)
            if "Results folder not found" in stderr or "not found" in stderr:
                print(f"  ⊘ Skipped (results not found)")
                skip_count += 1
                continue
            else:
                print(f"  ✗ Error: {stderr}")
        
        # Process the comparison to extract metrics (returns 2 rows: Up and Down)
        comparison_results = process_comparison(comparison, current_dir, up_gmt_genes, up_gmt_size, down_gmt_genes, down_gmt_size)
        results.extend(comparison_results)
        
        # Print results for both Up and Down
        for result in comparison_results:
            if result['status'] == 'Success':
                gmt_set = result['gmt_set']
                print(f"    {gmt_set} set (size={result['gmt_set_size']}): Top250={result['top_250_in_set']}, Bottom250={result['bottom_250_in_set']}, Jaccard={result['jaccard_distance']}")
            else:
                print(f"    {result['gmt_set']} set: {result['error']}")
        print()
    
    # Create summary DataFrame
    print("\n" + "="*80)
    print("Creating summary...")
    summary_df = pd.DataFrame(results)
    
    # Sort by comparison name alphabetically (then by GMT set for consistency)
    summary_df = summary_df.sort_values(['comparison', 'gmt_set'], ascending=[True, True]).reset_index(drop=True)
    
    # Save summary
    summary_df.to_csv(summary_file, sep='\t', index=False)
    print(f"\n✓ Summary saved to: {summary_file}")
    
    # Print statistics
    successful_rows = summary_df[summary_df['status'] == 'Success']
    print(f"\nStatistics:")
    print(f"  Total comparisons: {len(comparisons)}")
    print(f"  Successfully processed: {success_count}")
    print(f"  Skipped (no results): {skip_count}")
    print(f"  Total rows in summary: {len(summary_df)} (2 rows per comparison)")
    print(f"  Successful rows: {len(successful_rows)}")
    
    # Print sample of results
    print(f"\nTop 10 comparisons with minimal Jaccard distance (Up set):")
    up_set = successful_rows[successful_rows['gmt_set'] == 'Up'].sort_values('jaccard_distance', ascending=True)
    print(up_set[['comparison', 'gmt_set', 'gmt_set_size', 'top_250_in_set', 'bottom_250_in_set', 'jaccard_distance']].head(10).to_string(index=False))
    
    print(f"\nTop 10 comparisons with minimal Jaccard distance (Down set):")
    down_set = successful_rows[successful_rows['gmt_set'] == 'Down'].sort_values('jaccard_distance', ascending=True)
    print(down_set[['comparison', 'gmt_set', 'gmt_set_size', 'top_250_in_set', 'bottom_250_in_set', 'jaccard_distance']].head(10).to_string(index=False))
    
    print(f"\nJaccard distance statistics (Up set):")
    print(f"  Mean: {up_set['jaccard_distance'].mean():.4f}")
    print(f"  Median: {up_set['jaccard_distance'].median():.4f}")
    print(f"  Min: {up_set['jaccard_distance'].min():.4f}")
    print(f"  Max: {up_set['jaccard_distance'].max():.4f}")
    
    print(f"\nJaccard distance statistics (Down set):")
    print(f"  Mean: {down_set['jaccard_distance'].mean():.4f}")
    print(f"  Median: {down_set['jaccard_distance'].median():.4f}")
    print(f"  Min: {down_set['jaccard_distance'].min():.4f}")
    print(f"  Max: {down_set['jaccard_distance'].max():.4f}")


if __name__ == "__main__":
    main()
