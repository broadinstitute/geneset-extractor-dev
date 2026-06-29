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

The current latest GTEx bulk-expression release referenced for planning is `v10`, verified from the current Adult GTEx file index on April 23, 2026. The concrete counts target is `GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz`, with a current counts-by-tissue collection also present for `v10`.

## What This Planning Bundle Produced

- a fresh model catalog derived only from the current `dig-gene-set-extractors` code and docs
- an explicit manifest of supported model settings
- a current naming scheme with `AB*` for age-binned models, `AC*` for continuous-age models, `HZ*` for notebook-style/Harmonizome-style aging-signature models, and `TV*` reserved for future tissue-versus-reference models
- a recommended execution order for later pipeline runs
- consolidated runtime-interface notes and model provenance for the age-binned wrappers

## What This Planning Bundle Did Not Do

- did not use anything under `geneset-extractor-dev/GTEx/archive/`
- did not run the DIG workflow or any GTEx extraction model
- did not write runtime wrappers or downstream evaluation outputs

## Runtime Entry Points

- `geneset-extractor-dev/GTEx/run/build_genesets.sh`
- `geneset-extractor-dev/GTEx/src/run_age_binned_model.py`

Current runtime notes:

- `build_genesets.sh` is the main user-facing entry point for `AB*`
- shared prepared bundles are created once per tissue and reused across models
- the default output root is `./gtex_outputs`
- both detailed tissues and broad `SMTS` tissues are supported in the active pipeline

Supporting files in this directory:

- `run_script_inventory.md`
- `model_provenance/`
