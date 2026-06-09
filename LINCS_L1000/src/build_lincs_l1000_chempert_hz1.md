# HZ1 Wrapper Notes

This file tracks the earlier LINCS L1000 `HZ1` wrapper used by the pipeline:

- wrapper: `build_lincs_l1000_chempert_hz1.py`
- source script: `notebooks_adapted/build_lincs_l1000_chempert_gmt_only.py`

## Current status

The active pipeline now runs `HZ1` through:

- `geneset_extractors.cli workflows lincs_l1000_chempert`

and keeps `geneset-extractor-dev` as a top-level wrapper around that `dig` workflow plus `signed_term_gene`.

This older wrapper file remains as a record of the earlier notebook-import path.

## Integration Note

The final authoritative GMT output for the integrated pipeline model is written by `dig-gene-set-extractors`.
