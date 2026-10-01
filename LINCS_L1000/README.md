# LINCS L1000 submission modernization

This draft modernizes the existing LINCS L1000 HZ1 chemical-perturbation and
HZ2 CRISPR-knockout libraries. All matrix processing, ranking, mapping, and
GMT creation belong to `dig-gene-set-extractors`; this directory only supplies
declared inputs and dispatches DIG commands.

`CP1` (`cd_signature_export`, `l1000_cp`) is distinct from the released-matrix
models. It exports each Level-5 chemical-perturbation Characteristic Direction
signature independently: the top 250 `CD-coefficient` symbols are `up`, and
the bottom 250 are `down`. Provide a SigCom-derived TSV manifest through
`LINCS_CP_SIGNATURE_MANIFEST_TSV`; it must contain `persistent_id` and may
contain `source_url` or `source_path`. Bare persistent IDs resolve under
`https://lincs-dcic.s3.amazonaws.com/LINCS-sigs-2021/cd/cp/`. Downloaded TSVs
are cached under `LINCS_CP_CACHE_DIR` when set. The SigCom library identifier
is `54198d6e-fe17-5ef8-91ac-02b425761653`.

Run the committed HZ1 smoke fixture with:

```bash
SUBMISSION_WORK_DIR=/path/out DIG_REPO=../dig-gene-set-extractors \
  bash run/run_submission_models_apptainer.sh --smoke
```

For a full run set `LINCS_CHEMPERT_EXPRESSION_TSV`,
`LINCS_CRISPRKO_EXPRESSION_TSV`, `LINCS_MAPPING_FILE`, and
`LINCS_CP_SIGNATURE_MANIFEST_TSV`, then run
`bash run/run_submission_models_apptainer.sh --full`.

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
bash run/run_submission_models_apptainer.sh --full
bash run/submit_submission_models_cluster_apptainer.sh --model-id HZ1 --submit
```

`--model-id` is optional; omit it to submit all declared models. The adapters
keep the historic `DIG_DIR`, `WORK_ROOT`, `LINCS_OUT_ROOT`, and
`LINCS_ARRAY_*` details internal, although the latter resource variables
remain supported as compatibility fallbacks.
