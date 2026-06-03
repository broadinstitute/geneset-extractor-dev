# HZ2 Wrapper Notes

This file tracks the LINCS L1000 `HZ2` wrapper used by the pipeline:

- wrapper: `build_lincs_l1000_crisprko_hz2.py`
- source script: `notebooks_adapted/build_lincs_l1000_crisprko_gmt_only.py`

## Purpose

The pipeline uses `HZ2` as a wrapper around the notebook-replica standalone script while preserving the underlying notebook-style preprocessing logic.

## Differences From The Source Script

- no biological logic changes
- no data-processing changes
- no CLI argument changes

The wrapper only locates the standalone script from the repository root, imports it dynamically, and dispatches the current CLI arguments to the standalone script's `main()`.

## Integration Note

The final authoritative GMT output for the integrated pipeline model is written by `dig-gene-set-extractors`, not by this wrapper.
