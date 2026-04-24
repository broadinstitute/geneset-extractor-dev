# run_gtex_model_sweep_adipose.v1

Runs step 3 of the updated `GTEx_model_plan.txt` for Adipose tissue only.

This script:

1. derives Adipose-only workflow execution from the existing `gtex_model_sweep_v1` plans
2. runs or reuses the Adipose tissue DE workflow for each distinct workflow group
3. runs all 26 proposed models on the Adipose-only DEG tables
4. removes exact redundant gene lists across models and writes a canonical Adipose GMT
5. runs PIGEAN and EAGGL on each canonical Adipose gene list
6. emits a preliminary model filter based on adipose-related keyword hits in the PIGEAN and EAGGL outputs

Primary outputs are written under `outputs/gtex_model_sweep_adipose_v1/`.
