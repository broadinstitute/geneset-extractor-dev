# run_all_models.v1

Runs the full `GTEx_model_sweep_v1` pipeline in two phases:

1. all distinct workflow groups
2. all model-specific `rna_deg_multi` extractions

The generated scripts run serially and are resume-safe. If a workflow or model step completes successfully, rerunning this master script will skip completed work because the underlying execution wrappers use `--resume`.

Note for the interrupted first run: the R backend code was patched to drop invariant covariates within each contrast before fitting. That fixes the prior `contrasts can be applied only to factors with 2 or more levels` failure seen in the `backend=auto` workflow when a tissue-level covariate such as `smtsd` was constant within a tissue.
