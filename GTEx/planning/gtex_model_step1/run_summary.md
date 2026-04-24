# GTEx Step 1 Run Summary

- Date: `2026-04-23`
- Scope completed: step 1 only
- Archive use: none
- Existing scripts executed: none
- New model count: `22`
- Families:
  - `anchor`: `4`
  - `parameter_sweep`: `9`
  - `defensible_alternative`: `9`

## Key Decision

The current latest GTEx bulk-expression release referenced for planning is `v10`, verified from the current Adult GTEx CFDE index on April 23, 2026. The concrete counts target is `GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz`, with a current counts-by-tissue collection also present for `v10`.

## What This Step Produced

- a fresh model catalog derived only from the current `dig-gene-set-extractors` code and docs
- an explicit manifest of supported model settings
- a recommended execution order for later pipeline runs

## What This Step Did Not Do

- did not use anything under `geneset-extractor-dev/GTEx/archive/`
- did not run the DIG workflow or any GTEx extraction model
- did not write run scripts for step 2
