# HZ1 Wrapper Notes

This file tracks the HuBMAP `HZ1` wrapper used by the pipeline:

- primary runner: `run_hubmap_hz_model.py`
- `dig` workflow: `hubmap_asctb`
- source notebook reference: `notebooks_adapted/build_hubmap_asctb_gmt.py`

## Purpose

The active pipeline now uses `HZ1` as a wrapper around a `dig` workflow while preserving the notebook-style preprocessing logic.

## Differences From The Source Script

- the core workflow logic now lives in `dig-gene-set-extractors`
- the wrapper resolves model inputs and calls:
  - `dig workflows hubmap_asctb`
  - `dig convert unsigned_term_gene`
- output layout now uses:
  - `workflow/`
  - `extractor/`

The notebook-adapted script remains a reference for the workflow logic, but it is no longer the primary runtime entrypoint.

## Integration Note

The final authoritative GMT output for the integrated pipeline model is written by `dig-gene-set-extractors`, and the workflow provenance begins from the initial HuBMAP inputs.
