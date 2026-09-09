# Translator Gene Sets Extraction Agent

This document describes how to use the gene set extraction pipeline to create translator gene sets from biolink network data.

## Overview

The `build_translator_gene_sets.py` script orchestrates a three-step pipeline:

1. **Download** (`-d`): Download HGNC gene data and Translator network files
2. **Process** (`-p`): Parse edges, identify human genes, and populate database
3. **Export** (`-x`): Generate GMT format gene sets with filtering

Running without arguments executes all three steps automatically.

## Prerequisites

### Required Python Packages
```
sqlite3 (standard library)
json (standard library)
requests
argparse (standard library)
pathlib (standard library)
```

Install requests if needed:
```bash
pip install requests
```

### Required Configuration Files

#### 1. `predicate_inverse_config.json`
Located in `translator/src/` (same directory as the script). Maps biolink predicates to their inverse relationships.

**Format:**
```json
{
  "biolink:affects": {
    "inverse": "affected_by",
    "symmetric": false
  },
  "biolink:interacts_with": {
    "inverse": "interacts_with",
    "symmetric": true
  }
}
```

**Fields:**
- `inverse`: The inverse predicate (without "biolink:" prefix for directional predicates)
- `symmetric`: Boolean - if true, relationship is bidirectional (used for predicates like "interacts_with")

#### 2. `nodes.jsonl` (downloaded automatically)
JSON-lines file with node information. Each line:
```json
{"id": "MESH:D000001", "name": "Calcimycin", "category": "ChemicalSubstance"}
```

#### 3. `edges.jsonl` (downloaded automatically)
JSON-lines file with edge information. Each line:
```json
{"subject": "MESH:D000001", "predicate": "biolink:affects", "object": "NCBIGene:1234"}
```

## Directory Structure

```
translator/
├── translator/
│   ├── src/
│   │   ├── build_translator_gene_sets.py
│   │   └── predicate_inverse_config.json
│   ├── data/
│   │   ├── hgnc_ncbi_genes.json          (generated)
│   │   ├── edges.jsonl                   (downloaded)
│   │   ├── nodes.jsonl                   (downloaded)
│   │   ├── translator_gene_neighbors.sqlite (generated)
│   │   └── translator_gene_sets.gmt      (generated)
│   └── TRANSLATOR_GENE_SETS_AGENT.md     (this file)
```

## Usage

### Basic Usage (All Steps)
```bash
cd translator/translator/src
python build_translator_gene_sets.py
```

Executes: Download HGNC → Download Network → Process Edges → Export GMT

### Step-by-Step Usage
```bash
# Download only
python build_translator_gene_sets.py -d

# Process only (requires downloaded data files)
python build_translator_gene_sets.py -p

# Export only (requires processed database)
python build_translator_gene_sets.py -x

# Combine steps
python build_translator_gene_sets.py -d -p -x
python build_translator_gene_sets.py -p -x    # Skip download
```

## Step Details

### Step 1: Download (`-d`)

**What it does:**
- Downloads HGNC genes from https://storage.googleapis.com/public-download-files/hgnc/json/json/hgnc_complete_set.json
- Extracts genes with NCBI entrez IDs
- Saves to `../data/hgnc_ncbi_genes.json`
- Downloads edges.jsonl and nodes.jsonl from Translator KG (1MB chunks, progress every 10MB)

**Output files:**
- `../data/hgnc_ncbi_genes.json`: ~19,000+ genes with NCBI IDs
- `../data/edges.jsonl`: Network edges (potentially 10GB+)
- `../data/nodes.jsonl`: Network nodes

**Time estimate:** 5-30 minutes depending on network speed

### Step 2: Process (`-p`)

**What it does:**
1. Creates SQLite database: `../data/translator_gene_neighbors.sqlite`
2. Loads HGNC genes into memory
3. Loads predicate configuration
4. Iterates through edges.jsonl:
   - Identifies edges where subject or object is a human gene
   - Determines if relationship is symmetric or directional
   - Stores human gene → neighbor relationships
5. Creates composite index on (neighbor_id, predicate, is_inverse)

**Database schema:**
```sql
CREATE TABLE gene_neighbors (
    neighbor_id TEXT,
    predicate TEXT,
    is_inverse BOOLEAN,
    gene_symbol TEXT
);
CREATE INDEX idx_neighbor_predicate_inverse 
    ON gene_neighbors(neighbor_id, predicate, is_inverse);
```

**Processing logic:**

For each edge with subject S, predicate P, object O:

1. **If O is a human gene:**
   - is_inverse = False (subject is the neighbor)
   - Store: (S, P, False, gene_symbol)

2. **If S is a human gene:**
   - Check if P is symmetric (from predicate_inverse_config.json)
   - is_inverse = not symmetric
   - Store: (O, P, is_inverse, gene_symbol)

**Output:**
- `../data/translator_gene_neighbors.sqlite`: SQLite database with all relationships

**Console output:**
```
Processed 100000 lines, stored 45000 human gene neighbors in the database.
Processed 200000 lines, stored 89000 human gene neighbors in the database.
...
Creating index on gene_neighbors table...
Database processing complete.
```

**Time estimate:** 30 minutes - 2 hours (depending on edges.jsonl size)

### Step 3: Export (`-x`)

**What it does:**
1. Queries database for all unique (neighbor_id, predicate, is_inverse) combinations
2. For each combination:
   - Generates geneset name using neighbor node name + predicate
   - Retrieves all distinct genes connected to that neighbor via that predicate
   - Applies filters:
     - Minimum 5 genes per geneset (default, configurable)
     - Maximum 2000 genes per geneset (default, configurable)
3. Exports in GMT format (tab-separated)

**GMT Format:**
```
neighbor_name_predicate	neighbor_id|predicate	gene1	gene2	gene3	...
```

**Example output:**
```
MESH:D000001_affects	MESH:D000001|affects	HGNC:1	HGNC:42	HGNC:100
Protein_interacts_with	NCBIProtein:12345|interacts_with	HGNC:5	HGNC:18	HGNC:99	HGNC:102
```

**Filtering:**
- Genesets with < 5 genes: excluded (configurable with `min_genes`)
- Genesets with > 2000 genes: excluded (configurable with `max_genes`)
- Warnings printed for excluded genesets

**Output files:**
- `../data/translator_gene_sets.gmt`: GMT format gene sets

**Console output:**
```
Processed 5000 genesets, saved 4500, excluded 500
Processed 10000 genesets, saved 9000, excluded 1000

Export complete:
  Total genesets found: 15432
  Genesets saved (>= 5 genes): 14200
  Output file: /absolute/path/translator_gene_sets.gmt

Warnings (1232):
  1000 genesets excluded for exceeding max_genes
```

**Time estimate:** 5-15 minutes (depends on database size and query complexity)

## Configuration & Customization

### Adjusting Gene Set Filters

Modify filter parameters in the export step:

```python
# In the script or as future CLI options:
export_gene_sets(
    min_genes=5,      # Minimum genes per geneset
    max_genes=2000    # Maximum genes per geneset
)
```

### Updating Predicates

Edit `predicate_inverse_config.json`:

```json
{
  "biolink:new_predicate": {
    "inverse": "new_predicate_inverse",
    "symmetric": false
  }
}
```

Add missing predicates to avoid warnings during export.

## Troubleshooting

### Error: "Edges file not found"
**Cause:** edges.jsonl doesn't exist in ../data/
**Solution:** Run with `-d` flag to download: `python build_translator_gene_sets.py -d`

### Error: "No such table: gene_neighbors"
**Cause:** Database not created; process step not run
**Solution:** Run with `-p` flag: `python build_translator_gene_sets.py -p`

### Error: "Predicate not found in config"
**Cause:** A biolink predicate in edges.jsonl isn't in predicate_inverse_config.json
**Solution:** Add missing predicates to predicate_inverse_config.json

### Large number of "Warnings: Predicate X not found"
**Cause:** predicate_inverse_config.json is incomplete
**Solution:** Run with current config (it will work), then update config for next run

### Slow processing (Step 2)
**Cause:** Large edges.jsonl file (10GB+)
**Solution:** Normal - processing scales with file size. Commits happen every 10k relationships.

## Data Flow Diagram

```
1. DOWNLOAD STEP
   ├─ https://hgnc-api → hgnc_ncbi_genes.json (19k genes)
   ├─ https://translator-kg → edges.jsonl (10GB+)
   └─ https://translator-kg → nodes.jsonl (100MB+)

2. PROCESS STEP
   ├─ Load hgnc_ncbi_genes.json → memory dict
   ├─ Load predicate_inverse_config.json → memory dict
   ├─ Iterate edges.jsonl:
   │  └─ For each edge: identify human genes → SQLite
   └─ Create index on sqlite table

3. EXPORT STEP
   ├─ Query unique (neighbor_id, predicate, is_inverse)
   ├─ For each: get node name, fetch connected genes
   ├─ Apply filters (5-2000 genes)
   └─ Write GMT format
```

## Performance Notes

- **Memory:** ~500MB for HGNC + predicates + nodes in memory (step 2)
- **Disk:** SQLite grows to ~50% size of edges.jsonl
- **Network:** Downloads are 1MB chunks, 8x faster than 8KB chunks
- **Database:** Composite index speeds up export queries significantly

## Common Workflows

### Fresh Build from Scratch
```bash
python build_translator_gene_sets.py
# Runs: download → process → export (30-120 minutes)
```

### Update Gene Sets with New Predicates
```bash
# Edit predicate_inverse_config.json
python build_translator_gene_sets.py -p -x
# Reprocesses edges and re-exports (15-30 minutes, skips download)
```

### Adjust Filters and Re-export
```bash
# Modify min_genes/max_genes in script
python build_translator_gene_sets.py -x
# Exports with new filters (5-15 minutes)
```

## Integration with Geneset-Extractor

The output GMT file from this pipeline integrates with the parent geneset-extractor project:
- Place `translator_gene_sets.gmt` in the appropriate submission directory
- Use with other gene set libraries for cross-validation
- Combine with GTEx, HuBMAP, LINCS, MoTrPAC gene sets

## Support

For issues or enhancements:
1. Check this document's Troubleshooting section
2. Review predicate_inverse_config.json completeness
3. Verify data files exist and are readable
4. Check script output for specific error messages
