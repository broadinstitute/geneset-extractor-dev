# Selection Inputs

The top-level GTEx entrypoints accept model and tissue selections in either of these forms:

- comma-separated CLI values
- one identifier per row in an input file

## Shared Planning Tables

- `model_list.tsv`
- `tissue_list.tsv`

These files are intended to be updated as new model families and tissues are added.

## CLI Forms

Examples:

```bash
--models AB1,AB2,AC1
--tissues adipose_subcutaneous
```

or

```bash
--models_file geneset-extractor-dev/GTEx/planning/model_list.tsv
--tissues_file geneset-extractor-dev/GTEx/planning/tissue_list.tsv
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

- `--models all` selects all rows in `model_list.tsv` with `enabled=true`
- `--tissues all` selects all rows in `tissue_list.tsv` with `enabled=true`

At the moment, only tissues with a local counts GCT are enabled by default.
