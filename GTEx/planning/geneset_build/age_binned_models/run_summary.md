# Age-Binned Model Planning Summary

- Date: `2026-04-23`
- Scope completed: age-binned model planning only
- Archive use: none
- Existing scripts executed: none
- New model count: `22`
- Current model ID prefix: `AB`
- Families:
  - `anchor`: `4`
  - `parameter_sweep`: `9`
  - `defensible_alternative`: `9`

## Key Decision

The current latest GTEx bulk-expression release referenced for planning is `v10`, verified from the current Adult GTEx CFDE index on April 23, 2026. The concrete counts target is `GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz`, with a current counts-by-tissue collection also present for `v10`.

## What This Planning Bundle Produced

- a fresh model catalog derived only from the current `dig-gene-set-extractors` code and docs
- an explicit manifest of supported model settings
- a current naming scheme with `AB*` for age-binned models, `AC*` for continuous-age models, and `TV*` reserved for future tissue-versus-reference models
- a recommended execution order for later pipeline runs
- consolidated runtime-interface notes and model provenance for the age-binned wrappers

## What This Planning Bundle Did Not Do

- did not use anything under `geneset-extractor-dev/GTEx/archive/`
- did not run the DIG workflow or any GTEx extraction model
- did not write runtime wrappers or downstream evaluation outputs

## Runtime Entry Points

- `geneset-extractor-dev/GTEx/run/build_tissue_inputs.sh`
- `geneset-extractor-dev/GTEx/run/run_age_binned_model.sh`
- `geneset-extractor-dev/GTEx/run/run_all_age_binned_models.sh`
- `geneset-extractor-dev/GTEx/run/run_age_binned_pipeline.sh`

Supporting files in this directory:

- `run_script_inventory.md`
- `model_provenance/`
