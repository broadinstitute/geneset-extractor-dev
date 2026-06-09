

## `database/src/populate_database.py`

A command-line SQLite loader for gene set data stored in `.gmt` files.

### Overview

- Connects to a SQLite database and initializes the schema from a SQL file.
- Recursively finds `.gmt` files under either `--data-root` or `--s3-data-root`.
- Parses each GMT line into a gene set name plus its gene symbols.
- Creates or reuses reference rows for species, namespace, collection, and license.
- Inserts each gene set, its gene symbols, and the many-to-many links between them.
- When using S3 input, reads `.gmt`, provenance, and metadata files directly from the bucket via AWS APIs.

### Provenance Support

For each GMT file directory or S3 prefix, it looks for `geneset.provenance.json`, `geneset.meta.json`, and optional `run_summary.json`.

- If provenance is required, gene sets missing those files are skipped.
- Stores raw provenance/metadata JSON in a `provenance` table.
- Expands provenance graph nodes and edges into normalized `provenance_node` and `provenance_edge` tables.
- Derives a `gene_set_details` row from metadata, including descriptions, source info, external URL, species, namespace, and contributing organization.

### Naming and IDs

- Derives a tissue name from the GMT file's directory path when possible and builds a standardized gene set name:

### Example

Local filesystem input:

```bash
python database/src/populate_database.py \
  --db-path database.db \
  --schema-file schema.sql \
  --data-root /path/to/data \
  --output-log logs/populate_database.log
```

S3 input:

```bash
python database/src/populate_database.py \
  --db-path database.db \
  --schema-file schema.sql \
  --s3-data-root s3://geneset-marc-test \
  --aws-access-key-id "$AWS_ACCESS_KEY_ID" \
  --aws-secret-access-key "$AWS_SECRET_ACCESS_KEY" \
  --output-log logs/populate_database.log
```

### Options

- `--db-path`: Required. Path to the SQLite database file to create or update.
- `--schema-file`: Required. Path to the SQL schema file used to initialize the database.
- `--data-root`: Required unless `--s3-data-root` is provided. Root directory to search recursively for `.gmt` files.
- `--s3-data-root`: Required unless `--data-root` is provided. S3 URI to search recursively for `.gmt` files, for example `s3://s3-bucket-name`. Cannot be used together with `--data-root`.
- `--output-log`: Optional. Path to a log file. If omitted, logs are written only to stderr.
- `--aws-access-key-id`: Optional. AWS access key ID for S3 access. If provided together with `--aws-secret-access-key`, these credentials are tried before the default AWS credential chain.
- `--aws-secret-access-key`: Optional. AWS secret access key for S3 access. Must be provided together with `--aws-access-key-id`.
- `--aws-session-token`: Optional. AWS session token for temporary S3 credentials.
- `--aws-region`: Optional. AWS region passed to the S3 client.
- `--collection-name`: Optional. Collection name stored with imported gene sets. Default: `GTEx`.
- `--species-code`: Optional. Species code stored in reference tables and gene set details. Default: `Homo_sapiens`.
- `--species-name`: Optional. Human-readable species name. Default: `Homo sapiens`.
- `--namespace-label`: Optional. Gene symbol namespace label. Default: `HGNC`.
- `--license-code`: Optional. License code stored with imported gene sets. Default: `CC-BY-4.0`.
- `--contrib-organization`: Optional. Contributing organization stored in `gene_set_details`. Default: `GTEx Consortium`.
- `--require-provenance`: Optional flag. Keeps the default behavior of requiring `geneset.provenance.json` and `geneset.meta.json` for each imported gene set.
- `--skip-provenance-check`: Optional flag. Imports gene sets even when provenance and metadata files are missing.

### S3 Requirements

- `boto3` must be installed in the Python environment when using `--s3-data-root`.
- Credential resolution order for S3:
- 1. `--aws-access-key-id` / `--aws-secret-access-key` / `--aws-session-token` if provided.
- 2. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` environment variables if present.
- 3. The default AWS credential chain used by `boto3`.
- AWS credentials and permissions must allow `s3:ListBucket` on the bucket and `s3:GetObject` for the relevant objects.
