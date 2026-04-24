# generate_gtex_model_sweep_proposal.v1

Generates the step-1 proposal for `GTEx_model_sweep_v1`.

What it does:

1. defines a catalog of anchor models, focused parameter-sweep models, and defensible alternative workflow models
2. writes a tab-delimited manifest with one row per proposed model and explicit workflow/extractor settings
3. writes a family summary table
4. writes a markdown proposal describing the execution logic and recommended run order

Main outputs:

- `outputs/gtex_model_sweep_v1/model_manifest.v1.tsv`
- `outputs/gtex_model_sweep_v1/model_family_summary.v1.tsv`
- `outputs/gtex_model_sweep_v1/run_summary.v1.tsv`
- `outputs/gtex_model_sweep_v1/gtex_model_sweep_proposal.v1.md`
