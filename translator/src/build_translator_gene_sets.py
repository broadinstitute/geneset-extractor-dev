
import sqlite3

import json
import requests
import argparse
from pathlib import Path


def download_hgnc_genes(output_file: str = "../data/hgnc_ncbi_genes.json"):
    """
    From https://storage.googleapis.com/public-download-files/hgnc/json/json/hgnc_complete_set.json
    download HGNC genes, extract NCBI gene ids and save in a file.
    
    Args:
        output_file: Path to save the extracted NCBI gene IDs and gene information.
    
    Returns:
        dict: Dictionary mapping NCBI gene IDs to gene information.
    """
    hgnc_url = "https://storage.googleapis.com/public-download-files/hgnc/json/json/hgnc_complete_set.json"
    
    print(f"Downloading HGNC genes from {hgnc_url}...")
    response = requests.get(hgnc_url)
    response.raise_for_status()
    
    data = response.json()
    genes = data.get("response", {}).get("docs", [])
    
    # Extract genes with NCBI gene IDs
    ncbi_genes = {}
    for gene in genes:
        ncbi_id = gene.get("entrez_id")
        if ncbi_id:
            ncbi_genes[f"NCBIGene:{str(ncbi_id)}"] = {
                "hgnc_id": gene.get("hgnc_id"),
                "symbol": gene.get("symbol"),
                "name": gene.get("name"),
                "ncbi_id": ncbi_id,
                "ensembl_gene_id": gene.get("ensembl_gene_id"),
                "uniprot_ids": gene.get("uniprot_ids"),
            }
    
    # Save to file
    output_path = Path(output_file)
    with open(output_path, "w") as f:
        json.dump(ncbi_genes, f, indent=2)
    
    print(f"Extracted {len(ncbi_genes)} genes with NCBI IDs")
    print(f"Saved to {output_path.absolute()}")
    
    return ncbi_genes


def create_gene_neighbors_database(db_file: str = "../data/translator_gene_neighbors.sqlite"):
    """
    Create a SQLite database with a single table to store gene neighbor relationships.
    
    Args:
        db_file: Path to the database file to create.
    
    Returns:
        str: Path to the created database file.
    """
    db_path = Path(db_file)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table with specified columns
    cursor.execute("""
        CREATE TABLE gene_neighbors (
            neighbor_id TEXT,
            predicate TEXT,
            is_inverse BOOLEAN,
            gene_symbol TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    
    print(f"Created database at {db_path.absolute()}")
    return str(db_path)


def insert_gene_neighbor(conn, neighbor_id: str, predicate: str, is_inverse: bool, gene_symbol: str):
    """
    Insert a gene neighbor relationship into the database.
    
    Args:
        conn: SQLite connection object.
        neighbor_id: The ID of the neighboring gene.
        predicate: The type of relationship (e.g., "interacts_with").
        is_inverse: Whether the relationship is inverse.
        gene_symbol: The symbol of the gene.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO gene_neighbors (neighbor_id, predicate, is_inverse, gene_symbol)
        VALUES (?, ?, ?, ?)
    """, (neighbor_id, predicate, is_inverse, gene_symbol))


def load_hgnc_genes(file_path: str = "../data/hgnc_ncbi_genes.json"):
    """
    Load HGNC genes from a JSON file.
    
    Args:
        file_path: Path to the JSON file containing HGNC genes.
    """
    with open(file_path, "r") as f:
        return json.load(f)


def load_predicate_inverse_config(file_path: str = "predicate_inverse_config.json"):
    """
    Load predicate inverse configuration from a JSON file.
    
    Args:
        file_path: Path to the predicate inverse config JSON file.
    
    Returns:
        dict: Configuration mapping predicates to their inverse properties.
    """
    with open(file_path, "r") as f:
        return json.load(f)


def process_line(line: str, conn, hgnc_genes: dict, predicate_config: dict = None):
    """
    Process a single JSON line from the edges file and store in database if subject is a human gene.
    
    Args:
        line: A single JSON line from the edges file.
        conn: SQLite connection object.
        hgnc_genes: Dictionary of HGNC genes (mapping NCBIGene IDs to gene info).
        predicate_config: Dictionary of predicate inverse configuration.
    """
    if predicate_config is None:
        predicate_config = {}
    
    edge = json.loads(line)

    object_id = edge.get("object", "")
    predicate = edge.get("predicate", "")
    subject_id = edge.get("subject", "")

    #check if object is a human gene
    if object_id in hgnc_genes:
        gene_info = hgnc_genes[object_id]
        gene_symbol = gene_info.get("symbol", "")
        neighbor_id = subject_id
        is_inverse = False  # Not inverse relationship since object is the human gene

        if gene_symbol and neighbor_id and predicate:
            insert_gene_neighbor(conn, neighbor_id, predicate, is_inverse, gene_symbol)
            return True
        else:
            return False

    # Check if subject is a human gene
    if subject_id in hgnc_genes:
        gene_info = hgnc_genes[subject_id]
        gene_symbol = gene_info.get("symbol", "")
        neighbor_id = object_id
        
        # Check if predicate is symmetric
        is_symmetric = False
        if predicate in predicate_config:
            is_symmetric = predicate_config[predicate].get("symmetric", False)
        
        # For symmetric predicates, don't mark as inverse
        is_inverse = not is_symmetric

        if gene_symbol and neighbor_id and predicate:
            insert_gene_neighbor(conn, neighbor_id, predicate, is_inverse, gene_symbol)
            return True
        else:
            return False
    return False


def export_gene_sets(db_file: str = "../data/translator_gene_neighbors.sqlite", 
                     output_file: str = "../data/translator_gene_sets.gmt",
                     min_genes: int = 5):
    """
    Export gene neighbor relationships from database as GMT genesets.
    
    For each (neighbor_id, predicate, is_inverse) combination, create a geneset 
    containing all connected genes. Use inverse predicate from config when is_inverse=True.
    
    Args:
        db_file: Path to the SQLite database file.
        output_file: Path to the output GMT file.
        min_genes: Minimum number of genes required per geneset (default 5).
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Load predicate config to get inverse predicates
    predicate_config = load_predicate_inverse_config()
    
    # Get all unique combinations of (neighbor_id, predicate, is_inverse)
    cursor.execute("""
        SELECT DISTINCT neighbor_id, predicate, is_inverse
        FROM gene_neighbors
        ORDER BY neighbor_id, predicate, is_inverse
    """)
    
    combinations = cursor.fetchall()
    
    total_genesets_found = 0
    total_genes_found = 0
    total_genesets_saved = 0
    total_genes_saved = 0
    warnings = []
    
    with open(output_file, "w") as f:
        for neighbor_id, predicate, is_inverse in combinations:
            # Determine geneset name based on is_inverse
            if is_inverse:
                # Look up inverse predicate in config
                if predicate in predicate_config:
                    inverse_pred = predicate_config[predicate].get("inverse")
                    if inverse_pred:
                        # Remove "biolink:" prefix if present
                        inverse_pred = inverse_pred.replace("biolink:", "")
                        geneset_name = f"{neighbor_id}_{inverse_pred}"
                    else:
                        warning_msg = f"Warning: Predicate {predicate} not found inverse mapping in config, using original predicate"
                        warnings.append(warning_msg)
                        geneset_name = f"{neighbor_id}_{predicate.replace('biolink:', '')}"
                else:
                    warning_msg = f"Warning: Predicate {predicate} not found in config, using original predicate"
                    warnings.append(warning_msg)
                    geneset_name = f"{neighbor_id}_{predicate.replace('biolink:', '')}"
            else:
                # Use predicate as-is, remove "biolink:" prefix
                pred_name = predicate.replace("biolink:", "")
                geneset_name = f"{neighbor_id}_{pred_name}"
            
            # Get all distinct genes for this combination
            cursor.execute("""
                SELECT DISTINCT gene_symbol
                FROM gene_neighbors
                WHERE neighbor_id = ? AND predicate = ? AND is_inverse = ?
            """, (neighbor_id, predicate, is_inverse))
            
            genes = [row[0] for row in cursor.fetchall()]
            total_genesets_found += 1
            total_genes_found += len(genes)
            
            # Apply minimum gene count filter
            if len(genes) >= min_genes:
                total_genesets_saved += 1
                total_genes_saved += len(genes)
                
                # GMT format: geneset_name \t description \t gene1 \t gene2 \t ...
                line = f"{geneset_name}\t{geneset_name}\t" + "\t".join(genes) + "\n"
                f.write(line)
    
    conn.close()
    
    # Print results and warnings
    print(f"\nExport complete:")
    print(f"  Total genesets found: {total_genesets_found}")
    print(f"  Total genes found: {total_genes_found}")
    print(f"  Genesets saved (>= {min_genes} genes): {total_genesets_saved}")
    print(f"  Genes saved: {total_genes_saved}")
    print(f"  Output file: {Path(output_file).absolute()}")
    
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  {warning}")


def create_index(conn):
    """
    Create index on neighbor_id, predicate, and is_inverse columns after data loading.
    
    Args:
        conn: SQLite connection object.
    """
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_neighbor_predicate_inverse 
        ON gene_neighbors(neighbor_id, predicate, is_inverse)
    """)
    
    conn.commit()
    print(f"Created index on gene_neighbors table")


def process_edges_file():
    # Download HGNC genes and save to JSON
    # hgnc_genes = download_hgnc_genes()

    # Create gene neighbors database
    db_path = create_gene_neighbors_database()

    # Load HGNC genes from JSON file
    hgnc_genes = load_hgnc_genes()
    
    # Load predicate inverse configuration
    predicate_config = load_predicate_inverse_config()
    
    # Process edges file - single line (replace with your actual edges file path)
    edges_file = "../data/edges.jsonl"  # Update this path to your edges file
    counter_in = 0
    counter_out = 0
    if Path(edges_file).exists():
        conn = sqlite3.connect(db_path)
        
        # Process the edges file
        with open(edges_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        processed = process_line(line, conn, hgnc_genes, predicate_config)
                        if processed:
                            counter_out += 1
                        counter_in += 1
                        if counter_out % 10000 == 0:
                            conn.commit()
                        if counter_in % 100000 == 0:
                            print(f"Processed {counter_in} lines, stored {counter_out} human gene neighbors in the database.")
                    except json.JSONDecodeError as e:
                        print(f"Error parsing JSON line: {e}")
 
        print(f"Processed {counter_in} lines, stored {counter_out} human gene neighbors in the database.")

        print("Creating index on gene_neighbors table...")        
        create_index(conn)
        conn.close()
        print("Database processing complete.")
    else:
        print(f"Edges file not found: {edges_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build translator gene sets from HGNC and edges data.")
    parser.add_argument("-d", "--download", action="store_true", help="Download HGNC genes from the remote source")
    parser.add_argument("-p", "--process", action="store_true", help="Process edges file and populate the database")
    parser.add_argument("-x", "--export", action="store_true", help="Export gene neighbors data (not implemented yet)")
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if not any([args.download, args.process, args.export]):
        parser.print_help()
    else:
        if args.download:
            print("Downloading HGNC genes...")
            download_hgnc_genes()
        
        if args.process:
            print("Processing edges file...")
            process_edges_file()
        
        if args.export:
            print("Exporting gene sets to GMT format...")
            export_gene_sets()
