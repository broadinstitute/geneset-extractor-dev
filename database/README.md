

## `database/src/populate_database.py`

A command-line SQLite loader for gene set data stored in `.gmt` files.

### Overview

- Connects to a SQLite database and initializes the schema from a SQL file.
- Recursively finds `.gmt` files under `--data-root`.
- Parses each GMT line into a gene set name plus its gene symbols.
- Creates or reuses reference rows for species, namespace, collection, and license.
- Inserts each gene set, its gene symbols, and the many-to-many links between them.

### Provenance Support

For each GMT file directory, it looks for `geneset.provenance.json`, `geneset.meta.json`, and optional `run_summary.json`.

- If provenance is required, gene sets missing those files are skipped.
- Stores raw provenance/metadata JSON in a `provenance` table.
- Expands provenance graph nodes and edges into normalized `provenance_node` and `provenance_edge` tables.
- Derives a `gene_set_details` row from metadata, including descriptions, source info, external URL, species, namespace, and contributing organization.

### Naming and IDs

- Derives a tissue name from the GMT file's directory path when possible and builds a standardized gene set name:

