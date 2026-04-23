# execute_gtex_model_sweep_model.v1

Executes one model-specific extraction for `GTEx_model_sweep_v1`.

What it does:

1. reads one model row from `model_run_plan.v1.tsv`
2. runs `rna_deg_multi` with the model-specific extractor settings
3. rewrites the generated GMT into legacy GTEx set names
4. writes a model-named GMT gzip and a reference-comparison report

This is an execution helper used by the generated shell scripts under `run/gtex_model_sweep_v1/`.
