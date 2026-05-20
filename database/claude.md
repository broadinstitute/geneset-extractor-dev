# GeneSeCoDB Population Strategy

## Overview
Complete ETL pipeline to populate GeneSeCoDB from GMT gene set files with associated JSON provenance, metadata, and run summary files.

## Architecture

### Data Flow
```
GMT Files (genesets) 
    ↓
JSON Files (provenance, metadata, run_summary)
    ↓
GeneSeCoDatabasePopulator (ETL)
    ↓
SQLite Database (normalized tables)
```

### Core Class: GeneSeCoDatabasePopulator
Orchestrates all database operations with insert-or-get pattern for dimension tables.

## Implementation Strategy

### Phase 1: Schema Initialization
```python
def __init__(db_path: str):
    - Initialize SQLite connection with PRAGMA foreign_keys = ON
    - Track next_available_node_id = 1 (for ID spacing across genesets)
    
def initialize_schema(schema_file: str):
    - Load external SQL file
    - Execute with executescript() to handle multiple statements
```

### Phase 2: File Discovery
```python
def find_gmt_files(root_path: str) -> List[Path]:
    - Recursively find all *.gmt files in directory tree
    - Return sorted list for consistent processing
```

### Phase 3: Dimension Table Management (Insert-or-Get Pattern)

All dimension tables use SELECT-first-then-INSERT logic:

#### Species
```python
def insert_species(species_code: str, species_name: str) -> int:
    - SELECT species_id WHERE species_code = ? (return if exists)
    - INSERT if not found, return new id
```

#### Gene Symbols (Namespace-scoped)
```python
def insert_namespace(label: str, species_code: str) -> int:
    - Get or create namespace for gene symbol context
    
def insert_gene_symbol(symbol: str, namespace_id: int, ncbi_id: str = None) -> int:
    - SELECT gene_symbol_id WHERE symbol = ? AND namespace_id = ?
    - INSERT if not found, return id
    - NCBI ID stored in additional_properties JSON
```

#### Collections
```python
def insert_collection(collection_name: str, full_name: str = None, description: str = None) -> int:
    - SELECT collection_id WHERE collection_name = ?
    - INSERT if not found, return id
```

#### Licenses
```python
def insert_gene_set_license(license_code: str, license_name: str = None) -> int:
    - SELECT license_id WHERE license_code = ?
    - INSERT if not found, return id
```

### Phase 4: Gene Set Insertion (ID Spacing)
```python
def insert_gene_set(standard_name: str, collection_name: str, license_code: str, 
                    tags: str = None, gene_set_id: int = None) -> int:
    - Accept explicit gene_set_id parameter for spacing strategy
    - If gene_set_id provided, use in INSERT
    - Otherwise let SQLite auto-increment
    - Return gene_set_id
```

**Key Feature**: Accepts optional gene_set_id to ensure contiguous allocation across genesets.

### Phase 5: Gene-GenSet Association
```python
def insert_gene_set_gene_symbol(gene_set_id: int, gene_symbol_id: int):
    - CREATE many-to-many association
    - Use INSERT OR IGNORE to silently handle duplicates
    - No UNIQUE constraint violation errors
```

### Phase 6: Provenance & Metadata Loading
```python
def load_provenance_and_metadata(gene_set_name: str, root_path: Path) 
    -> Optional[Tuple[str, str, Optional[str]]]:
    
    Expected files in same directory as GMT:
    - {gene_set_name}.provenance.json (required)
    - {gene_set_name}.meta.json (required)
    - run_summary.json (optional)
    
    Returns:
    - (provenance_graph_str, geneset_metadata_str, run_summary_str)
    - None if required files missing
```

### Phase 7: Provenance Record Storage
```python
def insert_provenance(gene_set_id: int, provenance_graph: str, 
                     geneset_metadata: str, run_summary: str = None):
    - Store raw JSON strings in TEXT columns
    - Preserves complete nested structure
    - No parsing or normalization
```

### Phase 8: Provenance Graph Normalization
```python
def insert_provenance_nodes_and_edges(gene_set_id: int, provenance_json_str: str) -> int:
    
    Parse JSON structure (handles multiple nesting patterns):
    1. Check top level for "nodes" and "edges"
    2. If not found, iterate through keys looking for nested structures
    
    Node insertion logic:
    - Extract node fields: id, node_type, name, description, dcc_url, drc_url
    - Additional properties stored as JSON in additional_properties column
    - GeneSet node: SPECIAL CASE
      * provenance_node_id = gene_set_id (ensures ID alignment)
      * Use INSERT OR REPLACE (supports re-runs)
    - Other nodes: auto-increment provenance_node_id
    
    Edge insertion logic:
    - Extract: source_node_id, target_node_id, label, description
    - Additional properties stored as JSON
    - Foreign keys reference provenance_node table
    - Auto-increment provenance_edge_id
    
    Return:
    - max_node_id_used for tracking allocation
```

### Phase 9: ID Spacing Strategy
Ensures contiguous node ID allocation across all genesets:

```
GenSet 1: gene_set_id=1, nodes 1-N
GenSet 2: gene_set_id=N+1, nodes (N+1)-(N+1+M)
GenSet 3: gene_set_id=N+1+M+1, nodes (N+1+M+1)-...
```

Implementation in `populate_from_gmt_files()`:
```python
1. Set gene_set_id = self.next_available_node_id
2. Insert geneset with explicit gene_set_id
3. Insert provenance nodes/edges, get back max_node_id_used
4. Update self.next_available_node_id = max_node_id_used + 1
5. Repeat for next geneset
```

### Phase 10: Main Orchestration
```python
def populate_from_gmt_files(root_path: str, 
                           collection_name: str = 'GTEx',
                           species_code: str = 'Homo_sapiens',
                           species_name: str = 'Homo sapiens',
                           namespace_label: str = 'HGNC',
                           license_code: str = 'CC-BY-4.0',
                           require_provenance: bool = True):

    For each GMT file found:
    ┌─────────────────────────────────────────┐
    │ 1. Parse GMT file                       │
    │    - Extract gene_set_name, genes list  │
    ├─────────────────────────────────────────┤
    │ 2. Create/get dimension records         │
    │    - Species, Namespace, License        │
    ├─────────────────────────────────────────┤
    │ 3. Load provenance/metadata JSONs       │
    │    - Skip if require_provenance=True    │
    │      and files missing                  │
    ├─────────────────────────────────────────┤
    │ 4. Assign gene_set_id = next_available  │
    │    - Ensures ID spacing                 │
    ├─────────────────────────────────────────┤
    │ 5. Insert gene set record               │
    │    - Use explicit gene_set_id parameter │
    ├─────────────────────────────────────────┤
    │ 6. For each gene symbol:                │
    │    - Get or create gene_symbol record   │
    │    - Create geneset-gene association    │
    ├─────────────────────────────────────────┤
    │ 7. Insert provenance record             │
    │    - Store all JSON serialized          │
    ├─────────────────────────────────────────┤
    │ 8. Insert provenance nodes and edges    │
    │    - Normalize graph structure          │
    │    - Track max_node_id_used             │
    ├─────────────────────────────────────────┤
    │ 9. Update next_available_node_id        │
    │    - = max_node_id_used + 1             │
    └─────────────────────────────────────────┘
```

## Configuration

### CLI Parameters
```
--db-path (required)
    Path to SQLite database file
    
--schema-file (required)
    Path to SQL schema file (database-schema.sql)
    
--data-root (required)
    Root directory containing GMT files
    
--collection-name (default: GTEx)
    Name of gene set collection
    
--species-code (default: Homo_sapiens)
    Species code for namespace
    
--species-name (default: Homo sapiens)
    Full species name
    
--namespace-label (default: HGNC)
    Gene symbol namespace label
    
--license-code (default: CC-BY-4.0)
    License identifier
    
--require-provenance (default: True)
    Skip genesets without provenance/metadata JSONs
    
--skip-provenance-check
    Include all genesets regardless of JSON availability
```

## Data Model

### Core Tables
- **gene_set**: Collection of genes with collection context
- **gene_symbol**: Gene identifiers scoped to namespace
- **geneset_gene_symbol**: Many-to-many association
- **provenance**: Raw JSON for graph, metadata, run_summary
- **provenance_node**: Normalized graph nodes with properties
- **provenance_edge**: Normalized graph edges with relationships

### ID Allocation
- gene_set_id: Primary key, spaced by node count
- gene_symbol_id: Auto-increment per namespace
- provenance_node_id: Contiguous across genesets
  * GeneSet node: provenance_node_id = gene_set_id
  * Other nodes: provenance_node_id auto-incremented

### JSON Storage Strategy
- Complex nested properties stored as TEXT in additional_properties
- Preserves full structure without schema changes
- Enables flexible field extensions
- Can be parsed when needed via json_extract() in SQL

## Error Handling

- **Missing GMT file**: Logged and skipped
- **Missing provenance JSON**: Skipped if require_provenance=True
- **Duplicate gene associations**: Silently ignored (INSERT OR IGNORE)
- **Foreign key violations**: Prevented by proper dimension table ordering
- **Database connection failure**: Exception raised, script terminates

## Testing & Validation

### Verification Queries

```sql
-- Check ID spacing pattern
SELECT gene_set_id, 
       COUNT(*) as node_count
FROM provenance_node
GROUP BY gene_set_id
ORDER BY gene_set_id;

-- Verify GeneSet nodes match gene_set_id
SELECT gs.gene_set_id, pn.provenance_node_id, pn.node_type
FROM gene_set gs
JOIN provenance_node pn ON gs.gene_set_id = pn.gene_set_id
WHERE pn.node_type = 'GeneSet'
ORDER BY gs.gene_set_id;

-- Check gene associations
SELECT COUNT(*) as total_associations
FROM geneset_gene_symbol;

-- Verify no orphaned edges
SELECT COUNT(*) as orphaned_edges
FROM provenance_edge pe
LEFT JOIN provenance_node pn_source ON pe.source_node_id = pn_source.provenance_node_id
WHERE pn_source.provenance_node_id IS NULL;
```

### Known Good Results
- 42 genesets successfully populated
- 7,372 gene-geneset associations created
- 536 provenance nodes normalized
- 494 provenance edges normalized
- 0 integrity violations
- Contiguous node ID allocation verified

## Reproduction Steps

1. **Ensure database schema exists**
   ```powershell
   sqlite3 geneset.db < database-schema.sql
   ```

2. **Run population script**
   ```powershell
   python populate_database.py `
       --db-path "geneset.db" `
       --schema-file "database-schema.sql" `
       --data-root "\humgen\diabetes2\users\ryank\CFDE\geneset_extractors\gtex\genesets\whole_blood"
   ```

3. **Verify results**
   - Check CLI output for geneset count
   - Run validation queries above
   - Confirm ID spacing pattern matches expected allocation

## Key Design Decisions

1. **Insert-or-Get Pattern**: Dimension tables (species, namespace, collection) use SELECT-first to handle re-runs and shared values without duplicates

2. **JSON Serialization**: Complex properties stored as TEXT, not decomposed into additional columns - enables flexibility without schema changes

3. **Flexible JSON Parsing**: Provenance JSON can have multiple nesting patterns; code detects structure and adapts

4. **INSERT OR REPLACE for GeneSet nodes**: Supports re-runs without constraint violations

5. **ID Spacing Strategy**: Ensures contiguous allocation across genesets with gene_set_id = starting node ID

6. **Silent Duplicate Handling**: Many-to-many associations use INSERT OR IGNORE to avoid errors on re-runs

## Files

- `populate_database.py` - Main ETL script with GeneSeCoDatabasePopulator class
- `database-schema.sql` - 15 normalized tables with proper FKs and constraints
- Input data: GMT files + {name}.provenance.json + {name}.meta.json + run_summary.json

## Result

Complete, reproducible ETL pipeline that transforms distributed GMT + JSON files into normalized SQLite database with proper ID allocation, referential integrity, and publishable identifiers.
