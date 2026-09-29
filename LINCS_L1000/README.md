# LINCS L1000 submission modernization

This draft modernizes the existing LINCS L1000 HZ1 chemical-perturbation and
HZ2 CRISPR-knockout libraries. All matrix processing, ranking, mapping, and
GMT creation belong to `dig-gene-set-extractors`; this directory only supplies
declared inputs and dispatches DIG commands.

Run the committed HZ1 smoke fixture with:

```bash
SUBMISSION_WORK_DIR=/path/out DIG_REPO=../dig-gene-set-extractors \
  bash reproduction/reproduce.sh --smoke
```

For a full run set `LINCS_CHEMPERT_EXPRESSION_TSV`,
`LINCS_CRISPRKO_EXPRESSION_TSV`, and `LINCS_MAPPING_FILE`, then run
`bash reproduction/reproduce.sh full`.

For an Apptainer run, use the same standard variables as the other modernized
libraries. `run/run_submission_models_apptainer.sh` performs the reproduction
inside the image, while the cluster adapter translates those variables to the
established LINCS array launcher:

```bash
export DIG_REPO=/path/to/dig-gene-set-extractors
export SUBMISSION_WORK_DIR=/scratch/lincs_l1000_run
export APPTAINER_IMAGE=/path/to/geneset-extractor.sif
export LINCS_CHEMPERT_EXPRESSION_TSV=/path/to/chempert.tsv
export LINCS_CRISPRKO_EXPRESSION_TSV=/path/to/crispr_ko.tsv
export LINCS_MAPPING_FILE=/path/to/gene_mapping.tsv
export SUBMISSION_ARRAY_MEMORY=24G
export SUBMISSION_ARRAY_WALLTIME=24:00:00
bash run/run_submission_models_apptainer.sh full
bash run/submit_submission_models_cluster_apptainer.sh --model-id HZ1 --submit
```

`--model-id` is optional; omit it to submit all declared models. The adapters
keep the historic `DIG_DIR`, `WORK_ROOT`, `LINCS_OUT_ROOT`, and
`LINCS_ARRAY_*` details internal, although the latter resource variables
remain supported as compatibility fallbacks.
