# LINCS L1000 submission modernization

This draft modernizes the existing LINCS L1000 HZ1 chemical-perturbation and
HZ2 CRISPR-knockout libraries. All matrix processing, ranking, mapping, and
GMT creation belong to `dig-gene-set-extractors`; this directory only supplies
declared inputs and dispatches DIG commands.

`HZ4` (`cd_signature_export`, `l1000_cp`) is distinct from the released-matrix
models. It streams the single public `cp_coeff_mat.gctx` input, using
`0/META/ROW/id`, `0/META/COL/lincs_id`, and `0/DATA/0/matrix`. Each Level-5
chemical-perturbation signature independently emits the top 250
`CD-coefficient` symbols as `up` and bottom 250 as `down`. Set
`LINCS_CP_COEFF_GCTX` to a local copy of the GCTX; its public source is
`https://lincs-dcic.s3.amazonaws.com/LINCS-sigs-2021/gctx/cd-coefficient/cp_coeff_mat.gctx`.
The current public source contains about 102 more signatures than the legacy
GMT; HZ4 resolves the 102 repeated nonblank `lincs_id` groups by retaining the
last GCTX column occurrence. This yields 718,055 unique signatures (and
1,436,110 terms). Ninety-two duplicate groups have identical coefficient
vectors; for the ten differing groups, this is a deterministic public-source
resolution policy, not a claim about the historical pipeline.

Run the committed HZ1 smoke fixture with:

```bash
SUBMISSION_WORK_DIR=/path/out DIG_REPO=../dig-gene-set-extractors \
  bash run/run_submission_models_apptainer.sh --smoke
```

For a full run set `LINCS_CHEMPERT_EXPRESSION_TSV`,
`LINCS_CRISPRKO_EXPRESSION_TSV`, `LINCS_MAPPING_FILE`, and
`LINCS_CP_COEFF_GCTX`, then run
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

## HZ4 cell-line × perturbation-time array mode

HZ4 can also be partitioned without changing the meaning of a gene set. Each
task contains signatures from one `cell_line` × `pert_time` group; groups over
10,000 retained signatures are split into deterministic chunks. Every task
emits a separate, complete HZ4 GMT/model output, so the task outputs are not
merged afterward. The planner first applies the standard HZ4 rule that the
last GCTX column wins for duplicate `lincs_id` values.

HZ4 writes its final GMT while streaming coefficient vectors from the GCTX;
it does not create or reload a signed term-gene TSV. Consequently the HZ4
array launcher has a `3G` default memory request. This is independent of the
GCTX I/O load, so begin with modest concurrency on shared storage.

With the standard Apptainer environment variables plus `LINCS_CP_COEFF_GCTX`
set, create the plan, inspect its task count, then submit it:

```bash
export HZ4_MAX_SIGNATURES_PER_TASK=10000
export HZ4_MAX_CONCURRENT_TASKS=10
bash run/plan_hz4_cell_line_time_apptainer.sh
wc -l "${SUBMISSION_WORK_DIR}/genesets/hz4_cell_line_time_plan/task_manifest.tsv"
bash run/submit_hz4_cell_line_time_cluster_apptainer.sh --submit
```

The manifest has one header row, so its line count minus one is the number of
array tasks. The submitter defaults to `3G`, `24:00:00`, and at most ten
simultaneous tasks. `HZ4_TASK_MEMORY` and `HZ4_TASK_WALLTIME` take priority;
otherwise it uses `SUBMISSION_ARRAY_MEMORY` and `SUBMISSION_ARRAY_WALLTIME`
(then the legacy `LINCS_ARRAY_*` variables). Set
`HZ4_MAX_CONCURRENT_TASKS` to change concurrency. To use a nondefault plan
location, set `HZ4_PARTITION_PLAN_DIR` consistently for both commands.
