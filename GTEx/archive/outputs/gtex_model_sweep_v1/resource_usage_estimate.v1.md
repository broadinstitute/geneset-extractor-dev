# Resource Usage Estimate v1

This note estimates the runtime and resource profile for the generated `GTEx_model_sweep_v1` execution scripts.

## Run Order

The master script [run_all_models.v1.sh](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/run/gtex_model_sweep_v1/run_all_models.v1.sh) is fully serial.

It runs:

1. 8 workflow-group scripts
2. 26 model scripts

Within each new workflow group, [execute_gtex_model_sweep_workflow.v1.py](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src/execute_gtex_model_sweep_workflow.v1.py) iterates across the 27 GTEx tissues one at a time. There is no explicit job-level parallelism in the generated sweep scripts.

## Take-Home Estimate

The expensive part is generating new workflow DEG outputs. The model-specific extraction scripts are much lighter once the relevant workflow output already exists.

For planning purposes, budget approximately:

- 6 to 18 hours total wall time for the full sweep
- 8 to 16 GB peak RAM for the full run, driven mainly by the `r_limma_voom` workflow
- 4 to 8 GB of additional disk usage under `outputs/gtex_model_sweep_v1`

These are approximate planning numbers, not measured benchmarks. They are anchored to the actual generated script structure plus the size of existing GTEx baseline outputs already present in this workspace:

- [gtex_no_harmonizome_analysis_v1](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_no_harmonizome_analysis_v1): about 4.6 GB total
- [gtex_harmonizome_analysis_v1](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_harmonizome_analysis_v1): about 4.3 GB total

The sweep should use less new disk than those full baseline runs because the workflow helper reuses the existing prepared matrices instead of rebuilding them.

## Stage-Level Expectations

See [resource_usage_estimate.v1.tsv](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_model_sweep_v1/resource_usage_estimate.v1.tsv) for the compact machine-readable table. In practical terms:

- Reused workflow groups should finish quickly because they only validate preexisting outputs.
- New `lightweight` workflow groups should usually be on the order of tens of minutes to a couple of hours each.
- The single `auto` workflow group should be budgeted slightly above the `lightweight` groups.
- The single `r_limma_voom` workflow group is likely to dominate the wall time and memory peak.
- Each model extraction should usually be short relative to the workflow stage because it mainly converts an already-built DEG table into a GMT, renames sets, and compares to the reference.

## Operational Note

The run is serial at the script level, but individual DE tools may still use multiple CPU threads internally through R, BLAS, or other libraries. So you should expect one workflow or one model script at a time, but not necessarily a single-core process throughout.

## Resume Note

An early full-run attempt failed in the `backend=auto` workflow when `auto` resolved to `r_limma_voom` and passed a constant tissue-level covariate (`smtsd`) into the R design matrix for a single-tissue analysis. The R backend code in [r_limma_voom.py](/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src/geneset_extractors/preprocessing/rnaseq/de_backends/r_limma_voom.py) and [r_dream.py](/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src/geneset_extractors/preprocessing/rnaseq/de_backends/r_dream.py) now drops covariates and batch columns that have fewer than 2 observed nonblank levels within the selected samples for a contrast.

This means:

- the prior `contrasts can be applied only to factors with 2 or more levels` error should not recur for constant per-tissue covariates such as `smtsd`
- the generated sweep scripts do not need to be regenerated
- rerunning [run_all_models.v1.sh](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/run/gtex_model_sweep_v1/run_all_models.v1.sh) is resume-safe because the generated workflow and model scripts already use `--resume`
