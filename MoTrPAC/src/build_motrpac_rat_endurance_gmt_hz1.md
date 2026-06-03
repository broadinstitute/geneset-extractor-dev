# HZ1 Wrapper Notes

This file tracks the MoTrPAC `HZ1` wrapper used by the pipeline:

- wrapper: `build_motrpac_rat_endurance_gmt_hz1.py`
- source script: `notebooks_adapted/build_motrpac_rat_endurance_gmt.py`

## Purpose

The pipeline uses `HZ1` as a wrapper around the notebook-replica standalone script while keeping the biological workflow cell-for-cell with the standalone implementation.

## Differences From The Source Script

- no biological logic changes
- no data-processing changes
- no CLI argument changes

The wrapper only:

- locates the standalone script from the repository root
- imports it dynamically
- dispatches the current CLI arguments to the standalone script's `main()`

## Why This Exists

It gives the MoTrPAC pipeline a stable entrypoint under:

- `geneset-extractor-dev/MoTrPAC/src/`

while preserving the standalone notebook-replica logic as the authoritative workflow for preprocessing and term-gene construction inside `HZ1`.

The final GMT emission is now handled by `dig-gene-set-extractors`, which is the authoritative GMT writer for the integrated pipeline model.
