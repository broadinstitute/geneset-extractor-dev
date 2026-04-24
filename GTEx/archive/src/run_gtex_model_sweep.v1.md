# run_gtex_model_sweep.v1

Runs step 2 of `GTEx_model_sweep_v1`.

What it does:

1. reads the proposed model manifest from step 1
2. groups models by unique `rna_de_prepare` workflow settings
3. identifies which workflow groups can reuse existing GTEx baseline DEG tables and which require new execution later
4. writes generated shell scripts under `run/gtex_model_sweep_v1/` for each workflow group and each model
5. writes a master `run_all_models.v1.sh` script that runs the full planned pipeline later
6. writes companion provenance markdown files for each model with the exact command set to run it

Main outputs:

- `outputs/gtex_model_sweep_v1/workflow_run_plan.v1.tsv`
- `outputs/gtex_model_sweep_v1/model_run_plan.v1.tsv`
- `outputs/gtex_model_sweep_v1/run_script_inventory.v1.tsv`
- `outputs/gtex_model_sweep_v1/run_summary.v2.tsv`
- `outputs/gtex_model_sweep_v1/model_provenance_v1/<model_name>.v1.md`
- `run/gtex_model_sweep_v1/run_all_models.v1.sh`
- `run/gtex_model_sweep_v1/run_workflow_<workflow_slug>.v1.sh`
- `run/gtex_model_sweep_v1/run_model_<model_name>.v1.sh`
