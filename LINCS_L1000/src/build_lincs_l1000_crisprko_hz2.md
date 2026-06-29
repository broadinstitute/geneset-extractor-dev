# HZ2 Wrapper Notes

This file tracks the earlier LINCS L1000 `HZ2` wrapper used by the pipeline:

- wrapper: `build_lincs_l1000_crisprko_hz2.py`
- source script: `notebooks_adapted/build_lincs_l1000_crisprko_gmt_only.py`

## Current status

The active pipeline now runs `HZ2` through:

- `geneset_extractors.cli workflows lincs_l1000_crisprko`

and keeps `geneset-extractor-dev` as a top-level wrapper around that `dig` workflow plus `signed_term_gene`.

This older wrapper file remains as a record of the earlier notebook-import path.

## Integration Note

The final authoritative GMT output for the integrated pipeline model is written by `dig-gene-set-extractors`.
