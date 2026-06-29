# Selection Inputs

The top-level GTEx entrypoints accept model and tissue selections in either of these forms:

- comma-separated CLI values
- one identifier per row in an input file

## Shared Runtime Config Tables

- `config/model_list.tsv`
- `config/tissue_list.tsv`

These files are intended to be updated as new model families and tissues are added.

## CLI Forms

Examples:

```bash
--models AB1,AB2,AC1
--tissues adipose_subcutaneous
```

or

```bash
--models_file geneset-extractor-dev/GTEx/config/model_list.tsv
--tissues_file geneset-extractor-dev/GTEx/config/tissue_list.tsv
```

## Input File Format

The simplest accepted file format is one identifier per row:

```text
AB1
AB2
AC1
```

or

```text
adipose_subcutaneous
muscle_skeletal
```

The parser also tolerates TSV files whose first column is the identifier.

## Default Behavior

- `--models all` selects all rows in `config/model_list.tsv` with `enabled=true`
- `--tissues all` selects all rows in the active tissue list TSV
