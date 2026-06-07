

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

### Example

```bash
python database/src/populate_database.py \
  --db-path database.db \
  --schema-file schema.sql \
  --data-root /path/to/data \
  --output-log logs/populate_database.log
```

### Options

- `--db-path`: Required. Path to the SQLite database file to create or update.
- `--schema-file`: Required. Path to the SQL schema file used to initialize the database.
- `--data-root`: Required. Root directory to search recursively for `.gmt` files.
- `--output-log`: Optional. Path to a log file. If omitted, logs are written only to stderr.
- `--collection-name`: Optional. Collection name stored with imported gene sets. Default: `GTEx`.
- `--species-code`: Optional. Species code stored in reference tables and gene set details. Default: `Homo_sapiens`.
- `--species-name`: Optional. Human-readable species name. Default: `Homo sapiens`.
- `--namespace-label`: Optional. Gene symbol namespace label. Default: `HGNC`.
- `--license-code`: Optional. License code stored with imported gene sets. Default: `CC-BY-4.0`.
- `--contrib-organization`: Optional. Contributing organization stored in `gene_set_details`. Default: `GTEx Consortium`.
- `--require-provenance`: Optional flag. Keeps the default behavior of requiring `geneset.provenance.json` and `geneset.meta.json` for each imported gene set.
- `--skip-provenance-check`: Optional flag. Imports gene sets even when provenance and metadata files are missing.
