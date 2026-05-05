# GTEx Step 2 Run Summary

- Scope completed: step 2 only
- Model count covered by scripts: `22`
- Current model ID prefix for these age-binned scripts: `AB`
- New runtime scripts: `4`
- New provenance model docs: `22`
- Step-2 scripts start from GTEx tissue counts plus GTEx sample and subject metadata
- Full-model runs are parameterized and do not rely on hidden shell state
- The original step-2 provenance notes were written with legacy `M*` IDs; those correspond to current `AB*` IDs one-to-one

## Main Entry Points

- `geneset-extractor-dev/GTEx/run/prepare_gtex_tissue_inputs.sh`
- `geneset-extractor-dev/GTEx/run/run_gtex_model.sh`
- `geneset-extractor-dev/GTEx/run/run_all_gtex_models.sh`
- `geneset-extractor-dev/GTEx/run/run_full_gtex_tissue_pipeline.sh`
