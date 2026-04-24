# execute_gtex_model_sweep_workflow.v1

Executes one distinct workflow group for `GTEx_model_sweep_v1`.

What it does:

1. reads one workflow-group row from `workflow_run_plan.v1.tsv`
2. validates reused baseline DEG tables or runs `rna_de_prepare` for each tissue for a new workflow group
3. combines per-tissue outputs into one `deg_long_combined.v1.tsv`

This is an execution helper used by the generated shell scripts under `run/gtex_model_sweep_v1/`.
